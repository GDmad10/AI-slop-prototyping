"""Apple metadata investigation module (§6). Uses public iTunes Search/Lookup API."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

LOOKUP_URL = "https://itunes.apple.com/lookup"
SEARCH_URL = "https://itunes.apple.com/search"


@dataclass
class MetadataResult:
    found: bool
    raw: dict = field(default_factory=dict)
    error: str = ""


def _get_json(url: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "GhostIPA/1.0 preservation-research"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public Apple API
        return json.loads(resp.read().decode("utf-8", "replace"))


def lookup_by_apple_id(apple_id: str, country: str = "us") -> MetadataResult:
    """Query Apple's public lookup endpoint for an app record (§6)."""
    qs = urllib.parse.urlencode({"id": apple_id, "country": country, "entity": "software"})
    try:
        data = _get_json(f"{LOOKUP_URL}?{qs}")
    except Exception as exc:  # network failure — report, don't crash (§26)
        return MetadataResult(found=False, error=friendly_error(exc))
    results = data.get("results", [])
    if not results:
        return MetadataResult(found=False, error="No record returned — delisted or never existed.")
    return MetadataResult(found=True, raw=results[0])


def search_by_term(term: str, country: str = "us", limit: int = 20) -> list[dict]:
    qs = urllib.parse.urlencode(
        {"term": term, "country": country, "entity": "software", "limit": limit}
    )
    try:
        data = _get_json(f"{SEARCH_URL}?{qs}")
    except Exception:
        return []
    return data.get("results", [])


def normalize_apple_metadata(raw: dict) -> dict:
    """Flatten Apple's lookup payload into the preservation schema (§6)."""
    return {
        "name": raw.get("trackName", ""),
        "developer": raw.get("artistName", ""),
        "publisher": raw.get("sellerName", ""),
        "bundle_id": raw.get("bundleId", ""),
        "apple_id": str(raw.get("trackId", "")),
        "current_version": raw.get("version", ""),
        "release_date": raw.get("releaseDate", ""),
        "last_update": raw.get("currentVersionReleaseDate", ""),
        "minimum_os": raw.get("minimumOsVersion", ""),
        "supported_devices": raw.get("supportedDevices", []),
        "category": raw.get("primaryGenreName", ""),
        "description": raw.get("description", ""),
        "icon": raw.get("artworkUrl512", raw.get("artworkUrl100", "")),
        "price": raw.get("price", 0),
        "currency": raw.get("currency", ""),
        "screenshot_urls": raw.get("screenshotUrls", []),
        "ipad_screenshots": raw.get("ipadScreenshotUrls", []),
        "advisories": raw.get("contentAdvisories", []),
        "languages": raw.get("languageCodesISO2A", []),
    }


def friendly_error(exc: Exception) -> str:
    """Human-readable errors (§26); technical detail stays in the log."""
    msg = str(exc)
    if "403" in msg:
        return ("Apple's server rejected this request. The application record may require "
                "authentication, may no longer be publicly accessible, or the request may not "
                "be supported through this endpoint.")
    if "404" in msg:
        return "Apple returned no record at this endpoint. The app may be delisted or the ID may be wrong."
    if "urlopen" in msg or "URLError" in type(exc).__name__:
        return f"Network request failed ({exc}). Check connectivity and retry."
    return f"Lookup failed: {exc}"
