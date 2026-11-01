"""Site-wide settings, all overridable from the environment.

The site's name lives here and nowhere else, so renaming it (the Greek-name
decision is still open) is a one-line change. Every absolute URL the app emits
is built from BASE_URL; nothing in the code names a Fly hostname.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SITE_NAME = os.environ.get("SITE_NAME", "Rhet-Comp Journal Accessibility Health Dashboard")
SITE_TAGLINE = os.environ.get(
    "SITE_TAGLINE", "Continuity, preservation and access for Rhet/Comp journals"
)

# No trailing slash. Local default keeps canonical tags honest in dev.
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000").rstrip("/")

DB_PATH = Path(os.environ.get("DB_PATH", ROOT / "jhc.db"))
JOURNALS_PATH = Path(os.environ.get("JOURNALS_PATH", ROOT / "data" / "journals.yaml"))
SNAPSHOT_DIR = Path(os.environ.get("SNAPSHOT_DIR", ROOT / "snapshots"))
CACHE_DIR = Path(os.environ.get("JHC_CACHE_DIR", ROOT / ".cache" / "http"))

# Optional. When set it goes in the User-Agent and in Crossref's mailto
# parameter (Crossref's "polite pool"). Left empty by default so no address
# is sent anywhere unless the operator chooses one.
CONTACT_EMAIL = os.environ.get("JHC_CONTACT_EMAIL", "").strip()

USER_AGENT = "journal-health-check/0.1 (+{base}{contact})".format(
    base=BASE_URL,
    contact=f"; mailto:{CONTACT_EMAIL}" if CONTACT_EMAIL else "",
)

EUNOMIA_URL = "https://eunomiaslabors.xyz"
PINAKES_URL = "https://pinakes.wacclearinghouse.org"
