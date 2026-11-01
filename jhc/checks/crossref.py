"""Access: does the journal register DOIs with Crossref, and deposit the reference
lists that go with them?

Source: api.crossref.org. The two headline numbers use the same queries as
Eunomia's Labors, so the two sites report the same figures:

    DOI records      = total-results of /journals/{issn}/works
    reference lists  = total-results of /journals/{issn}/works?filter=has-references:true

The "current" rate is Crossref's own coverage figure for the last two
calendar years plus this one, from /journals/{issn}.
"""

from __future__ import annotations

from .. import config
from ..models import ACCESS, FAIL, PASS, UNKNOWN, WARN, CheckResult
from ._common import evidence, issn_checksum_ok, journal_titles, titles_match

NAME = "crossref"
AREA = ACCESS
LABEL = "Crossref DOIs and references"

API = "https://api.crossref.org"
PASS_OVERALL = 0.5    # half of all DOI records carry references, or
PASS_CURRENT = 0.8    # four in five of the recent ones do


def _params(extra: dict | None = None) -> dict:
    p = {"rows": 0}
    if config.CONTACT_EMAIL:
        p["mailto"] = config.CONTACT_EMAIL
    p.update(extra or {})
    return p


def _total(http, url, extra=None):
    r, data = http.get_json(url, params=_params(extra))
    if data is None:
        return r, None
    return r, (data.get("message") or {}).get("total-results")


def _by_prefix(journal, http, ev):
    """DOIs deposited with no ISSN (WLN) are reachable only by prefix + title."""
    url = f"{API}/prefixes/{journal.crossref_prefix}/works"
    f = f"container-title:{journal.crossref_container}"
    r, total = _total(http, url, {"filter": f})
    ev.append(evidence(r, excerpt={"total-results": total}, note="prefix + exact container-title"))
    r2, refs = _total(http, url, {"filter": f + ",has-references:true"})
    ev.append(evidence(r2, excerpt={"total-results": refs}, note="with has-references:true"))
    return total, refs


def run(journal, http) -> CheckResult:
    ev = []
    order = [journal.crossref_issn] if journal.crossref_issn else []
    order += [i for i in (journal.issn_online, journal.issn_print) if i and i not in order]
    order = [i for i in order if issn_checksum_ok(i)]

    meta, used = None, None
    candidates = []
    reached = False
    for issn in order:
        mailto = {"mailto": config.CONTACT_EMAIL} if config.CONTACT_EMAIL else None
        r, data = http.get_json(f"{API}/journals/{issn}", params=mailto)
        if r.status == 404:
            reached = True
            ev.append(evidence(r, note=f"Crossref has no journal record for {issn}"))
            continue
        if data is None:
            ev.append(evidence(r, note=r.error or "Crossref did not answer"))
            continue
        reached = True
        m = data.get("message") or {}
        ev.append(evidence(r, excerpt={k: m.get(k) for k in ("title", "publisher", "issn-type", "counts")}
                           | {"coverage": {k: (m.get("coverage") or {}).get(k)
                                           for k in ("references-current", "references-backfile")}}))
        if not titles_match(journal_titles(journal), m.get("title")):
            # Composition Forum's ISSN belongs to CCCC's Forum newsletter in
            # Crossref too; counting that newsletter's DOIs would be wrong.
            ev[-1].note = f"skipped: Crossref files {issn} under “{m.get('title')}”"
            continue
        if (m.get("counts") or {}).get("total-dois"):
            candidates.append((issn, m))
        meta = meta or m

    # Both ISSNs often share one journal record, but /works by ISSN can still
    # return different subsets (CCC: 6,945 works under the print ISSN, 4,031
    # under the online one). Count under each and keep the larger, which is
    # also the ISSN Pinakes and Eunomia's Labors use.
    total = None
    for issn, m in candidates:
        r, n = _total(http, f"{API}/journals/{issn}/works")
        ev.append(evidence(r, excerpt={"total-results": n}))
        if n is not None and (total is None or n > total):
            used, meta, total = issn, m, n

    if used:
        works = f"{API}/journals/{used}/works"
        r2, refs = _total(http, works, {"filter": "has-references:true"})
        ev.append(evidence(r2, excerpt={"total-results": refs}, note="filter=has-references:true"))
        if total is None or refs is None:
            return CheckResult(NAME, AREA, UNKNOWN, "Crossref stopped answering partway through.",
                               evidence=ev)
        current = ((meta.get("coverage") or {}).get("references-current"))
        current_dois = (meta.get("counts") or {}).get("current-dois") or 0
    elif journal.crossref_prefix and journal.crossref_container:
        total, refs = _by_prefix(journal, http, ev)
        if total is None:
            return CheckResult(NAME, AREA, UNKNOWN, "Crossref could not be reached.", evidence=ev)
        reached, current, current_dois = True, None, 0
    else:
        total, refs, current, current_dois = 0, 0, None, 0

    if not order and not journal.crossref_prefix:
        return CheckResult(NAME, AREA, UNKNOWN,
                           "No ISSN on file to look the journal up in Crossref by.", evidence=ev)
    if not reached:
        return CheckResult(NAME, AREA, UNKNOWN, "Crossref could not be reached.", evidence=ev)

    value = {"issn": used, "dois": total, "with_references": refs,
             "rate": round(refs / total, 4) if total else None,
             "current_rate": round(current, 4) if current is not None else None,
             "current_dois": current_dois}

    if not total:
        return CheckResult(NAME, AREA, FAIL,
                           "No DOIs registered with Crossref under the journal's ISSNs.",
                           value=value, evidence=ev)

    rate = refs / total
    pct = f"{rate:.1%}"
    head = f"{total:,} DOI records; {refs:,} carry a reference list ({pct})"
    if not used:
        head += ". These DOIs were deposited without an ISSN"
    if current is not None and current_dois:
        head += f"; {current:.0%} of the {current_dois:,} recent ones do"
    if rate >= PASS_OVERALL or (current is not None and current_dois and current >= PASS_CURRENT):
        return CheckResult(NAME, AREA, PASS if used else WARN, head + ".", value=value, evidence=ev)
    return CheckResult(NAME, AREA, WARN, head + ".", value=value, evidence=ev)
