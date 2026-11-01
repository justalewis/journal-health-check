"""The public site. Server-rendered, read-only, one SQLite file."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, Response, abort, g, jsonify, render_template, request, send_file

from jhc import config, report
from jhc.checks import ACTIVE, ALL_BY_NAME, PLANNED
from jhc.db import connect
from jhc.models import AREAS

START = time.time()

STATUS_LABEL = {"pass": "Met", "warn": "Check", "fail": "Not met", "unknown": "Unknown", "na": "n/a"}
STATUS_ICON = {"pass": "✓", "warn": "!", "fail": "✕", "unknown": "?", "na": "–"}
AREA_LABEL = {"continuity": "Continuity", "preservation": "Preservation", "access": "Access"}
STATUS_RANK = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3, "na": 4}


def _version() -> str:
    v = os.environ.get("FLY_RELEASE_VERSION") or os.environ.get("FLY_MACHINE_VERSION")
    if v:
        return v
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, cwd=config.ROOT).decode().strip()
    except Exception:
        return "dev"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(config.ROOT / "static"), static_url_path="/static")
    version = _version()

    def db():
        if "db" not in g:
            g.db = connect()
        return g.db

    @app.teardown_appcontext
    def _close(exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.context_processor
    def globals_():
        return {
            "site_name": config.SITE_NAME, "site_tagline": config.SITE_TAGLINE,
            "base_url": config.BASE_URL, "canonical": config.BASE_URL + request.path,
            "eunomia_url": config.EUNOMIA_URL, "pinakes_url": config.PINAKES_URL,
            "STATUS_LABEL": STATUS_LABEL, "STATUS_ICON": STATUS_ICON, "AREA_LABEL": AREA_LABEL,
            "AREAS": AREAS, "CHECKS_BY_AREA": report.CHECKS_BY_AREA, "version": version,
            "nav": request.endpoint,
            # Shown on the index until the first harvest has been reviewed by hand.
            "preview": os.environ.get("JHC_PREVIEW_NOTICE", "1") != "0",
        }

    @app.template_filter("pinakes_link")
    def pinakes_link(name: str) -> str:
        return f"{config.PINAKES_URL}/?journal={quote_plus(name)}"

    @app.template_filter("fmt_date")
    def fmt_date(iso: str | None) -> str:
        if not iso:
            return ""
        from datetime import datetime
        d = datetime.fromisoformat(iso)
        return f"{d.strftime('%B')} {d.day}, {d.year}"

    @app.template_filter("pretty")
    def pretty(obj) -> str:
        return json.dumps(obj, indent=1, ensure_ascii=False, default=str)

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; "
            "script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if config.BASE_URL.startswith("https://"):
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return resp

    # -- pages ------------------------------------------------------------

    def _load():
        conn = db()
        run = report.latest_run(conn)
        if run is None:
            return conn, None, {}, {}
        return conn, run, report.journals(conn), report.results(conn, run["id"])

    @app.route("/")
    def index():
        conn, run, js, res = _load()
        rows = []
        for slug, j in js.items():
            checks = res.get(slug, {})
            rows.append({"j": j, "checks": checks,
                         "areas": {a: report.area_score(checks, a) for a in AREAS}})
        rows.sort(key=lambda r: (r["j"].get("short") or r["j"]["name"]).lower().removeprefix("the "))
        totals = report.field_totals(res)
        return render_template("index.html", run=run, rows=rows, totals=totals,
                               checks=ACTIVE, n_journals=len(js), STATUS_RANK=STATUS_RANK)

    @app.route("/journal/<slug>")
    def journal(slug):
        conn, run, js, res = _load()
        j = js.get(slug)
        if not j:
            abort(404)
        checks = res.get(slug, {})
        return render_template("journal.html", run=run, j=j, checks=checks,
                               areas={a: report.area_score(checks, a) for a in AREAS},
                               hist=report.history(conn, slug), runs=report.runs(conn),
                               modules={m.NAME: m for m in ACTIVE})

    @app.route("/methods")
    def methods():
        return render_template("methods.html", active=ACTIVE, planned=PLANNED,
                               run=report.latest_run(db()))

    @app.route("/about")
    def about():
        return render_template("about.html")

    # -- data -------------------------------------------------------------

    @app.route("/data/latest.json")
    def latest_json():
        files = sorted(config.SNAPSHOT_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].json"))
        if not files:
            abort(404)
        return send_file(files[-1], mimetype="application/json", max_age=3600)

    @app.route("/data/<label>.json")
    def snapshot_json(label):
        if len(label) != 7 or label[4] != "-" or not label.replace("-", "").isdigit():
            abort(404)
        p = config.SNAPSHOT_DIR / f"{label}.json"
        if not p.exists():
            abort(404)
        return send_file(p, mimetype="application/json", max_age=3600)

    @app.route("/robots.txt")
    def robots():
        body = f"User-agent: *\nAllow: /\nSitemap: {config.BASE_URL}/sitemap.xml\n"
        return Response(body, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap():
        urls = ["/", "/methods", "/about"] + [f"/journal/{s}" for s in report.journals(db())]
        body = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        body += [f"<url><loc>{config.BASE_URL}{u}</loc></url>" for u in urls]
        body.append("</urlset>")
        return Response("\n".join(body), mimetype="application/xml")

    # -- health (the Pinakes pattern: liveness without the DB, readiness with it)

    @app.route("/health")
    def health():
        return jsonify(status="ok", version=version, uptime_seconds=round(time.time() - START, 3))

    @app.route("/health/ready")
    def ready():
        path = Path(config.DB_PATH)
        if not path.exists():
            return jsonify(status="degraded", db=f"missing: {path.name}"), 503
        try:
            conn = connect()
            conn.execute("PRAGMA busy_timeout=250")
            run = conn.execute("SELECT label FROM runs ORDER BY label DESC LIMIT 1").fetchone()
            conn.close()
        except Exception as exc:  # noqa: BLE001
            return jsonify(status="degraded", db=str(exc)), 503
        if run is None:
            return jsonify(status="degraded", db="no harvest runs loaded"), 503
        return jsonify(status="ok", db="reachable", latest_run=run["label"])

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    return app
