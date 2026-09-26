import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core.identify import identify_file, is_likely_comz
from comz_core.analyze import analyze_file
from comz_core.compare import compare_files
from comz_core.unity import scan_unity


def test_identify_negative():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".file") as f:
        f.write(b"\x00\x01\x02random bytes with no signals at all " * 100)
        p = f.name
    try:
        ident = identify_file(p)
        assert ident["is_likely_comz"] is False, ident
        assert ident["md5"] and ident["sha256"]
    finally:
        os.unlink(p)


def test_plaintext_zip_unity_hints():
    d = tempfile.mkdtemp()
    zp = os.path.join(d, "mini-zombies-test.file")
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("globalgamemanagers.assets", b"UnityFS fake")
        z.writestr("WMAppManifest.xml", b"Triniti Call of Mini Zombies")
    ident = identify_file(zp)
    assert ident["is_likely_comz"] is True, ident
    rep = analyze_file(zp)
    assert rep["zip_inventory"]["readable"] is True
    assert rep["zip_inventory"]["count"] == 2


def test_compare_and_unity_scan():
    d = tempfile.mkdtemp()
    a = os.path.join(d, "a.file")
    b = os.path.join(d, "b.file")
    open(a, "wb").write(b"hello world")
    open(b, "wb").write(b"hello WORLD!")
    diff = compare_files(a, b)
    assert diff["same_sha256"] is False
    udir = os.path.join(d, "unpacked")
    os.makedirs(os.path.join(udir, "Managed"), exist_ok=True)
    open(os.path.join(udir, "Managed", "Assembly-CSharp.dll"), "wb").write(b"MZ fake")
    open(os.path.join(udir, "globalgamemanagers"), "wb").write(b"UnityFS fake")
    r = scan_unity(udir)
    assert r["verdict"] == "UNITY STRUCTURES PRESENT"


if __name__ == "__main__":
    test_identify_negative()
    print("t1 ok")
    test_plaintext_zip_unity_hints()
    print("t2 ok")
    test_compare_and_unity_scan()
    print("t3 ok")
    print("ALL TESTS PASSED")
