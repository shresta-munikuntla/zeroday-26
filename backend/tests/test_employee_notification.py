from backend.agents.employee_notification import match_and_draft
from backend.tools.employee_queries import get_employee_matches


def test_store_setup(initialized_store):
    # The shared setup fixture gives direct tool/agent tests an isolated seeded DB.
    assert get_employee_matches(["DC-SRV-04"])[0]["employee_id"] == "EMP-001"


def test_expected_active_asset_owners_only(initialized_store):
    matches = get_employee_matches(["DC-SRV-04", "DC-SRV-05", "DC-DB-01"])
    assert [(m["employee_id"], m["asset_id"]) for m in matches] == [
        ("EMP-001", "DC-SRV-04"), ("EMP-003", "DC-SRV-05"), ("EMP-006", "DC-DB-01")]
    assert all(set(m) == {"employee_id", "display_name", "role", "team", "asset_id", "responsibility_type", "notification_channel"} for m in matches)
    assert "EMP-002" not in {m["employee_id"] for m in matches}
    assert "EMP-008" not in {m["employee_id"] for m in matches}


def test_inactive_owner_routes_to_team_channel(initialized_store):
    matches = get_employee_matches(["DC-SRV-06"])
    assert len(matches) == 1
    assert matches[0]["responsibility_type"] == "team_fallback"
    assert matches[0]["notification_channel"] == "mock:team-server-admin"
    assert matches[0]["employee_id"] == "TEAM:Server Administration"


def test_drafts_are_personal_and_only_include_agent_evidence(initialized_store, detections, investigation):
    detection = detections[0]
    drafts = match_and_draft({"detection": detection, "investigation": investigation})
    assert [d["recipient_id"] for d in drafts] == ["EMP-001", "EMP-003", "EMP-006"]
    by_recipient = {d["recipient_id"]: d for d in drafts}
    assert "LOG-101" in by_recipient["EMP-001"]["body"]
    assert "LOG-102" in by_recipient["EMP-001"]["body"]
    assert "DC-SRV-05" not in by_recipient["EMP-001"]["body"]
    assert "LOG-101" in by_recipient["EMP-003"]["body"]
    assert "LOG-103" in by_recipient["EMP-003"]["body"]
    assert "DC-DB-01" not in by_recipient["EMP-003"]["body"]
    assert "LOG-101" in by_recipient["EMP-006"]["body"]
    assert "LOG-104" in by_recipient["EMP-006"]["body"]
    assert "LOG-105" in by_recipient["EMP-006"]["body"]
    assert "DC-SRV-04" not in by_recipient["EMP-006"]["body"]
    assert all("details_json" not in d["body"] and "blame" not in d["body"].lower() for d in drafts)
    assert all(d["incident_id"] == detection["incident_id"] for d in drafts)
