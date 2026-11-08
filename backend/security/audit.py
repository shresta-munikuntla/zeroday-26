"""Parameterized audit persistence with conservative, allowlisted details."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import re

from backend import config
from backend.storage import connect

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
        with connect() as db:
            with audit_connection(db):
                return write_audit_event(incident_id, actor_type, actor_id, action, resource_type, resource_id, details)
    safe = {key: _clean(value) for key, value in details.items() if key in _FIELDS}
    columns = {row[1] for row in connection.execute('PRAGMA table_info(audit_events)')}
    if 'details_json' not in columns and incident_id is None:
        # P3's legacy schema requires an incident ID. P1's existing audit table
        # supports global failures, so never invent a sentinel incident.
        from backend.database.db import connection as native_connection
        with native_connection() as native:
            with audit_connection(native):
                return write_audit_event(None, actor_type, actor_id, action, resource_type, resource_id, details)
    if 'details_json' not in columns:
        payload = {'actor_type': actor_type, 'resource_type': resource_type,
                   'resource_id': resource_id, **safe}
        with connection:
            connection.execute('INSERT INTO audit_events (incident_id, actor_id, action, detail_json) VALUES (?, ?, ?, ?)',
                               (incident_id, actor_id, action, json.dumps(payload)))
        return
    with connection:
        connection.execute(
            'INSERT INTO audit_events (incident_id, actor_type, actor_id, action, '
            'resource_type, resource_id, details_json, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (incident_id, actor_type, actor_id, action, resource_type, resource_id,
             json.dumps(safe), datetime.now(timezone.utc).isoformat()))


def list_audit_events(incident_id):
    connection = _connection.get()
    if connection is None:
        with connect() as db:
            with audit_connection(db):
                return list_audit_events(incident_id)
    columns = {row[1] for row in connection.execute('PRAGMA table_info(audit_events)')}
    if 'details_json' not in columns and incident_id is None:
        from backend.database.db import connection as native_connection
        with native_connection() as native:
            with audit_connection(native):
                return list_audit_events(None)
    if 'details_json' not in columns:
        rows = connection.execute('SELECT * FROM audit_events WHERE incident_id=? ORDER BY event_id', (incident_id,)).fetchall()
        return [{**dict(row), 'details': json.loads(row['detail_json'])} for row in rows]
    cursor = connection.execute(
        'SELECT incident_id, actor_type, actor_id, action, resource_type, resource_id, '
        'details_json, timestamp FROM audit_events WHERE incident_id IS ? ORDER BY rowid', (incident_id,))
    keys = [column[0] for column in cursor.description]
    events = []
    for row in cursor.fetchall():
        event = dict(zip(keys, row))
        event['details'] = json.loads(event.pop('details_json'))
        events.append(event)
    return events


# API events use the separate application store and its schema.


def write_api_audit_event(incident_id: str, actor_id: str, action: str, detail: dict) -> None:
    with connect() as db:
        db.execute("INSERT INTO audit_events (incident_id, actor_id, action, detail_json) VALUES (?, ?, ?, ?)",
                   (incident_id, actor_id, action, json.dumps(detail)))


def list_api_audit_events(incident_id: str) -> list[dict]:
    with connect() as db:
        events = db.execute("SELECT * FROM audit_events WHERE incident_id = ? ORDER BY event_id", (incident_id,)).fetchall()
    return [{**dict(event), "detail": json.loads(event["detail_json"])} for event in events]
