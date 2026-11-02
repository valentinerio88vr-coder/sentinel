"""Job handlers. Everything that isn't a fast read/write of one row happens here.

The ingest endpoint only inserts events and enqueues; this module does the thinking:
alert rules, geofence transitions, offline detection.
"""
from __future__ import annotations

import json

from . import bus, db, geofence, queue

OFFLINE_AFTER = 3600  # seconds without a sync before we tell the parent


def register_all() -> None:
    """Kick the recurring jobs once, then let the worker pick them up."""
    with db.read() as c:
        existing = c.execute("SELECT 1 FROM jobs WHERE kind='check.offline' LIMIT 1").fetchone()
        existing_z = c.execute("SELECT 1 FROM jobs WHERE kind='sweep.zone_staleness' LIMIT 1").fetchone()
    if not existing:
        queue.enqueue("check.offline", {}, run_after=db.now() + 60)
    if not existing_z:
        queue.enqueue("sweep.zone_staleness", {}, run_after=db.now() + 120)


@queue.handler("process.events")
def process_events(payload: dict) -> None:
    device_id = payload["device_id"]
    org_id = payload["org_id"]
    events = payload.get("events") or []

    for ev in events:
        kind = ev.get("kind")

        if kind == "sos":
            queue_alert = queue_alert_sos
            queue_alert(org_id, device_id, ev)

        elif kind == "location" and ev.get("lat") is not None and ev.get("lon") is not None:
            transitions = geofence.evaluate_point(
                device_id, ev["lat"], ev["lon"], ev.get("accuracy"))
            for t in transitions:
                _alert(org_id, device_id, "zone_" + ("enter" if t["inside"] else "exit"),
                       "high" if t["zone_kind"] == "school" else "info",
                       t["message"], dedupe_key=f"{t['dedupe_key']}:{db.now() // 3600}")

        elif kind == "call" and (ev.get("duration") or 0) > 3600:
            _alert(org_id, device_id, "unusually_long_call", "info",
                   f"Call with {ev.get('counterpart')} lasted over an hour.",
                   dedupe_key=f"longcall:{ev.get('ts')}")

        elif kind == "app" and (ev.get("payload") or {}).get("action") == "install":
            pkg = (ev.get("payload") or {}).get("package", "unknown")
            _alert(org_id, device_id, "app_installed", "info", f"App installed: {pkg}",
                   dedupe_key=f"install:{pkg}")


def queue_alert_sos(org_id: str, device_id: str, ev: dict) -> None:
    _alert(org_id, device_id, "sos", "critical",
           f"SOS triggered on the device{': ' + ev['body'] if ev.get('body') else ''}",
           dedupe_key=f"sos:{ev.get('ts')}")


def _alert(org_id: str, device_id: str, rule: str, severity: str, message: str,
           dedupe_key: str | None = None) -> None:
    try:
        with db.conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO alerts (org_id, device_id, rule, severity, message, created_at, dedupe_key)
                   VALUES (?,?,?,?,?,?,?)""",
                (org_id, device_id, rule, severity, message, db.now(), dedupe_key),
            )
    except Exception as exc:
        print(f"[sentinel] alert insert failed: {exc}", flush=True)
        return
    bus.publish_sync(org_id, "alert", {
        "rule": rule, "severity": severity, "message": message, "device_id": device_id,
    })


@queue.handler("device.enrolled")
def device_enrolled(payload: dict) -> None:
    with db.read() as c:
        row = c.execute("SELECT org_id, label FROM devices WHERE id=?", (payload.get("device_id"),)).fetchone()
    if row:
        bus.publish_sync(row["org_id"], "device", {"device_id": payload.get("device_id"),
                                                   "event": "enrolled", "label": row["label"]})


@queue.handler("check.offline")
def check_offline(payload: dict) -> None:
    """Re-enqueues itself. One stale device gets one alert, not one per sweep."""
    cutoff = db.now() - OFFLINE_AFTER
    with db.read() as c:
        rows = c.execute(
            "SELECT id, org_id, last_seen, label FROM devices WHERE status='active' AND last_seen IS NOT NULL AND last_seen < ?",
            (cutoff,),
        ).fetchall()
    for r in rows:
        hours = round((db.now() - r["last_seen"]) / 3600, 1)
        _alert(r["org_id"], r["id"], "device_offline", "medium",
               f"{r['label']} has not synced for {hours}h. Check the device is on and connected.",
               dedupe_key=f"offline:{r['id']}:{db.now() // 21600}")  # once per 6h window
    queue.enqueue("check.offline", {}, run_after=db.now() + 300)


@queue.handler("sweep.zone_staleness")
def sweep_zone_staleness(payload: dict) -> None:
    """If no location fix has arrived for a device in 2h, its zone state is untrustworthy."""
    cutoff = (db.now() - 7200) * 1000
    with db.read() as c:
        stale = c.execute(
            """SELECT z.id FROM zones z
               WHERE NOT EXISTS (SELECT 1 FROM events e
                                 WHERE e.device_id=z.device_id AND e.kind='location' AND e.ts > ?)""",
            (cutoff,),
        ).fetchall()
    if stale:
        with db.conn() as c:
            for r in stale:
                c.execute("UPDATE zone_state SET inside=0, updated_at=? WHERE zone_id=?", (db.now(), r["id"]))
    queue.enqueue("sweep.zone_staleness", {}, run_after=db.now() + 1800)
