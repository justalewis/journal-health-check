"""Preservation: what share of outbound links in recent articles still resolve?
Dead links queue for Save Page Now only with approval.

Phase 2 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import PRESERVATION

NAME = "link_rot"
AREA = PRESERVATION
LABEL = "Link rot"
PHASE = 2


def run(journal, http):
    raise NotImplementedError("link_rot is a Phase 2 check")
