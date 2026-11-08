import json
from pathlib import Path
import sqlite3
from unittest.mock import Mock

import pytest

from backend.tests.fakes import agent1, agent2, agent5
from backend.workflow.orchestrator import WorkflowServices
from backend.workflow.storage import SQLiteWorkflowStore
from backend.rag.vector_store import record_results
from backend.agents.intelligence import _fallback

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def services(tmp_path):
    connection = sqlite3.connect(tmp_path / 'workflow.sqlite')
    connection.executescript((Path(__file__).parent / 'fakes/schema.sql').read_text())
    logs = {x['event_id'] for x in json.loads((ROOT / 'data/seed/security_logs.json').read_text())}
    permissions = {x['permission_id'] for x in json.loads((ROOT / 'data/seed/permissions.json').read_text())}
    sources = [{'doc_id': 'POL-003', 'title': 'Privileged Access Management Policy',
                'section': '2. Expired Permissions', 'source_type': 'internal_policy_sample',
                'text': 'Review expired permissions.', 'url': '', 'score': 0.6}]
    def analyze(investigation):
        record_results(sources)
        return _fallback(sources, [])
    result = WorkflowServices(
        detect=Mock(side_effect=agent1.detect), investigate=Mock(side_effect=agent2.investigate),
        event_exists=Mock(side_effect=lambda identifier: identifier in logs),
        permission_exists=Mock(side_effect=lambda identifier: identifier in permissions),
        match_and_draft=Mock(side_effect=agent5.match_and_draft),
        store=SQLiteWorkflowStore(connection), analyze=Mock(side_effect=analyze),
    )
    yield result
    connection.close()
