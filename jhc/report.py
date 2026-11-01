"""Read the database into the shapes the pages need. No scoring formula
beyond counting: each area is "passes out of the checks that applied"."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict

from .checks import ACTIVE
from .models import AREAS, FAIL, NA, PASS, UNKNOWN, WARN

CHECK_ORDER = [m.NAME for m in ACTIVE]
CHECKS_BY_AREA = {a: [m for m in ACTIVE if m.AREA == a] for a in AREAS}


def latest_run(conn: sqlite3.Connection):
    return conn.execute("SELECT * FROM runs ORDER BY label DESC LIMIT 1").fetchone()


def runs(conn):
    return conn.execute("SELECT * FROM runs ORDER BY label").fetchall()


def journals(conn) -> dict[str, dict]:
    rows = conn.execute("SELECT data FROM journals ORDER BY name").fetchall()
    out = {}
    for r in rows:
        j = json.loads(r["data"])
        out[j["slug"]] = j
    return out


def _row(r) -> dict:
    return {"check": r["check_name"], "area": r["area"], "status": r["status"],
            "summary": r["summary"], "value": json.loads(r["value"]) if r["value"] else None,
            "evidence": json.loads(r["evidence"]) if r["evidence"] else [],
            "checked_at": r["checked_at"]}


def results(conn, run_id: int) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in conn.execute("SELECT * FROM results WHERE run_id=?", (run_id,)):
        out[r["slug"]][r["check_name"]] = _row(r)
    return out


def area_score(checks: dict[str, dict], area: str) -> dict:
    sts = [checks[m.NAME]["status"] for m in CHECKS_BY_AREA[area] if m.NAME in checks]
    c = Counter(sts)
    applicable = c[PASS] + c[WARN] + c[FAIL]
    return {"pass": c[PASS], "warn": c[WARN], "fail": c[FAIL], "unknown": c[UNKNOWN],
            "na": c[NA], "applicable": applicable,
            # Sort key for the table: share passed, with unknowns last.
            "sort": (c[PASS] / applicable) if applicable else -1}


def field_totals(res: dict[str, dict[str, dict]]) -> dict:
    per_check = {name: Counter() for name in CHECK_ORDER}
    for checks in res.values():
        for name, row in checks.items():
            if name in per_check:
                per_check[name][row["status"]] += 1
    return per_check


def history(conn, slug: str) -> dict[str, list[dict]]:
    out = defaultdict(list)
    q = """SELECT runs.label, results.* FROM results JOIN runs ON runs.id = results.run_id
           WHERE slug=? ORDER BY runs.label"""
    for r in conn.execute(q, (slug,)):
        out[r["check_name"]].append({"label": r["label"], "status": r["status"],
                                     "summary": r["summary"]})
    return out
