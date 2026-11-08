"""Run the available detection and investigation agents on the seeded event store."""
from backend.agents.investigation import investigate
from backend.agents.threat_detection import detect
from backend.tools.asset_queries import get_assets
from backend.tools.security_queries import get_security_events


def run_detection_and_investigation(filters: dict | None = None) -> list[dict]:
    """Return paired Agent 1 and Agent 2 outputs for each detected incident."""
    return [{"detection": detection, "investigation": investigate(detection)}
            for detection in detect(filters)]


def dashboard_report(agent_outputs: dict) -> dict:
    """Project Agent 1/2 contracts into the fields consumed by the review UI.

    The original agent outputs are retained so Agent 5 can use their typed fields
    directly. Timeline entries are enriched only with safe columns from P1's query tool.
    """
    detection = agent_outputs["detection"]
    investigation = agent_outputs["investigation"]
    account_ids = detection.get("account_ids", [])
    time_window = detection.get("time_window", {})
    records = []
    for account_id in account_ids:
        filters = {"account_id": account_id}
        if time_window.get("start"):
            filters["start"] = time_window["start"]
        if time_window.get("end"):
            filters["end"] = time_window["end"]
        records.extend(get_security_events(filters))
    event_ids = set(detection.get("evidence_ids", []))
    records_by_id = {event["event_id"]: event for event in records if event["event_id"] in event_ids}

    timeline = []
    used_event_ids = set()
    for step in investigation.get("timeline", []):
        for event_id in step.get("evidence_ids", []):
            if event_id not in records_by_id or event_id in used_event_ids:
                continue
            event = records_by_id[event_id]
            timeline.append({"event_id": event_id, "timestamp": event["timestamp"],
                "event_type": event["event_type"], "asset_id": event["asset_id"],
                "outcome": event["status"], "description": step.get("description", ""),
                "evidence_ids": step.get("evidence_ids", [event_id])})
            used_event_ids.add(event_id)

    asset_ids = detection.get("affected_asset_ids", [])
    inventory = get_assets(asset_ids)
    investigated_assets = {asset["asset_id"]: asset
                           for asset in investigation.get("affected_assets", [])}
    assets = []
    for asset_id in asset_ids:
        asset = {**inventory.get(asset_id, {}), **investigated_assets.get(asset_id, {})}
        if asset:
            assets.append(asset)

    return {
        "incident_id": detection["incident_id"],
        "account_id": (detection.get("account_ids") or [None])[0],
        "account_ids": detection.get("account_ids", []),
        "severity": investigation.get("severity", detection.get("severity_initial", "unknown")),
        "summary": detection.get("summary", "Suspicious activity requires review."),
        "time_window": time_window,
        "affected_asset_ids": asset_ids,
        "assets": assets,
        "timeline": timeline,
        "evidence_ids": investigation.get("evidence_ids", detection.get("evidence_ids", [])),
        "facts": investigation.get("confirmed_facts", []),
        "recommended_actions": investigation.get("benign_explanations_to_check", []),
        "mitre_techniques": [],
        "policy_references": [],
        "status": "awaiting_approval",
        "approval_status": "pending",
        "detection": detection,
        "investigation": investigation,
        "intelligence": agent_outputs.get("intelligence", {}),
    }
