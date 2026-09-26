"""Smoke tests — offline. Run: python -m pytest tests/ -q (or python -m unittest)."""
import io
import os
import plistlib
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ghostipa.core.confidence import Confidence, SourceKind, confidence_for_source
from ghostipa.core.database import AppRecord, AppVersion, ResearchDB
from ghostipa.core.research_log import ResearchLog
from ghostipa.core.state_machine import AppState, StateMachine
from ghostipa.modules.device import check_compatibility, DeviceInfo
from ghostipa.modules.ipa_analysis import analyze_ipa, compare_ipas, hash_file
from ghostipa.modules.preservation import build_preservation_package, final_report
from ghostipa.modules.research import build_search_queries


def make_fake_ipa(path, bundle="com.example.app", version="1.2.3", min_ios="9.0"):
    info = {
        "CFBundleIdentifier": bundle,
        "CFBundleDisplayName": "Example App",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": "42",
        "MinimumOSVersion": min_ios,
        "CFBundleExecutable": "ExampleApp",
        "UIDeviceFamily": [1, 2],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Payload/Example.app/Info.plist", plistlib.dumps(info))
        # Minimal 64-bit Mach-O header with LC_ENCRYPTION_INFO_64 cryptid=0.
        import struct
        hdr = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 0, 1, 0, 0, 0)
        hdr += struct.pack("<IIIQ", 0x2C, 24, 0, 0)
        zf.writestr("Payload/Example.app/ExampleApp", hdr + b"\x00" * 64)
        zf.writestr("Payload/Example.app/_CodeSignature/CodeResources", b"sig")
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())


def test_state_machine():
    sm = StateMachine()
    assert sm.state == AppState.UNKNOWN
    assert sm.advance(AppState.APP_RECORD_FOUND)
    assert sm.advance(AppState.DELISTED)
    assert sm.advance(AppState.PURCHASE_RECORD_FOUND)
    assert sm.advance(AppState.DISTRIBUTION_CHECK)
    assert sm.advance(AppState.PACKAGE_UNAVAILABLE)
    assert not sm.advance(AppState.INSTALLABLE)  # illegal jump rejected
    sm.set_reasons(documented="dev removed", possible="policy (UNVERIFIED)")
    print("state_machine OK")


def test_ipa_analysis_and_hash(tmp=None):
    tmp = tmp or tempfile.mkdtemp()
    p = os.path.join(tmp, "app.ipa")
    make_fake_ipa(p)
    rep = analyze_ipa(p)
    assert rep.bundle_id == "com.example.app", rep
    assert rep.version == "1.2.3"
    assert rep.minimum_ios == "9.0"
    assert rep.encryption == "UNENCRYPTED", rep.encryption
    assert rep.signature_present
    assert len(rep.sha256) == 64
    p2 = os.path.join(tmp, "app2.ipa")
    make_fake_ipa(p2, version="1.2.4")
    assert compare_ipas(p, p) == "EXACT DUPLICATE"
    assert compare_ipas(p, p2) == "DIFFERENT VERSION"
    print("ipa_analysis OK")
    return tmp


def test_db_and_preservation(tmp=None):
    tmp = tmp or tempfile.mkdtemp()
    db = ResearchDB(root=os.path.join(tmp, "db"))
    rec = AppRecord(name="Example App", bundle_id="com.example.app",
                    apple_id="123456789", status="DELISTED",
                    metadata_found=True, possible_reason="32-bit cull (UNVERIFIED)")
    db.save(rec)
    assert db.load("123456789").name == "Example App"
    v = AppVersion(version_string="1.2.3", build_number="42", minimum_ios="9.0",
                   sha256="abc", ipa_filename="a.ipa", source="USER-OWNED BACKUP")
    assert db.add_version("123456789", v)
    assert not db.add_version("123456789", v)  # dup sha rejected
    log = ResearchLog()
    log.log("SEARCH", "Apple metadata", "Example App", version="1.2.3")
    dest = build_preservation_package(db.load("123456789"), log, out_root=os.path.join(tmp, "GhostApp"))
    for f in ("metadata.json", "versions.json", "sources.json", "hashes.txt", "README.txt"):
        assert os.path.exists(os.path.join(dest, f)), f
    print("db+preservation OK")


def test_device_compat():
    dev = DeviceInfo(model="iPhone SE", ios_version="15.7", architecture="arm64", connection="usb")
    ok, _ = check_compatibility("9.0", "arm64", dev)
    assert ok
    ok2, _ = check_compatibility("16.0", "arm64", dev)
    assert not ok2
    print("device OK")


def test_confidence_and_queries():
    assert confidence_for_source(SourceKind.OFFICIAL_APPLE) == Confidence.HIGH
    assert confidence_for_source(SourceKind.THIRD_PARTY) == Confidence.LOW
    assert confidence_for_source(SourceKind.THIRD_PARTY, True) == Confidence.MEDIUM
    qs = build_search_queries("Shadow Fight", "com.example.game", "123")
    assert any("delisted" in q for q in qs)
    print("confidence+queries OK")


if __name__ == "__main__":
    test_state_machine()
    d = test_ipa_analysis_and_hash()
    test_db_and_preservation(d)
    test_device_compat()
    test_confidence_and_queries()
    print("ALL SMOKE TESTS PASSED")
