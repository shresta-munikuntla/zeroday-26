"""Shared pytest setup.

P3 (API): test env vars, FastAPI TestClient on a temp backend.storage DB, auth helpers.
P1 (agents): a fresh seeded SQLite DB per session (DATABASE_URL) plus the answer key.
"""
import json
import os
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-sufficient-entropy-for-tests")
os.environ.setdefault("DEMO_VIEWER_PASSWORD", "viewer-test-password")
os.environ.setdefault("DEMO_REVIEWER_PASSWORD", "reviewer-test-password")
os.environ.setdefault("NOTIFICATION_MODE", "mock")

import pytest
from fastapi.testclient import TestClient
import backend.storage as storage
from backend.main import app
from backend.security.auth import initialize_users

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


# ---------------------------------------------------------------- P3: API
@pytest.fixture
def initialized_store(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.sqlite3")
    storage.initialize()
    initialize_users()


@pytest.fixture
def client(initialized_store):
    with TestClient(app) as test_client:
        yield test_client


def token(client, username="reviewer", password="reviewer-test-password"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(client):
    return {"Authorization": f"Bearer {token(client)}"}


# ---------------------------------------------------------------- P1: database + agents
@pytest.fixture(scope="session", autouse=True)
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{path.as_posix()}"
    from backend.database.seed import seed
    counts = seed()
    yield counts
    if old is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old


@pytest.fixture(scope="session")
def manifest():
    """Ground truth. Only tests may read this file - never agent code."""
    return json.loads((ROOT / "data" / "seed" / "scenario_manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def expected(manifest):
    return manifest["expected_incident"]


@pytest.fixture(scope="session")
def detections():
    from backend.agents.threat_detection import detect
    return detect()


@pytest.fixture(scope="session")
def investigation(detections):
    from backend.agents.investigation import investigate
    return investigate(detections[0])


# Workflow fixtures use their own isolated SQLite schema.
import sqlite3
from unittest.mock import Mock


from backend.tests.fakes import agent1, agent2, agent5
from backend.workflow.orchestrator import WorkflowServices
from backend.workflow.storage import SQLiteWorkflowStore
from backend.rag.vector_store import record_results
from backend.agents.intelligence import _fallback



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
