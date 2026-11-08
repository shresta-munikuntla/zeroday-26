"""Least-privilege employee and owner routing queries."""
from backend.storage import connect


def get_employee_matches(asset_ids: list[str]) -> list[dict]:
    """Return active owners only; route ownerless assets to their team channel."""
    matches: list[dict] = []
    with connect() as db:
        for asset_id in dict.fromkeys(asset_ids):
            owners = db.execute("""SELECT e.employee_id, e.display_name, e.role, e.team,
                    ea.asset_id, ea.responsibility_type, e.notification_channel
                FROM employee_assets ea JOIN employees e USING(employee_id)
                WHERE ea.asset_id = ? AND ea.active = 1 AND e.active = 1
                  AND ea.responsibility_type = 'owner'""", (asset_id,)).fetchall()
            if owners:
                matches.extend(dict(row) for row in owners)
                continue
            asset = db.execute("SELECT owner_team FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
            if asset is None:
                continue
            team = db.execute("SELECT team_channel FROM teams WHERE team = ?", (asset["owner_team"],)).fetchone()
            if team:
                matches.append({"employee_id": f"TEAM:{asset['owner_team']}", "display_name": asset["owner_team"],
                    "role": "team", "team": asset["owner_team"], "asset_id": asset_id,
                    "responsibility_type": "team_fallback", "notification_channel": team["team_channel"]})
    return matches


def get_escalation_contact(team: str) -> dict | None:
    """Look up the escalation contact configured for an owner team."""
    with connect() as db:
        row = db.execute("""SELECT e.employee_id, e.display_name, e.role
            FROM teams t JOIN employees e ON e.employee_id=t.escalation_contact
            WHERE t.team=? AND e.active=1""", (team,)).fetchone()
    return dict(row) if row else None
