"""Preservation: does any archiving agency in the Keepers Registry hold the journal?

Source: the Keepers holdings embedded in each ISSN's portal.issn.org record.
Holdings usually sit on the online ISSN, so every ISSN the journal uses is
read and the results pooled.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import FAIL, NA, PASS, PRESERVATION, UNKNOWN, WARN, CheckResult
from ._common import evidence, fetch_portal_record, issn_checksum_ok, journal_titles, titles_match

NAME = "keepers"
AREA = PRESERVATION
LABEL = "Keepers Registry"

# Coverage that stops more than this many years ago reads as "preserved once".
STALE_YEARS = 3


def _year(v) -> int | None:
    try:
        return int(str(v)[:4])
    except (TypeError, ValueError):
        return None


def run(journal, http) -> CheckResult:
    issns = [i for i in journal.issns if issn_checksum_ok(i)]
    if not issns:
        if journal.platform == "none":
            return CheckResult(NAME, AREA, NA, "Print-only journal with no ISSN on file.")
        return CheckResult(NAME, AREA, UNKNOWN,
                           "No ISSN on file, and the Keepers Registry is searched by ISSN.")

    ev, holdings, reached = [], [], 0
    for issn in issns:
        r, rec = fetch_portal_record(http, issn)
        if rec is None:
            ev.append(evidence(r, note=r.error or "no ISSN Portal record"))
            continue
        title = rec.get("key_title") or rec["page_title"]
        if not titles_match(journal_titles(journal), title):
            # Holdings on a record for some other serial say nothing about this one.
            ev.append(evidence(r, note=f"skipped: {issn} is registered to “{title}”"))
            continue
        reached += 1
        ks = rec.get("keepers") or []
        ev.append(evidence(r, excerpt=[{k: h.get(k) for k in ("keeper", "status", "from_", "to",
                                                             "last_updated_at")} for h in ks]
                           or "no Keepers holdings on this record"))
        for h in ks:
            holdings.append({**h, "issn": issn})

    if not reached:
        return CheckResult(NAME, AREA, UNKNOWN,
                           "No ISSN record for this journal could be read, so its holdings are unknown.",
                           evidence=ev)

    keepers = {}
    for h in holdings:
        k = keepers.setdefault(h.get("keeper") or "?", {"preserved_to": None, "statuses": set()})
        k["statuses"].add(h.get("status") or "?")
        if (h.get("status") or "").lower() == "preserved":
            y = _year(h.get("to"))
            if y and (k["preserved_to"] is None or y > k["preserved_to"]):
                k["preserved_to"] = y
    value = {name: {"preserved_to": v["preserved_to"], "statuses": sorted(v["statuses"])}
             for name, v in sorted(keepers.items())}

    if not keepers:
        return CheckResult(NAME, AREA, FAIL,
                           "No archiving agency reports holding this journal.",
                           value={}, evidence=ev)

    preserved = {n: v for n, v in keepers.items() if v["preserved_to"]}
    names = ", ".join(sorted(keepers))
    if not preserved:
        return CheckResult(NAME, AREA, WARN,
                           f"Listed with {names}, but nothing is marked preserved yet.",
                           value=value, evidence=ev)

    latest = max(v["preserved_to"] for v in preserved.values())
    this_year = datetime.now(timezone.utc).year
    if not journal.is_ceased and latest < this_year - STALE_YEARS:
        return CheckResult(NAME, AREA, WARN,
                           f"Held by {names}, but preserved coverage ends in {latest}.",
                           value=value, evidence=ev)
    return CheckResult(NAME, AREA, PASS,
                       f"Held by {len(keepers)} agenc{'y' if len(keepers) == 1 else 'ies'} "
                       f"({names}); preserved through {latest}.",
                       value=value, evidence=ev)
