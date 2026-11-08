"""Agent 2 against the answer key."""
import json

import pytest

from backend.agents.investigation import investigate
from backend.tools.security_queries import event_exists, permission_exists


def test_authorization_states(investigation):
    states = {a["asset_id"]: a["authorization"] for a in investigation["affected_assets"]}
    assert states == {"DC-SRV-04": "authorized", "DC-SRV-05": "expired", "DC-DB-01": "none"}


def test_severity_status_confidence(investigation, expected):
    assert investigation["severity"] == expected["expected_severity"]
    assert investigation["investigation_status"] == "potential_unauthorized_access"
    assert 0.5 <= investigation["confidence"] <= 0.9


def test_permission_evidence(investigation, expected):
    assert set(expected["permission_evidence_ids"]) <= set(investigation["evidence_ids"])
    assert set(expected["evidence_ids"]) <= set(investigation["evidence_ids"])


def test_every_id_exists(investigation):
    ids = set(investigation["evidence_ids"])
    ids |= {i for step in investigation["timeline"] for i in step["evidence_ids"]}
    for i in ids:
        assert event_exists(i) or permission_exists(i), i


def test_no_unsupported_claims(investigation, expected):
    text = json.dumps(investigation).lower()
    for phrase in ("exfiltrat", "confirmed compromise", "was compromised", "stole"):
        assert phrase not in text
    assert investigation["hypotheses"] and investigation["benign_explanations_to_check"]


def test_facts_cite_ids(investigation):
    for fact in investigation["confirmed_facts"]:
        assert "LOG-" in fact or "events reviewed" in fact


def test_timeline_is_ordered(investigation):
    times = [s["timestamp"] for s in investigation["timeline"]]
    assert times == sorted(times) and len(times) == 5


def test_rejects_incomplete_detection():
    with pytest.raises(ValueError):
        investigate({"incident_id": "INC-001"})
