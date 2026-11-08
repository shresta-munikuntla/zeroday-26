"""Photon (Beta, Photon 2.0) iMessage delivery adapter.

Demo routing: the seeded employees are fictional, so their phone numbers come
from .env, never from the seed data or git:
  PHOTON_RECIPIENTS=EMP-001=+15550000001,EMP-003=+15550000002
Employees not listed fall back to PHOTON_DEMO_HANDLE (one phone for everyone),
if set. Each message starts with a header naming the employee it is for.

Photon shared-line rule: it can only message a person who has an active
Assignment AND has texted the Photon number since that Assignment. So every
demo phone must be assigned in the Photon dashboard and text the Photon number
once before alerts can be sent. This adapter finds that inbound message and
reuses its conversation.

Check setup:      python -m backend.notifications.photon check
Send test texts:  python -m backend.notifications.photon test
"""
import os
import re
import sys

PHOTON_TEXT_LIMIT = 4000  # keep iMessages readable; drafts are well under this


def _digits(handle: str) -> str:
    return re.sub(r"\D", "", handle or "")


def _same_handle(a: str, b: str) -> bool:
    if "@" in (a or "") or "@" in (b or ""):  # iMessage email identity
        return (a or "").strip().lower() == (b or "").strip().lower()
    da, db = _digits(a), _digits(b)
    return bool(da) and da == db


def mask(handle: str) -> str:
    """Show enough of a phone number to recognise it in logs, not to reuse it."""
    digits = _digits(handle)
    return f"+{digits[:4]}***{digits[-2:]}" if len(digits) >= 8 else "***"


def parse_recipients(raw: str) -> dict[str, str]:
    """Parse 'EMP-001=+1555...,EMP-003=+1555...' into {employee_id: handle}."""
    mapping = {}
    for pair in (raw or "").split(","):
        if "=" in pair:
            employee_id, handle = (part.strip() for part in pair.split("=", 1))
            if employee_id and handle:
                mapping[employee_id] = handle
    return mapping


def _default_client(api_key: str):
    from photon_api import Photon  # imported lazily so mock mode needs no SDK
    return Photon(headers={"Authorization": f"Bearer {api_key}"}, timeout=20.0)


def _as_dict(model) -> dict:
    root = getattr(model, "root", model)
    root = getattr(root, "root", root)
    if hasattr(root, "model_dump"):
        return root.model_dump(mode="json", by_alias=True)
    return dict(root)


class PhotonAdapter:
    """Sends approved Agent 5 drafts as iMessages through Photon Beta."""

    def __init__(self, api_key: str | None = None, project_id: str | None = None,
                 demo_handle: str | None = None, recipients: dict[str, str] | None = None, client=None):
        self.api_key = api_key if api_key is not None else os.getenv("PHOTON_API_KEY", "")
        self.project_id = project_id if project_id is not None else os.getenv("PHOTON_PROJECT_ID", "")
        self.demo_handle = demo_handle if demo_handle is not None else os.getenv("PHOTON_DEMO_HANDLE", "")
        self.recipients = recipients if recipients is not None else parse_recipients(os.getenv("PHOTON_RECIPIENTS", ""))
        self._client = client
        self._conversations: dict[str, tuple[str, str]] = {}

    # -- setup -----------------------------------------------------------------
    def _missing_config(self) -> str | None:
        missing = [name for name, value in (("PHOTON_API_KEY", self.api_key),
                                            ("PHOTON_PROJECT_ID", self.project_id)) if not value]
        if not self.demo_handle and not self.recipients:
            missing.append("PHOTON_RECIPIENTS or PHOTON_DEMO_HANDLE")
        return f"Photon is not configured; set {', '.join(missing)} in .env." if missing else None

    def handle_for(self, recipient_id: str | None) -> str:
        return self.recipients.get(recipient_id or "", "") or self.demo_handle

    def configured_handles(self) -> list[str]:
        handles = list(self.recipients.values()) + ([self.demo_handle] if self.demo_handle else [])
        unique = []
        for handle in handles:
            if not any(_same_handle(handle, seen) for seen in unique):
                unique.append(handle)
        return unique

    def _photon(self):
        if self._client is None:
            self._client = _default_client(self.api_key)
        return self._client

    def find_conversation(self, handle: str) -> tuple[str, str] | None:
        """Return (space_id, agent_sender_id) from this handle's latest inbound iMessage."""
        key = _digits(handle) or handle.lower()
        if key in self._conversations:
            return self._conversations[key]
        from photon_api.rpc_generated import ListMessagesInput, ListMessagesPath, ListMessagesQuery
        page_token = None
        for _ in range(5):  # newest first; the phone's first text should be recent
            query = {"direction": "received", "platform": "imessage", "order": "desc", "page_size": 50}
            if page_token:
                query["page_token"] = page_token
            page = self._photon().projects.list_messages(ListMessagesInput(
                path=ListMessagesPath(id=self.project_id), query=ListMessagesQuery(**query)))
            for item in page.items:
                message = _as_dict(item)
                sent_by = message.get("sentBy") or {}
                received_by = message.get("receivedBy") or {}
                space = message.get("space") or {}
                if (_same_handle(sent_by.get("handle", ""), handle)
                        and space.get("kind", "direct") == "direct"
                        and space.get("id") and received_by.get("id")):
                    self._conversations[key] = (space["id"], received_by["id"])
                    return self._conversations[key]
            page_token = getattr(page, "nextPageToken", None)
            if not isinstance(page_token, str) or not page_token:
                break
        return None

    # -- delivery --------------------------------------------------------------
    def send(self, channel: str, subject: str, body: str, *, recipient_label: str | None = None,
             idempotency_key: str | None = None, recipient_id: str | None = None) -> dict:
        problem = self._missing_config()
        if problem:
            return {"status": "failed", "detail": problem}
        handle = self.handle_for(recipient_id)
        if not handle:
            return {"status": "failed", "detail": f"No demo phone number for {recipient_id} in PHOTON_RECIPIENTS."}
        conversation = self.find_conversation(handle)
        if not conversation:
            return {"status": "failed", "detail": (
                f"No iMessage from {mask(handle)} found in this Photon project. Assign that number in the "
                "Photon dashboard, text the Photon number from that phone (as an iMessage) once, then send again.")}
        space_id, sender_id = conversation
        header = f"[SentinelAI demo — alert for {recipient_label or channel}]"
        text = f"{header}\n{subject}\n\n{body}"[:PHOTON_TEXT_LIMIT]

        from photon_api.generated.models import SendMessageRequest, SendTextContent
        from photon_api.rpc_generated import SendMessageHeader, SendMessageInput, SendMessagePath
        key = idempotency_key or f"sentinelai:{channel}:{abs(hash(text))}"
        sent = self._photon().projects.send_message(SendMessageInput(
            path=SendMessagePath(id=self.project_id),
            headers=SendMessageHeader.model_validate({"idempotency-key": key}),
            body=SendMessageRequest(spaceId=space_id, senderId=sender_id,
                                    content=SendTextContent(type="text", format="plain", text=text))))
        message = _as_dict(sent)
        if message.get("status") == "failed":
            return {"status": "failed", "detail": "Photon reported the iMessage as failed.",
                    "photon_message_id": message.get("id")}
        return {"status": "sent", "photon_message_id": message.get("id"),
                "detail": f"Accepted by Photon (status: {message.get('status', 'unknown')}); "
                          f"sent to demo phone {mask(handle)}. Delivery is not confirmed by the API."}


def _cli(argv: list[str]) -> int:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    adapter = PhotonAdapter()
    problem = adapter._missing_config()
    if problem:
        print(problem)
        return 1
    command = argv[0] if argv else "check"
    owners = {}
    for employee_id, handle in adapter.recipients.items():
        owners.setdefault(_digits(handle), []).append(employee_id)
    ok = True
    for handle in adapter.configured_handles():
        who = ", ".join(owners.get(_digits(handle), [])) or "fallback (PHOTON_DEMO_HANDLE)"
        conversation = adapter.find_conversation(handle)
        if not conversation:
            ok = False
            print(f"NOT READY  {mask(handle)} ({who}): no inbound iMessage yet. Assign it in the Photon "
                  "dashboard, then text the Photon number from that phone.")
            continue
        print(f"READY      {mask(handle)} ({who})")
        if command == "test":
            result = adapter.send("demo-check", "SentinelAI test", "Photon is connected. Approved alerts will arrive here.",
                                  recipient_label=f"setup check: {who}",
                                  idempotency_key=f"sentinelai-test:{_digits(handle)}:{os.urandom(4).hex()}",
                                  recipient_id=owners.get(_digits(handle), [None])[0])
            print(f"           test message: {result['status']}")
            ok = ok and result["status"] == "sent"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
