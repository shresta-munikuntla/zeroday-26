"""Read-only asset inventory queries."""
from backend.database.db import check_id, connection

_ASSET_COLUMNS = "asset_id, asset_name, asset_type, criticality, owner_team, environment, description"


def get_server_details(asset_id: str) -> dict | None:
    check_id(asset_id, "asset_id")
    with connection() as conn:
        row = conn.execute(f"SELECT {_ASSET_COLUMNS} FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    return dict(row) if row else None


def get_assets(asset_ids: list[str]) -> dict[str, dict]:
    """{asset_id: details} for the given IDs; unknown IDs are simply absent."""
    ids = [check_id(a, "asset_id") for a in asset_ids]
    if not ids:
        return {}
    with connection() as conn:
        rows = conn.execute(f"SELECT {_ASSET_COLUMNS} FROM assets WHERE asset_id IN ({', '.join('?' for _ in ids)})",
                            ids).fetchall()
    return {r["asset_id"]: dict(r) for r in rows}
