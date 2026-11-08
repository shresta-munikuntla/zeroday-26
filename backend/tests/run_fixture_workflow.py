"""TEST-ONLY demo: temporary SQLite, fake P1/P3, real RAG, no Nemotron key.

Run python -m backend.tests.run_fixture_workflow after normal RAG ingestion.
It does not create or modify a production SQLite database.
"""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from backend import config
from backend.tests.fakes import agent1, agent2, agent5
from backend.workflow.orchestrator import WorkflowServices, workflow_services, run_incident_workflow
from backend.workflow.storage import SQLiteWorkflowStore
from backend.security.audit import list_audit_events


def main():
    root = config.ROOT
    logs = {item['event_id'] for item in json.loads((root / 'data/seed/security_logs.json').read_text())}
    permissions = {item['permission_id'] for item in json.loads((root / 'data/seed/permissions.json').read_text())}
    # Explicit test configuration: this demo never spends live API credits.
    config.NEMOTRON_API_KEY = ''
    with TemporaryDirectory(prefix='sentinelai-fixture-') as folder:
        connection = sqlite3.connect(str(Path(folder) / 'fixture.sqlite'))
        try:
            connection.executescript((Path(__file__).parent / 'fakes/schema.sql').read_text())
            integrations = WorkflowServices(
                agent1.detect, agent2.investigate,
                lambda value: value in logs, lambda value: value in permissions,
                agent5.match_and_draft, SQLiteWorkflowStore(connection))
            with workflow_services(integrations):
                first = run_incident_workflow()
                repeated = run_incident_workflow()
                assert first == repeated and not first[0]['errors']
                rows = connection.execute('SELECT incident_id, status, final_report_json FROM incidents').fetchall()
                assert len(rows) == 1 and rows[0][0] == 'INC-001' and rows[0][1] == 'awaiting_approval'
                audit = list_audit_events('INC-001')
                print(json.dumps({'mode': 'TEST ONLY: fake P1/P3 and provisional SQLite schema',
                                  'incident_count': len(rows), 'state': first[0], 'audit': audit}, indent=2))
        finally:
            connection.close()


if __name__ == '__main__':
    main()
