import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comz_core import dbox as D
from comz_core.catalog import Catalog


def test_ids_kept_separate():
    assert D.DBOX_PRODUCT_ID == "9WZDNCRFHZSZ"
    assert D.HISTORICAL_WP_APP_ID == "0febf8fa-35e8-4a87-8090-58b65220b3ed"
    assert D.DBOX_PRODUCT_ID != D.HISTORICAL_WP_APP_ID
    assert "9WZDNCRFHZSZ" in D.DBOX_PRODUCT_URL


def test_parse_and_relationship_exact():
    html = ("<html><head><title>Call of Mini Zombies</title></head><body>"
            "<div>Title: Call of Mini Zombies</div>"
            "<div>Platform: Windows Phone</div>"
            "<div>Version: 1.1.0.0</div>"
            "<div>Publisher: Triniti Interactive</div>"
            "<div>App: 0febf8fa-35e8-4a87-8090-58b65220b3ed</div>"
            "</body></html>")
    meta = D.parse_product_metadata(html)
    assert meta["mentions_comz"] is True
    assert meta["mentions_historical_wp_id"] is True
    assert "1.1.0.0" in meta["observed_versions"]
    rel = D.determine_relationship(meta)
    assert rel["relationship"] == "EXACT TARGET", rel


def test_relationship_related_generation():
    html = ("<html><body><div>Title: Call of Mini Zombies</div>"
            "<div>Version: 2.5.0.0</div></body></html>")
    rel = D.determine_relationship(D.parse_product_metadata(html))
    assert rel["relationship"] == "RELATED GENERATION", rel


def test_relationship_insufficient():
    rel = D.determine_relationship(D.parse_product_metadata(
        "<html><body><div>nothing here</div></body></html>"))
    assert rel["relationship"] == "INSUFFICIENT METADATA", rel


def test_acceptance_reference_only_vs_candidate():
    ok = D.check_candidate_against_target({
        "filename": "CallOfMiniZombies_1.1.0.0_neutral.xap",
        "label": "CallOfMiniZombies 1.1.0.0", "package_id": "",
        "product_id": "", "content_id": "", "package_type": "xap",
        "package_version": "1.1.0.0", "platform_hint": "Windows Phone (XAP)"})
    assert ok["testb_use"] == "TEST-B CANDIDATE", ok
    bad = D.check_candidate_against_target({
        "filename": "CallOfMiniZombies_2.0.0.0.appx",
        "label": "CallOfMiniZombies", "package_id": "",
        "product_id": "", "content_id": "", "package_type": "appx",
        "package_version": "2.0.0.0"})
    assert bad["testb_use"] == "REFERENCE ONLY", bad
    assert "version" in bad["acceptance"]


def test_preservation_record_fields():
    prec = D.preservation_record({"filename": "a.xap", "package_id": "p",
                                  "content_id": "c", "key_id": "k",
                                  "package_version": "1.1.0.0",
                                  "architecture": "neutral",
                                  "sha1": "s1", "sha256": "s2", "size": 5},
                                 "rg-adguard")
    for k in ("dbox_product_id", "historical_store_id", "package_id",
              "content_id", "key_id", "package_filename", "version",
              "platform", "architecture", "url_source", "sha1", "sha256",
              "size", "retrieval_timestamp"):
        assert k in prec, k
    assert prec["dbox_product_id"] == "9WZDNCRFHZSZ"


def test_xref_catalog_roundtrip():
    db = os.path.join(tempfile.mkdtemp(), "x.db")
    cat = Catalog(db)
    rid = cat.record_dbox("9WZDNCRFHZSZ", D.DBOX_PRODUCT_URL,
                          "Call of Mini Zombies", "Triniti",
                          "RELATED GENERATION", "modern generation")
    assert rid == 1
    xid = cat.record_xref(
        store_product="0febf8fa-35e8-4a87-8090-58b65220b3ed",
        dbox_product="9WZDNCRFHZSZ", package_id="p", content_id="c",
        historical_package="a.xap", note="t")
    assert xid == 1
    assert len(cat.list_xrefs()) == 1
    assert len(cat.list_dbox_refs()) == 1


if __name__ == "__main__":
    test_ids_kept_separate()
    print("t1 ok")
    test_parse_and_relationship_exact()
    print("t2 ok")
    test_relationship_related_generation()
    print("t3 ok")
    test_relationship_insufficient()
    print("t4 ok")
    test_acceptance_reference_only_vs_candidate()
    print("t5 ok")
    test_preservation_record_fields()
    print("t6 ok")
    test_xref_catalog_roundtrip()
    print("t7 ok")
    print("ALL DBOX TESTS PASSED")
