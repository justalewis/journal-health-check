"""Access: are the latest issue's PDFs tagged, with /Lang, a text layer, alt
text on figures and title metadata? veraPDF (PDF/UA) and pikepdf, run in
GitHub Actions.

Phase 2 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import ACCESS

NAME = "pdf_a11y"
AREA = ACCESS
LABEL = "PDF accessibility"
PHASE = 2


def run(journal, http):
    raise NotImplementedError("pdf_a11y is a Phase 2 check")
