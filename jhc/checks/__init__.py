"""Check registry. Each module exposes NAME, AREA, LABEL and run(journal, http).

ACTIVE runs in the harvester, in display order. PLANNED modules are stubs for
Phases 2 and 3; the methods page lists them so readers can see what's coming.
"""

from . import (crossref, doaj, homepage, html_a11y, issn, keepers, link_rot,
               openalex, pdf_a11y, pkp_pn, rdap, succession, tls, wayback)

ACTIVE = [tls, rdap, keepers, wayback, issn, doaj, openalex, crossref]
PLANNED = [homepage, succession, pkp_pn, link_rot, pdf_a11y, html_a11y]

BY_NAME = {m.NAME: m for m in ACTIVE}
ALL_BY_NAME = {m.NAME: m for m in ACTIVE + PLANNED}
