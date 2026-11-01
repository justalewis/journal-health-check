"""One block per Phase 1 check module. Every test runs offline against FakeHttp."""

from datetime import datetime, timedelta, timezone

from jhc.checks import crossref, doaj, issn, keepers, openalex, rdap, tls, wayback
from jhc.journals import Journal

from .conftest import FakeHttp, portal_page

PORTAL = "https://portal.issn.org/resource/ISSN/"
NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


# -- ISSN -------------------------------------------------------------------

def test_issn_pass(lics):
    http = FakeHttp({PORTAL + "2326-5620": (200, portal_page("2326-5620", "Literacy in composition studies"))})
    r = issn.run(lics, http)
    assert r.status == "pass" and r.value["issn_l"] == "2326-5620"


def test_issn_registered_to_other_title_warns():
    j = Journal(name="Composition Forum", issn_print="1522-7502", oa="gold")
    http = FakeHttp({PORTAL + "1522-7502": (200, portal_page(
        "1522-7502", "Forum (Conference on College Composition and Communication)"))})
    r = issn.run(j, http)
    assert r.status == "warn" and "doesn't match" in r.summary


def test_issn_none_on_file_is_unknown_not_fail():
    j = Journal(name="Enculturation", oa="gold")
    assert issn.run(j, FakeHttp({})).status == "unknown"


def test_issn_bad_check_digit_fails():
    j = Journal(name="X Journal", issn_print="2326-5621")
    assert issn.run(j, FakeHttp({})).status == "fail"


def test_issn_portal_down_is_unknown(lics):
    r = issn.run(lics, FakeHttp({PORTAL + "2326-5620": (None, "")}))
    assert r.status == "unknown"


# -- Keepers -----------------------------------------------------------------

def test_keepers_pass(lics):
    page = portal_page("2326-5620", "Literacy in composition studies", keepers=[
        {"keeper": "LOCKSS Archive", "status": "Preserved", "from_": "2013", "to": "2025"}])
    r = keepers.run(lics, FakeHttp({PORTAL + "2326-5620": (200, page)}))
    assert r.status == "pass" and "LOCKSS Archive" in r.value


def test_keepers_none_fails(lics):
    page = portal_page("2326-5620", "Literacy in composition studies", keepers=[])
    assert keepers.run(lics, FakeHttp({PORTAL + "2326-5620": (200, page)})).status == "fail"


def test_keepers_stale_coverage_warns(lics):
    page = portal_page("2326-5620", "Literacy in composition studies", keepers=[
        {"keeper": "Portico", "status": "Preserved", "to": "2015"}])
    assert keepers.run(lics, FakeHttp({PORTAL + "2326-5620": (200, page)})).status == "warn"


def test_keepers_ignores_record_for_other_title():
    j = Journal(name="Composition Forum", issn_print="1522-7502", oa="gold")
    page = portal_page("1522-7502", "Forum (Conference on College Composition and Communication)",
                       keepers=[{"keeper": "Portico", "status": "Preserved", "to": "2025"}])
    assert keepers.run(j, FakeHttp({PORTAL + "1522-7502": (200, page)})).status == "unknown"


# -- DOAJ --------------------------------------------------------------------

def _doaj_rec(title, issn, url="https://licsjournal.org/"):
    return {"id": "abc", "bibjson": {"title": title, "eissn": issn, "ref": {"journal": url}},
            "last_updated": "2026-01-01"}


def test_doaj_listed(lics):
    http = FakeHttp({"https://doaj.org/api/search/journals/issn%3A2326-5620":
                     (200, {"total": 1, "results": [_doaj_rec("Literacy in Composition Studies", "2326-5620")]})})
    assert doaj.run(lics, http).status == "pass"


def test_doaj_not_listed_warns(lics):
    http = FakeHttp({"https://doaj.org/api/search/journals/*": (200, {"total": 0, "results": []})})
    assert doaj.run(lics, http).status == "warn"


def test_doaj_subscription_is_na():
    j = Journal(name="College English", issn_print="0010-0994", oa="subscription")
    assert doaj.run(j, FakeHttp({})).status == "na"


def test_doaj_issn_collision_is_reported():
    j = Journal(name="Composition Forum", issn_print="1522-7502", oa="gold",
                home_url="https://compositionforum.com/")
    http = FakeHttp({
        "https://doaj.org/api/search/journals/issn%3A1522-7502":
            (200, {"total": 1, "results": [_doaj_rec("Forum", "1522-7502", "https://example.org")]}),
        "https://doaj.org/api/search/journals/*": (200, {"total": 0, "results": []}),
    })
    r = doaj.run(j, http)
    assert r.status == "warn" and r.value["issn_collision"]["title"] == "Forum"


# -- OpenAlex ----------------------------------------------------------------

def _source(name, issn_l="2326-5620", is_oa=True, works=214, home="http://licsjournal.org"):
    return {"id": "https://openalex.org/S1", "display_name": name, "issn_l": issn_l,
            "issn": [issn_l], "is_oa": is_oa, "works_count": works, "homepage_url": home}


def test_openalex_pass(lics):
    http = FakeHttp({"https://api.openalex.org/sources/issn:2326-5620":
                     (200, _source("Literacy in Composition Studies"))})
    assert openalex.run(lics, http).status == "pass"


def test_openalex_oa_mismatch_warns(lics):
    http = FakeHttp({"https://api.openalex.org/sources/issn:2326-5620":
                     (200, _source("Literacy in Composition Studies", is_oa=False))})
    r = openalex.run(lics, http)
    assert r.status == "warn" and "not open access" in r.summary


def test_openalex_no_record_fails():
    j = Journal(name="Enculturation", oa="gold", home_url="https://enculturation.net/")
    http = FakeHttp({"https://api.openalex.org/sources*": (200, {"results": []})})
    assert openalex.run(j, http).status == "fail"


def test_openalex_title_only_match_is_unconfirmed():
    j = Journal(name="Present Tense: A Journal of Rhetoric in Society", oa="gold",
                home_url="https://www.presenttensejournal.org/")
    http = FakeHttp({"https://api.openalex.org/sources*": (200, {"results": [
        _source("Present tense", issn_l="0092-4091", is_oa=None, works=0, home=None)]})})
    r = openalex.run(j, http)
    assert r.status == "warn" and "can't be confirmed" in r.summary


def test_openalex_down_is_unknown(lics):
    http = FakeHttp({"https://api.openalex.org/*": (None, "")})
    assert openalex.run(lics, http).status == "unknown"


# -- Crossref ----------------------------------------------------------------

def _cr_routes(issn, title, total, refs, current=0.9, current_dois=20):
    base = f"https://api.crossref.org/journals/{issn}"
    return {
        base: (200, {"message": {"title": title, "counts": {"total-dois": total, "current-dois": current_dois},
                                 "coverage": {"references-current": current}}}),
        base + "/works?rows=0": (200, {"message": {"total-results": total}}),
        base + "/works?rows=0&filter=has-references%3Atrue": (200, {"message": {"total-results": refs}}),
    }


def test_crossref_pass(lics):
    r = crossref.run(lics, FakeHttp(_cr_routes("2326-5620", "Literacy in Composition Studies", 191, 171)))
    assert r.status == "pass" and r.value["dois"] == 191 and r.value["with_references"] == 171


def test_crossref_low_rate_warns():
    j = Journal(name="College Composition and Communication", issn_print="0010-096X")
    r = crossref.run(j, FakeHttp(_cr_routes("0010-096X", "College Composition and Communication",
                                            6945, 231, current=0.5)))
    assert r.status == "warn" and "3.3%" in r.summary


def test_crossref_recent_rate_can_pass():
    j = Journal(name="College Composition and Communication", issn_print="0010-096X")
    r = crossref.run(j, FakeHttp(_cr_routes("0010-096X", "College Composition and Communication",
                                            6945, 231, current=0.85)))
    assert r.status == "pass"


def test_crossref_no_dois_fails():
    j = Journal(name="Composition Studies", issn_print="1534-9322")
    assert crossref.run(j, FakeHttp({})).status == "fail"


def test_crossref_skips_other_serial():
    j = Journal(name="Composition Forum", issn_print="1522-7502")
    r = crossref.run(j, FakeHttp(_cr_routes("1522-7502", "Forum", 34, 31)))
    assert r.status == "fail" and r.value["dois"] == 0


def test_crossref_prefix_fallback_warns():
    j = Journal(name="Writing Lab Newsletter", short="WLN", issn_print="1040-3779",
                crossref_prefix="10.37514",
                crossref_container="WLN: A Journal of Writing Center Scholarship")
    base = "https://api.crossref.org/prefixes/10.37514/works?rows=0&filter=container-title%3AWLN%3A+A+Journal+of+Writing+Center+Scholarship"
    http = FakeHttp({base: (200, {"message": {"total-results": 1805}}),
                     base + "%2Chas-references%3Atrue": (200, {"message": {"total-results": 1200}})})
    r = crossref.run(j, http)
    assert r.status == "warn" and "without an ISSN" in r.summary


# -- Wayback -----------------------------------------------------------------

def test_wayback_recent_capture_passes(lics):
    landing = "https://licsjournal.org/index.php/LiCS"
    http = FakeHttp({
        "https://licsjournal.org/": (200, "<html></html>"),
        "https://web.archive.org/cdx/search/cdx*": (200, [["timestamp", "statuscode", "original"],
                                                          ["20261019212731", "200", landing]]),
    }, final_urls={"https://licsjournal.org/": landing})
    r = wayback.run(lics, http, now=NOW)
    assert r.status == "pass" and r.value["age_days"] == 12


def test_wayback_old_capture_fails(lics):
    http = FakeHttp({
        "https://licsjournal.org/": (200, ""),
        "https://web.archive.org/cdx/search/cdx*": (200, [["timestamp", "statuscode", "original"],
                                                          ["20130909114454", "200", "x"]]),
    })
    assert wayback.run(lics, http, now=NOW).status == "fail"


def test_wayback_no_captures_fails(lics):
    http = FakeHttp({"https://licsjournal.org/": (200, ""),
                     "https://web.archive.org/cdx/search/cdx*": (200, "")})
    assert wayback.run(lics, http, now=NOW).status == "fail"


def test_wayback_ceased_any_capture_passes():
    j = Journal(name="JAC", home_url="http://www.jaconlinejournal.com/", status="ceased")
    http = FakeHttp({"https://web.archive.org/cdx/search/cdx*": (200, [["timestamp", "statuscode", "original"],
                                                                      ["20150101000000", "200", "x"]])},
                    final_urls={"http://www.jaconlinejournal.com/": "https://www.aiccindia.org/"})
    http.routes["http://www.jaconlinejournal.com/"] = (200, "")
    r = wayback.run(j, http, now=NOW)
    assert r.status == "pass"
    # The unrelated site the dead domain now redirects to is not queried.
    assert not any("aiccindia" in c for c in http.calls if "cdx" in c)


def test_wayback_archive_down_is_unknown(lics):
    http = FakeHttp({"https://licsjournal.org/": (200, ""),
                     "https://web.archive.org/*": (None, "")})
    assert wayback.run(lics, http, now=NOW).status == "unknown"


def test_wayback_no_site_is_na():
    assert wayback.run(Journal(name="Pre/Text", platform="none"), FakeHttp({})).status == "na"


# -- RDAP --------------------------------------------------------------------

def _rdap(expires):
    return {"ldhName": "LICSJOURNAL.ORG", "events": [{"eventAction": "expiration", "eventDate": expires}],
            "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "GoDaddy.com, LLC"]]]}]}


def test_rdap_pass(lics):
    r = rdap.run(lics, FakeHttp({"https://rdap.org/domain/licsjournal.org": (200, _rdap("2027-03-19T19:51:28Z"))}), now=NOW)
    assert r.status == "pass" and r.value["registrar"] == "GoDaddy.com, LLC"


def test_rdap_soon_warns(lics):
    r = rdap.run(lics, FakeHttp({"https://rdap.org/domain/licsjournal.org": (200, _rdap("2026-12-01T00:00:00Z"))}), now=NOW)
    assert r.status == "warn" and r.value["days_left"] == 30


def test_rdap_expired_fails(lics):
    r = rdap.run(lics, FakeHttp({"https://rdap.org/domain/licsjournal.org": (200, _rdap("2026-10-01T00:00:00Z"))}), now=NOW)
    assert r.status == "fail"


def test_rdap_university_and_publisher_are_na():
    wcj = Journal(name="Writing Center Journal", home_url="https://docs.lib.purdue.edu/wcj/")
    ce = Journal(name="College English", home_url="https://publicationsncte.org/x", platform="publisher")
    assert rdap.run(wcj, FakeHttp({})).status == "na"
    assert rdap.run(ce, FakeHttp({})).status == "na"


def test_rdap_no_record_is_unknown(lics):
    assert rdap.run(lics, FakeHttp({}), now=NOW).status == "unknown"


def test_registrable_domain():
    assert rdap.registrable_domain("kairos.technorhetoric.net") == "technorhetoric.net"
    assert rdap.registrable_domain("publications.coventry.ac.uk") == "coventry.ac.uk"


# -- TLS ---------------------------------------------------------------------

def _shake(days):
    def f(host):
        end = NOW + timedelta(days=days)
        return {"cert": {"notAfter": end.strftime("%b %d %H:%M:%S %Y GMT"),
                         "issuer": ((("organizationName", "Let's Encrypt"),),),
                         "subject": ((("commonName", host),),)}, "version": "TLSv1.3"}
    return f


def test_tls_pass(lics):
    r = tls.run(lics, now=NOW, shake=_shake(60))
    assert r.status == "pass" and r.value["issuer"] == "Let's Encrypt"


def test_tls_near_expiry_warns(lics):
    assert tls.run(lics, now=NOW, shake=_shake(5)).status == "warn"


def test_tls_verify_error_fails(lics):
    r = tls.run(lics, now=NOW, shake=lambda h: {"error": "certificate has expired", "kind": "verify"})
    assert r.status == "fail"


def test_tls_timeout_is_unknown(lics):
    assert tls.run(lics, now=NOW, shake=lambda h: {"error": "timed out", "kind": "timeout"}).status == "unknown"


def test_tls_uses_mozilla_roots(monkeypatch):
    # Regression: the Windows store once failed licsjournal.org's valid
    # Let's Encrypt chain as expired. The context must load certifi.
    import certifi
    seen = {}
    real = tls.ssl.create_default_context

    def spy(*a, **kw):
        seen.update(kw)
        return real(*a, **kw)
    monkeypatch.setattr(tls.ssl, "create_default_context", spy)
    monkeypatch.setattr(tls.socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    tls.handshake("example.org")
    assert seen.get("cafile") == certifi.where()
