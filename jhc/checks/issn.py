"""Access: is each ISSN the journal uses registered, to this journal, with an ISSN-L?

Source: the public record page on portal.issn.org.
"""

from __future__ import annotations

from ..models import ACCESS, FAIL, PASS, UNKNOWN, WARN, CheckResult, Evidence
from ._common import evidence, fetch_portal_record, issn_checksum_ok, journal_titles, titles_match

NAME = "issn"
AREA = ACCESS
LABEL = "ISSN registered"


def run(journal, http) -> CheckResult:
    issns = [i for i in (journal.issn_online, journal.issn_print) if i]
    if not issns:
        return CheckResult(
            NAME, AREA, UNKNOWN,
            journal.issn_note or "No ISSN on file here. The journal may have one we haven't found.",
            evidence=[Evidence(url=journal.home_url or "", note="no ISSN in data/journals.yaml")],
        )

    ev, records, problems = [], [], []
    for issn in issns:
        if not issn_checksum_ok(issn):
            problems.append(f"{issn} fails the ISSN check digit, so it can't be a real ISSN")
            ev.append(Evidence(url="", note=f"{issn}: bad check digit"))
            continue
        r, rec = fetch_portal_record(http, issn)
        if r.status is None or (r.status and r.status >= 500):
            ev.append(evidence(r, note=r.error or "ISSN Portal did not answer"))
            continue
        if rec is None:
            problems.append(f"{issn} has no record on the ISSN Portal")
            ev.append(evidence(r, note="no record page for this ISSN"))
            continue
        excerpt = {k: rec.get(k) for k in ("page_title", "key_title", "title_proper", "issn_l",
                                           "publication_medium", "record_status", "last_modified",
                                           "latest_publisher")}
        ev.append(evidence(r, excerpt=excerpt))
        records.append(rec)
        names = [rec.get("key_title"), rec.get("title_proper"), rec.get("page_title")]
        if not any(titles_match(journal_titles(journal), n) for n in names if n):
            problems.append(f"{issn} is registered to “{rec.get('key_title') or rec['page_title']}”, "
                            "a title that doesn't match this journal")

    if not records and not problems:
        return CheckResult(NAME, AREA, UNKNOWN, "The ISSN Portal could not be reached.", evidence=ev)

    issn_ls = sorted({r["issn_l"] for r in records if r.get("issn_l")})
    value = {"issns": issns, "issn_l": issn_ls[0] if len(issn_ls) == 1 else issn_ls or None,
             "record_status": sorted({r.get("record_status") or "?" for r in records})}

    if problems:
        # A title mismatch is a warning, not a failure: the registration may
        # be an old record the ISSN Centre never updated, and that is for a
        # person to sort out. Fail only when no ISSN resolves at all.
        status = FAIL if not records else WARN
        return CheckResult(NAME, AREA, status, "; ".join(problems) + ".", value=value, evidence=ev)
    if not issn_ls:
        return CheckResult(NAME, AREA, WARN, "Registered, but the record shows no ISSN-L.",
                           value=value, evidence=ev)
    if len(issn_ls) > 1:
        return CheckResult(NAME, AREA, WARN,
                           f"The print and online records point to different ISSN-Ls ({', '.join(issn_ls)}).",
                           value=value, evidence=ev)
    prov = [r["issn"] for r in records if r.get("record_status") == "Provisional"]
    if prov:
        return CheckResult(NAME, AREA, WARN,
                           f"Registered, but the record for {', '.join(prov)} is still provisional.",
                           value=value, evidence=ev)
    return CheckResult(NAME, AREA, PASS,
                       f"Registered, ISSN-L {issn_ls[0]}.", value=value, evidence=ev)
