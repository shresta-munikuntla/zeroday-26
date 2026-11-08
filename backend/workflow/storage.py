"""SQLite persistence adapter; creates no tables and never seeds production data.

Column expectations are provisional and documented in docs/p2-contracts.md.
The matching temporary schema exists only in backend/tests/fakes/schema.sql.
"""
import json
import sqlite3

from backend.workflow.state import INCIDENT_STATUSES


def evidence_key(evidence_ids):
    return json.dumps(sorted(set(evidence_ids)), separators=(',', ':'))


class SQLiteWorkflowStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        # Fail explicitly if the caller's schema has not been reconciled/bound.
        connection.execute('SELECT incident_id, evidence_key, status, state_json, final_report_json FROM incidents LIMIT 0')

    def find(self, evidence_ids):
        row = self.connection.execute(
            'SELECT state_json FROM incidents WHERE evidence_key = ?',
            (evidence_key(evidence_ids),)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, state, evidence_ids, status):
        if status not in INCIDENT_STATUSES:
            raise ValueError('Invalid incident lifecycle status')
        existing = self.connection.execute(
            'SELECT evidence_key FROM incidents WHERE incident_id = ?',
            (state['incident_id'],)).fetchone()
        if existing and existing[0] != evidence_key(evidence_ids):
            raise ValueError('Incident ID is already bound to different evidence')
        report = state['final_report']
        with self.connection:
            self.connection.execute(
                'INSERT INTO incidents (incident_id, evidence_key, status, state_json, final_report_json) '
                'VALUES (?, ?, ?, ?, ?) ON CONFLICT(incident_id) DO UPDATE SET '
                'status=excluded.status, state_json=excluded.state_json, final_report_json=excluded.final_report_json',
                (state['incident_id'], evidence_key(evidence_ids), status, json.dumps(state),
                 json.dumps(report) if report is not None else None))
