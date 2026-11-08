import json
from backend.storage import connect
from .conftest import token


def test_health_and_auth_roles(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/incidents").status_code == 401
    viewer = token(client, "viewer", "viewer-test-password")
    assert client.get("/api/incidents", headers={"Authorization": f"Bearer {viewer}"}).status_code == 200
    assert client.post("/api/incidents/INC-001/approve", json={}, headers={"Authorization": f"Bearer {viewer}"}).status_code == 403


def test_approval_send_and_audit(client, auth_headers):
    assert client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers).status_code == 409
    approved = client.post("/api/incidents/INC-001/approve", json={"comment": "Reviewed"}, headers=auth_headers)
    assert approved.status_code == 200
    assert approved.json()["approved_by"] == "reviewer"
    sent = client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers)
    assert sent.status_code == 200
    assert all(result["status"] == "mocked" for result in sent.json()["results"])
    assert "not actually sent" in sent.json()["results"][0]["detail"].lower()
    assert client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers).status_code == 409
    events = client.get("/api/incidents/INC-001/audit", headers=auth_headers).json()
    assert any(e["action"] == "approved" and e["actor_id"] == "reviewer" for e in events)
    status = client.get("/api/incidents/INC-001/recipients", headers=auth_headers).json()
    assert all(x["status"] == "mocked" and x["approved_at"] for x in status)


def test_send_rejects_unallowlisted_channel_before_delivery(client, auth_headers):
    client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers)
    with connect() as db:
        db.execute("UPDATE notifications SET recipient_channel='mock:attacker' WHERE recipient_id='EMP-001'")
    result = client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers)
    assert result.status_code == 400
    statuses = client.get("/api/incidents/INC-001/recipients", headers=auth_headers).json()
    assert all(x["status"] == "approved" for x in statuses)


def test_reject_records_reviewer_decision(client, auth_headers):
    response = client.post("/api/incidents/INC-001/reject", json={"comment": "Needs more investigation"}, headers=auth_headers)
    assert response.status_code == 200
    assert client.post("/api/incidents/INC-001/send", json={}, headers=auth_headers).status_code == 409
    details = client.get("/api/incidents/INC-001", headers=auth_headers).json()
    assert details["approval_status"] == "rejected"


def test_adapter_errors_are_saved_as_failed_and_visible(client, auth_headers, monkeypatch):
    import backend.api.routes_notifications as notification_routes

    class BrokenAdapter:
        def send(self, channel, subject, body):
            raise RuntimeError("provider unavailable")

    client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers)
    monkeypatch.setattr(notification_routes, "get_adapter", lambda: BrokenAdapter())
    response = client.post("/api/incidents/INC-001/send", json={"recipient_ids": ["EMP-001"]}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "failed"
    recipients = client.get("/api/incidents/INC-001/recipients", headers=auth_headers).json()
    failed = next(row for row in recipients if row["recipient_id"] == "EMP-001")
    assert failed["status"] == "failed"
    assert json.loads(failed["delivery_result"])["detail"] == "provider unavailable"


def test_run_demo_resets_incident_and_returns_full_fixture(client, auth_headers):
    response = client.post("/api/incidents/run-demo", json={}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["incident_id"] == "INC-001"
    details = client.get("/api/incidents/INC-001", headers=auth_headers).json()
    assert [r["recipient_id"] for r in details["recipients"]] == ["EMP-001", "EMP-003", "EMP-006"]
