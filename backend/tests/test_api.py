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


def test_run_demo_includes_intelligence_and_preserves_approval(client, auth_headers):
    result = client.post('/api/incidents/run-demo', json={}, headers=auth_headers)
    assert result.status_code == 200
    report = result.json()
    assert report['incident_id'] == 'INC-001' and report['severity'] == 'high'
    assert not report['errors'] and 'limitations' in report['intelligence']
    events = client.get('/api/incidents/INC-001/audit', headers=auth_headers).json()
    assert {'detection', 'investigation', 'retrieval', 'report_generation',
            'notification_drafting'} <= {event['action'] for event in events}
    assert client.post('/api/incidents/INC-001/approve', json={}, headers=auth_headers).status_code == 200
    repeated = client.post('/api/incidents/run-demo', json={}, headers=auth_headers)
    assert repeated.json()['approval_status'] == 'approved'
    recipients = client.get('/api/incidents/INC-001/recipients', headers=auth_headers).json()
    assert all(r['status'] == 'approved' for r in recipients)


def test_nemotron_check_requires_reviewer_and_does_not_fake_success(client, auth_headers, monkeypatch):
    from unittest.mock import Mock
    from backend.api import routes_ai
    provider = Mock()
    monkeypatch.setattr(routes_ai, 'NemotronClient', provider)
    assert client.post('/api/ai/check').status_code == 401
    viewer = token(client, 'viewer', 'viewer-test-password')
    assert client.post('/api/ai/check', headers={'Authorization': f'Bearer {viewer}'}).status_code == 403
    result = client.post('/api/ai/check', headers=auth_headers).json()
    assert result['mode'] == 'fallback' and result['verified'] is False
    provider.assert_not_called()


def test_nemotron_check_verifies_nonce(client, auth_headers, monkeypatch):
    from unittest.mock import Mock
    from backend.api import routes_ai
    from backend import config
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', 'test-placeholder')
    model = Mock()
    model.chat_json.side_effect = lambda system, task, untrusted: json.loads(task.removeprefix('Return exactly '))
    monkeypatch.setattr(routes_ai, 'NemotronClient', lambda: model)
    result = client.post('/api/ai/check', headers=auth_headers).json()
    assert result['verified'] is True and result['mode'] == 'nemotron'
    model.chat_json.return_value = {'status': 'ok', 'nonce': 'wrong'}
    model.chat_json.side_effect = None
    assert client.post('/api/ai/check', headers=auth_headers).json()['verified'] is False


def test_ai_preview_does_not_change_decision_or_drafts(client, auth_headers):
    client.post('/api/incidents/INC-001/reject', json={}, headers=auth_headers)
    before = client.get('/api/incidents/INC-001', headers=auth_headers).json()
    response = client.post('/api/incidents/INC-001/preview-intelligence', headers=auth_headers)
    assert response.status_code == 200
    assert response.json()['mode'] == 'fallback'
    after = client.get('/api/incidents/INC-001', headers=auth_headers).json()
    assert after['approval_status'] == before['approval_status'] == 'rejected'
    assert after['recipients'] == before['recipients']
    assert after['intelligence'] == before['intelligence']
    assert after['audit'][-1]['action'] == 'intelligence_preview'


def test_ai_preview_marks_validated_generation(client, auth_headers, monkeypatch):
    from backend.agents import intelligence
    from unittest.mock import Mock
    source = {'doc_id': 'POL-003', 'title': 'Access policy', 'section': 'Access review',
              'source_type': 'internal_policy_sample', 'text': 'Review expired access.', 'url': None}
    monkeypatch.setattr(intelligence, 'search_knowledge', lambda query, filters, k: [source] if filters['source_type'] == source['source_type'] else [])
    output = intelligence._fallback([source], [])
    output['limitations'] = []
    model = Mock()
    model.chat_json.return_value = output
    monkeypatch.setattr(intelligence, '_client', model)
    result = client.post('/api/incidents/INC-001/preview-intelligence', headers=auth_headers).json()
    assert result['mode'] == 'nemotron'
    assert result['document_ids'] == ['POL-003']
