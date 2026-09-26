"""Local JSON research database — metadata + version store (§6, §7)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class AppVersion:
    version_string: str
    build_number: str = ""
    release_date: str = ""
    minimum_ios: str = ""
    max_known_ios: str = ""
    architecture: str = ""
    encrypted: str = "UNKNOWN"          # UNENCRYPTED | FAIRPLAY | DRM | UNKNOWN
    file_size: int = 0
    sha256: str = ""
    ipa_filename: str = ""
    source: str = "UNKNOWN SOURCE"
    availability: str = "UNKNOWN"       # AVAILABLE | UNAVAILABLE | UNKNOWN
    install_status: str = "UNKNOWN"     # INSTALLABLE | NOT_INSTALLABLE | UNKNOWN


@dataclass
class AppRecord:
    name: str
    bundle_id: str = ""
    apple_id: str = ""
    developer: str = ""
    status: str = "UNKNOWN"
    metadata_found: bool = False
    binary_found: bool = False
    historical_versions: list[AppVersion] = field(default_factory=list)
    source: str = "Apple metadata"
    checked_at: str = ""
    documented_reason: str = ""
    possible_reason: str = ""           # unverified — always labelled (§14)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AppRecord":
        versions = [AppVersion(**v) for v in d.get("historical_versions", [])]
        d = dict(d)
        d["historical_versions"] = versions
        return cls(**d)


class ResearchDB:
    """JSON-file backed store: one file per app keyed by apple_id or bundle_id."""

    def __init__(self, root: str = "ghost_data") -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _key(self, record: AppRecord) -> str:
        return record.apple_id or record.bundle_id or record.name.replace(" ", "_")

    def save(self, record: AppRecord) -> str:
        record.checked_at = datetime.now(timezone.utc).isoformat()
        path = os.path.join(self.root, f"{self._key(record)}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record.to_dict(), fh, indent=2, ensure_ascii=False)
        return path

    def load(self, key: str) -> AppRecord | None:
        path = os.path.join(self.root, f"{key}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return AppRecord.from_dict(json.load(fh))

    def list_keys(self) -> list[str]:
        return [f[:-5] for f in os.listdir(self.root) if f.endswith(".json")]

    def add_version(self, key: str, version: AppVersion) -> bool:
        rec = self.load(key)
        if rec is None:
            return False
        # Duplicate detection (§20): same sha256 => exact duplicate, skip.
        for v in rec.historical_versions:
            if version.sha256 and v.sha256 == version.sha256:
                return False
        rec.historical_versions.append(version)
        self.save(rec)
        return True
