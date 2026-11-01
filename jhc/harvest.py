"""Run checks over journals and write a dated JSON snapshot."""

from __future__ import annotations

import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .checks import ACTIVE, BY_NAME
from .http import Http
from .journals import Journal, load_journals
from .models import UNKNOWN, CheckResult, Evidence, now_iso

log = logging.getLogger("jhc.harvest")


def run_one(module, journal: Journal, http: Http) -> CheckResult:
    try:
        return module.run(journal, http)
    except Exception as exc:  # a bug in one check must not sink the harvest
        log.exception("%s failed on %s", module.NAME, journal.slug)
        return CheckResult(module.NAME, module.AREA, UNKNOWN,
                           "The check itself failed; this is our error, not the journal's.",
                           evidence=[Evidence(url="", note=f"{type(exc).__name__}: {exc}",
                                              excerpt=traceback.format_exc(limit=3)[-800:])])


def harvest(journals: list[Journal], checks=None, http: Http | None = None,
            workers: int = 6, progress=None) -> list[dict]:
    http = http or Http()
    checks = checks or ACTIVE
    out = []
    jobs = [(m, j) for j in journals for m in checks]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(run_one, m, j, http): (m, j) for m, j in jobs}
        for fut in as_completed(futs):
            m, j = futs[fut]
            res = fut.result()
            out.append({"slug": j.slug, **res.to_dict()})
            if progress:
                progress(j, res)
    order = {m.NAME: i for i, m in enumerate(ACTIVE)}
    out.sort(key=lambda r: (r["slug"], order.get(r["check"], 99)))
    return out


def snapshot_path(label: str, snapshot_dir: Path | None = None) -> Path:
    return Path(snapshot_dir or config.SNAPSHOT_DIR) / f"{label}.json"


def write_snapshot(label: str, journals: list[Journal], results: list[dict],
                   started_at: str, snapshot_dir: Path | None = None,
                   merge: bool = True) -> Path:
    """Write snapshots/{label}.json. A partial run (one journal, one check)
    merges into an existing snapshot for the same month instead of replacing it."""
    path = snapshot_path(label, snapshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if merge and path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        existing = {(r["slug"], r["check"]): r for r in old.get("results", [])}
        started_at = old.get("started_at") or started_at
    for r in results:
        existing[(r["slug"], r["check"])] = r
    live = {j.slug for j in journals}
    merged = [r for k, r in sorted(existing.items()) if k[0] in live]
    snap = {
        "label": label,
        "started_at": started_at,
        "finished_at": now_iso(),
        "journals": [asdict(j) for j in journals],
        "results": merged,
    }
    path.write_text(json.dumps(snap, indent=1, ensure_ascii=False, default=str) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def current_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def select(journal_slugs=None, check_names=None):
    journals = load_journals()
    if journal_slugs:
        want = set(journal_slugs)
        unknown = want - {j.slug for j in journals}
        if unknown:
            raise SystemExit(f"unknown journal slug(s): {', '.join(sorted(unknown))}")
        sel = [j for j in journals if j.slug in want]
    else:
        sel = journals
    checks = None
    if check_names:
        bad = [c for c in check_names if c not in BY_NAME]
        if bad:
            raise SystemExit(f"unknown check(s): {', '.join(bad)}; choose from {', '.join(BY_NAME)}")
        checks = [BY_NAME[c] for c in check_names]
    return journals, sel, checks
