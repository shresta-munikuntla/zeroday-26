"""Parameterized audit persistence with conservative, allowlisted details."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import re

from backend import config

_connection = ContextVar('audit_connection', default=None)
_FIELDS = {'step', 'status', 'severity', 'evidence_ids', 'document_ids',
           'recipient_ids', 'asset_ids', 'error_type', 'reused', 'count'}


@contextmanager
def audit_connection(connection):
    token = _connection.set(connection)
    try:
        yield
    finally:
        _connection.reset(token)


def _clean(value):
    if isinstance(value, list):
        return [_clean(item) for item in value if isinstance(item, (str, int, float, bool))]
    if isinstance(value, str):
        if config.NEMOTRON_API_KEY:
            value = value.replace(config.NEMOTRON_API_KEY, '[REDACTED]')
        value = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[REDACTED_EMAIL]', value)
        return re.sub(r'(?:nvapi-|sk-|hf_)[A-Za-z0-9_-]+', '[REDACTED]', value)
    return value if isinstance(value, (int, float, bool)) or value is None else '[REDACTED]'


def write_audit_event(incident_id, actor_type, actor_id, action,
                      resource_type, resource_id, details):
    connection = _connection.get()
    if connection is None:
        raise RuntimeError('An existing SQLite audit connection must be bound')
    safe = {key: _clean(value) for key, value in details.items() if key in _FIELDS}
    with connection:
        connection.execute(
            'INSERT INTO audit_events (incident_id, actor_type, actor_id, action, '
            'resource_type, resource_id, details_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (incident_id, actor_type, actor_id, action, resource_type, resource_id,
             json.dumps(safe), datetime.now(timezone.utc).isoformat()))


def list_audit_events(incident_id):
    connection = _connection.get()
    if connection is None:
        raise RuntimeError('An existing SQLite audit connection must be bound')
    cursor = connection.execute(
        'SELECT incident_id, actor_type, actor_id, action, resource_type, resource_id, '
        'details_json, timestamp FROM audit_events WHERE incident_id = ? ORDER BY rowid', (incident_id,))
    keys = [column[0] for column in cursor.description]
    events = []
    for row in cursor.fetchall():
        event = dict(zip(keys, row))
        event['details'] = json.loads(event.pop('details_json'))
        events.append(event)
    return events
