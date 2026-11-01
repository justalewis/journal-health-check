"""Continuity: when does the journal's domain registration expire, and with whom?

Source: RDAP, through the rdap.org bootstrap redirector. University and
publisher hosts are n/a: a journal at docs.lib.purdue.edu can't lose its
domain the way an editor-registered .org can.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import CONTINUITY, FAIL, NA, PASS, UNKNOWN, WARN, CheckResult
from ._common import evidence, parse_date

NAME = "rdap"
AREA = CONTINUITY
LABEL = "Domain registration"

API = "https://rdap.org/domain/{domain}"
WARN_DAYS = 90

# Second-level suffixes we meet in this field. Not a public suffix list, just
# enough that "journal.ac.uk" isn't read as the registrable domain "ac.uk".
TWO_PART_SUFFIXES = {
    "co.uk", "ac.uk", "org.uk", "edu.au", "com.au", "org.au", "ac.nz", "co.nz",
    "edu.pl", "com.pl", "org.pl", "edu.mk", "com.br", "edu.br", "ac.za", "co.za",
}
ACADEMIC_SUFFIXES = (".edu", ".ac.uk", ".edu.au", ".ac.nz", ".edu.pl", ".edu.br", ".ac.za")


def registrable_domain(host: str) -> str:
    labels = (host or "").lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in TWO_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _registrar(data: dict) -> str | None:
    for ent in data.get("entities") or []:
        if "registrar" in (ent.get("roles") or []):
            for item in (ent.get("vcardArray") or [None, []])[1]:
                if item and item[0] == "fn":
                    return item[3]
    return None


def run(journal, http, now: datetime | None = None) -> CheckResult:
    if not journal.host:
        return CheckResult(NAME, AREA, NA, "No web presence.")
    domain = registrable_domain(journal.host)
    if journal.platform == "publisher":
        return CheckResult(NAME, AREA, NA, f"Hosted by the publisher at {domain}.",
                           value={"domain": domain})
    if domain.endswith(ACADEMIC_SUFFIXES) or ("." + domain).endswith(ACADEMIC_SUFFIXES):
        return CheckResult(NAME, AREA, NA,
                           f"Hosted on a university domain ({domain}), which doesn't lapse "
                           "the way a privately registered one can.", value={"domain": domain})

    now = now or datetime.now(timezone.utc)
    r, data = http.get_json(API.format(domain=domain))
    if data is None:
        note = "RDAP has no record for this domain" if r.status == 404 else (r.error or "no answer")
        return CheckResult(NAME, AREA, UNKNOWN,
                           f"No registration data available for {domain}.",
                           value={"domain": domain}, evidence=[evidence(r, note=note)])

    events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events") or []}
    registrar = _registrar(data)
    excerpt = {"ldhName": data.get("ldhName"), "status": data.get("status"),
               "events": events, "registrar": registrar}
    ev = [evidence(r, excerpt=excerpt)]
    expires = parse_date(events.get("expiration"))
    value = {"domain": domain, "registrar": registrar,
             "expires": events.get("expiration"), "registered": events.get("registration")}

    if journal.site_lost:
        until = f" through {expires.strftime('%B')} {expires.day}, {expires.year}" if expires else ""
        return CheckResult(NAME, AREA, WARN,
                           f"{domain} is registered{until}, but it no longer serves the journal.",
                           value=value, evidence=ev)
    if not expires:
        return CheckResult(NAME, AREA, UNKNOWN,
                           f"{domain} is registered{' with ' + registrar if registrar else ''}, "
                           "but the registry doesn't publish an expiry date.",
                           value=value, evidence=ev)
    days = (expires - now).days
    value["days_left"] = days
    who = f" with {registrar}" if registrar else ""
    when = f"{expires.strftime('%B')} {expires.day}, {expires.year}"
    if days < 0:
        return CheckResult(NAME, AREA, FAIL, f"{domain} expired on {when}.", value=value, evidence=ev)
    if days < WARN_DAYS:
        return CheckResult(NAME, AREA, WARN, f"{domain} expires on {when}, in {days} days{who}.",
                           value=value, evidence=ev)
    return CheckResult(NAME, AREA, PASS, f"{domain} is registered{who} through {when}.",
                       value=value, evidence=ev)
