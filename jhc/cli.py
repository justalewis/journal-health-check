"""jhc: the harvester command line.

    jhc harvest [--journal SLUG ...] [--check NAME ...] [--fresh] [--label YYYY-MM]
    jhc build-db
    jhc list
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import config, db
from .checks import ACTIVE
from .harvest import current_label, harvest, select, write_snapshot
from .http import Http
from .models import now_iso

GLYPH = {"pass": "+", "warn": "!", "fail": "x", "unknown": "?", "na": "-"}


def cmd_harvest(args) -> int:
    journals, sel, checks = select(args.journal, args.check)
    http = Http(use_cache=not args.fresh)
    started = now_iso()
    n = len(sel) * len(checks or ACTIVE)
    done = [0]

    def progress(j, res):
        done[0] += 1
        if not args.quiet:
            print(f"[{done[0]:>4}/{n}] {GLYPH[res.status]} {res.check:<9} {j.slug:<45} {res.summary[:90]}",
                  flush=True)

    results = harvest(sel, checks, http=http, workers=args.workers, progress=progress)
    label = args.label or current_label()
    path = write_snapshot(label, journals, results, started)
    print(f"wrote {path}")
    runs = db.build()
    print(f"rebuilt {config.DB_PATH} from {runs} snapshot(s)")
    return 0


def cmd_build_db(args) -> int:
    runs = db.build()
    print(f"rebuilt {config.DB_PATH} from {runs} snapshot(s)")
    return 0


def cmd_list(args) -> int:
    journals, _, _ = select()
    for j in journals:
        print(f"{j.slug:<50} {j.status:<11} {', '.join(j.issns) or '(no ISSN)'}")
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="jhc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="run checks and write this month's snapshot")
    h.add_argument("--journal", action="append", metavar="SLUG")
    h.add_argument("--check", action="append", metavar="NAME")
    h.add_argument("--fresh", action="store_true", help="ignore the HTTP cache")
    h.add_argument("--label", help="snapshot label, default this month (YYYY-MM)")
    h.add_argument("--workers", type=int, default=6)
    h.add_argument("--quiet", action="store_true")
    h.set_defaults(func=cmd_harvest)

    b = sub.add_parser("build-db", help="rebuild the SQLite file from snapshots/")
    b.set_defaults(func=cmd_build_db)

    ls = sub.add_parser("list", help="list journals in data/journals.yaml")
    ls.set_defaults(func=cmd_list)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
