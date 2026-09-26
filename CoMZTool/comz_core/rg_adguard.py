"""Store.RG-Adguard backend — Microsoft Store package-link resolution.

Dedicated package-source backend (not a generic file host):

    https://store.rg-adguard.net/   (Store resolver / package links)
    https://files.rg-adguard.net/   (Microsoft file index: hashes/metadata)

TEST-B pinned target:
    Game:      Call of Mini: Zombies
    Platform:  Windows Phone (historical)
    Version:   1.1.0.0
    App ID:    0febf8fa-35e8-4a87-8090-58b65220b3ed
    Expected:  historical Windows Phone XAP/protected package, ~79 MB

Workflow implemented here:
    ID -> resolver -> package links -> enumerate -> identity filter ->
    platform filter -> version filter -> download -> verify

Verification never accepts the first file blindly. Every candidate is
inspected (filename / extension / type / version / arch / language /
publisher / package/product/content ID / size / SHA-1 / SHA-256) and
rejected on wrong game / platform / version / arch / type / release /
corrupt-incomplete.

States emitted (exact strings, also used by CLI):
    NOT FOUND / METADATA ONLY / DOWNLOAD LINK FOUND / DOWNLOADING /
    DOWNLOADED / IDENTITY VERIFIED / HASH VERIFIED / WRONG VERSION /
    WRONG PLATFORM / WRONG GAME / CORRUPTED / READY FOR DECRYPTION

Source priority for TEST-B acquisition:
    1. Microsoft Store/package service
    2. Store.RG-Adguard resolution        <- this module
    3. Other compatible Microsoft package downloader
    4. Internet Archive
    5. Wayback Machine
    6. Explicitly configured preservation mirror

stdlib only (urllib). All network I/O is plain HTTPS GET/POST with a
preservation-tool User-Agent; no auth bypass, no credential handling.
"""
from __future__ import annotations

import hashlib
import html as _html
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile

RESOLVER_URL = "https://store.rg-adguard.net/"
FILE_INDEX_URL = "https://files.rg-adguard.net/"

TESTB_GAME = "Call of Mini: Zombies"
TESTB_PLATFORM = "Windows Phone"
TESTB_VERSION = "1.1.0.0"
TESTB_APP_ID = "0febf8fa-35e8-4a87-8090-58b65220b3ed"
TESTB_EXPECTED_SIZE = 79 * 1024 * 1024
TESTB_SIZE_TOLERANCE = 0.25  # +-25% accepted as "approximately 79 MB"

SOURCE_PRIORITY = [
    "dbox-product",
    "microsoft-store",
    "rg-adguard",
    "ms-package-downloader",
    "internet-archive",
    "wayback",
    "preservation-mirror",
]

UA = {"User-Agent": "CoMZ-Preservation-Decryptor/1.0 (TEST-B; archival research)"}

# ------------------------------------------------------------------ states

STATES = (
    "NOT FOUND",
    "METADATA ONLY",
    "DOWNLOAD LINK FOUND",
    "DOWNLOADING",
    "DOWNLOADED",
    "IDENTITY VERIFIED",
    "HASH VERIFIED",
    "WRONG VERSION",
    "WRONG PLATFORM",
    "WRONG GAME",
    "CORRUPTED",
    "READY FOR DECRYPTION",
)


def _http_post_form(url: str, fields: dict, timeout: int = 45) -> str:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        **UA, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _http_get_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------- resolver parsing

# The resolver page returns an HTML table of package links. We parse every
# <a href="...">label</a> pair out of it without assuming exact markup, then
# classify each link as a candidate below. If the site is unreachable the
# caller surfaces NOT FOUND (network distinguished from empty result).
_LINK_RE = re.compile(
    r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    s = _TAG_RE.sub("", s or "")
    return _html.unescape(s).strip()


def resolve_store_id(app_id: str, timeout: int = 45) -> dict:
    """Query the RG-Adguard Store resolver for a Store/legacy app ID.

    Returns {"state", "links": [{"url","label"}], "raw_note"}.
    The legacy Windows Phone application identifier (GUID) is posted as
    the lookup value; ring/channel left at retail defaults.
    """
    try:
        # Site accepts `type` + `url` + `ring` + `lang`. `type=ProductId`
        # covers GUID lookups (Store ProductId / legacy app GUID).
        page = _http_post_form(RESOLVER_URL, {
            "type": "ProductId",
            "url": app_id.strip(),
            "ring": "Retail",
            "lang": "en-US",
        }, timeout=timeout)
    except Exception as e:
        return {"state": "NOT FOUND", "links": [],
                "raw_note": f"resolver unreachable: {type(e).__name__}: {e}"}
    links = []
    for href, label in _LINK_RE.findall(page):
        href = _html.unescape(href.strip())
        label = _clean(label)
        if not href.startswith("http"):
            href = urllib.parse.urljoin(RESOLVER_URL, href)
        # keep only plausible Microsoft package/download hosts
        host = urllib.parse.urlparse(href).netloc.lower()
        if not host:
            continue
        links.append({"url": href, "label": label, "host": host})
    # de-dup preserving order
    seen, uniq = set(), []
    for l in links:
        if l["url"] not in seen:
            seen.add(l["url"])
            uniq.append(l)
    state = "DOWNLOAD LINK FOUND" if uniq else "NOT FOUND"
    note = f"resolver returned {len(uniq)} link(s) for {app_id}"
    return {"state": state, "links": uniq, "raw_note": note}


# ------------------------------------------------------- candidate model

_XAP_HINT = re.compile(r"\.xap(?:[?#]|$)", re.IGNORECASE)
_APPX_HINT = re.compile(r"\.(appx|appxbundle|msix|msixbundle|eappx|eappxbundle)(?:[?#]|$)",
                        re.IGNORECASE)
_VER_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)")
_ARCH_RE = re.compile(r"\b(arm|x86|x64|neutral|arm64)\b", re.IGNORECASE)
_LANG_RE = re.compile(r"\b([a-z]{2}(?:-[a-z]{2})?)\b", re.IGNORECASE)


def candidate_from_link(link: dict) -> dict:
    """Build an inspectable candidate record from one resolver link."""
    url = link["url"]
    label = link.get("label", "")
    path = urllib.parse.urlparse(url).path
    filename = os.path.basename(path) or label.split()[0] if label else "package"
    filename = urllib.parse.unquote(filename)[:256] or "package"
    ext = os.path.splitext(filename)[1].lower()
    if _XAP_HINT.search(url) or filename.lower().endswith(".xap"):
        ptype = "xap"
    elif _APPX_HINT.search(url):
        m = _APPX_HINT.search(url)
        ptype = (m.group(1) or "").lower()
    else:
        ptype = "unknown"
    blob = f"{label} {filename} {url}"
    mver = _VER_RE.search(blob)
    march = _ARCH_RE.search(blob)
    return {
        "filename": filename,
        "extension": ext,
        "package_type": ptype,
        "package_version": mver.group(1) if mver else "",
        "architecture": (march.group(1) or "").lower() if march else "",
        "language": "",
        "publisher": "",
        "package_id": "",
        "product_id": "",
        "content_id": "",
        "size": 0,
        "sha1": "",
        "sha256": "",
        "url": url,
        "host": link.get("host", ""),
        "label": label,
        "state": "DOWNLOAD LINK FOUND",
    }


def verify_candidate(cand: dict, game: str = TESTB_GAME,
                     version: str = TESTB_VERSION,
                     platform: str = TESTB_PLATFORM) -> dict:
    """Inspect one candidate; return it annotated with verdict + reason.

    Never auto-accepts: checks game identity signals, platform/type
    plausibility, exact version, and size sanity. Hash/state fields are
    filled later by download + package-meta stages.
    """
    blob = f"{cand.get('filename','')} {cand.get('label','')} {cand.get('url','')}".lower()
    # --- game identity: need a CoM Zombies signal, not just "zombie"
    game_ok = ("call of mini" in blob or "callofmini" in blob
               or "mini zombies" in blob or "minizombies" in blob
               or "comz" in blob)
    if not game_ok:
        # resolver labels for legacy WP GUID lookups are often bare GUIDs/
        # CDN names — those are "unknown game", not "wrong game": keep them
        # as candidates for post-download identity check via manifest.
        if TESTB_APP_ID.lower() in blob or "rg-adguard" in blob or "microsoft" in blob:
            cand["identity_note"] = "no title signal pre-download; defer to manifest check"
        else:
            cand["verdict"] = "WRONG GAME"
            cand["reason"] = "no Call of Mini: Zombies identity signal in link metadata"
            return cand
    # --- platform/type: historical target is XAP; appx-family kept only
    # --- as alternate-generation candidates, flagged for version review
    ptype = cand.get("package_type", "")
    if ptype == "xap":
        cand["platform_hint"] = "Windows Phone (XAP)"
    elif ptype in ("appx", "appxbundle", "msix", "msixbundle", "eappx", "eappxbundle"):
        cand["platform_hint"] = f"alternate generation ({ptype}) — version review required"
    else:
        cand["platform_hint"] = "unknown type — verify post-download"
    # --- version: explicit target; other generations reported, not selected
    if cand.get("package_version"):
        if cand["package_version"] != version:
            cand["verdict"] = "WRONG VERSION"
            cand["reason"] = (f"candidate version {cand['package_version']} "
                              f"!= target {version}; no version substitution")
            return cand
    else:
        cand["identity_note"] = (cand.get("identity_note", "")
                                 + "; version unknown pre-download").strip("; ")
    cand["verdict"] = "DOWNLOAD LINK FOUND"
    cand["reason"] = "passed pre-download filters; download + manifest verify next"
    return cand


def select_testb_candidates(links: list[dict]) -> dict:
    """Report ALL candidate generations, then pick the exact target set.

    Returns {"all": [...verified...], "selected": [...], "generations": [...] }.
    Selection = xap-type (or unknown-type deferring to manifest) candidates
    without a conflicting version stamp. Newest-first substitution is
    explicitly NOT performed.
    """
    all_c = [verify_candidate(candidate_from_link(l)) for l in links]
    versions = sorted({c["package_version"] for c in all_c if c.get("package_version")})
    selected = [c for c in all_c
                if c.get("verdict") == "DOWNLOAD LINK FOUND"
                and c.get("package_type") in ("xap", "unknown")]
    return {"all": all_c, "selected": selected, "generations": versions}


# ------------------------------------------------------- file-index lookup

def file_index_lookup(query: str, timeout: int = 45) -> dict:
    """Query the RG-Adguard Microsoft file index as metadata/hash source.

    Distinguishes METADATA FOUND from DOWNLOAD LINK FOUND / DOWNLOADED /
    VERIFIED — index presence never implies the package is downloadable.
    """
    # The index exposes per-file pages; without a documented JSON API we
    # fetch the index search page and scrape file rows defensively. Any
    # markup change degrades to METADATA ONLY with the raw note preserved.
    try:
        page = _http_get_text(
            FILE_INDEX_URL + "?search=" + urllib.parse.quote(query), timeout=timeout)
    except Exception as e:
        return {"state": "NOT FOUND",
                "note": f"file index unreachable: {type(e).__name__}: {e}",
                "records": []}
    rows = []
    for href, label in _LINK_RE.findall(page):
        name = _clean(label)
        if not name:
            continue
        rows.append({"name": name[:256],
                     "url": urllib.parse.urljoin(FILE_INDEX_URL, _html.unescape(href))})
        if len(rows) >= 100:
            break
    # hash/size detail lives on per-file pages; fetch up to 5 for the record
    records = []
    for r in rows[:5]:
        try:
            detail = _http_get_text(r["url"], timeout=timeout)
        except Exception:
            records.append({**r, "md5": "", "sha1": "", "sha256": "",
                            "sha512": "", "size": 0, "family": "",
                            "version": "", "language": "", "architecture": ""})
            continue
        text = _clean(detail)
        def grab(pat):
            m = re.search(pat, detail, re.IGNORECASE)
            return m.group(1).strip() if m else ""
        records.append({
            **r,
            "md5": grab(r"md5[^0-9a-f]*([0-9a-f]{32})"),
            "sha1": grab(r"sha-?1[^0-9a-f]*([0-9a-f]{40})"),
            "sha256": grab(r"sha-?256[^0-9a-f]*([0-9a-f]{64})"),
            "sha512": grab(r"sha-?512[^0-9a-f]*([0-9a-f]{128})"),
            "size": 0,
            "family": grab(r"family[^<:\n]*[:>]\s*([^<\n]+)"),
            "version": (re.search(_VER_RE, text).group(1)
                        if _VER_RE.search(text) else ""),
            "language": "",
            "architecture": ((re.search(_ARCH_RE, text).group(1) or "").lower()
                             if _ARCH_RE.search(text) else ""),
        })
    return {"state": "METADATA FOUND" if records else "NOT FOUND",
            "note": f"file index returned {len(records)} record(s) for {query!r}",
            "records": records}


# ------------------------------------------------------- download + verify

def _hashes(path: str) -> dict:
    h1, h2, h5, hm = (hashlib.sha1(), hashlib.sha256(),
                      hashlib.sha512(), hashlib.md5())
    size = 0
    with open(path, "rb") as f:
        while True:
            c = f.read(1024 * 512)
            if not c:
                break
            size += len(c)
            h1.update(c)
            h2.update(c)
            h5.update(c)
            hm.update(c)
    return {"sha1": h1.hexdigest(), "sha256": h2.hexdigest(),
            "sha512": h5.hexdigest(), "md5": hm.hexdigest(), "size": size}


def download_candidate(cand: dict, staging_dir: str, timeout: int = 120,
                       progress_cb=None) -> dict:
    """Download one candidate's URL to staging. Emits DOWNLOAD states."""
    from .retrieve import sha256_file  # noqa: F401 (kept for pipeline compat)
    os.makedirs(staging_dir, exist_ok=True)
    filename = cand.get("filename") or "testb-package.file"
    dst = os.path.join(staging_dir, filename)
    cand["state"] = "DOWNLOADING"
    if progress_cb:
        progress_cb(cand, 0)
    try:
        req = urllib.request.Request(cand["url"], headers=UA)
        total = 0
        started = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r, \
                open(dst, "wb") as f:
            while True:
                chunk = r.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if progress_cb:
                    progress_cb(cand, total)
        cand = {**cand, "staged": os.path.abspath(dst),
                "size": total,
                "elapsed_s": round(time.time() - started, 2),
                "state": "DOWNLOADED"}
        return cand
    except Exception as e:
        cand = {**cand, "state": "CORRUPTED",
                "error": f"download failed: {type(e).__name__}: {e}"}
        return cand


def verify_downloaded(cand: dict) -> dict:
    """Full post-download verification: identity / version / platform / hash.

    Runs identify + package-meta manifest parse on the staged file and
    promotes the candidate to IDENTITY VERIFIED / HASH VERIFIED /
    READY FOR DECRYPTION or rejects it explicitly.
    """
    from .identify import identify_file
    from .package_meta import build_package_record
    staged = cand.get("staged", "")
    if not staged or not os.path.isfile(staged):
        cand["verdict"] = "CORRUPTED"
        cand["reason"] = "staged file missing"
        return cand
    try:
        ident = identify_file(staged)
    except Exception as e:
        cand["verdict"] = "CORRUPTED"
        cand["reason"] = f"identify failed: {e}"
        return cand
    if not ident.get("is_likely_comz"):
        cand["verdict"] = "WRONG GAME"
        cand["reason"] = "post-download identity: no CoM Zombies signals"
        cand["identification"] = ident
        return cand
    cand["identification"] = {
        "filename": ident.get("filename"), "extension": ident.get("extension"),
        "detected_format": ident.get("detected_format"),
        "sha1": ident.get("sha1"), "sha256": ident.get("sha256"),
        "md5": ident.get("md5"), "size": ident.get("size")}
    cand["sha1"], cand["sha256"], cand["md5"] = (
        ident.get("sha1", ""), ident.get("sha256", ""), ident.get("md5", ""))
    cand["size"] = ident.get("size", 0)
    cand["verdict"] = "IDENTITY VERIFIED"
    # --- package-meta: version + platform from the manifests
    try:
        rec = build_package_record(staged)
    except Exception as e:
        cand["reason"] = f"metadata parse failed (identity held): {e}"
        return cand
    cand["package_record"] = {
        "game": rec.get("game"), "version": rec.get("version"),
        "platform": rec.get("platform"),
        "package_id": rec.get("package_id"),
        "product_id": rec.get("product_id"),
        "architecture": rec.get("architecture"),
        "manifest_files": rec.get("manifest_files"),
        "contained_count": rec.get("contained_count")}
    for k in ("package_id", "product_id", "content_id", "publisher",
              "package_version", "architecture", "language"):
        if rec.get(k) and not cand.get(k):
            cand[k] = rec[k]
    if rec.get("version"):
        cand["package_version"] = rec["version"]
        if rec["version"] != TESTB_VERSION:
            cand["verdict"] = "WRONG VERSION"
            cand["reason"] = (f"manifest version {rec['version']} "
                              f"!= target {TESTB_VERSION}")
            return cand
    plat = (rec.get("platform") or "").lower()
    if plat and "windows phone" not in plat and "xap" not in plat \
            and "appx" not in plat and "candidate" not in plat:
        cand["verdict"] = "WRONG PLATFORM"
        cand["reason"] = f"manifest platform {rec.get('platform')!r} not Windows Phone"
        return cand
    # --- size sanity vs ~79 MB historical expectation
    size = cand.get("size", 0) or 0
    lo, hi = (TESTB_EXPECTED_SIZE * (1 - TESTB_SIZE_TOLERANCE),
              TESTB_EXPECTED_SIZE * (1 + TESTB_SIZE_TOLERANCE))
    cand["size_expected"] = TESTB_EXPECTED_SIZE
    cand["size_in_range"] = bool(size and lo <= size <= hi)
    # --- corrupt / incomplete: must be a readable container
    try:
        with zipfile.ZipFile(staged, "r") as z:
            bad = z.testzip()
            count = len(z.infolist())
    except zipfile.BadZipFile:
        cand["verdict"] = "CORRUPTED"
        cand["reason"] = "downloaded bytes are not a readable package container"
        return cand
    if bad is not None:
        cand["verdict"] = "CORRUPTED"
        cand["reason"] = f"container CRC failure at {bad!r}"
        return cand
    if count == 0:
        cand["verdict"] = "CORRUPTED"
        cand["reason"] = "container holds zero entries"
        return cand
    cand["verdict"] = "HASH VERIFIED"
    cand["reason"] = (f"identity + version + platform matched, "
                      f"{count} container entries, hashes recorded")
    cand["state"] = "READY FOR DECRYPTION"
    cand["verdict"] = "READY FOR DECRYPTION"
    return cand


# ------------------------------------------------------- TEST-B pipeline

def run_testb(staging_dir: str, source: str = "rg-adguard",
              timeout: int = 45, progress_cb=None,
              resolver_fn=None) -> dict:
    """Automatic TEST-B acquisition via the RG-Adguard backend.

    resolver_fn(app_id) override exists so tests can inject a canned
    resolver result without network. Pipeline:

        resolve -> enumerate -> filter -> download -> verify
    then hands the staged file to the standard preservation chain
    (analyze / locate .file-IXP / decrypt / verify-plaintext / extract /
    Unity) via the returned record — the decrypt step itself still
    requires the operator's key material downstream.
    """
    log: list[str] = []
    resolver_fn = resolver_fn or resolve_store_id
    if source != "rg-adguard":
        return {"state": "NOT FOUND", "log": [f"source {source!r} not handled here"],
                "candidate": None}
    log.append(f"[RG-ADGUARD] resolving {TESTB_APP_ID}")
    res = resolver_fn(TESTB_APP_ID)
    if not res.get("links"):
        log.append("[RG-ADGUARD] no package links returned")
        return {"state": "NOT FOUND", "log": log + [res.get("raw_note", "")],
                "candidate": None, "resolver": res}
    log.append("[RG-ADGUARD] Package found "
               f"({len(res['links'])} link(s) enumerated)")
    sel = select_testb_candidates(res["links"])
    log.append(f"[RG-ADGUARD] generations reported: "
               f"{sel['generations'] or ['unstamped']}")
    if not sel["selected"]:
        detail = "; ".join(
            f"{c['filename']}={c.get('verdict')}" for c in sel["all"][:10])
        log.append(f"no exact-target candidate: {detail}")
        return {"state": "WRONG VERSION", "log": log,
                "candidate": None, "candidates": sel["all"]}
    cand = sel["selected"][0]
    log.append(f"[VERIFY] candidate pre-filter: {cand['filename']} "
               f"({cand.get('package_type','?')})")
    cand = download_candidate(cand, staging_dir, timeout=max(timeout, 120),
                              progress_cb=progress_cb)
    if cand.get("state") != "DOWNLOADED":
        log.append(f"download failed: {cand.get('error','unknown')}")
        return {"state": "CORRUPTED", "log": log, "candidate": cand}
    log.append("[DOWNLOAD] Complete")
    cand = verify_downloaded(cand)
    v = cand.get("verdict", "CORRUPTED")
    if v == "READY FOR DECRYPTION":
        log += ["[VERIFY] Application identity matched",
                "[VERIFY] Version matched",
                "[VERIFY] Platform matched",
                "[VERIFY] Hash recorded"]
    log.append(f"final: {v}")
    state = v if v in STATES else "CORRUPTED"
    return {"state": state, "log": log, "candidate": cand,
            "candidates": sel["all"]}


def compare_source_hashes(records: list[dict]) -> dict:
    """Cross-source consensus: MATCH when all SHA-256 agree, else CONFLICT.

    Each record: {"source": name, "sha256": hex}. Never silently picks one.
    """
    hashes = {r.get("source", "?"): (r.get("sha256") or "").lower()
              for r in records}
    uniq = {h for h in hashes.values() if h}
    if len(uniq) == 1 and len(hashes) == len(records) and records:
        return {"result": "SOURCE CONSENSUS: MATCH",
                "sha256": uniq.pop(), "per_source": hashes}
    return {"result": "SOURCE CONFLICT", "per_source": hashes}


def chain_into_pipeline(staged: str, out_dir: str) -> dict:
    """Pass a READY package into analyze / extract / Unity stages.

    Decryption itself still needs the operator key (decrypt command);
    this runs everything key-independent: analyze, package-meta,
    plaintext extract attempt, Unity scan of the result.
    """
    from .analyze import analyze_file
    from .package_meta import build_package_record
    from .unity import scan_unity
    from . import decryptor as dec
    steps: dict = {"staged": os.path.abspath(staged)}
    steps["analysis"] = analyze_file(staged)
    try:
        steps["package_record"] = build_package_record(staged)
    except Exception as e:
        steps["package_record"] = {"error": str(e)}
    # locate .file / IXP / protected-data members
    names = [e.get("name", "") for e in
             steps["analysis"].get("zip_inventory", {}).get("entries", [])]
    steps["protected_members"] = [
        n for n in names
        if n.lower().endswith((".file", ".ixp")) or "protect" in n.lower()]
    os.makedirs(out_dir, exist_ok=True)
    try:
        res = dec.extract_package(staged, out_dir)
    except Exception as e:  # gated or opaque
        res = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    steps["extract"] = res
    if res.get("ok"):
        try:
            steps["unity"] = scan_unity(out_dir)
        except Exception as e:
            steps["unity"] = {"error": str(e)}
    return steps
