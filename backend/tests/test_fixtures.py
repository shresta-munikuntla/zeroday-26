"""The JSON fixtures teammates build against must match what the agents really return.
If this fails after you change an agent, regenerate them:
    python -m backend.agents.threat_detection --out backend/tests/fixtures/detection_INC-001.json
    python -m backend.agents.investigation    --out backend/tests/fixtures/investigation_INC-001.json
"""
import json

from conftest import FIXTURES


def _load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_detection_fixture_current(detections):
    assert _load("detection_INC-001.json") == detections


def test_investigation_fixture_current(investigation):
    assert _load("investigation_INC-001.json") == [investigation]
