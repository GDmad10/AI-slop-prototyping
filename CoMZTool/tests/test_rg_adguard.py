import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core import rg_adguard as R


def _make_comz_xap(d, name="callofmini-zombies-1.1.0.0.xap"):
    p = os.path.join(d, name)
    wm = (b'<?xml version="1.0"?><Deployment><App '
          b'ProductID="{0febf8fa-35e8-4a87-8090-58b65220b3ed}" '
          b'Title="Call of Mini Zombies" Version="1.1.0.0" '
          b'Publisher="Triniti Interactive" /></Deployment>')
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("WMAppManifest.xml", wm)
        z.writestr("globalgamemanagers.assets", b"UnityFS fake comz")
        z.writestr("Assembly-CSharp.dll", b"MZ fake comz")
    return p


def test_candidate_version_filter_no_substitution():
    links = [
        {"url": "https://cdn/a/CallOfMiniZombies_2.0.0.0_neutral.xap",
         "label": "CallOfMiniZombies 2.0.0.0", "host": "cdn"},
        {"url": "https://cdn/b/CallOfMiniZombies_1.1.0.0_neutral.xap",
         "label": "CallOfMiniZombies 1.1.0.0", "host": "cdn"},
    ]
    sel = R.select_testb_candidates(links)
    assert sel["generations"] == ["1.1.0.0", "2.0.0.0"], sel
    assert len(sel["selected"]) == 1
    assert sel["selected"][0]["package_version"] == "1.1.0.0"
    assert sel["all"][0]["verdict"] == "WRONG VERSION"


def test_wrong_game_rejected():
    c = R.verify_candidate(R.candidate_from_link(
        {"url": "https://cdn/other-game_1.1.0.0.xap",
         "label": "Some Other Game", "host": "cdn"}))
    assert c["verdict"] == "WRONG GAME", c


def test_consensus_match_and_conflict():
    m = R.compare_source_hashes([
        {"source": "microsoft-store", "sha256": "ab" * 32},
        {"source": "rg-adguard", "sha256": "AB" * 32},
        {"source": "internet-archive", "sha256": "ab" * 32}])
    assert m["result"] == "SOURCE CONSENSUS: MATCH", m
    c = R.compare_source_hashes([
        {"source": "microsoft-store", "sha256": "ab" * 32},
        {"source": "rg-adguard", "sha256": "cd" * 32}])
    assert c["result"] == "SOURCE CONFLICT", c


def test_verify_downloaded_ready_and_corrupt():
    d = tempfile.mkdtemp()
    good = _make_comz_xap(d)
    cand = {"filename": os.path.basename(good), "extension": ".xap",
            "package_type": "xap", "package_version": "", "architecture": "",
            "language": "", "publisher": "", "package_id": "", "product_id": "",
            "content_id": "", "size": 0, "sha1": "", "sha256": "",
            "url": "", "staged": good, "state": "DOWNLOADED"}
    v = R.verify_downloaded(dict(cand))
    assert v["verdict"] == "READY FOR DECRYPTION", v
    assert v["package_record"]["version"] == "1.1.0.0", v
    bad_path = os.path.join(d, "callofmini-zombies-bad.xap")
    open(bad_path, "wb").write(b"not a container, but comz call of mini " * 100)
    b = R.verify_downloaded({**cand, "staged": bad_path})
    assert b["verdict"] == "CORRUPTED", b


def test_run_testb_injected_resolver_end_to_end():
    import pathlib
    d = tempfile.mkdtemp()
    src = _make_comz_xap(d, name="CallOfMiniZombies_1.1.0.0_neutral.xap")
    url = pathlib.Path(src).as_uri()  # file:// — exercises real download path
    links = [{"url": url,
              "label": "CallOfMiniZombies 1.1.0.0 neutral",
              "host": "localhost"}]

    def fake_resolver(app_id):
        assert app_id == R.TESTB_APP_ID
        return {"state": "DOWNLOAD LINK FOUND", "links": links,
                "raw_note": "injected"}

    out = R.run_testb(os.path.join(d, "staging"), resolver_fn=fake_resolver)
    assert out["state"] == "READY FOR DECRYPTION", out
    assert "[RG-ADGUARD] Package found" in out["log"][1]
    assert "[VERIFY] Hash recorded" in out["log"], out
    # pipeline chain on the acquired file
    pipe = R.chain_into_pipeline(out["candidate"]["staged"], os.path.join(d, "pipe"))
    assert pipe["extract"]["ok"], pipe
    assert pipe["unity"]["verdict"] == "UNITY STRUCTURES PRESENT", pipe


def test_run_testb_empty_resolver_not_found():
    out = R.run_testb(tempfile.mkdtemp(),
                      resolver_fn=lambda aid: {"state": "NOT FOUND",
                                               "links": [], "raw_note": "empty"})
    assert out["state"] == "NOT FOUND", out


if __name__ == "__main__":
    test_candidate_version_filter_no_substitution()
    print("t1 ok")
    test_wrong_game_rejected()
    print("t2 ok")
    test_consensus_match_and_conflict()
    print("t3 ok")
    test_verify_downloaded_ready_and_corrupt()
    print("t4 ok")
    test_run_testb_injected_resolver_end_to_end()
    print("t5 ok")
    test_run_testb_empty_resolver_not_found()
    print("t6 ok")
    print("ALL RG-ADGUARD TESTS PASSED")
