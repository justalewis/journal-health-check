"""The shape every check returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

PASS, WARN, FAIL, UNKNOWN, NA = "pass", "warn", "fail", "unknown", "na"
STATUSES = (PASS, WARN, FAIL, UNKNOWN, NA)

CONTINUITY, PRESERVATION, ACCESS = "continuity", "preservation", "access"
AREAS = (CONTINUITY, PRESERVATION, ACCESS)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Evidence:
    """One source consulted: where we looked and what we saw there.

    `excerpt` is the trimmed part of the response the status rests on (a
    JSON object, or a few lines of text). `sha256` fingerprints the full raw
    body, which stays in the local HTTP cache, so a published status can be
    matched to the exact response it came from.
    """

    url: str
    http_status: int | None = None
    excerpt: object = None
    sha256: str | None = None
    note: str | None = None


@dataclass
class CheckResult:
    check: str
    area: str
    status: str
    summary: str
    value: object = None
    evidence: list[Evidence] = field(default_factory=list)
    checked_at: str = field(default_factory=now_iso)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"bad status {self.status!r}")
        if self.area not in AREAS:
            raise ValueError(f"bad area {self.area!r}")

    def to_dict(self) -> dict:
        return asdict(self)
