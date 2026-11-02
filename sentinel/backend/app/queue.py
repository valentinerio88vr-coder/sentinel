"""Postgres-style job queue on SQLite.

Rows are claimed with an atomic UPDATE ... WHERE id = (SELECT ...) so two workers can
never take the same job. Failed jobs retry with exponential backoff up to max_attempts,
then land in 'failed' where they stay visible instead of vanishing.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import traceback
from typing import Callable

from . import db

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{threading.get_ident()}"
LEASE_SECONDS = 120
POLL_INTERVAL = 0.5


def enqueue(kind: str, payload: dict | None = None, run_after: int | None = None,
            max_attempts: int = 5) -> int:
    ts = db.now()
    with db.conn() as c:
        cur = c.execute(
            """INSERT INTO jobs (kind, payload, status, attempts, max_attempts, run_after, created_at, updated_at)
               VALUES (?,?,'queued',0,?,?,?,?)""",
            (kind, json.dumps(payload or {}), max_attempts, run_after or ts, ts, ts),
        )
        return cur.lastrowid


def claim() -> dict | None:
    ts = db.now()
    with db.conn() as c:
        row = c.execute(
            """SELECT id FROM jobs
               WHERE status = 'queued' AND run_after <= ?
               ORDER BY run_after ASC, id ASC LIMIT 1""",
            (ts,),
        ).fetchone()
        if not row:
            return None
        cur = c.execute(
            """UPDATE jobs SET status='running', locked_by=?, locked_until=?, updated_at=?
               WHERE id = ? AND status = 'queued'""",
            (WORKER_ID, ts + LEASE_SECONDS, ts, row["id"]),
        )
        if cur.rowcount != 1:
            return None
        job = c.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
    return db.row_to_dict(job)


def complete(job_id: int) -> None:
    with db.conn() as c:
        c.execute("UPDATE jobs SET status='done', updated_at=?, locked_by=NULL WHERE id=?",
                  (db.now(), job_id))


def fail(job: dict, error: str) -> None:
    attempts = job["attempts"] + 1
    ts = db.now()
    terminal = attempts >= job["max_attempts"]
    backoff = min(300, 2 ** attempts)
    with db.conn() as c:
        c.execute(
            """UPDATE jobs SET status=?, attempts=?, last_error=?, updated_at=?,
                      locked_by=NULL, run_after=?
               WHERE id=?""",
            ("failed" if terminal else "queued", attempts, error[:2000], ts,
             ts if terminal else ts + backoff, job["id"]),
        )


def reap_expired_leases() -> int:
    """A worker that died mid-job releases its lease so the job can be retried."""
    ts = db.now()
    with db.conn() as c:
        cur = c.execute(
            """UPDATE jobs SET status='queued', locked_by=NULL, updated_at=?
               WHERE status='running' AND locked_until < ?""",
            (ts, ts),
        )
        return cur.rowcount


_HANDLERS: dict[str, Callable[[dict], None]] = {}


def handler(kind: str):
    def registrar(fn: Callable[[dict], None]) -> Callable[[dict], None]:
        _HANDLERS[kind] = fn
        return fn
    return registrar


def run_once() -> bool:
    job = claim()
    if not job:
        return False
    fn = _HANDLERS.get(job["kind"])
    if fn is None:
        fail(job, f"no handler registered for kind={job['kind']}")
        return True
    try:
        fn(json.loads(job["payload"] or "{}"))
        complete(job["id"])
    except Exception:
        fail(job, traceback.format_exc())
    return True


def worker_loop(stop: threading.Event) -> None:
    last_reap = 0.0
    while not stop.is_set():
        if time.time() - last_reap > 30:
            try:
                reap_expired_leases()
            except Exception:
                pass
            last_reap = time.time()
        try:
            if not run_once():
                stop.wait(POLL_INTERVAL)
        except Exception:
            stop.wait(1.0)


def stats() -> dict:
    with db.read() as c:
        rows = c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status").fetchall()
    return {r["status"]: r["n"] for r in rows}


def register_all() -> None:
    """Import handler modules so their @handler decorators run."""
    from . import jobs  # noqa: F401
    jobs.register_all()
