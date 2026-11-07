import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.agents.employee_notification import match_and_draft
from backend.security.audit import list_audit_events, write_audit_event
from backend.security.auth import current_user, require_role
from backend.storage import connect, demo_report, rows

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
Viewer = Annotated[dict, Depends(current_user)]
Reviewer = Annotated[dict, Depends(require_role("reviewer"))]


class ReviewRequest(BaseModel):
    comment: str = Field(default="", max_length=1000)


class DemoRequest(BaseModel):
    pass


def incident_or_404(incident_id: str) -> dict:
    results = rows("SELECT * FROM incidents WHERE incident_id=?", (incident_id,))
    if not results:
        raise HTTPException(404, "Incident not found")
    result = results[0]
    result["report"] = json.loads(result.pop("report_json"))
    return result


def notification_views(incident_id: str) -> list[dict]:
    drafts = rows("SELECT * FROM notifications WHERE incident_id=? ORDER BY recipient_id", (incident_id,))
    people = {x["employee_id"]: x for x in rows("SELECT employee_id,display_name,role,team FROM employees WHERE active=1")}
    result = []
    for draft in drafts:
        assets = json.loads(draft.pop("asset_ids_json"))
        person = people.get(draft["recipient_id"])
        result.append({**draft, "asset_ids": assets,
            "display_name": person["display_name"] if person else draft["recipient_id"].removeprefix("TEAM:"),
            "role": person["role"] if person else "Owner team",
            "team": person["team"] if person else draft["recipient_id"].removeprefix("TEAM:"),
            "why_selected": "Active owner of " + ", ".join(assets) if person else "Owner team fallback; no active individual owner."})
    return result


@router.post("/run-demo")
def run_demo(payload: DemoRequest, user: Viewer):
    report = demo_report()
    match_and_draft(report)
    with connect() as db:
        db.execute("UPDATE incidents SET status='awaiting_approval', approval_status='pending', report_json=? WHERE incident_id='INC-001'",
                   (json.dumps(report),))
        db.execute("UPDATE notifications SET status='draft', approved_by=NULL, approved_at=NULL, sent_at=NULL, delivery_result=NULL WHERE incident_id='INC-001'")
    write_audit_event("INC-001", user["user_id"], "demo_run", {"source": "synthetic fixture"})
    incident = incident_or_404("INC-001")
    return {**incident["report"], "status": incident["status"], "approval_status": incident["approval_status"]}


@router.get("")
def list_incidents(user: Viewer):
    return [{k: x[k] for k in ("incident_id", "severity", "status", "approval_status", "summary")} for x in rows(
        "SELECT incident_id,severity,status,approval_status,summary FROM incidents ORDER BY incident_id")]


@router.get("/{incident_id}")
def get_incident(incident_id: str, user: Viewer):
    incident = incident_or_404(incident_id)
    return {**incident["report"], "status": incident["status"], "approval_status": incident["approval_status"],
            "recipients": notification_views(incident_id),
            "audit": list_audit_events(incident_id)}


@router.get("/{incident_id}/evidence")
def evidence(incident_id: str, user: Viewer):
    report = incident_or_404(incident_id)["report"]
    return {"evidence_ids": report["evidence_ids"], "timeline": report["timeline"]}


@router.get("/{incident_id}/recipients")
def recipients(incident_id: str, user: Viewer):
    incident_or_404(incident_id)
    return notification_views(incident_id)


@router.get("/{incident_id}/audit")
def audit(incident_id: str, user: Viewer):
    incident_or_404(incident_id)
    return list_audit_events(incident_id)


@router.post("/{incident_id}/approve")
def approve(incident_id: str, payload: ReviewRequest, user: Reviewer):
    incident = incident_or_404(incident_id)
    if incident["approval_status"] != "pending":
        raise HTTPException(409, "Incident is not awaiting approval")
    with connect() as db:
        db.execute("UPDATE incidents SET approval_status='approved',status='approved' WHERE incident_id=?", (incident_id,))
        db.execute("UPDATE notifications SET status='approved',approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE incident_id=? AND status='draft'",
                   (user["user_id"], incident_id))
    write_audit_event(incident_id, user["user_id"], "approved", {"comment": payload.comment})
    return {"incident_id": incident_id, "approval_status": "approved", "approved_by": user["user_id"]}


@router.post("/{incident_id}/reject")
def reject(incident_id: str, payload: ReviewRequest, user: Reviewer):
    incident = incident_or_404(incident_id)
    if incident["approval_status"] != "pending":
        raise HTTPException(409, "Incident is not awaiting approval")
    with connect() as db:
        db.execute("UPDATE incidents SET approval_status='rejected',status='rejected' WHERE incident_id=?", (incident_id,))
        db.execute("UPDATE notifications SET status='rejected',approved_by=?,approved_at=CURRENT_TIMESTAMP WHERE incident_id=? AND status='draft'",
                   (user["user_id"], incident_id))
    write_audit_event(incident_id, user["user_id"], "rejected", {"comment": payload.comment})
    return {"incident_id": incident_id, "approval_status": "rejected"}
