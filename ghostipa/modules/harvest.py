"""GhostHarvest — unlisted-app discovery (§21/22 extension).

How unlisted apps are found in practice (no brute force — the adamID space is
billions wide and Apple rate-limits lookup):
  1. Common Crawl URL index: query itunes.apple.com/*/app/* → historical URLs with IDs.
  2. Wayback CDX: same host pattern → archived App Store pages with IDs.
  3. Any pasted corpus (forum dumps, spreadsheets): regex-extract candidate IDs.
Then every candidate is verified with a live lookup — only genuine records enter
the DB. Politeness: 1s between lookups, small page caps, resumable ID cache.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from ghostipa.core.database import AppRecord, ResearchDB
from ghostipa.core.research_log import ResearchLog
from ghostipa.modules.metadata import lookup_by_apple_id, normalize_apple_metadata

ID_PATTERNS = [
    re.compile(r"/id(\d{6,12})"),          # .../app/foo/id123456789
    re.compile(r"[?&]id=(\d{6,12})"),      # ...?id=123456789
    re.compile(r"(?:^|[\s\"'(\[])id=(\d{6,12})"),  # pasted dumps: "id=123456789"
    re.compile(r"\bapple-id[:=]\s*(\d{6,12})", re.I),
]

CC_INDEX = "https://index.commoncrawl.org/collinfo.json"
CDX_URL = "https://web.archive.org/cdx/search/cdx"


def extract_ids(text: str) -> list[str]:
    found: list[str] = []
    for pat in ID_PATTERNS:
        for m in pat.findall(text):
            if m not in found:
                found.append(m)
    return found


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "GhostIPA/1.0 preservation-research"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public indexes
        return json.loads(resp.read().decode("utf-8", "replace"))


def _get_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "GhostIPA/1.0 preservation-research"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public indexes
        return resp.read().decode("utf-8", "replace")


def commoncrawl_urls(match_host: str = "itunes.apple.com", cap: int = 200) -> list[str]:
    """List captures of App Store URLs from the newest Common Crawl index."""
    try:
        infos = _get_json(CC_INDEX)
        newest = infos[0]["id"] if isinstance(infos, list) else infos["id"]
    except Exception:
        return []
    q = urllib.parse.urlencode({
        "url": f"{match_host}/*/app/*", "output": "json",
        "filter": "status:200", "limit": cap,
    })
    try:
        raw = _get_text(f"https://index.commoncrawl.org/{newest}-index?{q}")
    except Exception:
        return []
    urls = []
    for line in raw.splitlines():
        try:
            urls.append(json.loads(line).get("url", ""))
        except Exception:
            continue
    return [u for u in urls if u]


def wayback_urls(prefix: str = "itunes.apple.com", cap: int = 200) -> list[str]:
    """Archived App Store URLs via Wayback CDX."""
    q = urllib.parse.urlencode({
        "url": f"{prefix}/*", "output": "text", "fl": "original",
        "filter": "urlkey:.*app.*", "collapse": "urlkey", "limit": cap,
    })
    try:
        raw = _get_text(f"{CDX_URL}?{q}")
    except Exception:
        return []
    return [l.strip() for l in raw.splitlines() if "/app/" in l]


def verify_ids(ids: list[str], country: str = "us", delay: float = 1.0,
               db: ResearchDB | None = None, log: ResearchLog | None = None) -> dict:
    """Live-lookup every candidate; genuine records enter the DB. Returns stats."""
    db = db or ResearchDB()
    log = log or ResearchLog()
    stats = {"candidates": len(ids), "confirmed": 0, "dead": 0, "errors": 0}
    for adam in ids:
        try:
            res = lookup_by_apple_id(adam, country)
        except Exception as exc:
            stats["errors"] += 1
            log.log("HARVEST", "Apple metadata", adam, error=str(exc))
            time.sleep(delay)
            continue
        if res.found:
            meta = normalize_apple_metadata(res.raw)
            rec = AppRecord(name=meta["name"], bundle_id=meta["bundle_id"],
                            apple_id=meta["apple_id"], developer=meta["developer"],
                            status="HARVESTED_UNLISTED", metadata_found=True,
                            source="GhostHarvest (CC/CDX corpus + live lookup)",
                            extra=meta)
            db.save(rec)
            stats["confirmed"] += 1
            log.log("HARVEST", "Apple metadata", f"{rec.name} ({adam})", version=meta["current_version"])
        else:
            stats["dead"] += 1
            log.log("HARVEST", "Apple metadata", adam, error=res.error)
        time.sleep(delay)
    return stats
