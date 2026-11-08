"""Photon adapter tests with a fake client; no network and no real credentials."""
from types import SimpleNamespace

from backend.notifications.photon import PhotonAdapter

DEMO = "+14155550123"


def inbound(handle, space_id="pho_spc_1", agent_id="pho_usr_agent", kind="direct"):
    return {"id": "pho_msg_in", "status": "received", "platform": "imessage",
            "sentBy": {"handle": handle, "id": "pho_usr_peer"},
            "receivedBy": {"id": agent_id}, "space": {"id": space_id, "kind": kind}}


class FakeProjects:
    def __init__(self, items, send_status="dispatched"):
        self.items, self.send_status, self.sent, self.list_calls = items, send_status, [], 0

    def list_messages(self, request):
        self.list_calls += 1
        query = request.query.model_dump(by_alias=True, exclude_unset=True)
        assert query["direction"] == "received" and query["platform"] == "imessage"
        return SimpleNamespace(items=self.items, nextPageToken=None)

    def send_message(self, request):
        self.sent.append(request)
        return {"id": "pho_msg_out", "status": self.send_status}


def adapter_with(items, **kwargs):
    projects = FakeProjects(items, **kwargs)
    adapter = PhotonAdapter(api_key="test-key", project_id="pho_prj_test", demo_handle=DEMO,
                            client=SimpleNamespace(projects=projects))
    return adapter, projects


def test_missing_config_fails_without_calling_photon():
    adapter = PhotonAdapter(api_key="", project_id="", demo_handle="", recipients={}, client=object())
    result = adapter.send("mock:avery.chen", "s", "b")
    assert result["status"] == "failed"
    assert "PHOTON_API_KEY" in result["detail"] and "PHOTON_DEMO_HANDLE" in result["detail"]


def test_fails_clearly_until_demo_phone_has_texted_first():
    adapter, projects = adapter_with([inbound("+19998887777")])
    result = adapter.send("mock:avery.chen", "s", "b")
    assert result["status"] == "failed" and "text the Photon number from that phone" in result["detail"]
    assert projects.sent == []


def test_redirects_draft_to_demo_phone_with_intended_employee_header():
    adapter, projects = adapter_with([inbound("+1 (415) 555-0123")])
    result = adapter.send("mock:avery.chen", "[HIGH] SentinelAI incident INC-001 — DC-SRV-04", "What happened...",
                          recipient_label="Avery Chen, Network Security Engineer", idempotency_key="sentinelai:n1")
    assert result["status"] == "sent" and result["photon_message_id"] == "pho_msg_out"
    request = projects.sent[0]
    assert request.path.id == "pho_prj_test"
    assert request.headers.idempotency_key == "sentinelai:n1"
    assert request.body.spaceId == "pho_spc_1" and request.body.senderId == "pho_usr_agent"
    text = request.body.content.text
    assert text.startswith("[SentinelAI demo — alert for Avery Chen, Network Security Engineer]")
    assert "INC-001" in text and "What happened..." in text


def test_conversation_lookup_is_reused_across_recipients():
    adapter, projects = adapter_with([inbound(DEMO)])
    adapter.send("mock:a", "s", "b")
    adapter.send("mock:b", "s", "b")
    assert projects.list_calls == 1 and len(projects.sent) == 2


def test_group_chats_are_ignored():
    adapter, projects = adapter_with([inbound(DEMO, kind="group")])
    assert adapter.send("mock:a", "s", "b")["status"] == "failed"


def test_photon_failed_status_is_reported_as_failed():
    adapter, _ = adapter_with([inbound(DEMO)], send_status="failed")
    assert adapter.send("mock:a", "s", "b")["status"] == "failed"


def test_send_route_passes_employee_label_and_stable_idempotency_key(client, auth_headers, monkeypatch):
    import backend.api.routes_notifications as routes

    calls = []

    class Recorder:
        def send(self, channel, subject, body, *, recipient_label=None, idempotency_key=None, recipient_id=None):
            calls.append((recipient_label, idempotency_key, recipient_id))
            return {"status": "sent", "detail": "ok"}

    client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers)
    monkeypatch.setattr(routes, "get_adapter", lambda: Recorder())
    response = client.post("/api/incidents/INC-001/send", json={"recipient_ids": ["EMP-001"]}, headers=auth_headers)
    assert response.status_code == 200 and response.json()["results"][0]["status"] == "sent"
    label, key, recipient_id = calls[0]
    assert recipient_id == "EMP-001"
    assert label == "Avery Chen, Network Security Engineer"
    assert key.startswith("sentinelai:")


def test_bad_adapter_config_marks_rows_failed_not_stuck(client, auth_headers, monkeypatch):
    import backend.api.routes_notifications as routes

    def broken():
        raise RuntimeError("Unsupported NOTIFICATION_MODE: nope")

    client.post("/api/incidents/INC-001/approve", json={}, headers=auth_headers)
    monkeypatch.setattr(routes, "get_adapter", broken)
    response = client.post("/api/incidents/INC-001/send", json={"recipient_ids": ["EMP-001"]}, headers=auth_headers)
    assert response.json()["results"][0]["status"] == "failed"
    rows = client.get("/api/incidents/INC-001/recipients", headers=auth_headers).json()
    assert next(r for r in rows if r["recipient_id"] == "EMP-001")["status"] == "failed"


def test_each_employee_is_routed_to_their_own_phone():
    projects = FakeProjects([inbound("+15550000001", space_id="pho_spc_a", agent_id="pho_usr_a"),
                             inbound("+15550000002", space_id="pho_spc_b", agent_id="pho_usr_b")])
    adapter = PhotonAdapter(api_key="k", project_id="pho_prj_test", demo_handle="",
                            recipients={"EMP-001": "+15550000001", "EMP-003": "+15550000002"},
                            client=SimpleNamespace(projects=projects))
    assert adapter.send("c", "s", "b", recipient_id="EMP-001")["status"] == "sent"
    assert adapter.send("c", "s", "b", recipient_id="EMP-003")["status"] == "sent"
    assert [r.body.spaceId for r in projects.sent] == ["pho_spc_a", "pho_spc_b"]
    missing = adapter.send("c", "s", "b", recipient_id="EMP-006")
    assert missing["status"] == "failed" and "EMP-006" in missing["detail"]


def test_unlisted_employee_falls_back_to_demo_handle_and_numbers_are_masked():
    adapter, projects = adapter_with([inbound(DEMO)])
    adapter.recipients = {"EMP-001": "+15550000001"}
    result = adapter.send("c", "s", "b", recipient_id="EMP-006")
    assert result["status"] == "sent" and "5550123" not in result["detail"]
    failed = adapter.send("c", "s", "b", recipient_id="EMP-001")
    assert failed["status"] == "failed" and "5550000001" not in failed["detail"]


def test_parse_recipients():
    from backend.notifications.photon import parse_recipients
    assert parse_recipients(" EMP-001=+1555 , bad, EMP-003=+1666,") == {"EMP-001": "+1555", "EMP-003": "+1666"}
