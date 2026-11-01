"""Continuity: is the home page up, and when did the newest issue appear?

Plan: HTTP status and Last-Modified, plus newest item date from RSS or
OAI-PMH where the journal has them. No new issue in 24+ months is a signal;
ceased titles are flagged differently.

Phase 2 stub. Not run by the harvester yet; listed on the methods page as
planned.
"""

from ..models import CONTINUITY

NAME = "homepage"
AREA = CONTINUITY
LABEL = "Home page and newest issue"
PHASE = 2


def run(journal, http):
    raise NotImplementedError("homepage is a Phase 2 check")
