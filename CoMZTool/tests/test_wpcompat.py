import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core import wpcompat as W


def test_profiles_isolated_no_secrets():
    p = W.describe_profile("legacy-wp8")
    assert p["profile"] == "CallOfMiniZombies-WP8"
    assert p["device_family"] == "Windows Phone"
    assert p["app_id"] == W.TESTB_APP_ID
    h = W.profile_headers("legacy-wp8")
    blob = " ".join(h.values()).lower()
    for secret in ("password", "token", "certificate", "attest",
                   "private key", "license", "entitlement"):
        assert secret not in blob, secret
    assert "CoM-WP8-VirtualDevice" in W.describe_profile("virtual-device")["name"]


def test_failure_taxonomy():
    assert W.classify_failure("device incompatible with request") == "INCOMPATIBLE DEVICE"
    assert W.classify_failure("404 not found") == "PACKAGE NOT OFFERED"
    assert W.classify_failure("windows phone retired") == "LEGACY PLATFORM"
    assert W.classify_failure("package family mismatch") == "PACKAGE FAMILY MISMATCH"
    assert W.classify_failure("version gone") == "HISTORICAL VERSION UNAVAILABLE"
    assert W.classify_failure("weird frobnicate") == "UNKNOWN RESPONSE"


def test_cross_match_classes():
    exact = W.cross_match({"filename": "CallOfMiniZombies_1.1.0.0_neutral.xap",
                           "label": "", "package_id": "", "product_id": "",
                           "content_id": "", "package_type": "xap",
                           "package_version": "1.1.0.0",
                           "platform_hint": "Windows Phone (XAP)"})
    assert exact["match_class"] == "EXACT HISTORICAL WP PACKAGE", exact
    assert exact["testb_eligible"] is True
    pc = W.cross_match({"filename": "CallOfMiniZombies_4.2.0.0_x64.appx",
                        "label": "", "package_id": "", "product_id": "",
                        "content_id": "", "package_type": "appx",
                        "package_version": "4.2.0.0",
                        "platform_hint": "Windows.Desktop x64"})
    assert pc["match_class"] == "CURRENT PC PACKAGE", pc
    assert pc["testb_eligible"] is False
    assert pc["testb_use"] == "CURRENT PC REFERENCE ONLY"
    wrong = W.cross_match({"filename": "OtherGame_1.1.0.0.xap",
                           "label": "Other", "package_id": "", "product_id": "",
                           "content_id": "", "package_type": "xap",
                           "package_version": "1.1.0.0", "platform_hint": ""})
    assert wrong["match_class"] == "UNRELATED PACKAGE", wrong


def test_final_report_states():
    rep = W.final_report({"state": "NOT FOUND", "candidate": None,
                          "store_page": "NOT FOUND", "dbox": "NOT FOUND",
                          "rg_adguard": "NOT FOUND"},
                         {"legacy_wp8": "UNKNOWN"}, {})
    assert rep["historical_package"] == "NOT FOUND"
    assert rep["historical_package_downloaded"] == "NO"
    assert rep["testb"] == "NOT AVAILABLE", rep
    assert len(W.failure_ladder()) == 9


def test_profile_run_offline_safe():
    # attempt_legacy_metadata hits live endpoints; it must degrade to
    # states, never raise on network failure.
    try:
        att = W.attempt_legacy_metadata("legacy-wp8", timeout=8)
    except Exception as e:
        raise AssertionError(f"probe must not raise: {e}")
    assert "steps" in att and "legacy_wp8" in att
    t = W.test_store_profiles(timeout=8)
    assert set(t["profiles"]) == {"pc", "wp8", "historical", "last_resort"}


if __name__ == "__main__":
    test_profiles_isolated_no_secrets()
    print("t1 ok")
    test_failure_taxonomy()
    print("t2 ok")
    test_cross_match_classes()
    print("t3 ok")
    test_final_report_states()
    print("t4 ok")
    test_profile_run_offline_safe()
    print("t5 ok")
    print("ALL WPCOMPAT TESTS PASSED")
