"""Sentinel — self-hosted, consent-based device monitoring, built for child safety.

v2 engine: versioned migrations, job queue with a real worker, geofencing with hysteresis,
device command channel, live WebSocket push, TOTP 2FA.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import threading
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import (Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket,
                     WebSocketDisconnect, status)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator

from . import auth, bus, db, geofence, queue, totp

EVENT_KINDS = {"sms", "call", "location", "app", "contact", "network", "sos"}
MAX_BATCH = 500
COMMAND_KINDS = {"locate_now", "ring", "sync_now"}


# --------------------------------------------------------------------------- lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    queue.register_all()
    stop = threading.Event()
    t = threading.Thread(target=queue.worker_loop, args=(stop,), name="sentinel-worker", daemon=True)
    t.start()
    if not os.environ.get("SENTINEL_SECRET"):
        print("[sentinel] WARNING: SENTINEL_SECRET not set; tokens reset on restart.", flush=True)
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=5)


app = FastAPI(title="Sentinel", version="2.0.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SENTINEL_ORIGINS", "*").split(","),
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


# --------------------------------------------------------------------------- models
class RegisterOrg(BaseModel):
    org_name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)


class Login(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class DeviceCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    owner_name: str = Field(min_length=1, max_length=80)
    owner_email: EmailStr
    lawful_basis: Literal["consent", "parental", "employment"]


class ConsentPayload(BaseModel):
    accepted: bool
    consent_version: str = "v1"
    notice_hash: str | None = None


class EnrollClaim(BaseModel):
    code: str = Field(min_length=6, max_length=64)
    model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    consent: ConsentPayload


class EventIn(BaseModel):
    kind: str
    ts: int
    direction: str | None = None
    counterpart: str | None = None
    body: str | None = None
    duration: int | None = None
    lat: float | None = None
    lon: float | None = None
    accuracy: float | None = None
    payload: dict[str, Any] | None = None

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in EVENT_KINDS:
            raise ValueError(f"kind must be one of {sorted(EVENT_KINDS)}")
        return v


class CommandAckIn(BaseModel):
    command_id: str
    status: Literal["acked", "failed"]
    result: dict[str, Any] | None = None


class SyncBatch(BaseModel):
    events: list[EventIn] = Field(default_factory=list)
    battery: int | None = None
    app_version: str | None = None

    @field_validator("events")
    @classmethod
    def cap(cls, v: list[EventIn]) -> list[EventIn]:
        if len(v) > MAX_BATCH:
            raise ValueError(f"max {MAX_BATCH} events per batch")
        return v


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["home", "school", "other"] = "other"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=200, ge=50, le=5000)
    notify_enter: bool = True
    notify_exit: bool = True


class PauseIn(BaseModel):
    seconds: int = Field(default=3600, ge=60, le=86400)
    reason: str | None = None


# --------------------------------------------------------------------------- deps
def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown"))


def current_user(request: Request, authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    claims = auth.read_token(authorization.split(" ", 1)[1].strip())
    if not claims:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    with db.read() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer exists")
    return db.row_to_dict(row)


def require_role(*roles: str):
    def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role: {' or '.join(roles)}")
        return user
    return _dep


def current_device(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing device token")
    token = authorization.split(" ", 1)[1].strip()
    with db.read() as c:
        row = c.execute("SELECT * FROM devices WHERE device_token = ?", (token,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown device token")
    d = db.row_to_dict(row)
    if d["status"] == "revoked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "device revoked by administrator")
    if d["status"] == "paused":
        raise HTTPException(status.HTTP_423_LOCKED, "monitoring paused")
    return d


def owned_device(device_id: str, org_id: str) -> dict:
    with db.read() as c:
        row = c.execute("SELECT * FROM devices WHERE id = ? AND org_id = ?", (device_id, org_id)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return db.row_to_dict(row)


def owned_zone(zone_id: str, org_id: str) -> dict:
    with db.read() as c:
        row = c.execute("SELECT * FROM zones WHERE id = ? AND org_id = ?", (zone_id, org_id)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "zone not found")
    return db.row_to_dict(row)


# --------------------------------------------------------------------------- alerts helper
def raise_alert(org_id: str, device_id: str, rule: str, severity: str, message: str,
                dedupe_key: str | None = None) -> dict | None:
    """Insert an alert (deduped) and push it to live subscribers. Safe to call from threads."""
    try:
        with db.conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO alerts (org_id, device_id, rule, severity, message, created_at, dedupe_key)
                   VALUES (?,?,?,?,?,?,?)""",
                (org_id, device_id, rule, severity, message, db.now(), dedupe_key),
            )
            row = c.execute("SELECT * FROM alerts WHERE device_id=? AND dedupe_key=? ORDER BY id DESC LIMIT 1",
                            (device_id, dedupe_key)).fetchone() if dedupe_key else None
    except sqlite3.Error as exc:
        print(f"[sentinel] alert insert failed: {exc}", flush=True)
        return None
    alert = db.row_to_dict(row) if row else {"rule": rule, "severity": severity, "message": message}
    bus.publish_sync(org_id, "alert", alert or {})
    return alert


# --------------------------------------------------------------------------- account
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "sentinel", "version": "2.0.0", "time": db.now(),
            "queue": queue.stats(), "live_subscribers": bus.subscriber_count()}


@app.post("/api/auth/register", status_code=201)
def register_org(body: RegisterOrg, request: Request) -> dict:
    with db.conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email = ?", (body.email.lower(),)).fetchone():
            raise HTTPException(409, "an account with that email already exists")
        org_id, user_id = db.new_id("org"), db.new_id("usr")
        c.execute("INSERT INTO orgs (id, name, created_at) VALUES (?,?,?)", (org_id, body.org_name, db.now()))
        c.execute(
            "INSERT INTO users (id, org_id, email, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, org_id, body.email.lower(), auth.hash_password(body.password), "owner", db.now()),
        )
    db.audit(org_id, user_id, "org.register", org_id, client_ip(request))
    return {"token": auth.make_token(user_id, org_id, "owner"),
            "user": {"id": user_id, "email": body.email.lower(), "role": "owner"},
            "org": {"id": org_id, "name": body.org_name}}


@app.post("/api/auth/login")
def login(body: Login, request: Request) -> dict:
    with db.read() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (body.email.lower(),)).fetchone()
    if not row or not auth.verify_password(body.password, row["password_hash"]):
        db.audit(None, None, "auth.login_failed", body.email.lower(), client_ip(request))
        raise HTTPException(401, "invalid email or password")
    if row["totp_enabled"]:
        if not body.totp_code:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "totp_required")
        if not totp.verify(row["totp_secret"], body.totp_code):
            db.audit(row["org_id"], row["id"], "auth.totp_failed", row["id"], client_ip(request))
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid two-factor code")
    db.audit(row["org_id"], row["id"], "auth.login", row["id"], client_ip(request))
    return {"token": auth.make_token(row["id"], row["org_id"], row["role"]),
            "user": {"id": row["id"], "email": row["email"], "role": row["role"], "totp_enabled": bool(row["totp_enabled"])},
            "org": {"id": row["org_id"]}}


@app.get("/api/me")
def me(user: dict = Depends(current_user)) -> dict:
    with db.read() as c:
        org = c.execute("SELECT id, name FROM orgs WHERE id = ?", (user["org_id"],)).fetchone()
    return {"user": {"id": user["id"], "email": user["email"], "role": user["role"],
                     "totp_enabled": bool(user["totp_enabled"])},
            "org": db.row_to_dict(org)}


@app.post("/api/auth/2fa/setup")
def setup_2fa(request: Request, user: dict = Depends(current_user)) -> dict:
    secret = totp.new_secret()
    with db.conn() as c:
        c.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, user["id"]))
    db.audit(user["org_id"], user["id"], "auth.2fa_setup", user["id"], client_ip(request))
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, user["email"]),
            "instructions": "Add this to your authenticator app, then POST the 6-digit code to /api/auth/2fa/enable."}


@app.post("/api/auth/2fa/enable")
def enable_2fa(body: dict, request: Request, user: dict = Depends(current_user)) -> dict:
    code = str(body.get("code", ""))
    if not user["totp_secret"] or not totp.verify(user["totp_secret"], code):
        raise HTTPException(400, "invalid code")
    with db.conn() as c:
        c.execute("UPDATE users SET totp_enabled=1 WHERE id=?", (user["id"],))
    db.audit(user["org_id"], user["id"], "auth.2fa_enabled", user["id"], client_ip(request))
    return {"ok": True, "totp_enabled": True}


# --------------------------------------------------------------------------- devices
@app.get("/api/devices")
def list_devices(user: dict = Depends(current_user)) -> dict:
    with db.read() as c:
        rows = c.execute(
            """SELECT d.id, d.label, d.owner_name, d.owner_email, d.platform, d.model, d.os_version,
                      d.app_version, d.status, d.consent_at, d.consent_version, d.last_seen, d.battery,
                      d.created_at,
                      (SELECT COUNT(*) FROM zones z WHERE z.device_id = d.id) AS zone_count,
                      (SELECT COUNT(*) FROM alerts a WHERE a.device_id = d.id AND a.acked_at IS NULL) AS open_alerts
               FROM devices d WHERE d.org_id = ? ORDER BY d.created_at DESC""",
            (user["org_id"],),
        ).fetchall()
        devices = db.rows_to_dicts(rows)
        for d in devices:
            loc = c.execute(
                "SELECT lat, lon, accuracy, ts FROM events WHERE device_id=? AND kind='location' "
                "ORDER BY ts DESC LIMIT 1", (d["id"],)).fetchone()
            d["last_location"] = db.row_to_dict(loc)
            d["last_location_age"] = (db.now() - loc["ts"] // 1000) if loc else None
            zone = c.execute(
                """SELECT z.name, z.kind FROM zones z JOIN zone_state s ON s.zone_id = z.id
                   WHERE z.device_id = ? AND s.inside = 1 LIMIT 1""", (d["id"],)).fetchone()
            d["current_zone"] = db.row_to_dict(zone)
    return {"devices": devices}


@app.post("/api/devices", status_code=201)
def create_device(body: DeviceCreate, request: Request, user: dict = Depends(require_role("owner", "operator"))) -> dict:
    device_id = db.new_id("dev")
    code = secrets.token_hex(4).upper()
    expires = db.now() + 3600
    with db.conn() as c:
        c.execute(
            """INSERT INTO devices (id, org_id, label, owner_name, owner_email, enroll_code, enroll_expires,
                                    status, created_at) VALUES (?,?,?,?,?,?,?,'pending',?)""",
            (device_id, user["org_id"], body.label, body.owner_name, body.owner_email.lower(), code, expires, db.now()),
        )
    db.audit(user["org_id"], user["id"], "device.create", device_id, client_ip(request),
             {"label": body.label, "lawful_basis": body.lawful_basis})
    return {"device_id": device_id, "enroll_code": code, "expires_at": expires,
            "enroll_url": f"/enroll?code={code}",
            "instructions": "Open Sentinel Agent on the device, enter this code, and read the consent screen together with the person who will carry it."}


@app.post("/api/devices/{device_id}/revoke")
def revoke_device(device_id: str, request: Request, user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    with db.conn() as c:
        c.execute("UPDATE devices SET status='revoked', device_token=NULL WHERE id=?", (device_id,))
    db.audit(user["org_id"], user["id"], "device.revoke", device_id, client_ip(request))
    return {"ok": True, "status": "revoked"}


@app.post("/api/devices/{device_id}/pause")
def pause_device(device_id: str, request: Request, user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    with db.conn() as c:
        c.execute("UPDATE devices SET status='paused' WHERE id=?", (device_id,))
    db.audit(user["org_id"], user["id"], "device.pause", device_id, client_ip(request))
    return {"ok": True, "status": "paused"}


@app.post("/api/devices/{device_id}/resume")
def resume_device(device_id: str, request: Request, user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    with db.conn() as c:
        c.execute("UPDATE devices SET status='active' WHERE id=? AND status='paused'", (device_id,))
    db.audit(user["org_id"], user["id"], "device.resume", device_id, client_ip(request))
    return {"ok": True, "status": "active"}


@app.delete("/api/devices/{device_id}")
def delete_device(device_id: str, request: Request, user: dict = Depends(require_role("owner"))) -> dict:
    owned_device(device_id, user["org_id"])
    with db.conn() as c:
        n = c.execute("SELECT COUNT(*) FROM events WHERE device_id=?", (device_id,)).fetchone()[0]
        c.execute("DELETE FROM events WHERE device_id=?", (device_id,))
        c.execute("DELETE FROM zones WHERE device_id=?", (device_id,))
        c.execute("DELETE FROM commands WHERE device_id=?", (device_id,))
        c.execute("DELETE FROM alerts WHERE device_id=?", (device_id,))
        c.execute("DELETE FROM devices WHERE id=?", (device_id,))
    db.audit(user["org_id"], user["id"], "device.delete", device_id, client_ip(request), {"events_deleted": n})
    return {"ok": True, "events_deleted": n}


# --------------------------------------------------------------------------- enrollment + sync
@app.post("/api/enroll/claim")
def claim_enrollment(body: EnrollClaim, request: Request) -> dict:
    if not body.consent.accepted:
        raise HTTPException(400, "consent must be accepted on the device before enrollment")
    with db.conn() as c:
        row = c.execute("SELECT * FROM devices WHERE enroll_code = ?", (body.code.strip().upper(),)).fetchone()
        if not row:
            raise HTTPException(404, "invalid enrollment code")
        d = db.row_to_dict(row)
        if d["status"] == "revoked":
            raise HTTPException(403, "this device has been revoked")
        if d["enroll_expires"] and d["enroll_expires"] < db.now():
            raise HTTPException(410, "enrollment code expired; generate a new one")
        token = db.new_token()
        ip = client_ip(request)
        c.execute(
            """UPDATE devices SET device_token=?, status='active', consent_at=?, consent_version=?,
                      consent_ip=?, model=?, os_version=?, app_version=?, last_seen=?, enroll_code=NULL
               WHERE id=?""",
            (token, db.now(), body.consent.consent_version, ip, body.model, body.os_version,
             body.app_version, db.now(), d["id"]),
        )
    db.audit(d["org_id"], None, "device.enroll", d["id"], client_ip(request),
             {"consent_version": body.consent.consent_version, "notice_hash": body.consent.notice_hash,
              "model": body.model, "os": body.os_version})
    queue.enqueue("device.enrolled", {"device_id": d["id"]})
    return {"device_token": token, "device_id": d["id"], "label": d["label"],
            "sync_interval_seconds": 300,
            "notice": "Monitoring is active and visible on this device."}


@app.post("/api/sync")
def sync(body: SyncBatch, device: dict = Depends(current_device)) -> dict:
    if device["status"] != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "device is not active")
    received = db.now()
    accepted = duplicates = 0
    with db.conn() as c:
        for ev in body.events:
            if ev.ts > (received + 300) * 1000:
                continue
            try:
                cur = c.execute(
                    """INSERT OR IGNORE INTO events
                       (device_id, kind, ts, received_at, direction, counterpart, body, duration,
                        lat, lon, accuracy, payload, dedupe_key)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (device["id"], ev.kind, ev.ts, received, ev.direction, ev.counterpart, ev.body,
                     ev.duration, ev.lat, ev.lon, ev.accuracy,
                     json.dumps(ev.payload) if ev.payload else None, _dedupe_key(ev)),
                )
                if cur.rowcount:
                    accepted += 1
                else:
                    duplicates += 1
            except sqlite3.IntegrityError:
                duplicates += 1
            except sqlite3.Error as exc:
                print(f"[sentinel] event insert failed: {exc}", flush=True)
                raise HTTPException(500, "storage error while ingesting events")
        c.execute(
            "UPDATE devices SET last_seen=?, battery=COALESCE(?, battery), app_version=COALESCE(?, app_version) WHERE id=?",
            (received, body.battery, body.app_version, device["id"]),
        )
        pending = c.execute(
            """SELECT id, kind, args, created_at FROM commands
               WHERE device_id=? AND status='pending' AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY created_at ASC LIMIT 20""",
            (device["id"], received),
        ).fetchall()
        if pending:
            c.execute(
                f"UPDATE commands SET status='delivered', delivered_at=? WHERE id IN ({','.join('?' * len(pending))})",
                [received, *[p["id"] for p in pending]],
            )

    # Heavy work goes to the queue rather than blocking the ingest path.
    if accepted:
        queue.enqueue("process.events", {
            "device_id": device["id"],
            "org_id": device["org_id"],
            "events": [e.model_dump() for e in body.events],
        })
    bus.publish_sync(device["org_id"], "sync", {
        "device_id": device["id"], "accepted": accepted, "at": received, "battery": body.battery,
    })
    return {"ok": True, "accepted": accepted, "duplicates": duplicates, "server_time": received,
            "next_sync_seconds": 300, "commands": db.rows_to_dicts(pending)}


def _dedupe_key(ev: EventIn) -> str:
    parts = [ev.kind, str(ev.ts), ev.direction or "", ev.counterpart or "", ev.body or "",
             str(ev.duration if ev.duration is not None else ""),
             f"{ev.lat:.6f}" if ev.lat is not None else "",
             f"{ev.lon:.6f}" if ev.lon is not None else ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@app.post("/api/device/commands/ack")
def ack_command(body: CommandAckIn, device: dict = Depends(current_device)) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM commands WHERE id=? AND device_id=?",
                        (body.command_id, device["id"])).fetchone()
        if not row:
            raise HTTPException(404, "command not found for this device")
        c.execute("UPDATE commands SET status=?, acked_at=?, result=? WHERE id=?",
                  (body.status, db.now(), json.dumps(body.result or {}), body.command_id))
    bus.publish_sync(device["org_id"], "command", {"id": body.command_id, "status": body.status,
                                                   "device_id": device["id"]})
    return {"ok": True}


@app.get("/api/device/config")
def device_config(device: dict = Depends(current_device)) -> dict:
    with db.read() as c:
        pol = c.execute("SELECT * FROM device_policy WHERE device_id=?", (device["id"],)).fetchone()
    policy = db.row_to_dict(pol) or {}
    return {
        "status": device["status"],
        "sync_interval_seconds": 300,
        "collect": {"sms": True, "call": True, "location": True, "apps": True},
        "show_persistent_notification": True,
        "policy": {
            "screen_time_start": policy.get("screen_time_start"),
            "screen_time_end": policy.get("screen_time_end"),
            "blocked_apps": json.loads(policy.get("blocked_apps") or "[]"),
        },
        "notice": "Monitoring is visible on the device at all times.",
    }


# --------------------------------------------------------------------------- zones
@app.get("/api/devices/{device_id}/zones")
def list_zones(device_id: str, user: dict = Depends(current_user)) -> dict:
    owned_device(device_id, user["org_id"])
    with db.read() as c:
        rows = c.execute(
            """SELECT z.*, COALESCE(s.inside, 0) AS inside, s.updated_at AS state_at
               FROM zones z LEFT JOIN zone_state s ON s.zone_id = z.id
               WHERE z.device_id = ? ORDER BY z.created_at""", (device_id,)).fetchall()
    return {"zones": db.rows_to_dicts(rows)}


@app.post("/api/devices/{device_id}/zones", status_code=201)
def create_zone(device_id: str, body: ZoneCreate, request: Request,
                user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    zone_id = db.new_id("zone")
    with db.conn() as c:
        c.execute(
            """INSERT INTO zones (id, org_id, device_id, name, kind, lat, lon, radius_m,
                                  notify_enter, notify_exit, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (zone_id, user["org_id"], device_id, body.name, body.kind, body.lat, body.lon,
             body.radius_m, int(body.notify_enter), int(body.notify_exit), db.now()),
        )
    db.audit(user["org_id"], user["id"], "zone.create", zone_id, client_ip(request),
             {"device_id": device_id, "name": body.name})
    return {"zone_id": zone_id, "ok": True}


@app.delete("/api/zones/{zone_id}")
def delete_zone(zone_id: str, request: Request, user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_zone(zone_id, user["org_id"])
    with db.conn() as c:
        c.execute("DELETE FROM zone_state WHERE zone_id=?", (zone_id,))
        c.execute("DELETE FROM zones WHERE id=?", (zone_id,))
    db.audit(user["org_id"], user["id"], "zone.delete", zone_id, client_ip(request))
    return {"ok": True}


# --------------------------------------------------------------------------- commands
@app.post("/api/devices/{device_id}/commands", status_code=201)
def create_command(device_id: str, body: dict, request: Request,
                   user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    kind = body.get("kind")
    if kind not in COMMAND_KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(COMMAND_KINDS)}")
    cmd_id = db.new_id("cmd")
    with db.conn() as c:
        c.execute(
            """INSERT INTO commands (id, org_id, device_id, kind, args, status, created_by, created_at, expires_at)
               VALUES (?,?,?,?,?,'pending',?,?,?)""",
            (cmd_id, user["org_id"], device_id, kind, json.dumps(body.get("args") or {}),
             user["id"], db.now(), db.now() + 3600),
        )
    db.audit(user["org_id"], user["id"], "command.create", cmd_id, client_ip(request),
             {"device_id": device_id, "kind": kind})
    bus.publish_sync(user["org_id"], "command", {
        "id": cmd_id, "kind": kind, "status": "pending", "device_id": device_id,
    })
    return {"command_id": cmd_id, "kind": kind, "status": "pending",
            "note": "Delivered on the device's next sync (≤5 min). The device shows a notification when it runs."}


@app.get("/api/devices/{device_id}/commands")
def list_commands(device_id: str, user: dict = Depends(current_user)) -> dict:
    owned_device(device_id, user["org_id"])
    with db.read() as c:
        rows = c.execute(
            "SELECT * FROM commands WHERE device_id=? ORDER BY created_at DESC LIMIT 50", (device_id,)
        ).fetchall()
    return {"commands": db.rows_to_dicts(rows)}


# --------------------------------------------------------------------------- policy
@app.put("/api/devices/{device_id}/policy")
def set_policy(device_id: str, body: dict, request: Request,
               user: dict = Depends(require_role("owner", "operator"))) -> dict:
    owned_device(device_id, user["org_id"])
    start, end = body.get("screen_time_start"), body.get("screen_time_end")
    for v in (start, end):
        if v is not None and (not isinstance(v, str) or len(v) != 5 or v[2] != ":"):
            raise HTTPException(400, "times must be HH:MM")
    blocked = body.get("blocked_apps") or []
    if not isinstance(blocked, list):
        raise HTTPException(400, "blocked_apps must be a list")
    with db.conn() as c:
        c.execute(
            """INSERT INTO device_policy (device_id, screen_time_start, screen_time_end, blocked_apps, updated_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(device_id) DO UPDATE SET
                 screen_time_start=excluded.screen_time_start,
                 screen_time_end=excluded.screen_time_end,
                 blocked_apps=excluded.blocked_apps,
                 updated_at=excluded.updated_at""",
            (device_id, start, end, json.dumps(blocked), db.now()),
        )
    db.audit(user["org_id"], user["id"], "policy.update", device_id, client_ip(request),
             {"screen_time": [start, end], "blocked_apps": blocked})
    return {"ok": True}


# --------------------------------------------------------------------------- data
@app.get("/api/devices/{device_id}/timeline")
def timeline(device_id: str, request: Request, kind: str | None = None, limit: int = 100,
             offset: int = 0, since: int | None = None,
             user: dict = Depends(current_user)) -> dict:
    owned_device(device_id, user["org_id"])
    limit = max(1, min(limit, 500))
    sql = "SELECT * FROM events WHERE device_id = ?"
    args: list[Any] = [device_id]
    if kind:
        if kind not in EVENT_KINDS:
            raise HTTPException(400, "unknown kind")
        sql += " AND kind = ?"
        args.append(kind)
    if since:
        sql += " AND ts >= ?"
        args.append(since)
    sql += " ORDER BY ts DESC LIMIT ? OFFSET ?"
    args += [limit, max(0, offset)]
    with db.read() as c:
        rows = c.execute(sql, args).fetchall()
        total = c.execute("SELECT COUNT(*) FROM events WHERE device_id=?", (device_id,)).fetchone()[0]
    db.audit(user["org_id"], user["id"], "device.read_timeline", device_id, client_ip(request), {"kind": kind})
    return {"events": db.rows_to_dicts(rows), "total": total, "limit": limit, "offset": offset}


@app.get("/api/devices/{device_id}/stats")
def stats(device_id: str, user: dict = Depends(current_user)) -> dict:
    owned_device(device_id, user["org_id"])
    with db.read() as c:
        by_kind = c.execute("SELECT kind, COUNT(*) n FROM events WHERE device_id=? GROUP BY kind",
                            (device_id,)).fetchall()
        today = (db.now() - 86400) * 1000
        last24 = c.execute("SELECT COUNT(*) FROM events WHERE device_id=? AND ts>=?",
                           (device_id, today)).fetchone()[0]
        top = c.execute(
            """SELECT counterpart, COUNT(*) n FROM events WHERE device_id=? AND counterpart IS NOT NULL
               GROUP BY counterpart ORDER BY n DESC LIMIT 5""", (device_id,)).fetchall()
    return {"by_kind": {r["kind"]: r["n"] for r in by_kind}, "last_24h": last24,
            "top_contacts": db.rows_to_dicts(top)}


@app.get("/api/devices/{device_id}/live")
def live(device_id: str, user: dict = Depends(current_user)) -> dict:
    owned_device(device_id, user["org_id"])
    with db.read() as c:
        loc = c.execute("SELECT lat, lon, accuracy, ts FROM events WHERE device_id=? AND kind='location' "
                        "ORDER BY ts DESC LIMIT 1", (device_id,)).fetchone()
        zones = c.execute(
            """SELECT z.id, z.name, z.kind, z.lat, z.lon, z.radius_m, COALESCE(s.inside,0) inside
               FROM zones z LEFT JOIN zone_state s ON s.zone_id=z.id WHERE z.device_id=?""",
            (device_id,)).fetchall()
        pol = c.execute("SELECT * FROM device_policy WHERE device_id=?", (device_id,)).fetchone()
    policy = db.row_to_dict(pol) or {}
    return {"location": db.row_to_dict(loc), "zones": db.rows_to_dicts(zones),
            "policy": {
                "screen_time_start": policy.get("screen_time_start"),
                "screen_time_end": policy.get("screen_time_end"),
                "blocked_apps": json.loads(policy.get("blocked_apps") or "[]"),
            }}


@app.get("/api/alerts")
def list_alerts(user: dict = Depends(current_user), unacked: bool = False) -> dict:
    sql = "SELECT a.*, d.label FROM alerts a JOIN devices d ON d.id=a.device_id WHERE a.org_id=?"
    args: list[Any] = [user["org_id"]]
    if unacked:
        sql += " AND a.acked_at IS NULL"
    sql += " ORDER BY a.created_at DESC LIMIT 200"
    with db.read() as c:
        rows = c.execute(sql, args).fetchall()
    return {"alerts": db.rows_to_dicts(rows)}


@app.post("/api/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, request: Request, user: dict = Depends(current_user)) -> dict:
    with db.conn() as c:
        row = c.execute("SELECT * FROM alerts WHERE id=? AND org_id=?", (alert_id, user["org_id"])).fetchone()
        if not row:
            raise HTTPException(404, "alert not found")
        c.execute("UPDATE alerts SET acked_at=?, acked_by=? WHERE id=?", (db.now(), user["id"], alert_id))
    db.audit(user["org_id"], user["id"], "alert.ack", str(alert_id), client_ip(request))
    return {"ok": True}


@app.get("/api/audit")
def audit_log(user: dict = Depends(require_role("owner")), limit: int = 200) -> dict:
    limit = max(1, min(limit, 1000))
    with db.read() as c:
        rows = c.execute("SELECT * FROM audit_log WHERE org_id=? ORDER BY ts DESC LIMIT ?",
                         (user["org_id"], limit)).fetchall()
    return {"entries": db.rows_to_dicts(rows)}


@app.get("/api/export/{device_id}")
def export_device(device_id: str, request: Request, user: dict = Depends(require_role("owner"))) -> JSONResponse:
    owned_device(device_id, user["org_id"])
    with db.read() as c:
        dev = c.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        events = c.execute("SELECT * FROM events WHERE device_id=? ORDER BY ts ASC", (device_id,)).fetchall()
    d = db.row_to_dict(dev)
    d.pop("device_token", None)
    d.pop("enroll_code", None)
    db.audit(user["org_id"], user["id"], "device.export", device_id, client_ip(request))
    return JSONResponse({"device": d, "events": db.rows_to_dicts(events), "exported_at": db.now()})


# --------------------------------------------------------------------------- live websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str = Query(default="")):
    claims = auth.read_token(token)
    if not claims:
        await ws.close(code=4401)
        return
    await ws.accept()
    q = await bus.subscribe()
    try:
        await ws.send_text(json.dumps({"topic": "hello", "data": {"ok": True}}))
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=25)
                if msg["org"] != claims["org"]:
                    continue
                await ws.send_text(json.dumps({"topic": msg["topic"], "data": msg["data"]}))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"topic": "ping", "data": {"t": db.now()}}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await bus.unsubscribe(q)


# --------------------------------------------------------------------------- web UI
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "web")
if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
