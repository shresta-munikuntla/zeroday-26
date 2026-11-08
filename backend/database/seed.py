"""Rebuild the SQLite database from data/seed/*.json.

Usage:  python -m backend.database.seed
Deletes the existing DB file first (decision: always a clean, repeatable state).
scenario_manifest.json is NOT loaded: it is the test answer key.
"""
import json
import os
from pathlib import Path

from backend.database.db import db_path, get_connection

ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "seed"
SCHEMA = Path(__file__).with_name("schema.sql")

# Order matters: parents before children (foreign keys).
TABLE_FILES = [
    ("assets", "assets.json"),
    ("accounts", "accounts.json"),
    ("security_logs", "security_logs.json"),
    ("permissions", "permissions.json"),
    ("teams", "teams.json"),
    ("employees", "employees.json"),
    ("employee_assets", "employee_assets.json"),
    ("approved_networks", "approved_networks.json"),
    ("maintenance_windows", "maintenance_windows.json"),
]


def _to_sql(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def seed(path: str | None = None, seed_dir: Path = SEED_DIR) -> dict[str, int]:
    path = path or db_path()
    if path != ":memory:" and os.path.exists(path):
        os.remove(path)
    counts: dict[str, int] = {}
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        for table, filename in TABLE_FILES:
            rows = json.loads((seed_dir / filename).read_text(encoding="utf-8"))
            columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]  # table names are constants
            for row in rows:
                unknown = set(row) - set(columns)
                if unknown:
                    raise ValueError(f"{filename}: unknown fields {sorted(unknown)}")
                keys = list(row)
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                    [_to_sql(row[k]) for k in keys],
                )
            counts[table] = len(rows)
        problems = conn.execute("PRAGMA foreign_key_check").fetchall()
        if problems:
            raise ValueError(f"foreign key problems: {[tuple(p) for p in problems]}")
        conn.commit()
    finally:
        conn.close()
    return counts


def main() -> None:
    path = db_path()
    counts = seed(path)
    print(f"Seeded {path}")
    for table, n in counts.items():
        print(f"  {table:<20} {n}")


if __name__ == "__main__":
    main()
