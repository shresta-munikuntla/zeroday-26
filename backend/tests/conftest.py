import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-sufficient-entropy-for-tests")
os.environ.setdefault("DEMO_VIEWER_PASSWORD", "viewer-test-password")
os.environ.setdefault("DEMO_REVIEWER_PASSWORD", "reviewer-test-password")
os.environ.setdefault("NOTIFICATION_MODE", "mock")

import pytest
from fastapi.testclient import TestClient
import backend.storage as storage
from backend.main import app
from backend.security.auth import initialize_users


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
