"""TEST ONLY: documented INC-001 investigation, not P1 business logic."""
from copy import deepcopy

INVESTIGATION = {
    'incident_id': 'INC-001', 'status': 'suspicious',
    'evidence_ids': ['LOG-101', 'LOG-102', 'LOG-103', 'LOG-104', 'LOG-105'],
    'permission_ids': ['PERM-001', 'PERM-003'],
    'affected_asset_ids': ['DC-SRV-04', 'DC-SRV-05', 'DC-DB-01'],
    'severity': 'high',
    'confirmed_facts': ['Privileged account used an external IP and accessed multiple assets.',
                        'SSH access succeeded after a permission expired; database access was denied.'],
    'investigation_reasons': ['Review privileged account valid accounts remote services SSH expired permission policy.'],
}


def investigate(detection):
    result = deepcopy(INVESTIGATION)
    result['incident_id'] = detection['incident_id']
    result['evidence_ids'] = detection['evidence_ids'][:]
    return result
