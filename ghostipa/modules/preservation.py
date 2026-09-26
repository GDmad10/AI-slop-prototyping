"""Preservation package (§18), hashing (§19), dup detection (§20), final report (§29)."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

from ghostipa.core.confidence import Confidence
from ghostipa.core.database import AppRecord
from ghostipa.core.research_log import ResearchLog


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_preservation_package(record: AppRecord, log: ResearchLog,
                               out_root: str = "GhostApp") -> str:
    """Assemble the §18 directory tree. Preservation ≠ installation (§28)."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in record.name) or "unknown"
    dest = os.path.join(out_root, safe)
    for sub in ("screenshots", "metadata", "ipa", "reports"):
        os.makedirs(os.path.join(dest, sub), exist_ok=True)

    with open(os.path.join(dest, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(record.to_dict(), fh, indent=2, ensure_ascii=False)
    with open(os.path.join(dest, "versions.json"), "w", encoding="utf-8") as fh:
        json.dump([v.__dict__ for v in record.historical_versions], fh, indent=2, ensure_ascii=False)
    with open(os.path.join(dest, "appstore-history.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "documented_reason": record.documented_reason,
            "possible_reason": (record.possible_reason + " [UNVERIFIED]" if record.possible_reason else ""),
            "status": record.status,
        }, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(dest, "sources.json"), "w", encoding="utf-8") as fh:
        json.dump({"primary_source": record.source, "checked_at": record.checked_at}, fh, indent=2)
    with open(os.path.join(dest, "reports", "research-log.json"), "w", encoding="utf-8") as fh:
        fh.write(log.to_json())
    with open(os.path.join(dest, "reports", "research-log.txt"), "w", encoding="utf-8") as fh:
        fh.write(log.render_text())

    hashes_path = os.path.join(dest, "hashes.txt")
    with open(hashes_path, "w", encoding="utf-8") as fh:
        for v in record.historical_versions:
            fh.write(f"filename:\n{v.ipa_filename}\n\nSHA256:\n{v.sha256}\n\n"
                     f"Size:\n{v.file_size}\n\nSource:\n{v.source}\n\nAcquired:\n{_utcnow()}\n\n---\n")

    readme = (
        f"Ghost IPA preservation package — {record.name}\n"
        f"Bundle ID: {record.bundle_id}\nApple ID: {record.apple_id}\n"
        f"Status: {record.status}\nSource of each artifact:\n"
        f"- metadata.json ......... {record.source}\n"
        f"- versions.json ......... local version DB (§7)\n"
        f"- appstore-history.json . documented vs possible removal reasons (§14)\n"
        f"- sources.json .......... provenance index\n"
        f"- hashes.txt ............ SHA-256 manifest, originals unmodified (§19)\n"
        f"- ipa/ .................. user-provided or officially obtained IPAs only (§5)\n"
        f"Preservation is separate from installation (§28): this package is complete\n"
        f"even when installation is impossible.\n"
    )
    with open(os.path.join(dest, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(readme)
    return dest


def final_report(record: AppRecord, versions_found: int, ipa_state: str,
                 install_state: str, reason: str,
                 confidence: Confidence, sources: list[str]) -> str:
    """Generate the §29 report block."""
    first = min((v.release_date for v in record.historical_versions if v.release_date), default="?")
    last = max((v.release_date for v in record.historical_versions if v.release_date), default="?")
    src = "\n".join(f"- {s}" for s in sources) or "- (none recorded)"
    return (
        "==================================================\n"
        "GHOST IPA REPORT\n"
        "================\n\n"
        f"Application: {record.name}\n"
        f"Developer: {record.developer}\n"
        f"Bundle ID: {record.bundle_id}\n"
        f"Apple ID: {record.apple_id}\n\n"
        f"First known release: {first}\n"
        f"Last known release: {last}\n\n"
        f"PUBLIC AVAILABILITY:\n{'Yes' if record.status == 'PUBLIC_LISTED' else 'No'}\n\n"
        f"HISTORICAL RECORD:\n{'Yes' if record.metadata_found else 'No'}\n\n"
        "PURCHASE HISTORY:\nUnknown (requires user-authorized account check)\n\n"
        f"HISTORICAL VERSIONS:\n{versions_found} identified\n\n"
        f"IPA:\n{ipa_state}\n\n"
        f"INSTALLATION:\n{install_state}\n\n"
        f"REASON:\n{reason}\n\n"
        f"CONFIDENCE:\n{confidence.value}\n\n"
        f"SOURCES:\n{src}\n\n"
        "==================================================\n"
    )


def stage_ipa_copy(ipa_path: str, dest_dir: str) -> str:
    """Copy (never move/modify) a user-provided IPA into the package (§19)."""
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(ipa_path))
    shutil.copy2(ipa_path, dest)
    return dest
