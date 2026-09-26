import io
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core import crypto as C
from comz_core import decryptor as D
from comz_core.package_meta import build_package_record


def test_aes_cbc_roundtrip():
    k = bytes.fromhex("00112233445566778899aabbccddeeff")
    iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    pt = b"Call of Mini Zombies v1.1.0.0 Windows Phone"
    ct = C.aes_cbc_encrypt(C.pkcs7_pad(pt), k, iv)
    assert C.pkcs7_unpad(C.aes_cbc_decrypt(ct, k, iv)) == pt


def test_aes_ecb_roundtrip():
    k = b"0123456789abcdef"
    assert C.aes_ecb_decrypt(C.aes_ecb_encrypt(b"0123456789abcdef", k), k) == b"0123456789abcdef"


def test_xor_roundtrip():
    assert C.xor_stream(C.xor_stream(b"hello comz", b"key"), b"key") == b"hello comz"


def test_metadata_primary_target():
    d = tempfile.mkdtemp()
    xap = os.path.join(d, "callofmini-zombies-1.1.0.0.file")
    wm = (b'<?xml version="1.0"?><Deployment><App '
          b'ProductID="{11111111-2222-3333-4444-555555555555}" '
          b'Title="Call of Mini Zombies" Version="1.1.0.0" '
          b'Publisher="Triniti Interactive" /></Deployment>')
    with zipfile.ZipFile(xap, "w") as z:
        z.writestr("WMAppManifest.xml", wm)
        z.writestr("globalgamemanagers.assets", b"UnityFS fake comz")
        z.writestr("Assembly-CSharp.dll", b"MZ fake comz")
    rec = build_package_record(xap)
    assert rec["game"] == "Call of Mini: Zombies", rec
    assert rec["version"] == "1.1.0.0", rec
    assert rec["is_primary_target_v1_1_0_0"] is True
    assert rec["contained_count"] == 3


def test_gate_refuses_non_comz():
    import comz_core.decryptor as Dmod
    d = tempfile.mkdtemp()
    p = os.path.join(d, "random.file")
    open(p, "wb").write(b"\x00\x01random bytes, no signals here " * 50)
    try:
        Dmod.decrypt_file_blob(p, os.path.join(d, "o"),
                               b"0123456789abcdef", "xor-file")
    except Dmod.NotComZombies:
        return
    raise AssertionError("gate did not refuse")


def test_end_to_end_encrypt_decrypt_extract():
    d = tempfile.mkdtemp()
    xap = os.path.join(d, "callofmini-zombies-1.1.0.0.file")
    wm = (b'<?xml version="1.0"?><Deployment><App '
          b'ProductID="{11111111-2222-3333-4444-555555555555}" '
          b'Title="Call of Mini Zombies" Version="1.1.0.0" '
          b'Publisher="Triniti Interactive" /></Deployment>')
    with zipfile.ZipFile(xap, "w") as z:
        z.writestr("WMAppManifest.xml", wm)
        z.writestr("globalgamemanagers.assets", b"UnityFS fake comz")
        z.writestr("Assembly-CSharp.dll", b"MZ fake comz")
    key = bytes.fromhex("00112233445566778899aabbccddeeff")
    iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    plain = open(xap, "rb").read()
    enc = os.path.join(d, "callofmini-zombies-1.1.0.0-enc.file")
    open(enc, "wb").write(C.aes_cbc_encrypt(C.pkcs7_pad(plain), key, iv))
    out = os.path.join(d, "decrypted.file")
    res = D.decrypt_file_blob(enc, out, key, "aes-cbc-file", iv)
    assert res["ok"], res
    assert res["validation"] == "PLAINTEXT VERIFIED"
    ex = D.extract_package(out, os.path.join(d, "out"))
    assert ex["ok"] and ex["entries"] == 3, ex
    # wrong key must fail validation, not fake success
    bad = D.decrypt_file_blob(enc, os.path.join(d, "bad.file"),
                              b"ffffffffffffffff", "xor-file")
    assert not bad["ok"], bad


if __name__ == "__main__":
    test_aes_cbc_roundtrip()
    print("t1 ok")
    test_aes_ecb_roundtrip()
    print("t2 ok")
    test_xor_roundtrip()
    print("t3 ok")
    test_metadata_primary_target()
    print("t4 ok")
    test_gate_refuses_non_comz()
    print("t5 ok")
    test_end_to_end_encrypt_decrypt_extract()
    print("t6 ok")
    print("ALL DECRYPTOR TESTS PASSED")
