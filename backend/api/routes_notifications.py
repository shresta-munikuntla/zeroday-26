import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.notifications.registry import get_adapter
from backend.security.audit import write_api_audit_event as write_audit_event
from backend.security.auth import require_role
from backend.storage import connect, rows

router = APIRouter(prefix="/api/incidents", tags=["notifications"])
Reviewer = Annotated[dict, Depends(require_role("reviewer"))]


class SendRequest(BaseModel):
    recipient_ids: list[str] | None = Field(default=None, max_length=50)


@router.post("/{incident_id}/send")
def send(incident_id: str, payload: SendRequest, user: Reviewer):
    incidents = rows("SELECT approval_status FROM incidents WHERE incident_id=?", (incident_id,))
    if not incidents:
        raise HTTPException(404, "Incident not found")
    # Required order: approval, channel allowlist, duplicate delivery.
    if incidents[0]["approval_status"] != "approved":
        raise HTTPException(409, "Incident must be approved before sending")
    drafts = rows("SELECT * FROM notifications WHERE incident_id=? ORDER BY recipient_id", (incident_id,))
    selected = set(payload.recipient_ids if payload.recipient_ids is not None else [d["recipient_id"] for d in drafts])
    if selected - {d["recipient_id"] for d in drafts}:
        raise HTTPException(404, "Unknown recipient")
    targets = [d for d in drafts if d["recipient_id"] in selected]
    # Validate every target before any external side effect to avoid partial sends
    # caused by a stale recipient mapping.
    for draft in targets:
        assets = json.loads(draft["asset_ids_json"])
        if draft["recipient_id"].startswith("TEAM:"):
            placeholders = ",".join("?" for _ in assets)
            asset_teams = rows("SELECT DISTINCT t.team_channel FROM assets a JOIN teams t ON t.team=a.owner_team WHERE a.asset_id IN (" + placeholders + ")", tuple(assets)) if assets else []
            valid = any(t["team_channel"] == draft["recipient_channel"] for t in asset_teams)
        else:
            employee = rows("SELECT notification_channel FROM employees WHERE employee_id=? AND active=1", (draft["recipient_id"],))
            valid = bool(employee and employee[0]["notification_channel"] == draft["recipient_channel"])
        if not valid:
            raise HTTPException(400, f"Recipient channel is not allowlisted for {draft['recipient_id']}")
    for draft in targets:
        if draft["status"] in ("sent", "mocked") or draft["sent_at"]:
            raise HTTPException(409, f"Already delivered to {draft['recipient_id']}")
        if draft["status"] == "sending":
            raise HTTPException(409, f"Delivery is already in progress for {draft['recipient_id']}")
        if draft["status"] == "rejected":
            raise HTTPException(409, f"Notification for {draft['recipient_id']} was rejected")
    # Atomically claim every selected row. This prevents concurrent requests from
    # both passing the duplicate check and delivering the same notification.
    with connect() as db:
        for draft in targets:
            claimed = db.execute("UPDATE notifications SET status='sending' WHERE notification_id=? AND status IN ('approved','failed') AND sent_at IS NULL",
                                 (draft["notification_id"],))
            if claimed.rowcount != 1:
                raise HTTPException(409, f"Delivery is already in progress for {draft['recipient_id']}")
        db.commit()
    results = []
    try:  # one adapter per request so Photon looks up the conversation once
        adapter, adapter_error = get_adapter(), None
    except Exception as exc:  # bad mode/config still releases every claimed row as failed
        adapter, adapter_error = None, str(exc)
    for draft in targets:
        assets = json.loads(draft["asset_ids_json"])
        person = rows("SELECT display_name, role FROM employees WHERE employee_id=?", (draft["recipient_id"],))
        label = f"{person[0]['display_name']}, {person[0]['role']}" if person else draft["recipient_id"]
        try:
            if adapter is None:
                raise RuntimeError(adapter_error)
            result = adapter.send(draft["recipient_channel"], draft["subject"], draft["body"],
                                  recipient_label=label, idempotency_key=f"sentinelai:{draft['notification_id']}",
                                  recipient_id=draft["recipient_id"])
        except Exception as exc:  # delivery errors are visible and persisted
            result = {"status": "failed", "detail": str(exc)}
        state = result.get("status") if result.get("status") in ("sent", "mocked") else "failed"
        sent_at = datetime.now(timezone.utc).isoformat() if state in ("sent", "mocked") else None
        with connect() as db:
            db.execute("UPDATE notifications SET status=?, sent_at=?, delivery_result=? WHERE notification_id=?",
                       (state, sent_at, json.dumps(result), draft["notification_id"]))
        write_audit_event(incident_id, user["user_id"], "notification_" + state,
                          {"recipient_id": draft["recipient_id"], "channel": draft["recipient_channel"], "detail": result.get("detail")})
        results.append({"recipient_id": draft["recipient_id"], "asset_ids": assets, **result})
    current = rows("SELECT status FROM notifications WHERE incident_id=?", (incident_id,))
    if current and all(r["status"] in ("sent", "mocked") for r in current):
        with connect() as db:
            db.execute("UPDATE incidents SET status='notified' WHERE incident_id=?", (incident_id,))
    return {"incident_id": incident_id, "results": results}
