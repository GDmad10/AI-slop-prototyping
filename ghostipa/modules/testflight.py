"""TestFlight beta tracking — companion to GhostHarvest.

Scope truth: TestFlight lives on a separate backend (App Store Connect beta
groups), NOT App Store records. There is no public beta-metadata lookup, and a
join link can only be redeemed on-device inside the TestFlight app with the
user's own Apple ID. Expired/removed betas do not reinstall — Apple deletes
the build, receipt or not.

What this module CAN do (and does):
  1. Harvest public join codes from text/URLs: testflight.apple.com/join/<CODE>.
  2. Check whether a join link still resolves (HTTP level, no auth): Apple's
     join pages return success for live/known codes and an error page for dead
     ones. "Resolves" means the beta slot exists, NOT that you can join —
     slots fill up and developers close testing.
  3. Store codes + link status in the research DB for the device-side flow:
     tap link on iPhone/iPad → TestFlight app → Apple's own accept control.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

CODE_RE = re.compile(r"testflight\.apple\.com/join/([A-Za-z0-9]{4,16})", re.I)
BARE_RE = re.compile(r"(?:^|[\s\"'(\[])(?:TF|tf|beta)[ _:-]+([A-Za-z0-9]{4,16})")


def extract_codes(text: str) -> list[str]:
    found: list[str] = []
    for m in CODE_RE.findall(text) + BARE_RE.findall(text):
        if m not in found:
            found.append(m)
    return found


def join_url(code: str) -> str:
    return f"https://testflight.apple.com/join/{code}"


def check_code(code: str, timeout: int = 20) -> dict:
    """HEAD/GET the join page. Returns status verdict — link-level only."""
    url = join_url(code)
    req = urllib.request.Request(url, headers={"User-Agent": "GhostIPA/1.0 preservation-research"},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — public join page
            body = resp.read(65536).decode("utf-8", "replace")
            final = resp.geturl()
    except Exception as exc:
        msg = str(exc)
        if "404" in msg:
            return {"code": code, "url": url, "link": "DEAD", "detail": "Apple: no such beta."}
        return {"code": code, "url": url, "link": "UNKNOWN", "detail": f"request failed: {exc}"}
    lowered = body.lower()
    if "couldn't be found" in lowered or "not available" in lowered or "could not be found" in lowered:
        return {"code": code, "url": final, "link": "DEAD", "detail": "Apple: beta unavailable."}
    if "to join the" in lowered or "join the beta" in lowered or "testflight" in lowered:
        return {"code": code, "url": final, "link": "RESOLVES",
                "detail": "Join page live. Open on-device in TestFlight; slot/eligibility decided by Apple."}
    return {"code": code, "url": final, "link": "UNKNOWN", "detail": "Unrecognized page shape."}
