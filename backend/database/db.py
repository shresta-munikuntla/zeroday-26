"""SQLite connection helpers and shared conventions.

Decisions (docs/architecture.md section 5): built-in sqlite3, '?' placeholders only,
ISO-8601 UTC text timestamps, *_json columns stored with json.dumps().
"""
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DEFAULT_DATABASE_URL = "sqlite:///./sentinelai.db"
_SQLITE_PREFIX = "sqlite:///"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def db_path() -> str:
    """File path from DATABASE_URL (read on every call so tests can point elsewhere)."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not url.startswith(_SQLITE_PREFIX):
        raise ValueError("DATABASE_URL must start with 'sqlite:///'")
    return url[len(_SQLITE_PREFIX):]


def get_connection(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(path: str | None = None):
    """`with connection() as conn:` — commits on success and ALWAYS closes.
    (sqlite3's own `with conn:` commits but leaves the file open, which blocks reseeding on Windows.)"""
    conn = get_connection(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- timestamps
def parse_ts(value: str) -> datetime:
    """'2026-11-07T09:10:00Z' -> aware UTC datetime. Raises ValueError on bad input."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def normalize_ts(value: str) -> str:
    """Validate a timestamp and return it in the stored format (so text comparison is correct)."""
    return format_ts(parse_ts(value))


# ---------------------------------------------------------------- validation + rows
def check_id(value: str, name: str = "id") -> str:
    """Reject anything that doesn't look like one of our IDs (defence in depth; SQL still uses '?')."""
    if not isinstance(value, str) or not _ID_PATTERN.match(value):
        raise ValueError(f"invalid {name}: {value!r}")
    return value


def row_to_dict(row: sqlite3.Row) -> dict:
    """Row -> dict, decoding every *_json column."""
    out = dict(row)
    for key, val in out.items():
        if key.endswith("_json") and isinstance(val, str):
            out[key] = json.loads(val)
    return out


# ---------------------------------------------------------------- incidents
def evidence_key(evidence_ids: list[str]) -> str:
    return ",".join(sorted(set(evidence_ids)))


def find_incident_by_evidence(evidence_ids: list[str]) -> str | None:
    with connection() as conn:
        row = conn.execute("SELECT incident_id FROM incidents WHERE evidence_key = ?",
                           (evidence_key(evidence_ids),)).fetchone()
    return row["incident_id"] if row else None


def next_incident_number() -> int:
    """Next free INC number (MAX + 1). Agent 1 adds an offset when it finds several incidents in one run."""
    with connection() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(incident_id, 5) AS INTEGER)) AS n FROM incidents").fetchone()
    return (row["n"] or 0) + 1


def next_incident_id() -> str:
    return f"INC-{next_incident_number():03d}"
