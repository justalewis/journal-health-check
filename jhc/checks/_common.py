"""Helpers shared by more than one check."""

from __future__ import annotations

import html as htmllib
import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher

from ..http import Http, Response
from ..models import Evidence

# -- ISSNs ------------------------------------------------------------------

ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")


def issn_checksum_ok(issn: str) -> bool:
    if not ISSN_RE.match(issn or ""):
        return False
    digits = issn.replace("-", "")
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    return digits[7] == ("X" if check == 10 else str(check))


# -- Titles -----------------------------------------------------------------

_STOP_LEADING = ("the ", "a ")


def norm_title(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    t = t.lower().replace("&", " and ")
    t = re.sub(r"\((online|print|en ligne|imprime)[^)]*\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    for s in _STOP_LEADING:
        if t.startswith(s):
            t = t[len(s):]
    return t


def main_title(t: str | None) -> str:
    """The part before a subtitle colon: 'Kairos: A Journal of...' -> 'Kairos'."""
    return norm_title(re.split(r"[:(]", t or "", maxsplit=1)[0])


def titles_match(ours: list[str], theirs: str | None) -> bool:
    """Loose enough for 'Peitho.' vs 'Peitho' or 'BWe basic writing e-journal'
    vs 'Basic Writing e-Journal'; strict enough that 'Forum (Conference on
    College Composition and Communication)' does not match 'Composition Forum'.
    """
    if not theirs:
        return False
    t_full, t_main = norm_title(theirs), main_title(theirs)
    for o in ours:
        o_full, o_main = norm_title(o), main_title(o)
        if not o_main:
            continue
        if t_full == o_full or t_main == o_main:
            return True
        if t_full.startswith(o_full) or (o_full.startswith(t_full) and len(t_full) >= 8):
            return True
        if t_full.startswith(o_main + " ") and len(o_main) >= 6:
            return True
        if SequenceMatcher(None, t_full, o_full).ratio() >= 0.85:
            return True
        if SequenceMatcher(None, t_main, o_main).ratio() >= 0.9:
            return True
    return False


def journal_titles(journal) -> list[str]:
    names = [journal.name]
    if journal.short:
        names.append(journal.short)
    names += list(getattr(journal, "alt_titles", None) or [])
    return names


# -- Evidence ---------------------------------------------------------------

def evidence(r: Response, excerpt=None, note: str | None = None) -> Evidence:
    return Evidence(url=r.url, http_status=r.status, excerpt=excerpt,
                    sha256=r.sha256, note=note or r.error)


def trim(d: dict, keys) -> dict:
    return {k: d.get(k) for k in keys if k in d}


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y%m%d%H%M%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def days_until(d: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return (d - now).days


# -- ISSN Portal record pages -------------------------------------------------
# The portal's public record page carries both the registration data (key
# title, ISSN-L, medium) and, in an inline script, the Keepers Registry
# holdings for that ISSN. The ISSN and Keepers checks both read it, and the
# HTTP cache means the page is fetched once per harvest.

PORTAL = "https://portal.issn.org/resource/ISSN/{issn}"

_LABELS = ["Key title", "ISSN-L", "Title proper", "Publication Medium",
           "Country", "Latest publisher", "Earliest publisher", "Other media",
           "Dates of publication"]


def _page_text(h: str) -> str:
    t = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t))


def fetch_portal_record(http: Http, issn: str) -> tuple[Response, dict | None]:
    r = http.get(PORTAL.format(issn=issn))
    if not r.ok:
        return r, None
    return r, parse_portal_record(r.text, issn)


def parse_portal_record(h: str, issn: str) -> dict | None:
    m = re.search(r"<title>\s*ISSN\s+" + re.escape(issn) + r"\s*-\s*([^<]+)</title>", h)
    if not m:
        return None
    rec = {"issn": issn, "page_title": htmllib.unescape(m.group(1)).strip()}
    text = _page_text(h)
    start = text.find("Displaying")
    body = text[start:] if start >= 0 else text
    rs = re.search(r"\b(Confirmed|Provisional|Legacy|Register|Suppressed|Cancelled|Unreported|Validated)\s+record", body)
    rec["record_status"] = rs.group(1) if rs else None
    label_alt = "|".join(re.escape(x) for x in _LABELS + ["Titles", "Identifiers", "Copy permalink",
                                                          "Title variant", "Title variants", "Online",
                                                          "Search in", "Record Last modified", "Type",
                                                          "Frequency", "Issuing body", "Intervening publisher",
                                                          "Incorrect ISSN", "CODEN", "ISSN-H", "Language"])
    for label in _LABELS:
        mm = re.search(re.escape(label) + r"\s*:\s*(.+?)(?=\s(?:" + label_alt + r")\b|$)", body)
        if mm:
            rec[label.lower().replace(" ", "_").replace("-", "_")] = mm.group(1).strip()[:300]
    lm = re.search(r"Record Last modified:\s*(\d{4}/\d{2}/\d{2})", body)
    rec["last_modified"] = lm.group(1) if lm else None
    il = re.search(r"ISSN-L:\s*(\d{4}-\d{3}[\dX])", body)
    rec["issn_l"] = il.group(1) if il else None
    km = re.search(r"const recordKeepers = (\[.*?\]);</script>", h, flags=re.S)
    try:
        rec["keepers"] = json.loads(km.group(1)) if km else None
    except ValueError:
        rec["keepers"] = None
    return rec
