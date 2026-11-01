"""Access: is the journal listed in the Directory of Open Access Journals?

Source: DOAJ's public search API, by ISSN, then by title as a fallback.
DOAJ lists only open-access journals, so subscription titles are n/a.
"""

from __future__ import annotations

from urllib.parse import quote

from ..models import ACCESS, NA, PASS, UNKNOWN, WARN, CheckResult
from ._common import evidence, issn_checksum_ok, journal_titles, titles_match

NAME = "doaj"
AREA = ACCESS
LABEL = "DOAJ listing"

API = "https://doaj.org/api/search/journals/{q}"


def _excerpt(rec: dict) -> dict:
    b = rec.get("bibjson", {})
    return {
        "id": rec.get("id"),
        "title": b.get("title"),
        "pissn": b.get("pissn"),
        "eissn": b.get("eissn"),
        "url": (b.get("ref") or {}).get("journal"),
        "preservation": [s if isinstance(s, str) else s.get("name")
                         for s in (b.get("preservation") or {}).get("service", []) or []],
        "seal": (rec.get("admin") or {}).get("seal"),
        "last_updated": rec.get("last_updated"),
    }


def run(journal, http) -> CheckResult:
    if not journal.is_open:
        return CheckResult(NAME, AREA, NA, "DOAJ lists open-access journals only.")

    ev, found, other = [], None, []
    for issn in [i for i in journal.issns if issn_checksum_ok(i)]:
        r, data = http.get_json(API.format(q=quote(f"issn:{issn}")))
        if data is None:
            ev.append(evidence(r, note=r.error or "DOAJ did not answer"))
            continue
        hits = data.get("results", [])
        ev.append(evidence(r, excerpt={"total": data.get("total"),
                                       "results": [_excerpt(h) for h in hits[:3]]}))
        for h in hits:
            if titles_match(journal_titles(journal), (h.get("bibjson") or {}).get("title")):
                found = found or h
            else:
                other.append(_excerpt(h))
        if found:
            break

    if not found:
        q = quote('bibjson.title:"' + journal.name.split(":")[0] + '"')
        r, data = http.get_json(API.format(q=q))
        if data is not None:
            hits = data.get("results", [])
            ev.append(evidence(r, excerpt={"total": data.get("total"),
                                           "results": [_excerpt(h) for h in hits[:5]]},
                               note="title search"))
            for h in hits:
                ex = _excerpt(h)
                # Title alone is too weak: "Praxis" matched Práxis Pedagógica.
                # A title-search hit counts only when it points at our host.
                same_host = journal.host and ex["url"] and journal.host.removeprefix("www.") in ex["url"]
                if same_host:
                    found = h
                    break
        else:
            ev.append(evidence(r, note=r.error or "DOAJ did not answer"))

    if not ev or all(e.http_status is None for e in ev):
        return CheckResult(NAME, AREA, UNKNOWN, "DOAJ could not be reached.", evidence=ev)

    if found:
        ex = _excerpt(found)
        extra = f" DOAJ records preservation with {', '.join(ex['preservation'])}." if ex["preservation"] else ""
        return CheckResult(NAME, AREA, PASS, f"Listed in DOAJ as “{ex['title']}”.{extra}",
                           value=ex, evidence=ev)
    if other:
        o = other[0]
        return CheckResult(NAME, AREA, WARN,
                           f"Not listed. The journal's ISSN matches a DOAJ record for a different "
                           f"title (“{o['title']}”), which is worth checking.",
                           value={"listed": False, "issn_collision": o}, evidence=ev)
    return CheckResult(NAME, AREA, WARN,
                       "Not listed in DOAJ. Open-access journals can apply for free.",
                       value={"listed": False}, evidence=ev)
