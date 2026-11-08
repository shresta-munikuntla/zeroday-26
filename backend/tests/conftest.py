"""Shared pytest setup: a fresh seeded SQLite DB per test session, plus the answer key."""
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


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
