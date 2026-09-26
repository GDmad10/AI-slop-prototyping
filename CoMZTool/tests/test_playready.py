import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core import crypto as C
from comz_core import decryptor as D

CLAIMED = "staging-claim/A3482A80.CallofMiniZombies_3stxm41ntn5hm"
KID_B64 = "LOz53L92kk6hGHVjSRTXvQ=="


def test_ctr_roundtrip():
    k = bytes.fromhex("00112233445566778899aabbccddeeff")
    iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    pt = b"PlayReady AESCTR preservation path probe 12345"
    ct = C.aes_ctr_crypt(pt, k, iv)
    assert ct != pt
    assert C.aes_ctr_crypt(ct, k, iv) == pt
    # unaligned tail
    pt2 = b"odd-length tail!"
    assert C.aes_ctr_crypt(C.aes_ctr_crypt(pt2, k, iv), k, iv) == pt2


def test_parse_claimed_playready_header():
    if not os.path.isfile(CLAIMED):
        print("SKIP (claimed sample absent)")
        return
    data = open(CLAIMED, "rb").read()
    info = D.parse_playready_header(data)
    assert info["algid"].upper() == "AESCTR", info
    assert info["kid_b64"] == KID_B64, info
    assert info["payload_len"] == os.path.getsize(CLAIMED) - info["header_len"]
    assert info["payload_len"] > 80_000_000, info
    print(f"KID {info['kid_b64']} KEYLEN {info['keylen']} "
          f"header_len {info['header_len']} payload {info['payload_len']}")


def test_synthetic_pre_decrypt_validates():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("WMAppManifest.xml",
                   b"Call of Mini Zombies Triniti 1.1.0.0")
        z.writestr("globalgamemanagers.assets", b"UnityFS fake comz")
    plain_pkg = buf.getvalue()
    k = bytes.fromhex("00112233445566778899aabbccddeeff")
    iv = bytes.fromhex("0102030405060708090a0b0c0d0e0f10")
    hdr = ("<WRMHEADER xmlns=\"http://schemas.microsoft.com/DRM/2007/03/"
           "PlayReadyHeader\" version=\"4.0.0.0\"><DATA><PROTECTINFO>"
           "<KEYLEN>16</KEYLEN><ALGID>AESCTR</ALGID></PROTECTINFO>"
           f"<KID>{KID_B64}</KID></DATA></WRMHEADER>").encode("utf-16-le")
    pre = b"PRE\x07" + hdr + C.aes_ctr_crypt(plain_pkg, k, iv)
    import tempfile
    d = tempfile.mkdtemp()
    src = os.path.join(d, "callofmini-zombies-synth-pre.file")
    open(src, "wb").write(pre)
    info = D.parse_playready_header(open(src, "rb").read())
    assert info["kid_b64"] == KID_B64
    out = os.path.join(d, "out.file")
    res = D.decrypt_file_blob(src, out, k, "playready-aesctr-file", iv)
    assert res["ok"], res
    assert res["validation"] == "PLAINTEXT VERIFIED", res


if __name__ == "__main__":
    test_ctr_roundtrip()
    print("t1 ok")
    test_parse_claimed_playready_header()
    print("t2 ok")
    test_synthetic_pre_decrypt_validates()
    print("t3 ok")
    print("ALL PLAYREADY TESTS PASSED")
