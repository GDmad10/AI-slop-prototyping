"""Research helpers: archive queries (§16), structured + multilingual search (§21, §22)."""
from __future__ import annotations

import urllib.parse
import webbrowser
from dataclasses import dataclass

ARCHIVE_CDX = "https://web.archive.org/cdx/search/cdx"

# §21 structured query templates.
QUERY_TEMPLATES = [
    '"{name}" IPA', '"{name}" iOS', '"{name}" App Store', '"{name}" bundle identifier',
    '"{name}" version', '"{name}" removed', '"{name}" delisted', '"{name}" discontinued',
    '"{name}" developer', '"{name}" IPA archive', '"{bundle}"', '"{apple}"',
]

# §22 languages for regional-community searches.
LANGUAGES = ["English", "Russian", "Japanese", "Chinese", "Korean", "German", "French", "Spanish"]


@dataclass
class Evidence:
    source: str
    date: str
    url: str
    confidence: str
    evidence_type: str


def build_search_queries(name: str = "", bundle: str = "", apple_id: str = "") -> list[str]:
    out: list[str] = []
    for tpl in QUERY_TEMPLATES:
        try:
            q = tpl.format(name=name, bundle=bundle, apple=apple_id)
        except KeyError:
            continue
        if '""' in q or q.strip('" ') == "":
            continue
        out.append(q)
    return out


def web_archive_url(appstore_url: str) -> str:
    """CDX lookup URL for a historical App Store page (§16)."""
    qs = urllib.parse.urlencode(
        {"url": appstore_url, "output": "json", "filter": "statuscode:200",
         "collapse": "digest", "limit": 50}
    )
    return f"{ARCHIVE_CDX}?{qs}"


def open_research_queries(name: str = "", bundle: str = "", apple_id: str = "",
                          open_browser: bool = False) -> list[str]:
    """Return engine URLs; optionally open them. Never scrapes, just structures (§21)."""
    queries = build_search_queries(name, bundle, apple_id)
    urls = [f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}" for q in queries]
    if open_browser:
        for u in urls[:5]:
            webbrowser.open(u)
    return urls
