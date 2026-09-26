#!/usr/bin/env python3
"""CoM Zombies Preservation Decryptor — Call of Mini: Zombies only.

Windows-native preservation, package-retrieval, decryption, and
extraction for legitimately obtained historical game packages.
Primary target: historical Windows Phone release, especially
Call of Mini: Zombies v1.1.0.0 packages / server-archive files.

Reference model for package metadata: DBOX Tools (https://dbox.tools/).

Real recovery + real decryption (operator-supplied keys only):
  retrieve  | metadata | decrypt | extract
Analysis / catalog / compare / Unity scan from the prior build remain.

Gate: non-matching files print NOT CALL OF MINI: Zombies and the
game-specific decryptor stays disabled.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

from comz_core.identify import identify_file, gate_message
from comz_core.analyze import analyze_file
from comz_core.catalog import Catalog
from comz_core.compare import compare_files
from comz_core.unity import scan_unity
from comz_core.wrappers import detect_wrapper
from comz_core.package_meta import build_package_record
from comz_core.retrieve import ingest_local, retrieve_url
from comz_core import crypto as _crypto
from comz_core import decryptor as _dec
from comz_core import rg_adguard as _rg
from comz_core import dbox as _dbox
from comz_core import wpcompat as _wp


def cmd_identify(args):
    ident = identify_file(args.file)
    print(gate_message(ident))
    print(json.dumps(ident, indent=2))
    if not ident.get("is_likely_comz"):
        return 2
    return 0


def cmd_analyze(args):
    rep = analyze_file(args.file)
    wrap = detect_wrapper(args.file)
    ident = rep["identification"]
    print(gate_message(ident))
    print("\n== STRUCTURAL MAP ==")
    print(rep["structural_map"]["tree"])
    for s in rep["structural_map"]["sections"]:
        print(f"  {s['name']:12s} offset={s['offset']} size={s['size']} :: {s['note']}")
    print(f"\nhead_hex(0..255): {rep['structural_map']['head_hex'][:160]}...")
    print("\n== WRAPPER ==")
    print(json.dumps(wrap, indent=2))
    print("\n== CHUNK ENTROPIES ==")
    for c in rep["chunk_entropies"]:
        print(f"  offset={c['offset']:>10d} size={c['size']:>8d} entropy={c['entropy']} zero={c['zero_ratio']}")
    print(f"\nfull_entropy_head(1MiB): {rep['full_entropy_head']}")
    print("\n== OBSERVABLES (plaintext only) ==")
    print(json.dumps(rep["observables"], indent=2))
    print("\n== ZIP INVENTORY ==")
    zi = rep["zip_inventory"]
    if zi["readable"]:
        print(f"readable plaintext container, {zi['count']} entries (first 40):")
        for e in zi["entries"][:40]:
            flag = " ENCRYPTED-FLAG" if e["is_encrypted_flag"] else ""
            print(f"  {e['name']} ({e['file_size']}b){flag}")
    else:
        print(f"not a readable plaintext container: {zi['error']}")
        print("No extraction or decryption attempted.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"analysis": rep, "wrapper": wrap}, f, indent=2)
        print(f"\nwrote {args.json}")
    return 0


def cmd_report(args):
    rep = analyze_file(args.file)
    wrap = detect_wrapper(args.file)
    out = {"identification": rep["identification"], "analysis": rep, "wrapper": wrap,
           "scope": "analysis only — no decryption performed"}
    if args.format == "json":
        text = json.dumps(out, indent=2)
    else:
        text = (f"File: {rep['identification']['filename']}\n"
                f"SHA256: {rep['identification']['sha256']}\n"
                f"Format: {rep['identification']['detected_format']}\n"
                f"Likely CoMZ: {rep['identification']['is_likely_comz']}\n"
                f"Scope: analysis only\n")
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


def cmd_compare(args):
    d = compare_files(args.a, args.b)
    print(json.dumps(d, indent=2))
    if d.get("protection_changed"):
        print("\nNOTE: container readability/entropy differs — record as an "
              "observational difference only, not as an identified cipher change.")
    return 0


def cmd_scan_unity(args):
    r = scan_unity(args.dir)
    print(json.dumps(r, indent=2))
    return 0


def cmd_catalog_add(args):
    ident = identify_file(args.file)
    cat = Catalog(args.db)
    rid = cat.auto_record(ident, {"source_notes": args.source_notes or "",
                                  "research_notes": args.research_notes or ""})
    print(f"recorded id={rid} likely_comz={ident.get('is_likely_comz')}")
    return 0


def cmd_catalog_list(args):
    cat = Catalog(args.db)
    rows = cat.list_all()
    print(json.dumps(rows, indent=2))
    return 0


def cmd_extract_plaintext(args):
    """Extract ONLY plaintext zip-based containers. Refuse opaque/flagged content."""
    try:
        with zipfile.ZipFile(args.file, "r") as z:
            infos = z.infolist()
            flagged = [i.filename for i in infos if i.flag_bits & 0x1]
            if flagged:
                print("REFUSED: archive sets the encrypted flag on "
                      f"{len(flagged)} entries (e.g. {flagged[0]}).")
                print("This tool does not remove password/drm protection. "
                      "Use the vendor-supported export of a copy you own.")
                return 3
            os.makedirs(args.output, exist_ok=True)
            z.extractall(args.output)
            print(f"EXTRACTED {len(infos)} entries to {args.output}")
            print("PLAINTEXT EXTRACTED (container was already plaintext — no decryption performed).")
            return 0
    except zipfile.BadZipFile:
        print("REFUSED: not a plaintext zip container (BadZipFile).")
        print("DECRYPTION FAILED")
        print("PLAINTEXT VALIDATION FAILED")
        print("No decryption attempted — opaque Microsoft/Windows Phone "
              "protection is out of scope for this tool.")
        return 4


def cmd_verify_plaintext(args):
    """Validate an already-unpacked directory OR a plaintext file.
    Never claims a decryption break."""
    target = args.path
    if os.path.isdir(target):
        r = scan_unity(target)
        # check for PE / Unity markers in top-level files
        markers = []
        for root, _, files in os.walk(target):
            if os.path.relpath(root, target).count(os.sep) > 2:
                continue
            for fn in files:
                p = os.path.join(root, fn)
                try:
                    with open(p, "rb") as f:
                        head = f.read(8)
                    if head.startswith(b"MZ"):
                        markers.append(os.path.relpath(p, target) + " [MZ]")
                    if head.startswith(b"UnityFS"):
                        markers.append(os.path.relpath(p, target) + " [UnityFS]")
                except OSError:
                    pass
            if len(markers) > 20:
                break
        ok = bool(r["unity_files"] or r["unity_dlls"] or markers)
        if ok:
            print("DECRYPTION NOT APPLICABLE — INPUT WAS ALREADY PLAINTEXT")
            print("PLAINTEXT VERIFIED (Unity/PE structures found)")
            print(json.dumps({"unity": r, "pe_unity_markers": markers[:20]}, indent=2))
            return 0
        print("DECRYPTION FAILED")
        print("PLAINTEXT VALIDATION FAILED (no Unity/PE/manifest structures found)")
        return 5
    else:
        rep = analyze_file(target)
        zi = rep["zip_inventory"]
        if zi["readable"] and zi["count"] > 0:
            print("PLAINTEXT VERIFIED (readable plaintext container — no decryption performed)")
            return 0
        print("DECRYPTION FAILED")
        print("PLAINTEXT VALIDATION FAILED (opaque — no decryption attempted)")
        return 5


def cmd_research_diff(args):
    """Lawful before/after comparison: compares two directories or files
    you already possess (e.g. archived copy vs vendor-exported backup).
    Records hashes, changed ranges at file level — never derives keys."""
    import hashlib

    def fhash(p):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    a, b = args.a, args.b
    if os.path.isfile(a) and os.path.isfile(b):
        da = open(a, "rb").read()
        db = open(b, "rb").read()
        changed = sum(1 for x, y in zip(da, db) if x != y) + abs(len(da) - len(db))
        print(json.dumps({
            "a": {"path": a, "size": len(da), "sha256": fhash(a)},
            "b": {"path": b, "size": len(db), "sha256": fhash(b)},
            "size_delta": len(db) - len(da),
            "differing_bytes_in_overlap": changed,
            "note": "byte-level diff only — reproduce transformations solely "
                    "with vendor-supported tooling on copies you own",
        }, indent=2))
        return 0
    print("research-diff expects two files (for directories, use compare + scan-unity).")
    return 2


def cmd_retrieve(args):
    if args.url:
        def prog(n):
            print(f"\r  downloaded {n} bytes…", end="", flush=True)
        r = retrieve_url(args.url, args.staging, filename=args.filename or "",
                         expected_sha256=args.expect_sha256 or "",
                         progress_cb=prog)
        print()
        ident = identify_file(r["staged"])
        print(gate_message(ident))
        print(json.dumps(r, indent=2))
        if args.catalog:
            Catalog(args.catalog).auto_record(
                ident, {"source_notes": f"url-retrieval {args.url}",
                        "research_notes": "CoM Zombies preservation decryptor"})
            print("cataloged.")
        return 0 if (r.get("sha256_match") is not False) else 6
    r = ingest_local(args.file, args.staging)
    ident = identify_file(r["staged"])
    print(gate_message(ident))
    print(json.dumps(r, indent=2))
    if args.catalog:
        Catalog(args.catalog).auto_record(
            ident, {"source_notes": f"local-ingest {r['source']}",
                    "research_notes": "CoM Zombies preservation decryptor"})
        print("cataloged.")
    return 0


def cmd_metadata(args):
    rec = build_package_record(args.file)
    print(gate_message(rec["identification"]))
    print(json.dumps(rec, indent=2) if args.format == "json" else (
        f"Game: {rec['game']}\nVersion: {rec['version']}\n"
        f"Primary target v1.1.0.0: {rec['is_primary_target_v1_1_0_0']}\n"
        f"Package ID: {rec['package_id']}\nProduct ID: {rec['product_id']}\n"
        f"Platform: {rec['platform']}\nArch: {rec['architecture']}\n"
        f"Manifests: {rec['manifest_files']}\n"
        f"Contained files: {rec['contained_count']}\n"))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
        print(f"wrote {args.output}")
    if args.catalog:
        Catalog(args.catalog).add({
            "game": rec["game"], "package_id": rec["package_id"],
            "content_id": rec["content_id"], "product_id": rec["product_id"],
            "version": rec["version"], "platform": rec["platform"],
            "architecture": rec["architecture"],
            "filename": rec["identification"]["filename"],
            "extension": rec["identification"]["extension"],
            "detected_format": rec["identification"]["detected_format"],
            "encrypted": "", "encryption_type": "operator-key decryptor",
            "key_status": "operator-supplied (never stored)",
            "decryption_status": "metadata only",
            "sha1": rec["identification"]["sha1"],
            "sha256": rec["identification"]["sha256"],
            "md5": rec["identification"]["md5"],
            "file_size": rec["identification"]["size"],
            "source_notes": "metadata extraction",
            "research_notes": f"primary-target={rec['is_primary_target_v1_1_0_0']}",
        })
        print("cataloged.")
    return 0


def _load_key(args) -> bytes:
    if args.key_hex:
        return _crypto.parse_key_hex(args.key_hex)
    if args.key_file:
        with open(args.key_file, "rb") as f:
            raw = f.read().strip()
        try:
            return _crypto.parse_key_hex(raw.decode("ascii"))
        except Exception:
            if len(raw) in (16, 24, 32):
                return raw
            raise SystemExit("key-file must hold hex or 16/24/32 raw bytes")
    if args.password is not None:
        return args.password.encode("utf-8")
    raise SystemExit("supply --key-hex, --key-file, or --password")


def cmd_decrypt(args):
    mode = args.mode
    try:
        if mode == "zip-password":
            pwd = _load_key(args) if (args.password is not None or args.key_file) else (
                args.password or "").encode("utf-8")
            # --password empty string allowed (tests empty-pwd zips)
            if args.password is None and not args.key_file:
                raise SystemExit("zip-password needs --password or --key-file")
            res = _dec.decrypt_zip_password(args.file, args.output, pwd)
        else:
            key = _load_key(args)
            if args.derive:
                key = _crypto.derive_key_sha256(key)
            iv = bytes.fromhex(args.iv_hex) if args.iv_hex else None
            if mode == "aes-cbc-file" and iv is None:
                raise SystemExit("aes-cbc-file needs --iv-hex (16 bytes hex)")
            res = _dec.decrypt_file_blob(args.file, args.output, key, mode, iv)
    except _dec.NotComZombies as e:
        print(str(e))
        return 2
    print(json.dumps(res, indent=2))
    if res.get("ok"):
        print(f"{res.get('decryption', 'DECRYPTION SUCCEEDED')}")
        print(f"{res.get('validation', 'PLAINTEXT VERIFIED')}")
        if args.catalog:
            from comz_core.identify import identify_file as _id
            try:
                ident = _id(args.output)
            except Exception:
                ident = identify_file(args.file)
            Catalog(args.catalog).auto_record(
                ident, {"source_notes": f"decrypted {mode} from {args.file}",
                        "research_notes": f"markers={res.get('markers', [])}"})
        return 0
    print("DECRYPTION FAILED")
    print("PLAINTEXT VALIDATION FAILED")
    return 5


def cmd_extract(args):
    try:
        res = _dec.extract_package(args.file, args.output)
    except _dec.NotComZombies as e:
        print(str(e))
        return 2
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 4


def _run_testb(args) -> int:
    print(f"TEST-B target: {_rg.TESTB_GAME} {_rg.TESTB_VERSION} "
          f"({_rg.TESTB_PLATFORM}) historical id={_rg.TESTB_APP_ID}")
    print(f"DBOX reference: {_dbox.DBOX_PRODUCT_ID} ({_dbox.DBOX_PRODUCT_URL})")
    print("note: DBOX product ID != package ID != Content ID != historical WP app ID")
    print(f"source priority: {' > '.join(_rg.SOURCE_PRIORITY)}")
    print(f"requested source: {args.source}")
    profile = getattr(args, "profile", "last-resort")
    if profile not in ("normal", "legacy-wp8", "last-resort"):
        print(f"unknown profile {profile!r}; using last-resort")
        profile = "last-resort"
    print(f"resolver profile: {profile}")
    if profile == "legacy-wp8":
        print("[legacy-wp8] CallOfMiniZombies-WP8 virtual profile "
              "(request metadata only; device untouched)")
    elif profile == "last-resort":
        print("[last-resort] automatic fallback: "
              + " > ".join(_wp.FALLBACK_CHAIN))
    tried: list[str] = []
    result: dict | None = None
    dbox_rel: dict | None = None
    compat: dict | None = None
    if profile in ("legacy-wp8", "last-resort"):
        try:
            compat = _wp.attempt_legacy_metadata("legacy-wp8")
            for s in compat.get("steps", []):
                print(f"[{s['layer']}] {s['state']} — {s.get('note','')}")
            tried.append("legacy-wp8-profile:" +
                         str(compat.get("legacy_wp8", "UNKNOWN")))
        except Exception as e:  # noqa: BLE001
            print(f"[legacy-wp8-profile] probe failed: {e}")
            tried.append("legacy-wp8-profile:UNKNOWN")
    if profile == "legacy-wp8" and compat:
        # legacy-only run still falls through to the shared chain below
        pass
    order = _rg.SOURCE_PRIORITY
    try:
        start = order.index(args.source)
    except ValueError:
        start = order.index("rg-adguard") if "rg-adguard" in order else 0
    for src in order[start:]:
        if src == "dbox-product":
            print("[dbox-product] resolving product reference…")
            pres = _dbox.resolve_product()
            print(f"[dbox-product] state: {pres['state']}")
            if pres.get("metadata"):
                dbox_rel = _dbox.determine_relationship(pres["metadata"])
                print(f"[dbox-product] relationship: "
                      f"{dbox_rel['relationship']} — {dbox_rel['reason']}")
                if args.catalog:
                    Catalog(args.catalog).record_dbox(
                        _dbox.DBOX_PRODUCT_ID, _dbox.DBOX_PRODUCT_URL,
                        pres["metadata"].get("title", ""),
                        pres["metadata"].get("publisher", ""),
                        dbox_rel["relationship"], dbox_rel["reason"])
            else:
                print(f"[dbox-product] {pres.get('note','no metadata')}")
            tried.append("dbox-product:" + pres.get("state", "?"))
            continue
        if src != "rg-adguard":
            print(f"[{src}] no package (backend not configured) — next")
            tried.append(src + ":NOT FOUND")
            continue
        def prog(cand, n):
            print(f"\r  DOWNLOADING {cand.get('filename','')} {n} bytes…",
                  end="", flush=True)
        result = _rg.run_testb(args.staging, source="rg-adguard",
                               progress_cb=prog)
        print()
        tried.append("rg-adguard:" + result.get("state", "?"))
        break
    assert result is not None
    for line in result.get("log", []):
        print(line)
    cand = result.get("candidate") or {}
    if cand:
        cand = _dbox.check_candidate_against_target(cand)
        cand = _wp.cross_match(cand)
        result["candidate"] = cand
        view = {k: cand.get(k) for k in (
            "filename", "extension", "package_type", "package_version",
            "architecture", "language", "publisher", "package_id",
            "product_id", "content_id", "size", "sha1", "sha256",
            "verdict", "reason", "state", "staged",
            "testb_use", "acceptance",
            "match_class", "testb_eligible") if cand.get(k) is not None}
        print(json.dumps(view, indent=2))
        if cand.get("testb_use") == "REFERENCE ONLY":
            print(f"candidate marked REFERENCE ONLY — {cand.get('acceptance')}")
        print(f"cross-match: {cand.get('match_class')}")
        if cand.get("match_class") == "CURRENT PC PACKAGE":
            print("CURRENT PC REFERENCE ONLY — not a TEST-B pass; "
                  "no silent downgrade to the PC build.")
    state = result.get("state", "NOT FOUND")
    if cand.get("testb_use") == "REFERENCE ONLY":
        state = "REFERENCE ONLY"
        result["state"] = state
    if cand and not cand.get("testb_eligible", True) and state == "READY FOR DECRYPTION":
        state = "REFERENCE ONLY"
        result["state"] = state
    print(f"TEST-B acquisition state: {state}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"target": {"game": _rg.TESTB_GAME,
                                  "version": _rg.TESTB_VERSION,
                                  "platform": _rg.TESTB_PLATFORM,
                                  "historical_app_id": _rg.TESTB_APP_ID,
                                  "dbox_product_id": _dbox.DBOX_PRODUCT_ID,
                                  "dbox_url": _dbox.DBOX_PRODUCT_URL},
                       "profile": profile,
                       "compat_probe": compat,
                       "dbox_relationship": dbox_rel,
                       "tried": tried, "result": result}, f, indent=2,
                      default=str)
        print(f"wrote {args.json}")
    if state == "READY FOR DECRYPTION":
        staged = (cand or {}).get("staged", "")
        prec = _dbox.preservation_record(cand, "rg-adguard")
        print(json.dumps({"preservation": prec}, indent=2))
        if args.json:
            with open(args.json, "r", encoding="utf-8") as f:
                _j = json.load(f)
            _j["preservation"] = prec
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(_j, f, indent=2, default=str)
        if args.catalog and staged:
            cat = Catalog(args.catalog)
            cat.auto_record(
                cand.get("identification", {}) | {
                    "filename": cand.get("filename", ""),
                    "extension": cand.get("extension", "")},
                {"source_notes": "TEST-B via rg-adguard; "
                                 f"dbox={_dbox.DBOX_PRODUCT_ID}",
                 "research_notes": f"sha256={cand.get('sha256','')}"})
            cat.record_xref(
                store_product=_rg.TESTB_APP_ID,
                dbox_product=_dbox.DBOX_PRODUCT_ID,
                package_id=cand.get("package_id", ""),
                content_id=cand.get("content_id", ""),
                key_id=cand.get("key_id", ""),
                historical_package=os.path.basename(staged),
                note=f"sha256={cand.get('sha256','')} size={cand.get('size',0)}")
            print("cataloged.")
        if args.chain and staged:
            pipe = _rg.chain_into_pipeline(staged, args.out_dir)
            print(json.dumps({
                "protected_members": pipe.get("protected_members"),
                "extract": pipe.get("extract", {}).get("ok"),
                "unity": (pipe.get("unity", {}) or {}).get("verdict",
                         pipe.get("unity", {}))}, indent=2, default=str))
        _print_final_report(result, tried, profile, compat)
        return 0
    # explicit non-success states keep their meaning; never fake acquired
    print("TEST-B NOT acquired — no verified package (see state above).")
    _print_final_report(result, tried, profile, compat)
    return 7


def _print_final_report(result, tried, profile, compat):
    rep = _wp.final_report(
        {"state": (result or {}).get("state", "NOT FOUND"),
         "candidate": (result or {}).get("candidate"),
         "store_page": next((t.split(":", 1)[1] for t in tried
                             if t.startswith("microsoft-store:")), "NOT FOUND"),
         "dbox": next((t.split(":", 1)[1] for t in tried
                       if t.startswith("dbox-product:")), "NOT FOUND"),
         "rg_adguard": next((t.split(":", 1)[1] for t in tried
                             if t.startswith("rg-adguard:")), "NOT FOUND")},
        {"legacy_wp8": ((compat or {}).get("legacy_wp8", "UNKNOWN"))})
    print("== TEST-B FINAL ==")
    for k, v in rep.items():
        print(f"{k}: {v}")
    print("ladder: " + " > ".join(_wp.failure_ladder()))


def cmd_retrieve_testb(args):
    return _run_testb(args)


def cmd_test(args):
    if args.name != "TEST-B":
        print(f"unknown test {args.name!r} (only TEST-B is implemented)")
        return 2
    # `test TEST-B` uses the same priority walk; earlier Microsoft
    # methods fall through to the RG-Adguard backend automatically.
    return _run_testb(args)


def cmd_rg_file_index(args):
    r = _rg.file_index_lookup(args.query)
    print(f"state: {r['state']}")
    print(r.get("note", ""))
    print(json.dumps(r.get("records", []), indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)
        print(f"wrote {args.json}")
    return 0


def cmd_test_store_profiles(args):
    print("VIRTUAL DEVICE PROFILE")
    print("Device Family: Windows Phone | OS Generation: Windows Phone 8 | "
          "Application: Call of Mini: Zombies "
          f"| App ID: {_wp.TESTB_APP_ID}")
    print("(request/profile emulation only — device untouched, "
          "no credentials/tokens/attestation)")
    r = _wp.test_store_profiles()
    for name, rec in r["profiles"].items():
        flags = " ".join(f"{k}={v}" for k, v in rec.items()
                         if k in _wp.PROFILE_TEST_FIELDS)
        print(f"[{name}] {flags}")
        if rec.get("error"):
            print(f"[{name}] error: {rec['error']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, default=str)
        print(f"wrote {args.json}")
    return 0


def cmd_dbox_product(args):
    pres = _dbox.resolve_product(args.product_id or _dbox.DBOX_PRODUCT_ID)
    print(f"DBOX product: {pres.get('dbox_product_id')}")
    print(f"DBOX URL: {pres.get('dbox_url')}")
    print(f"state: {pres['state']}")
    print(pres.get("note", ""))
    rel = None
    if pres.get("metadata"):
        rel = _dbox.determine_relationship(pres["metadata"])
        print(f"relationship: {rel['relationship']} — {rel['reason']}")
        print(json.dumps(pres["metadata"], indent=2)[:6000])
        if args.catalog:
            Catalog(args.catalog).record_dbox(
                pres["dbox_product_id"], pres["dbox_url"],
                pres["metadata"].get("title", ""),
                pres["metadata"].get("publisher", ""),
                rel["relationship"], rel["reason"])
            print("cataloged.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"product": pres, "relationship": rel}, f, indent=2,
                      default=str)
        print(f"wrote {args.json}")
    return 0


def cmd_xref_add(args):
    cat = Catalog(args.db)
    rid = cat.record_xref(
        store_product=args.store_product, dbox_product=args.dbox_product,
        package_id=args.package_id, content_id=args.content_id,
        key_id=args.key_id, historical_package=args.historical_package,
        archive_item=args.archive_item, runtime_files=args.runtime_files,
        note=args.note)
    print(f"recorded xref id={rid}")
    return 0


def cmd_xref_list(args):
    cat = Catalog(args.db)
    print(json.dumps({"xrefs": cat.list_xrefs(),
                      "dbox_refs": cat.list_dbox_refs()}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="CoMZTool", description="CoM Zombies Preservation Decryptor (Call of Mini: Zombies only)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("identify", help="hash + heuristic identification")
    s.add_argument("file"); s.set_defaults(fn=cmd_identify)

    s = sub.add_parser("analyze", help="structural map + entropy + observables")
    s.add_argument("file"); s.add_argument("--json", default="")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("report", help="write identification report")
    s.add_argument("file"); s.add_argument("--format", default="json", choices=["json", "text"])
    s.add_argument("--output", default=""); s.set_defaults(fn=cmd_report)

    s = sub.add_parser("compare", help="compare two samples")
    s.add_argument("a"); s.add_argument("b"); s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("scan-unity", help="scan unpacked directory for Unity structures")
    s.add_argument("dir"); s.set_defaults(fn=cmd_scan_unity)

    s = sub.add_parser("catalog-add", help="record sample in local catalog")
    s.add_argument("file"); s.add_argument("--db", default="comz_catalog.db")
    s.add_argument("--source-notes", default=""); s.add_argument("--research-notes", default="")
    s.set_defaults(fn=cmd_catalog_add)

    s = sub.add_parser("catalog-list", help="list catalog entries")
    s.add_argument("--db", default="comz_catalog.db"); s.set_defaults(fn=cmd_catalog_list)

    s = sub.add_parser("extract-plaintext", help="extract ONLY already-plaintext zip containers")
    s.add_argument("file"); s.add_argument("--output", required=True)
    s.set_defaults(fn=cmd_extract_plaintext)

    s = sub.add_parser("verify-plaintext", help="validate unpacked/plaintext data")
    s.add_argument("path"); s.set_defaults(fn=cmd_verify_plaintext)

    s = sub.add_parser("research-diff", help="lawful before/after byte diff of two files you own")
    s.add_argument("a"); s.add_argument("b"); s.set_defaults(fn=cmd_research_diff)

    s = sub.add_parser("retrieve", help="recover package: local ingest or URL download")
    s.add_argument("--file", default="", help="local file you possess")
    s.add_argument("--url", default="", help="direct package/archive URL you hold")
    s.add_argument("--filename", default="")
    s.add_argument("--expect-sha256", default="")
    s.add_argument("--staging", default="staging")
    s.add_argument("--catalog", default="")
    s.set_defaults(fn=cmd_retrieve)

    s = sub.add_parser("metadata", help="DBOX-style package metadata (identifiers/versions/arch/files)")
    s.add_argument("file"); s.add_argument("--format", default="json", choices=["json", "text"])
    s.add_argument("--output", default=""); s.add_argument("--catalog", default="")
    s.set_defaults(fn=cmd_metadata)

    s = sub.add_parser("decrypt", help="REAL decrypt with operator-supplied key (CoM Zombies only)")
    s.add_argument("file"); s.add_argument("--output", required=True)
    s.add_argument("--mode", required=True,
                    choices=["zip-password", "aes-cbc-file", "aes-ecb-file", "xor-file",
                             "playready-aesctr-file"])
    s.add_argument("--key-hex", default="")
    s.add_argument("--key-file", default="")
    s.add_argument("--password", default=None)
    s.add_argument("--iv-hex", default="")
    s.add_argument("--derive", action="store_true",
                   help="SHA-256 KDF over supplied password bytes first")
    s.add_argument("--catalog", default="")
    s.set_defaults(fn=cmd_decrypt)

    s = sub.add_parser("extract", help="extract decrypted plaintext package")
    s.add_argument("file"); s.add_argument("--output", required=True)
    s.set_defaults(fn=cmd_extract)

    s = sub.add_parser("retrieve-test-b", help="TEST-B acquisition (DBOX > Store > RG-Adguard …)")
    s.add_argument("--source", default="dbox-product",
                   choices=["dbox-product", "microsoft-store", "rg-adguard",
                            "ms-package-downloader", "internet-archive",
                            "wayback", "preservation-mirror"])
    s.add_argument("--profile", default="last-resort",
                   choices=["normal", "legacy-wp8", "last-resort"])
    s.add_argument("--staging", default="staging-testb")
    s.add_argument("--out-dir", default="testb-out")
    s.add_argument("--chain", action="store_true",
                   help="on READY, run analyze/extract/Unity pipeline stages")
    s.add_argument("--catalog", default="")
    s.add_argument("--json", default="", help="write full TEST-B record to file")
    s.set_defaults(fn=cmd_retrieve_testb)

    s = sub.add_parser("test", help="named test flows (TEST-B walks full pipeline)")
    s.add_argument("name", help="TEST-B")
    s.add_argument("--source", default="dbox-product")
    s.add_argument("--profile", default="last-resort",
                   choices=["normal", "legacy-wp8", "last-resort"])
    s.add_argument("--staging", default="staging-testb")
    s.add_argument("--out-dir", default="testb-out")
    s.add_argument("--chain", action="store_true")
    s.add_argument("--catalog", default="")
    s.add_argument("--json", default="")
    s.set_defaults(fn=cmd_test)

    s = sub.add_parser("test-store-profiles", help="test PC/WP8/historical/last-resort profiles")
    s.add_argument("--json", default="")
    s.set_defaults(fn=cmd_test_store_profiles)

    s = sub.add_parser("rg-file-index", help="RG-Adguard file-index metadata lookup")
    s.add_argument("query"); s.add_argument("--json", default="")
    s.set_defaults(fn=cmd_rg_file_index)

    s = sub.add_parser("dbox-product", help="DBOX product reference resolution")
    s.add_argument("--product-id", default="9WZDNCRFHZSZ")
    s.add_argument("--catalog", default=""); s.add_argument("--json", default="")
    s.set_defaults(fn=cmd_dbox_product)

    s = sub.add_parser("xref-add", help="record store/dbox/package/content/key relationship")
    s.add_argument("--db", default="comz_catalog.db")
    s.add_argument("--store-product", default="")
    s.add_argument("--dbox-product", default="")
    s.add_argument("--package-id", default="")
    s.add_argument("--content-id", default="")
    s.add_argument("--key-id", default="")
    s.add_argument("--historical-package", default="")
    s.add_argument("--archive-item", default="")
    s.add_argument("--runtime-files", default="")
    s.add_argument("--note", default="")
    s.set_defaults(fn=cmd_xref_add)

    s = sub.add_parser("xref-list", help="list cross-reference relationships")
    s.add_argument("--db", default="comz_catalog.db")
    s.set_defaults(fn=cmd_xref_list)

    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except FileNotFoundError as e:
        print(f"file not found: {e}", file=sys.stderr)
        return 2
    except NotADirectoryError as e:
        print(f"not a directory: {e}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
