from jhc.checks._common import issn_checksum_ok, parse_portal_record, titles_match

from .conftest import portal_page


def test_issn_checksum():
    assert issn_checksum_ok("0010-096X")
    assert issn_checksum_ok("2326-5620")
    assert not issn_checksum_ok("2326-5621")
    assert not issn_checksum_ok("23265620")


def test_titles_match_tolerates_punctuation_and_medium():
    assert titles_match(["Peitho"], "Peitho.")
    assert titles_match(["Kairos: A Journal of Rhetoric, Technology, and Pedagogy"], "Kairos (Online)")
    assert titles_match(["Writing Center Journal"], "The Writing center journal")
    assert titles_match(["Basic Writing e-Journal"], "BWe basic writing e-journal")
    assert titles_match(["Computers and Composition"], "Computers & composition (Online)")
    assert titles_match(["WPA: Writing Program Administration"], "WPA. Writing program administration")


def test_titles_match_rejects_other_serials():
    # The real collision behind this rule: Composition Forum's ISSN is
    # registered to CCCC's Forum newsletter.
    assert not titles_match(["Composition Forum"], "Forum (Conference on College Composition and Communication)")
    assert not titles_match(["Present Tense: A Journal of Rhetoric in Society"], "AP environmental science")


def test_parse_portal_record():
    rec = parse_portal_record(portal_page("2326-5620", "Literacy in composition studies",
                                          keepers=[{"keeper": "LOCKSS Archive"}]), "2326-5620")
    assert rec["key_title"] == "Literacy in composition studies"
    assert rec["issn_l"] == "2326-5620"
    assert rec["record_status"] == "Confirmed"
    assert rec["keepers"] == [{"keeper": "LOCKSS Archive"}]


def test_parse_portal_record_wrong_page():
    assert parse_portal_record("<title>400 Bad Request</title>", "1710-4249") is None
