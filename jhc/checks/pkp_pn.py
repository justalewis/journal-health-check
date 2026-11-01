"""Preservation: is an OJS journal enrolled in the PKP Preservation Network?

Phase 2 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import PRESERVATION

NAME = "pkp_pn"
AREA = PRESERVATION
LABEL = "PKP Preservation Network"
PHASE = 2


def run(journal, http):
    raise NotImplementedError("pkp_pn is a Phase 2 check")
