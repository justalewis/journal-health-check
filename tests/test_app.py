import json

import pytest

from jhc import config, db
from jhc.harvest import write_snapshot
from jhc.journals import Journal
from jhc.models import CheckResult


@pytest.fixture
def client(tmp_path, monkeypatch, lics):
    snaps = tmp_path / "snapshots"
    monkeypatch.setattr(config, "SNAPSHOT_DIR", snaps)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "BASE_URL", "https://example.test")
    res = [{"slug": lics.slug, **CheckResult("tls", "continuity", "pass", "ok").to_dict()},
           {"slug": lics.slug, **CheckResult("keepers", "preservation", "fail", "none").to_dict()}]
    write_snapshot("2026-11", [lics], res, "2026-11-01T00:00:00+00:00", snapshot_dir=snaps)
    db.build(tmp_path / "t.db", snaps)
    from app import create_app
    return create_app().test_client()


def test_index_lists_journal(client):
    html = client.get("/").get_data(as_text=True)
    assert "LiCS" in html and 'href="https://example.test/"' in html


def test_journal_page(client, lics):
    html = client.get(f"/journal/{lics.slug}").get_data(as_text=True)
    assert "HTTPS certificate" in html and "Keepers Registry" in html
    assert "pinakes.wacclearinghouse.org/?journal=Literacy+in+Composition+Studies" in html


def test_static_pages_and_404(client):
    assert client.get("/methods").status_code == 200
    assert client.get("/about").status_code == 200
    assert client.get("/journal/nope").status_code == 404


def test_health(client):
    assert client.get("/health").json["status"] == "ok"
    assert client.get("/health/ready").json["latest_run"] == "2026-11"


def test_sitemap_uses_base_url(client):
    body = client.get("/sitemap.xml").get_data(as_text=True)
    assert "https://example.test/journal/literacy-in-composition-studies" in body
    assert "fly.dev" not in body


def test_latest_json(client):
    assert json.loads(client.get("/data/latest.json").get_data())["label"] == "2026-11"


def test_no_hardcoded_fly_hostname():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for p in list((root / "app").rglob("*")) + list((root / "jhc").rglob("*.py")):
        if p.is_file() and p.suffix in (".py", ".html", ".js", ".css"):
            assert "fly.dev" not in p.read_text(encoding="utf-8"), p


def test_partial_snapshot_merges(tmp_path, lics):
    other = Journal(name="Peitho", issn_online="2169-0774")
    a = {"slug": lics.slug, **CheckResult("tls", "continuity", "pass", "a").to_dict()}
    b = {"slug": other.slug, **CheckResult("tls", "continuity", "warn", "b").to_dict()}
    write_snapshot("2026-11", [lics, other], [a, b], "t", snapshot_dir=tmp_path)
    a2 = {**a, "status": "fail", "summary": "a2"}
    p = write_snapshot("2026-11", [lics, other], [a2], "t", snapshot_dir=tmp_path)
    snap = json.loads(p.read_text(encoding="utf-8"))
    by = {(r["slug"], r["check"]): r for r in snap["results"]}
    assert by[(lics.slug, "tls")]["status"] == "fail"
    assert by[(other.slug, "tls")]["status"] == "warn"
