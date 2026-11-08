"""TEST ONLY: fixed detection fixture, not P1 detection rules."""
from copy import deepcopy

DETECTION = {'incident_id': 'INC-001',
             'evidence_ids': ['LOG-101', 'LOG-102', 'LOG-103', 'LOG-104', 'LOG-105'],
             'reasons': ['Privileged external login and expired SSH permissions']}


def detect():
    return [deepcopy(DETECTION)]
