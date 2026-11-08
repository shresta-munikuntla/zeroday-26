"""Reviewer-only demo reset: fresh drafts after a completed send, audit history kept."""
from backend.storage import connect
from backend.tests.conftest import token


def test_reset_after_send_gives_fresh_pending_drafts_and_keeps_audit(client, auth_headers):
    assert client.post("/api/incidents/run-demo", json={}, headers=auth_headers).status_code == 200
    assert client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers).status_code == 200
    assert client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers).status_code == 200
    # Without a reset, Run demo keeps the approved, delivered incident.
    client.post("/api/incidents/run-demo", json={}, headers=auth_headers)
    assert client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers).status_code == 409
    audit_before = len(client.get("/api/incidents/INC-001/audit", headers=auth_headers).json())

    response = client.post("/api/incidents/reset-demo", json={}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["incident_id"] == "INC-001"
    assert response.json()["approval_status"] == "pending"
    details = client.get("/api/incidents/INC-001", headers=auth_headers).json()
    assert {r["status"] for r in details["recipients"]} == {"draft"}
    assert [r["recipient_id"] for r in details["recipients"]] == ["EMP-001", "EMP-003", "EMP-006"]
    audit = client.get("/api/incidents/INC-001/audit", headers=auth_headers).json()
    assert len(audit) > audit_before
    assert any(event["action"] == "demo_reset" for event in audit)
    # The fresh drafts can go through the full flow again.
    assert client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers).status_code == 200
    assert client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers).status_code == 200


def test_viewer_cannot_reset_demo(client, auth_headers):
    client.post("/api/incidents/run-demo", json={}, headers=auth_headers)
    viewer = {"Authorization": f"Bearer {token(client, 'viewer', 'viewer-test-password')}"}
    assert client.post("/api/incidents/reset-demo", json={}, headers=viewer).status_code == 403
    assert client.get("/api/incidents/INC-001", headers=auth_headers).status_code == 200


def test_reset_is_blocked_while_a_delivery_is_in_progress(client, auth_headers):
    client.post("/api/incidents/run-demo", json={}, headers=auth_headers)
    with connect() as db:
        db.execute("UPDATE notifications SET status='sending' WHERE recipient_id='EMP-001'")
    response = client.post("/api/incidents/reset-demo", json={}, headers=auth_headers)
    assert response.status_code == 409
    assert client.get("/api/incidents/INC-001", headers=auth_headers).status_code == 200
