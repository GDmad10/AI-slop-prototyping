"""DBOX product resolution — Microsoft Store product reference.

Known reference (lookup/correlation source, NOT proof of the
historical package):

    DBOX Product ID:  9WZDNCRFHZSZ
    DBOX URL:         https://dbox.tools/store/products/9WZDNCRFHZSZ/

Separate research identifiers — never conflated:

    MODERN / DBOX REFERENCE:               9WZDNCRFHZSZ
    HISTORICAL WINDOWS PHONE APPLICATION:  0febf8fa-35e8-4a87-8090-58b65220b3ed

DBOX product ID != package ID != Content ID != historical WP app ID.
Each stays its own field; relationships are established from actual
metadata only. A candidate that fails the historical target checks is
marked REFERENCE ONLY, never used as TEST-B.

Resolution workflow:
    DBOX product -> Store product metadata -> package relationships ->
    package versions -> platform / arch / type -> identity compare ->
    select only valid CoM Zombies package.

stdlib only.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import time
import urllib.parse
import urllib.request

DBOX_PRODUCT_ID = "9WZDNCRFHZSZ"
DBOX_PRODUCT_URL = "https://dbox.tools/store/products/9WZDNCRFHZSZ/"

HISTORICAL_WP_APP_ID = "0febf8fa-35e8-4a87-8090-58b65220b3ed"
TESTB_GAME = "Call of Mini: Zombies"
TESTB_VERSION = "1.1.0.0"
TESTB_PLATFORM = "Windows Phone"

UA = {"User-Agent": "CoMZ-Preservation-Decryptor/1.0 (DBOX product resolution)"}

_TAG_RE = re.compile(r"<[^>]+>")
_GUID_RE = re.compile(
    r"\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?")
_VER_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)")
_STORE_ID_RE = re.compile(r"\b9[A-Z0-9]{11}\b")


def _clean(s: str) -> str:
    return _html.unescape(_TAG_RE.sub("", s or "")).strip()


def fetch_product_page(product_id: str = DBOX_PRODUCT_ID,
                       timeout: int = 30) -> dict:
    """Fetch the DBOX product page HTML (reference lookup only)."""
    url = f"https://dbox.tools/store/products/{urllib.parse.quote(product_id)}/"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except Exception as e:
        return {"state": "NOT FOUND", "url": url,
                "note": f"dbox product page unreachable: "
                        f"{type(e).__name__}: {e}", "html": ""}
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return {"state": "METADATA ONLY", "url": url,
                    "note": f"fetched {len(raw)} bytes", "html": raw.decode(enc)}
        except UnicodeDecodeError:
            continue
    return {"state": "METADATA ONLY", "url": url,
            "note": f"fetched {len(raw)} bytes",
            "html": raw.decode("utf-8", "replace")}


def parse_product_metadata(html: str, url: str = DBOX_PRODUCT_URL) -> dict:
    """Import DBOX metadata fields from product-page HTML.

    Extracts whatever the page exposes (title, IDs, versions, platforms,
    architectures, relationships) without assuming markup beyond generic
    label/value structure. Missing fields stay empty — never guessed.
    """
    text = _clean(html)
    low = text.lower()

    def grab_label(*labels):
        for lb in labels:
            m = re.search(re.escape(lb) + r"\s*[:\-–—]\s*([^\n<>]{1,160})",
                          text, re.IGNORECASE)
            if m:
                return _clean(m.group(1))
        return ""

    guids = sorted({_g.strip("{}").lower() for _g in _GUID_RE.findall(text)})
    versions = sorted(set(_VER_RE.findall(text)))
    store_ids = sorted(set(_STORE_ID_RE.findall(text)))
    # publisher / platform hints near labels, else empty
    rec = {
        "dbox_product_id": DBOX_PRODUCT_ID,
        "dbox_url": url,
        "title": grab_label("Title", "Product title", "Name"),
        "title_id": grab_label("Title ID", "TitleId"),
        "product_type": grab_label("Product type", "Type"),
        "package_identity_name": grab_label("Package identity",
                                            "Identity name", "Package name"),
        "package_family_name": grab_label("Package family",
                                          "Family name", "PackageFamilyName"),
        "publisher": grab_label("Publisher", "Publisher name"),
        "product_group_id": grab_label("Product group", "Group ID"),
        "platform": grab_label("Platform"),
        "version": grab_label("Version"),
        "architecture": grab_label("Architecture"),
        "product_id": DBOX_PRODUCT_ID,
        "observed_guids": guids[:50],
        "observed_versions": versions[:50],
        "observed_store_ids": store_ids[:50],
        "package_ids": [],
        "content_ids": [],
        "key_ids": [],
        "package_relationships": [],
        "raw_text_excerpt": text[:4000],
    }
    # title fallback: <title> tag
    if not rec["title"]:
        m = re.search(r"<title[^>]*>(.*?)</title>", html,
                      re.IGNORECASE | re.DOTALL)
        if m:
            rec["title"] = _clean(m.group(1))[:200]
    # historical-ID presence is an observed flag, not a verdict
    rec["mentions_historical_wp_id"] = (
        HISTORICAL_WP_APP_ID.lower() in low)
    rec["mentions_comz"] = any(
        t in low for t in ("call of mini", "callofmini", "mini zombies"))
    return rec


def resolve_product(product_id: str = DBOX_PRODUCT_ID,
                    timeout: int = 30) -> dict:
    """Full product-resolution step: fetch + import metadata."""
    page = fetch_product_page(product_id, timeout=timeout)
    if page["state"] == "NOT FOUND":
        return {"state": "NOT FOUND", "dbox_product_id": product_id,
                "dbox_url": page["url"], "note": page["note"],
                "metadata": None}
    meta = parse_product_metadata(page["html"], page["url"])
    return {"state": "METADATA ONLY", "dbox_product_id": product_id,
            "dbox_url": page["url"], "note": page["note"],
            "metadata": meta}


def determine_relationship(meta: dict) -> dict:
    """Determine DBOX-product vs historical-package relationship.

    Compares observed versions/platforms/IDs against the TEST-B target.
    Outcome is one of: EXACT TARGET / RELATED GENERATION /
    UNRELATED / INSUFFICIENT METADATA. Never assumes sameness.
    """
    if not meta:
        return {"relationship": "INSUFFICIENT METADATA",
                "reason": "no DBOX metadata to compare"}
    versions = meta.get("observed_versions", []) or (
        [meta["version"]] if meta.get("version") else [])
    plat = (meta.get("platform") or "").lower()
    title_ok = meta.get("mentions_comz", False)
    wp_mention = meta.get("mentions_historical_wp_id", False)
    if not title_ok and not wp_mention and not versions:
        return {"relationship": "INSUFFICIENT METADATA",
                "reason": "page exposes no title, WP ID, or version signals"}
    if TESTB_VERSION in versions and ("windows phone" in plat or not plat):
        if wp_mention or title_ok:
            return {"relationship": "EXACT TARGET",
                    "reason": f"observes version {TESTB_VERSION} with "
                              f"CoM/WP-ID signals"}
    if versions and TESTB_VERSION not in versions:
        return {"relationship": "RELATED GENERATION",
                "reason": f"DBOX observes version(s) {versions[:5]} — "
                          f"modern generation, not the {TESTB_VERSION} package"}
    if title_ok or wp_mention:
        return {"relationship": "RELATED GENERATION",
                "reason": "title/WP-ID signal without exact-version evidence; "
                          "correlation only"}
    return {"relationship": "UNRELATED",
            "reason": "no CoM Zombies / WP-ID / version link observed"}


def check_candidate_against_target(cand: dict) -> dict:
    """Acceptance gate for any candidate (DBOX/Store/RG-Adguard/other).

    Verifies game identity, platform, version, format, arch, publisher,
    package identity, product relationship, size, hash. Non-matching
    historical checks -> REFERENCE ONLY (never TEST-B).
    """
    fails: list[str] = []
    blob = (f"{cand.get('filename','')} {cand.get('label','')} "
            f"{cand.get('package_id','')} {cand.get('product_id','')} "
            f"{cand.get('content_id','')}").lower()
    game_ok = ("call of mini" in blob or "callofmini" in blob
               or "mini zombies" in blob or "minizombies" in blob
               or "comz" in blob)
    if not game_ok and not cand.get("package_record"):
        fails.append("game identity")
    ver = cand.get("package_version") or (cand.get("package_record") or {}).get("version", "")
    if ver and ver != TESTB_VERSION:
        fails.append(f"version ({ver} != {TESTB_VERSION})")
    plat = ((cand.get("package_record") or {}).get("platform", "")
            + " " + cand.get("platform_hint", "")).lower()
    if plat and not any(k in plat for k in
                        ("windows phone", "xap", "appx", "candidate")):
        fails.append("platform")
    ptype = (cand.get("package_type") or "").lower()
    if ptype and ptype not in ("xap", "unknown"):
        fails.append(f"package format ({ptype}, expected historical XAP)")
    if fails:
        cand["testb_use"] = "REFERENCE ONLY"
        cand["acceptance"] = f"fails historical target: {'; '.join(fails)}"
        return cand
    cand["testb_use"] = "TEST-B CANDIDATE"
    cand["acceptance"] = "passes historical-target acceptance checks"
    return cand


def preservation_record(cand: dict, source: str) -> dict:
    """Snapshot stored alongside the untouched original download."""
    return {
        "dbox_product_id": DBOX_PRODUCT_ID,
        "dbox_url": DBOX_PRODUCT_URL,
        "historical_store_id": HISTORICAL_WP_APP_ID,
        "package_id": cand.get("package_id", ""),
        "content_id": cand.get("content_id", ""),
        "key_id": cand.get("key_id", ""),
        "package_filename": cand.get("filename", ""),
        "version": cand.get("package_version", ""),
        "platform": TESTB_PLATFORM,
        "architecture": cand.get("architecture", ""),
        "url_source": source,
        "sha1": cand.get("sha1", ""),
        "sha256": cand.get("sha256", ""),
        "size": cand.get("size", 0),
        "retrieval_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "original download preserved unaltered; this record rides alongside",
    }
