"""Legacy Windows Phone compatibility-emulation fallback (TEST-B).

Situation: the historical Call of Mini: Zombies package may still exist
in Microsoft's package infrastructure while the current Store client
refuses to offer it — the requesting system is not a compatible
Windows Phone device.

What this module IS:
  - a controlled Store compatibility-emulation layer used ONLY by the
    downloader/resolver: virtual request profiles (device family,
    platform, arch, app ID) presented as package-resolution metadata
    where the Microsoft service accepts such metadata;
  - PC-side delivery fallback: historical package/content identifiers
    resolved through currently available Microsoft delivery endpoints
    as a transport mechanism (payload always verified — a PC package
    is never relabeled as the WP build);
  - metadata translation: legacy product -> identifiers -> current
    endpoint -> historical payload (payload never modified).

What this module NEVER does (hard rules, no exceptions):
  - no forging of Microsoft account credentials, auth tokens, signing
    certificates, package signatures, licensing entitlements, DRM
    credentials, device-attestation proofs, or Microsoft private keys;
  - no modification of the user's real Windows installation to
    impersonate a Windows Phone — emulation is isolated to the
    package-resolution process (HTTP request metadata only).

Resolver modes: NORMAL (current PC Store resolution), LEGACY-WP8
(CallOfMiniZombies-WP8 profile), LAST-RESORT (legacy metadata ->
current infra -> RG-Adguard -> Archive -> Wayback).

stdlib only.
"""
from __future__ import annotations

import os
import urllib.parse
import urllib.request

TESTB_GAME = "Call of Mini: Zombies"
TESTB_VERSION = "1.1.0.0"
TESTB_PLATFORM = "Windows Phone"
TESTB_APP_ID = "0febf8fa-35e8-4a87-8090-58b65220b3ed"

UA_BASE = "CoMZ-Preservation-Decryptor/1.0 (TEST-B; archival research)"

# ---------------------------------------------------------- failure taxonomy

FAILURE_REASONS = (
    "INCOMPATIBLE DEVICE",
    "PACKAGE NOT OFFERED",
    "LEGACY PLATFORM",
    "PACKAGE FAMILY MISMATCH",
    "HISTORICAL VERSION UNAVAILABLE",
    "UNKNOWN RESPONSE",
)

# ---------------------------------------------------------- device profiles

PROFILES = {
    "normal": {
        "name": "normal",
        "device_family": "Windows.Desktop",
        "target_platform": "Windows 10/11 (PC)",
        "architecture": "x64",
        "application": TESTB_GAME,
        "app_id": TESTB_APP_ID,
        "note": "current PC Store/package resolution, no emulation",
    },
    "legacy-wp8": {
        "name": "legacy-wp8",
        "profile": "CallOfMiniZombies-WP8",
        "device_family": "Windows Phone",
        "target_platform": "Windows Phone 8",
        "architecture": "ARM",
        "application": TESTB_GAME,
        "app_id": TESTB_APP_ID,
        "note": "virtual request profile for historical package metadata, "
                "isolated to package resolution",
    },
    "virtual-device": {
        "name": "CoM-WP8-VirtualDevice",
        "profile": "CoM-WP8-VirtualDevice",
        "device_family": "Windows Phone",
        "target_platform": "Windows Phone 8",
        "architecture": "ARM",
        "application": TESTB_GAME,
        "app_id": TESTB_APP_ID,
        "note": "research-only virtual profile for resolution-logic testing; "
                "not a modification of Windows device identity",
    },
}

MODES = ("normal", "legacy-wp8", "last-resort")

# Order the automatic fallback walks through.
FALLBACK_CHAIN = [
    "normal-pc-store",
    "legacy-wp8-profile",
    "pc-side-delivery",
    "rg-adguard",
    "internet-archive",
    "wayback",
]


def describe_profile(name: str = "legacy-wp8") -> dict:
    """Return the virtual request profile (metadata dict, nothing applied)."""
    if name not in PROFILES:
        raise ValueError(f"unknown profile {name!r} "
                         f"(normal / legacy-wp8 / virtual-device)")
    return dict(PROFILES[name])


def profile_headers(name: str = "legacy-wp8") -> dict:
    """HTTP request metadata for a profile — User-Agent/Client hints only.

    No credentials, tokens, certificates, or attestation material are ever
    emitted here. The service receives an honest archival-research client
    string plus non-authenticating device-family context parameters.
    """
    p = describe_profile(name)
    return {
        "User-Agent": (
            f"{UA_BASE} "
            f"(profile={p.get('profile', p['name'])}; "
            f"device-family={p['device_family']}; "
            f"platform={p['target_platform']}; arch={p['architecture']})"),
        "X-CoMZ-Device-Family": p["device_family"],
        "X-CoMZ-Target-Platform": p["target_platform"],
        "X-CoMZ-App-Id": p["app_id"],
    }


def classify_failure(context: str) -> str:
    """Map a failure context string onto the fixed failure taxonomy."""
    low = (context or "").lower()
    if any(k in low for k in ("incompatible", "not supported on", "device")):
        return "INCOMPATIBLE DEVICE"
    if any(k in low for k in ("not offered", "no download", "unavailable",
                              "404", "not found")):
        return "PACKAGE NOT OFFERED"
    if any(k in low for k in ("legacy", "windows phone", "wp8", "retired",
                              "end of support", "end-of-support")):
        return "LEGACY PLATFORM"
    if "family" in low or "mismatch" in low:
        return "PACKAGE FAMILY MISMATCH"
    if "version" in low:
        return "HISTORICAL VERSION UNAVAILABLE"
    return "UNKNOWN RESPONSE"


# ---------------------------------------------------------- cross-matching

CLASSES = (
    "EXACT HISTORICAL WP PACKAGE",
    "HISTORICAL MOBILE PACKAGE",
    "CURRENT PC PACKAGE",
    "WRONG PLATFORM",
    "WRONG VERSION",
    "UNRELATED PACKAGE",
)


def cross_match(cand: dict) -> dict:
    """Classify one candidate against the historical WP target.

    Only EXACT HISTORICAL WP PACKAGE may become TEST-B. A current PC
    package is CURRENT PC PACKAGE / CURRENT PC REFERENCE ONLY — never a
    TEST-B pass, never silently downgraded.
    """
    blob = (f"{cand.get('filename','')} {cand.get('label','')} "
            f"{cand.get('package_id','')} {cand.get('product_id','')} "
            f"{cand.get('content_id','')}").lower()
    game_ok = any(t in blob for t in
                  ("call of mini", "callofmini", "mini zombies",
                   "minizombies", "comz"))
    ver = cand.get("package_version") or (
        cand.get("package_record") or {}).get("version", "")
    plat = ((cand.get("package_record") or {}).get("platform", "")
            + " " + cand.get("platform_hint", "")).lower()
    ptype = (cand.get("package_type") or "").lower()
    is_wp = ("windows phone" in plat or ptype == "xap")
    is_pc = any(k in plat for k in
                ("windows.desktop", "windows 10", "windows 11", "win32"))
    if not game_ok and not cand.get("package_record"):
        cand["match_class"] = "UNRELATED PACKAGE"
    elif ver and ver != TESTB_VERSION:
        # modern PC generation of the same title, e.g. 4.x
        cand["match_class"] = ("CURRENT PC PACKAGE" if (is_pc or not is_wp)
                               else "WRONG VERSION")
    elif is_wp and (not ver or ver == TESTB_VERSION):
        cand["match_class"] = ("EXACT HISTORICAL WP PACKAGE"
                               if ver == TESTB_VERSION
                               else "HISTORICAL MOBILE PACKAGE")
    elif is_pc:
        cand["match_class"] = "CURRENT PC PACKAGE"
    else:
        cand["match_class"] = ("WRONG PLATFORM" if plat
                               else "HISTORICAL MOBILE PACKAGE")
    cand["testb_eligible"] = (cand["match_class"] == "EXACT HISTORICAL WP PACKAGE")
    if cand["match_class"] == "CURRENT PC PACKAGE":
        cand["testb_use"] = "CURRENT PC REFERENCE ONLY"
    return cand


# ---------------------------------------------------------- resolution attempts

def attempt_legacy_metadata(profile: str = "legacy-wp8",
                            timeout: int = 30) -> dict:
    """Attempt historical package-metadata resolution under a WP8 profile.

    Probes the documented public product endpoints with the virtual
    profile's request metadata and captures whatever package metadata or
    URLs the service exposes. Authentication-gated or absent data is
    reported as such — never worked around.
    """
    from . import dbox as _dbox
    from . import rg_adguard as _rg
    headers = profile_headers(profile)
    findings: dict = {"profile": profile, "request_metadata": headers,
                      "steps": []}

    def get(url):
        req = urllib.request.Request(url, headers={
            "User-Agent": headers["User-Agent"]})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(4096)

    # 1. DBOX product reference (public page, correlation source)
    try:
        pres = _dbox.resolve_product(timeout=timeout)
        findings["steps"].append({"layer": "dbox-product",
                                  "state": pres.get("state"),
                                  "note": pres.get("note", "")})
        findings["dbox"] = pres.get("state")
    except Exception as e:
        findings["steps"].append({"layer": "dbox-product",
                                  "state": "NOT FOUND",
                                  "note": f"{type(e).__name__}: {e}"})
        findings["dbox"] = "NOT FOUND"
    # 2. RG-Adguard resolver with legacy ID (public resolver)
    try:
        res = _rg.resolve_store_id(TESTB_APP_ID, timeout=timeout)
        findings["steps"].append(
            {"layer": "rg-adguard",
             "state": res.get("state"),
             "note": res.get("raw_note", ""),
             "links": len(res.get("links", []))})
        findings["rg_adguard"] = res.get("state")
        findings["rg_links"] = res.get("links", [])[:50]
    except Exception as e:
        findings["steps"].append({"layer": "rg-adguard",
                                  "state": "NOT FOUND",
                                  "note": f"{type(e).__name__}: {e}"})
        findings["rg_adguard"] = "NOT FOUND"
    # 3. Legacy profile acceptance probe: no privileged endpoint exists
    # publicly for WP8 package delivery; record the boundary honestly.
    findings["steps"].append({
        "layer": "legacy-wp8-profile",
        "state": "UNKNOWN",
        "note": "no public Microsoft endpoint accepts virtual WP8 device "
                "metadata for package delivery; profile metadata is sent "
                "only to the public layers above. No credentials, tokens, "
                "or attestation were presented."})
    findings["legacy_wp8"] = "UNKNOWN"
    return findings


def pc_side_delivery_identifiers() -> dict:
    """Metadata-translation layer: legacy product -> identifiers.

    Builds the identifier set the current delivery infrastructure can be
    asked about (product/app/package/content IDs + version/arch/family)
    without modifying any payload.
    """
    return {
        "legacy_product": TESTB_GAME,
        "historical_app_id": TESTB_APP_ID,
        "target_version": TESTB_VERSION,
        "target_platform": TESTB_PLATFORM,
        "device_family": "Windows Phone",
        "architectures": ["ARM", "neutral"],
        "package_types": ["xap"],
        "note": "identifiers for current-endpoint lookup; transport only, "
                "payload verified post-download, never relabeled",
    }


# ---------------------------------------------------------- profile testing

PROFILE_TEST_FIELDS = (
    "request_accepted",
    "product_found",
    "package_metadata_found",
    "package_url_found",
    "package_downloaded",
    "package_identity_matched",
    "version_matched",
    "platform_matched",
)


def test_store_profiles(timeout: int = 30) -> dict:
    """Run PC / WP8 / historical / last-resort profile checks.

    Returns per-profile records over PROFILE_TEST_FIELDS. Nothing is
    downloaded here beyond metadata probes; download flags stay False
    until the real acquisition path runs.
    """
    out: dict = {"profiles": {}}
    # PC profile: current-platform request, honest client string
    pc = {f: False for f in PROFILE_TEST_FIELDS}
    pc["request_accepted"] = True  # local resolution path runs
    out["profiles"]["pc"] = {"profile": describe_profile("normal"), **pc}
    # WP8 virtual profile: metadata probe
    wp = {f: False for f in PROFILE_TEST_FIELDS}
    try:
        att = attempt_legacy_metadata("legacy-wp8", timeout=timeout)
        wp["request_accepted"] = True
        wp["product_found"] = att.get("dbox") not in (None, "NOT FOUND", False)
        wp["package_metadata_found"] = att.get("rg_adguard") == "DOWNLOAD LINK FOUND"
        wp["package_url_found"] = bool(att.get("rg_links"))
        out["profiles"]["wp8"] = {"profile": describe_profile("legacy-wp8"),
                                  **wp, "attempt": att}
    except Exception as e:
        out["profiles"]["wp8"] = {"profile": describe_profile("legacy-wp8"),
                                  **wp, "error": str(e)}
    # historical package profile: same probe, target-scoped verdict
    hist = dict(out["profiles"]["wp8"])
    hist["profile"] = {"historical_package": f"{TESTB_GAME} {TESTB_VERSION}",
                       "app_id": TESTB_APP_ID, **describe_profile("legacy-wp8")}
    out["profiles"]["historical"] = hist
    # last-resort: aggregate of the chain (nothing further probed here)
    out["profiles"]["last_resort"] = {
        "profile": {"mode": "last-resort", "chain": FALLBACK_CHAIN},
        **{f: False for f in PROFILE_TEST_FIELDS},
        "note": "runs legacy metadata -> current infra -> RG-Adguard -> "
                "Archive -> Wayback inside retrieve-test-b --profile last-resort",
    }
    return out


# ---------------------------------------------------------- final report

def final_report(acquisition: dict | None = None,
                 profile_tests: dict | None = None,
                 runtime: dict | None = None) -> dict:
    """Build the TEST-B final report (FOUND/NOT FOUND + PASS/FAIL states)."""
    acq = acquisition or {}
    cand = acq.get("candidate") or {}
    state = acq.get("state", "NOT FOUND")
    verified = state == "READY FOR DECRYPTION"
    rt = runtime or {}
    report = {
        "microsoft_store_page": acq.get("store_page", "NOT FOUND"),
        "dbox_reference": acq.get("dbox", "NOT FOUND"),
        "rg_adguard_resolution": acq.get("rg_adguard", "NOT FOUND"),
        "legacy_wp8_profile": (profile_tests or {}).get("legacy_wp8", "UNKNOWN"),
        "historical_package": "FOUND" if cand else "NOT FOUND",
        "historical_package_downloaded": "YES" if cand.get("staged") else "NO",
        "historical_package_verified": "YES" if verified else "NO",
        "runtime_recovery": rt.get("runtime_recovery", "NOT AVAILABLE"),
        "offline_decryption": rt.get("offline_decryption", "NOT AVAILABLE"),
        "plaintext_validation": rt.get("plaintext_validation", "FAIL"),
        "unity_recovery": rt.get("unity_recovery", "FAIL"),
        "testb": "PASS" if (verified and rt.get("plaintext_validation") == "PASS"
                            and rt.get("unity_recovery") == "PASS") else (
            "FAIL" if verified else "NOT AVAILABLE"),
    }
    return report


def failure_ladder() -> list[str]:
    """Ordered distinction list for failure reporting (existence != access)."""
    return ["store page exists", "product exists", "metadata exists",
            "historical package exists", "historical package URL exists",
            "historical package downloadable", "historical package downloaded",
            "historical package verified", "decryption possible"]
