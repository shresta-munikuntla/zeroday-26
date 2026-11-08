"""Exact shared state from architecture §2.3; lifecycle status lives in SQLite."""
from typing import TypedDict


class IncidentState(TypedDict):
    incident_id: str
    detection: dict | None
    investigation: dict | None
    intelligence: dict | None
    employee_matches: list | None
    final_report: dict | None
    approval_status: str
    notification_status: str
    errors: list


INCIDENT_STATUSES = frozenset({'detected', 'investigating', 'awaiting_approval',
                               'notified', 'closed', 'incomplete', 'rejected'})
APPROVAL_STATUSES = frozenset({'pending', 'approved', 'rejected'})
NOTIFICATION_STATUSES = frozenset({'not_sent', 'sent', 'failed', 'mocked'})


def initial_state(incident_id: str) -> IncidentState:
    return {'incident_id': incident_id, 'detection': None, 'investigation': None,
            'intelligence': None, 'employee_matches': None, 'final_report': None,
            'approval_status': 'pending', 'notification_status': 'not_sent', 'errors': []}
