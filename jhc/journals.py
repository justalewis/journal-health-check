"""The journal list, read from data/journals.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from . import config


def slugify(name: str) -> str:
    # Same rule as Pinakes, so slugs line up across the two sites.
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


@dataclass
class Journal:
    name: str
    slug: str = ""
    short: str | None = None
    issn_print: str | None = None
    issn_online: str | None = None
    # The ISSN Crossref indexes the journal's DOIs under, when it differs
    # from what a plain lookup would pick (carried over from Pinakes).
    crossref_issn: str | None = None
    # DOIs deposited without any ISSN (WLN) can only be found by prefix +
    # container title. Rare; set by hand.
    crossref_prefix: str | None = None
    crossref_container: str | None = None
    home_url: str | None = None
    platform: str | None = None          # ojs, wordpress, drupal, digital-commons, bespoke, publisher, none
    publisher: str | None = None
    host_institution: str | None = None
    oa: str | None = None                # gold, bronze, hybrid, subscription
    webtext: bool = False
    status: str = "active"               # active, dormant, ceased, unavailable
    start_year: int | None = None
    end_year: int | None = None
    group: str | None = None
    in_pinakes: bool = True
    notes: str | None = None
    issn_note: str | None = None
    alt_titles: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.slug:
            self.slug = slugify(self.name)

    @property
    def display(self) -> str:
        return self.short or self.name

    @property
    def issns(self) -> list[str]:
        seen = []
        for i in (self.issn_online, self.issn_print, self.crossref_issn):
            if i and i not in seen:
                seen.append(i)
        return seen

    @property
    def host(self) -> str | None:
        if not self.home_url:
            return None
        return urlsplit(self.home_url).hostname

    @property
    def is_open(self) -> bool:
        return self.oa in ("gold", "bronze", "diamond")

    @property
    def is_ceased(self) -> bool:
        return self.status in ("ceased", "unavailable")


def load_journals(path: Path | None = None) -> list[Journal]:
    path = Path(path or config.JOURNALS_PATH)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for entry in raw.get("journals", []):
        out.append(Journal(**entry))
    slugs = [j.slug for j in out]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        raise ValueError(f"duplicate journal slugs in {path}: {sorted(dupes)}")
    return out


def by_slug(journals: list[Journal]) -> dict[str, Journal]:
    return {j.slug: j for j in journals}
