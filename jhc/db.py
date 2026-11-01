"""SQLite store. The database is always rebuilt from the JSON snapshots in
snapshots/, which are the record; the .db file is a disposable index of them.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    label       TEXT UNIQUE NOT NULL,      -- YYYY-MM
    started_at  TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS journals (
    slug  TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    data  TEXT NOT NULL                    -- JSON of the journals.yaml entry
);
CREATE TABLE IF NOT EXISTS results (
    run_id     INTEGER NOT NULL REFERENCES runs(id),
    slug       TEXT NOT NULL,
    check_name TEXT NOT NULL,
    area       TEXT NOT NULL,
    status     TEXT NOT NULL,
    summary    TEXT NOT NULL,
    value      TEXT,
    evidence   TEXT,
    checked_at TEXT,
    PRIMARY KEY (run_id, slug, check_name)
);
CREATE INDEX IF NOT EXISTS results_slug ON results(slug, check_name);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def snapshot_files(snapshot_dir: Path | None = None) -> list[Path]:
    d = Path(snapshot_dir or config.SNAPSHOT_DIR)
    return sorted(d.glob("*.json"))


def build(db_path: Path | None = None, snapshot_dir: Path | None = None) -> int:
    """Rebuild the database from every snapshot. Returns the number of runs."""
    db_path = Path(db_path or config.DB_PATH)
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    conn.executescript(SCHEMA)
    files = snapshot_files(snapshot_dir)
    latest_journals = []
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        cur = conn.execute("INSERT INTO runs(label, started_at, finished_at) VALUES (?,?,?)",
                           (snap["label"], snap.get("started_at"), snap.get("finished_at")))
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)",
            [(run_id, r["slug"], r["check"], r["area"], r["status"], r["summary"],
              json.dumps(r.get("value")), json.dumps(r.get("evidence")), r.get("checked_at"))
             for r in snap["results"]])
        latest_journals = snap["journals"]
    conn.executemany("INSERT INTO journals VALUES (?,?,?)",
                     [(j["slug"], j["name"], json.dumps(j)) for j in latest_journals])
    conn.commit()
    conn.close()
    tmp.replace(db_path)
    return len(files)
