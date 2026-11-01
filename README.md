# Journal Health Check

A monthly report card for rhetoric and composition journals, covering three areas:

- **continuity:** domain registration and the HTTPS certificate
- **preservation:** Keepers Registry holdings and Wayback captures
- **access:** ISSN, DOAJ, OpenAlex, and Crossref DOI and reference deposits

Each check stores the response it relied on. Each journal's page shows that evidence next to the result. The journal list comes from Pinakes. The design comes from Eunomia's Labors (the Alexandrian Suite), vendored in `static/vendor/`.

The working name lives in one place, `SITE_NAME` in `jhc/config.py`. The public hostname lives in one place too, `BASE_URL` in the environment (see `fly.toml`).

## Layout

```
jhc/            harvester package
  checks/       one module per check: NAME, AREA, LABEL, run(journal, http) -> CheckResult
  http.py       polite HTTP: per-host spacing, retries, 20-day file cache in .cache/
  harvest.py    runs checks, writes snapshots/YYYY-MM.json
  db.py         rebuilds jhc.db from every snapshot
app/            Flask site (server-rendered, read-only)
data/journals.yaml   the journal list, curated by hand
snapshots/      one JSON file per monthly harvest; this is the record
scripts/sync_journals.py   report Pinakes titles missing from journals.yaml
```

Phase 1 checks: `tls`, `rdap`, `keepers`, `wayback`, `issn`, `doaj`, `openalex`, `crossref`.
The Phase 2 and 3 checks (`homepage`, `pkp_pn`, `link_rot`, `pdf_a11y`, `html_a11y`, `succession`) are stubs.

## Running it

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m jhc harvest                       # all journals, all checks, this month
python -m jhc harvest --journal peitho --check doaj   # merges into this month's snapshot
python -m jhc build-db
flask --app wsgi:app run
```

Set `JHC_CONTACT_EMAIL` to put a contact address in the User-Agent and in Crossref's `mailto` parameter. Without it, no address is sent.

## Deploying

`fly.toml` and the `Dockerfile` target the Fly app `journal-health-check`. The image builds `jhc.db` from `snapshots/` at build time, so it needs no volume. `.github/workflows/harvest.yml` runs the harvest on the 1st of each month and commits the snapshot. It deploys only when the repository variable `DEPLOY_ENABLED` is `true`.

First deployed to https://journal-health-check.fly.dev/ on 2026-11-01. No GitHub remote exists yet, so the workflow hasn't run.
