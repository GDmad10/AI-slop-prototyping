"""Ghost IPA Installer — CLI (§23)."""
from __future__ import annotations

import argparse
import json
import sys

from ghostipa.core.confidence import Confidence
from ghostipa.core.database import AppVersion, ResearchDB
from ghostipa.core.research_log import ResearchLog
from ghostipa.modules.detector import detect
from ghostipa.modules.device import check_compatibility, detect_device, render_device
from ghostipa.modules.ipa_analysis import analyze_ipa, compare_ipas, hash_file
from ghostipa.modules.metadata import lookup_by_apple_id, normalize_apple_metadata
from ghostipa.modules.preservation import build_preservation_package, final_report
from ghostipa.modules.research import build_search_queries, web_archive_url
from ghostipa.modules.harvest import commoncrawl_urls, extract_ids, verify_ids, wayback_urls
from ghostipa.modules.testflight import check_code, extract_codes, join_url

DB = ResearchDB()
LOG = ResearchLog()


def cmd_search(args: argparse.Namespace) -> int:
    report, sm, _rec = detect(name=args.query, bundle_id=args.bundle or "",
                              apple_id=args.apple_id or "", country=args.country)
    print(report.render())
    print(f"State: {sm.state.value}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    rep = analyze_ipa(args.ipa)
    if rep.error:
        print(f"ERROR: {rep.error}")
        return 1
    print(rep.render())
    if rep.encryption == "FAIRPLAY_ENCRYPTED":
        print("Package obtained, but executable is encrypted and cannot be "
              "analyzed/installed through this workflow.")
    return 0


def cmd_metadata(args: argparse.Namespace) -> int:
    res = lookup_by_apple_id(args.apple_id, args.country)
    if not res.found:
        print(f"NOT FOUND: {res.error}")
        return 1
    print(json.dumps(normalize_apple_metadata(res.raw), indent=2, ensure_ascii=False))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    key = args.key
    rec = DB.load(key)
    if rec is None:
        print(f"No local history for '{key}'. Run `ghostipa search` first, or import archive data.")
        return 1
    print(f"{rec.name} — {len(rec.historical_versions)} version(s), status {rec.status}")
    print(f"{'VERSION':<14}{'BUILD':<10}{'MIN IOS':<10}{'SHA256 (short)':<14}SOURCE")
    for v in rec.historical_versions:
        print(f"{v.version_string:<14}{v.build_number:<10}{v.minimum_ios:<10}"
              f"{v.sha256[:12]:<14}{v.source}")
    if rec.possible_reason:
        print(f"\nPossible reason [UNVERIFIED]: {rec.possible_reason}")
    if rec.documented_reason:
        print(f"Documented reason: {rec.documented_reason}")
    return 0


def cmd_device(args: argparse.Namespace) -> int:
    dev = detect_device()
    print(render_device(dev, minimum_ios=args.min_ios or "", ipa_arch=args.arch or ""))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    h256, h1, hmd5, size = hash_file(args.ipa)
    print(f"filename:\n{args.ipa}\n\nSHA256:\n{h256}\n\nSHA1:\n{h1}\n\nMD5:\n{hmd5}\n\nSize:\n{size}\n")
    if args.against:
        print(compare_ipas(args.ipa, args.against))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    report, _sm, record = detect(name=args.query, country=args.country)
    print(report.render())
    pkg = build_preservation_package(record, LOG)
    print(f"Preservation package: {pkg}")
    print(final_report(record, len(record.historical_versions), report.package,
                       report.installation, report.reason,
                       Confidence(report.confidence), [record.source]))
    return 0


def cmd_queries(args: argparse.Namespace) -> int:
    for q in build_search_queries(args.name, args.bundle or "", args.apple_id or ""):
        print(q)
    if args.archive_url:
        print("\nWeb Archive CDX:")
        print(web_archive_url(args.archive_url))
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    candidates: list[str] = []
    if args.cc:
        print("Common Crawl: listing captures…")
        candidates += extract_ids("\n".join(commoncrawl_urls(cap=args.cap)))
    if args.cdx:
        print("Wayback CDX: listing captures…")
        candidates += extract_ids("\n".join(wayback_urls(cap=args.cap)))
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            candidates += extract_ids(fh.read())
    if args.ids:
        candidates += [i.strip() for i in args.ids.split(",") if i.strip().isdigit()]
    candidates = list(dict.fromkeys(candidates))  # de-dup, order kept
    print(f"{len(candidates)} candidate ID(s). Verifying against live lookup…")
    stats = verify_ids(candidates, args.country, args.delay, DB, LOG)
    print(f"confirmed={stats['confirmed']} dead={stats['dead']} errors={stats['errors']}")
    return 0


def cmd_testflight(args: argparse.Namespace) -> int:
    import os
    if args.list:
        db_path = os.path.join("ghost_data", "testflight_compiled.json")
        try:
            with open(db_path, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as exc:
            print(f"No compiled DB ({exc}). Run the harvest compiler first.")
            return 1
        if args.list == "games":
            for v in d.get("verified_games", []):
                print(f"{v['name']} [{v['code']}]: {v['link']}\n  https://testflight.apple.com/join/{v['code']}")
        else:
            print(f"total={d['counts']['total']} resolves={d['counts']['resolves']} "
                  f"unknown={d['counts']['unknown']} (source: {d['source']})")
        return 0
    codes: list[str] = []
    if args.codes:
        codes += [c.strip() for c in args.codes.split(",") if c.strip()]
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            codes += extract_codes(fh.read())
    codes = list(dict.fromkeys(codes))
    print(f"{len(codes)} join code(s).")
    for c in codes:
        if args.check:
            r = check_code(c)
            print(f"{c}: {r['link']} — {r['detail']}\n  {r['url']}")
        else:
            print(f"{c}: {join_url(c)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ghostipa", description="Ghost IPA Installer — App Store preservation research")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Ghost-app detect by name/bundle/apple-id")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--bundle", default="")
    s.add_argument("--apple-id", default="")
    s.add_argument("--country", default="us")
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("inspect", help="Forensic IPA analysis")
    s.add_argument("ipa")
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("metadata", help="Fetch Apple metadata by ID")
    s.add_argument("apple_id")
    s.add_argument("--country", default="us")
    s.set_defaults(func=cmd_metadata)

    s = sub.add_parser("history", help="Show local version history")
    s.add_argument("key")
    s.set_defaults(func=cmd_history)

    s = sub.add_parser("device", help="Probe connected device + compatibility")
    s.add_argument("--min-ios", default="")
    s.add_argument("--arch", default="")
    s.set_defaults(func=cmd_device)

    s = sub.add_parser("verify", help="Hash IPA, optionally diff against a second copy")
    s.add_argument("ipa")
    s.add_argument("--against", default="")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("report", help="Full ghost report + preservation package")
    s.add_argument("query")
    s.add_argument("--country", default="us")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("queries", help="Structured archive search queries (§21/22)")
    s.add_argument("--name", default="")
    s.add_argument("--bundle", default="")
    s.add_argument("--apple-id", default="")
    s.add_argument("--archive-url", default="")
    s.set_defaults(func=cmd_queries)

    s = sub.add_parser("harvest", help="Discover unlisted apps via CC/CDX corpora + live verify")
    s.add_argument("--cc", action="store_true", help="pull App Store URLs from Common Crawl index")
    s.add_argument("--cdx", action="store_true", help="pull App Store URLs from Wayback CDX")
    s.add_argument("--file", default="", help="text file to regex-extract candidate IDs from")
    s.add_argument("--ids", default="", help="comma-separated adamIDs to verify directly")
    s.add_argument("--cap", type=int, default=200)
    s.add_argument("--country", default="us")
    s.add_argument("--delay", type=float, default=1.0, help="seconds between lookups (politeness)")
    s.set_defaults(func=cmd_harvest)

    s = sub.add_parser("testflight", help="Harvest + check TestFlight join links (link-level only)")
    s.add_argument("--codes", default="", help="comma-separated join codes")
    s.add_argument("--file", default="", help="text file to extract join codes from")
    s.add_argument("--check", action="store_true", help="resolve each link against Apple")
    s.add_argument("--list", default="", help="'all' (counts) or 'games' (verified games)")
    s.set_defaults(func=cmd_testflight)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
