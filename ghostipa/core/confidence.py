"""Confidence + source taxonomy (§17, §5)."""
from __future__ import annotations

from enum import Enum


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class Verdict(str, Enum):
    FOUND = "FOUND"
    CONFIRMED = "CONFIRMED"
    LIKELY = "LIKELY"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"
    NOT_FOUND = "NOT FOUND"


class SourceKind(str, Enum):
    OFFICIAL_APPLE = "OFFICIAL APPLE SOURCE"
    USER_BACKUP = "USER-OWNED BACKUP"
    THIRD_PARTY = "THIRD-PARTY ARCHIVE"
    UNKNOWN = "UNKNOWN SOURCE"


def confidence_for_source(kind: SourceKind, corroborated: bool = False) -> Confidence:
    """Map evidence (§17) to a confidence level. Never upgrades LOW→fact."""
    if kind == SourceKind.OFFICIAL_APPLE:
        return Confidence.HIGH
    if kind == SourceKind.USER_BACKUP:
        return Confidence.HIGH
    if kind == SourceKind.THIRD_PARTY:
        return Confidence.MEDIUM if corroborated else Confidence.LOW
    return Confidence.UNKNOWN
