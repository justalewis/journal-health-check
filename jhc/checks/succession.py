"""Continuity: has the editor filed a succession kit? Public pages show yes/no
only, and only with the editor's consent.

Phase 3 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import CONTINUITY

NAME = "succession"
AREA = CONTINUITY
LABEL = "Succession plan on file"
PHASE = 3


def run(journal, http):
    raise NotImplementedError("succession is a Phase 3 check")
