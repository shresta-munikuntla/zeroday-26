"""Agent 1 against the answer key (spec tests 1-3, 9)."""
from backend.agents.threat_detection import detect
from backend.database.db import connection, evidence_key, format_ts
from datetime import datetime, timezone


def test_exactly_one_incident(detections):
    assert len(detections) == 1


def test_matches_expected_incident(detections, expected):
    d = detections[0]
    assert d["incident_id"] == expected["incident_id"]
    assert d["evidence_ids"] == expected["evidence_ids"]
    assert d["affected_asset_ids"] == expected["affected_asset_ids"]
    assert d["account_ids"] == expected["account_ids"]
    assert d["source_ip_addresses"] == expected["source_ip_addresses"]
    assert d["time_window"] == expected["time_window"]
    assert d["severity_initial"] == expected["expected_severity"]


def test_decoys_never_flagged(detections, manifest):
    flagged = {i for d in detections for i in d["evidence_ids"]}
    for decoy in manifest["decoys"]:
        assert not flagged & set(decoy["evidence_ids"]), decoy["id"]


def test_reasons_cite_evidence(detections):
    d = detections[0]
    assert d["reasons"] and all("LOG-" in r for r in d["reasons"])
    assert d["detection_status"] == "suspicious"
    assert d["uncertainties"]


def test_off_hours_is_reason_not_rule(detections):
    d = detections[0]
    assert any("Saturday" in r for r in d["reasons"])
    assert all(r.startswith(("R1", "R2", "R3", "R4")) for r in d["rules_triggered"])


def test_injection_log_is_plain_data(detections):
    text = str(detections)
    assert "LOG-190" not in text and "IGNORE" not in text


def test_reuses_saved_incident_id(detections):
    with connection() as conn:
        conn.execute("INSERT INTO incidents (incident_id, created_at, status, evidence_key) VALUES (?, ?, ?, ?)",
                     ("INC-007", format_ts(datetime.now(timezone.utc)), "detected",
                      evidence_key(detections[0]["evidence_ids"])))
    try:
        assert detect()[0]["incident_id"] == "INC-007"
    finally:
        with connection() as conn:
            conn.execute("DELETE FROM incidents WHERE incident_id = 'INC-007'")
