"""Build-to-build comparison. Header/entropy/hash/file-list diffs only."""
from __future__ import annotations

from .analyze import analyze_file


def compare_files(path_a: str, path_b: str) -> dict:
    a = analyze_file(path_a)
    b = analyze_file(path_b)
    ia, ib = a["identification"], b["identification"]
    diffs = {
        "file_a": {"filename": ia["filename"], "sha256": ia["sha256"], "size": ia["size"]},
        "file_b": {"filename": ib["filename"], "sha256": ib["sha256"], "size": ib["size"]},
        "same_sha256": ia["sha256"] == ib["sha256"],
        "size_delta": ib["size"] - ia["size"],
        "magic_a": ia["magic_hex"],
        "magic_b": ib["magic_hex"],
        "magic_equal": ia["magic_hex"] == ib["magic_hex"],
        "format_a": ia["detected_format"],
        "format_b": ib["detected_format"],
        "signals_a": ia["signal_hits"],
        "signals_b": ib["signal_hits"],
        "entropy_a": a["full_entropy_head"],
        "entropy_b": b["full_entropy_head"],
        "zip_a": {"readable": a["zip_inventory"]["readable"],
                  "count": a["zip_inventory"].get("count")},
        "zip_b": {"readable": b["zip_inventory"]["readable"],
                  "count": b["zip_inventory"].get("count")},
        "guids_only_in_a": sorted(set(a["observables"]["guids"]) - set(b["observables"]["guids"])),
        "guids_only_in_b": sorted(set(b["observables"]["guids"]) - set(a["observables"]["guids"])),
        "strings_only_in_a": sorted(set(a["observables"]["interesting_strings"]) -
                                    set(b["observables"]["interesting_strings"]))[:40],
        "strings_only_in_b": sorted(set(b["observables"]["interesting_strings"]) -
                                    set(a["observables"]["interesting_strings"]))[:40],
    }
    # recovered filename sets (plaintext zips only)
    if a["zip_inventory"]["readable"] and b["zip_inventory"]["readable"]:
        sa = {e["name"] for e in a["zip_inventory"]["entries"]}
        sb = {e["name"] for e in b["zip_inventory"]["entries"]}
        diffs["files_only_in_a"] = sorted(sa - sb)[:100]
        diffs["files_only_in_b"] = sorted(sb - sa)[:100]
        diffs["common_files"] = len(sa & sb)
    else:
        diffs["files_only_in_a"] = []
        diffs["files_only_in_b"] = []
        diffs["note"] = "inner file lists comparable only when both samples are plaintext containers"
    diffs["protection_changed"] = (
        a["zip_inventory"]["readable"] != b["zip_inventory"]["readable"]
        or abs(a["full_entropy_head"] - b["full_entropy_head"]) > 1.0
    )
    return diffs
