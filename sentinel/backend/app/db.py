"""SQLite storage layer with a migration runner and thread-local connections.

Design notes
------------
* WAL mode + a generous busy_timeout so the sync path and the background worker can
  write concurrently without "database is locked" errors.
* Thread-local connections: FastAPI runs sync endpoints on a threadpool, and sqlite3
  objects must not be shared across threads.
* Migrations are versioned files in app/migrations, applied once, in order.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterable

DB_PATH = os.environ.get(
    "SENTINEL_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "sentinel.db"),
)
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

_local = threading.local()
_init_lock = threading.Lock()
_initialised = False


def now() -> int:
    return int(time.time())


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def new_token() -> str:
    return secrets.token_urlsafe(32)


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _get() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def conn():
    """Yield a thread-local connection inside an explicit transaction."""
    c = _get()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


@contextmanager
def read():
    """Read-only helper — no transaction needed for single statements under WAL."""
    yield _get()


def row_to_dict(r: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(r) if r is not None else None


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def init_db() -> None:
    global _initialised
    with _init_lock:
        if _initialised:
            return
        c = _connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at INTEGER)")
            applied = {r[0] for r in c.execute("SELECT version FROM schema_version")}
            for path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
                version = int(os.path.basename(path).split("_")[0])
                if version in applied:
                    continue
                with open(path, encoding="utf-8") as fh:
                    sql = fh.read()
                for stmt in _split_statements(sql):
                    _exec_tolerant(c, stmt)
                c.execute("INSERT INTO schema_version (version, applied_at) VALUES (?,?)", (version, now()))
            _ensure_columns(c)
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        finally:
            c.close()
        _initialised = True


def _split_statements(sql: str) -> list[str]:
    out, buf = [], []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip().rstrip(";").strip()
    if tail:
        out.append(tail)
    return out


def _exec_tolerant(c: sqlite3.Connection, stmt: str) -> None:
    try:
        c.execute(stmt)
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        # Re-running a migration against an existing database is expected; only
        # genuine schema conflicts are swallowed, everything else propagates.
        if "duplicate column name" in msg or "already exists" in msg:
            return
        raise


def _ensure_columns(c: sqlite3.Connection) -> None:
    """Additive column upgrades for databases created by older builds."""
    wanted = {
        "users": {
            "totp_secret": "TEXT",
            "totp_enabled": "INTEGER NOT NULL DEFAULT 0",
        },
        "devices": {
            "consent_withdrawn_at": "INTEGER",
        },
        "alerts": {
            "dedupe_key": "TEXT",
        },
        "events": {
            "dedupe_key": "TEXT",
        },
    }
    for table, cols in wanted.items():
        existing = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue
        for name, decl in cols.items():
            if name not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    # Backfill event dedupe keys if an older build left them null.
    missing = c.execute("SELECT COUNT(*) FROM events WHERE dedupe_key IS NULL").fetchone()[0]
    if missing:
        rows = c.execute(
            "SELECT id, kind, ts, direction, counterpart, body, duration, lat, lon FROM events WHERE dedupe_key IS NULL"
        ).fetchall()
        for r in rows:
            key = "|".join([
                r["kind"], str(r["ts"]), r["direction"] or "", r["counterpart"] or "", r["body"] or "",
                str(r["duration"] if r["duration"] is not None else ""),
                f"{r['lat']:.6f}" if r["lat"] is not None else "",
                f"{r['lon']:.6f}" if r["lon"] is not None else "",
            ])
            c.execute("UPDATE events SET dedupe_key=? WHERE id=?",
                      (hashlib.sha256(key.encode()).hexdigest(), r["id"]))
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedupe ON events(device_id, dedupe_key)")


def audit(org_id: str | None, user_id: str | None, action: str, target: str | None = None,
          ip: str | None = None, detail: str | None = None) -> None:
    """Every read and write of monitored data lands here."""
    with conn() as c:
        c.execute(
            "INSERT INTO audit_log (org_id, user_id, action, target, ip, detail, ts) VALUES (?,?,?,?,?,?,?)",
            (org_id, user_id, action, target, ip,
             json.dumps(detail) if isinstance(detail, (dict, list)) else detail, now()),
        )
