"""Preservation: how recently did the Internet Archive capture the journal's home page?

Source: the Wayback Machine CDX API. The home page is fetched first so that
a redirect (licsjournal.org/ to its OJS path, say) is followed and the
capture we count is of the page readers actually land on.

Phase 1 looks at the home page only. The latest-issue page needs a
per-journal issue URL, which comes with the Phase 2 issue-date work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

from ..models import FAIL, NA, PASS, PRESERVATION, UNKNOWN, WARN, CheckResult, Evidence
from ._common import evidence, parse_date
from .rdap import registrable_domain

NAME = "wayback"
AREA = PRESERVATION
LABEL = "Wayback capture"

CDX = "https://web.archive.org/cdx/search/cdx"
FRESH_DAYS = 180
STALE_DAYS = 730


def _cdx_key(url: str) -> str:
    p = urlsplit(url)
    return (p.hostname or "") + (p.path or "/") + (f"?{p.query}" if p.query else "")


def latest_capture(http, url: str):
    r, data = http.get_json(CDX, params={"url": _cdx_key(url), "output": "json",
                                         "fl": "timestamp,statuscode,original",
                                         "filter": "statuscode:200", "limit": "-1",
                                         "fastLatest": "true"})
    if data is None:
        if r.ok and not r.text.strip():
            return r, None, True     # empty body: no captures at all
        return r, None, False
    rows = [row for row in data[1:] if row]
    if not rows:
        return r, None, True
    ts = max(row[0] for row in rows)
    return r, ts, True


def run(journal, http, now: datetime | None = None) -> CheckResult:
    if not journal.home_url:
        return CheckResult(NAME, AREA, NA, "No web presence to capture.")
    if journal.platform == "publisher":
        return CheckResult(NAME, AREA, NA,
                           "Hosted on a publisher's platform, where the Keepers check is a better "
                           "guide to preservation than captures of a landing page.")
    now = now or datetime.now(timezone.utc)

    ev = []
    home = http.get(journal.home_url)
    landing = home.final_url if home.ok and home.final_url else None
    note = None
    if home.status in (401, 403, 429):
        note = f"the site answered {home.status} to an automated request, so redirects weren't followed"
    elif home.status is None:
        note = f"the home page did not answer ({home.error})"
    ev.append(Evidence(url=journal.home_url, http_status=home.status,
                       excerpt={"final_url": home.final_url}, note=note))

    candidates = [journal.home_url]
    if landing and _cdx_key(landing) != _cdx_key(journal.home_url):
        same_site = registrable_domain(urlsplit(landing).hostname or "") == \
            registrable_domain(journal.host or "")
        # A ceased journal whose domain now lands somewhere else: the new
        # site's captures are not this journal's.
        if same_site or not journal.is_ceased:
            candidates.insert(0, landing)

    best, reached = None, False
    for url in candidates:
        r, ts, ok = latest_capture(http, url)
        reached = reached or ok
        ev.append(evidence(r, excerpt={"url": _cdx_key(url), "latest_200": ts}))
        if ts and (best is None or ts > best[1]):
            best = (url, ts)

    if not reached:
        return CheckResult(NAME, AREA, UNKNOWN, "The Wayback Machine could not be reached.", evidence=ev)
    if best is None:
        return CheckResult(NAME, AREA, FAIL, "The Wayback Machine holds no successful capture of the home page.",
                           value=None, evidence=ev)

    when = parse_date(best[1])
    age = (now - when).days
    value = {"url": best[0], "timestamp": best[1], "age_days": age,
             "snapshot": f"https://web.archive.org/web/{best[1]}/{best[0]}"}
    head = f"Last captured {when.strftime('%B')} {when.day}, {when.year} ({age:,} days ago)"

    if journal.is_ceased:
        why = "has ceased" if journal.status == "ceased" else "is no longer online"
        return CheckResult(NAME, AREA, PASS, head + f". The journal {why}, so any capture counts.",
                           value=value, evidence=ev)
    if age <= FRESH_DAYS:
        return CheckResult(NAME, AREA, PASS, head + ".", value=value, evidence=ev)
    if age <= STALE_DAYS:
        return CheckResult(NAME, AREA, WARN, head + ".", value=value, evidence=ev)
    return CheckResult(NAME, AREA, FAIL, head + ".", value=value, evidence=ev)
