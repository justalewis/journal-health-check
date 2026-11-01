"""Access: do recent HTML articles meet WCAG 2.1 AA under axe-core? Playwright,
run in GitHub Actions.

Phase 2 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import ACCESS

NAME = "html_a11y"
AREA = ACCESS
LABEL = "HTML accessibility"
PHASE = 2


def run(journal, http):
    raise NotImplementedError("html_a11y is a Phase 2 check")
