"""Access: does OpenAlex have a source record for the journal, and does it agree
with what we know about the journal's open-access status?

Source: api.openalex.org/sources, by ISSN; by title when no ISSN is on file.
"""

from __future__ import annotations

from ..models import ACCESS, FAIL, PASS, UNKNOWN, WARN, CheckResult
from ._common import evidence, issn_checksum_ok, journal_titles, titles_match

NAME = "openalex"
AREA = ACCESS
LABEL = "OpenAlex record"

API = "https://api.openalex.org/sources"


def _excerpt(s: dict) -> dict:
    return {k: s.get(k) for k in ("id", "display_name", "issn_l", "issn", "is_oa", "is_in_doaj",
                                  "works_count", "homepage_url", "host_organization_name", "type",
                                  "updated_date")}


def _host_matches(journal, s: dict) -> bool:
    home = s.get("homepage_url") or ""
    return bool(journal.host and journal.host.removeprefix("www.") in home)


def run(journal, http) -> CheckResult:
    ev, src = [], None
    reached = False
    for issn in [i for i in journal.issns if issn_checksum_ok(i)]:
        r, data = http.get_json(f"{API}/issn:{issn}")
        if r.status == 404:
            reached = True
            ev.append(evidence(r, note=f"no source record for ISSN {issn}"))
            continue
        if data is None:
            ev.append(evidence(r, note=r.error or "OpenAlex did not answer"))
            continue
        reached = True
        ev.append(evidence(r, excerpt=_excerpt(data)))
        src = data
        break

    by_title = False
    if src is None:
        r, data = http.get_json(API, params={"search": journal.name.split(":")[0], "per_page": 5})
        if data is not None:
            reached = True
            hits = data.get("results", [])
            ev.append(evidence(r, excerpt=[_excerpt(h) for h in hits], note="title search"))
            for h in hits:
                if titles_match(journal_titles(journal), h.get("display_name")):
                    src, by_title = h, True
                    break
        else:
            ev.append(evidence(r, note=r.error or "OpenAlex did not answer"))

    if not reached:
        return CheckResult(NAME, AREA, UNKNOWN, "OpenAlex could not be reached.", evidence=ev)
    if src is None:
        return CheckResult(NAME, AREA, FAIL, "OpenAlex has no source record for this journal.",
                           value=None, evidence=ev)

    ex = _excerpt(src)
    problems = []
    if by_title and not _host_matches(journal, src):
        problems.append(f"the only candidate (“{ex['display_name']}”, {ex['works_count']} works) "
                        "was found by title and can't be confirmed as this journal")
    elif not titles_match(journal_titles(journal), ex["display_name"]):
        problems.append(f"the ISSN resolves to “{ex['display_name']}”, which doesn't look like this journal")
    if not ex.get("issn_l"):
        problems.append("the record has no ISSN-L")
    if journal.is_open and ex.get("is_oa") is False:
        problems.append("OpenAlex marks it as not open access")
    if not journal.is_open and ex.get("is_oa") is True:
        problems.append("OpenAlex marks it as open access, which we don't")
    if not ex.get("works_count"):
        problems.append("the record holds no works")

    head = f"Source record “{ex['display_name']}”, {ex.get('works_count') or 0:,} works"
    if problems:
        return CheckResult(NAME, AREA, WARN, head + "; " + "; ".join(problems) + ".",
                           value=ex, evidence=ev)
    return CheckResult(NAME, AREA, PASS, head + ".", value=ex, evidence=ev)
