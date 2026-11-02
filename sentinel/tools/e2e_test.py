#!/usr/bin/env python3
"""End-to-end test suite for the Sentinel v2 engine.

Covers auth + 2FA, enrollment/consent, ingest + dedupe, the job queue, geofencing with
hysteresis, the device command channel, live alerting, policy, audit, erasure and the
WebSocket push channel.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASS, FAIL = [], []


def call(method, path, body=None, token=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "null")
        except json.JSONDecodeError:
            return e.code, raw


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}  {name}{('  → ' + str(extra)) if not cond and extra != '' else ''}")


def wait_for(fn, timeout=12, interval=0.25):
    """Poll until fn() is truthy — used to test async queue behaviour without sleeping blindly."""
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(interval)
    return None


email = f"qa{int(time.time())}@example.com"

# ---------------------------------------------------------------- auth
code, d = call("POST", "/api/auth/register", {"org_name": "QA Org", "email": email, "password": "correct-horse-battery"})
check("register org", code == 201 and "token" in d, d)
tok = d["token"]

code, d = call("POST", "/api/auth/register", {"org_name": "QA", "email": email, "password": "correct-horse-battery"})
check("duplicate email rejected", code == 409, code)
code, d = call("POST", "/api/auth/login", {"email": email, "password": "wrong-password-here"})
check("bad password rejected", code == 401, code)
code, d = call("GET", "/api/devices")
check("unauthenticated read blocked", code == 401, code)
code, d = call("GET", "/api/devices", token="garbage.token")
check("forged token rejected", code == 401, code)

# ---------------------------------------------------------------- 2FA lifecycle
code, d = call("POST", "/api/auth/2fa/setup", {}, tok)
check("2fa setup returns otpauth uri", code == 200 and d["otpauth_uri"].startswith("otpauth://totp/"), d)
secret = d["secret"]

sys.path.insert(0, "backend")
from app import totp as totp_mod  # noqa: E402  (same algorithm the server uses)
good_code = totp_mod.now_code(secret)

code, d = call("POST", "/api/auth/2fa/enable", {"code": "000000"}, tok)
check("2fa enable rejects wrong code", code == 400, code)
code, d = call("POST", "/api/auth/2fa/enable", {"code": good_code}, tok)
check("2fa enable accepts valid code", code == 200 and d["totp_enabled"], d)

code, d = call("POST", "/api/auth/login", {"email": email, "password": "correct-horse-battery"})
check("login without totp blocked when enabled", code == 401 and d.get("detail") == "totp_required", d)
code, d = call("POST", "/api/auth/login", {"email": email, "password": "correct-horse-battery", "totp_code": "111111"})
check("login with wrong totp blocked", code == 401, d)
code, d = call("POST", "/api/auth/login",
               {"email": email, "password": "correct-horse-battery", "totp_code": totp_mod.now_code(secret)})
check("login with valid totp succeeds", code == 200 and "token" in d, d)
tok = d["token"]

# ---------------------------------------------------------------- device + enrollment
code, d = call("POST", "/api/devices", {"label": "QA phone", "owner_name": "QA Child",
                                        "owner_email": "qa.child@example.com", "lawful_basis": "parental"}, tok)
check("create device + enroll code", code == 201 and len(d["enroll_code"]) == 8, d)
dev_id, enroll_code = d["device_id"], d["enroll_code"]

code, d = call("POST", "/api/enroll/claim", {"code": "BADCODE1", "consent": {"accepted": True}})
check("bad enroll code rejected", code == 404, code)
code, d = call("POST", "/api/enroll/claim", {"code": enroll_code, "consent": {"accepted": False}})
check("enrollment without consent refused", code == 400, code)
code, d = call("POST", "/api/enroll/claim", {"code": enroll_code, "model": "Pixel QA", "os_version": "Android 14",
                                             "app_version": "2.0.0",
                                             "consent": {"accepted": True, "consent_version": "v1", "notice_hash": "abc"}})
check("device enrolls with consent", code == 200 and "device_token" in d, d)
dev_tok = d["device_token"]
code, d = call("POST", "/api/enroll/claim", {"code": enroll_code, "consent": {"accepted": True}})
check("enroll code is single-use", code == 404, code)

# ---------------------------------------------------------------- geofences
code, d = call("POST", f"/api/devices/{dev_id}/zones",
               {"name": "School", "kind": "school", "lat": 19.0760, "lon": 72.8777, "radius_m": 200}, tok)
check("create school zone", code == 201 and "zone_id" in d, d)
school_zone = d["zone_id"]
code, d = call("POST", f"/api/devices/{dev_id}/zones",
               {"name": "Home", "kind": "home", "lat": 19.1200, "lon": 72.9000, "radius_m": 150}, tok)
check("create home zone", code == 201, d)
code, d = call("POST", f"/api/devices/{dev_id}/zones",
               {"name": "Bad", "kind": "school", "lat": 999, "lon": 0, "radius_m": 200}, tok)
check("invalid latitude rejected", code == 422, code)
code, d = call("GET", f"/api/devices/{dev_id}/zones", token=tok)
check("zones listed with state", code == 200 and len(d["zones"]) == 2, d)

# ---------------------------------------------------------------- ingest
now = int(time.time() * 1000)
events = [
    {"kind": "location", "ts": now - 60000, "lat": 19.0760, "lon": 72.8777, "accuracy": 10.0, "payload": {"provider": "gps"}},
    {"kind": "sms", "ts": now - 50000, "direction": "in", "counterpart": "+919820011223", "body": "Client call moved to 4pm."},
    {"kind": "call", "ts": now - 40000, "direction": "in", "counterpart": "+919930044556", "duration": 4210},
    {"kind": "app", "ts": now - 30000, "body": "com.whatsapp", "payload": {"action": "install", "package": "com.whatsapp"}},
    {"kind": "sms", "ts": now + 999999999, "body": "future timestamp should be dropped"},
]
code, d = call("POST", "/api/sync", {"events": events}, dev_tok)
check("sync accepts valid batch", code == 200 and d["accepted"] == 4, d)
check("future-dated event dropped", d["accepted"] == 4, d)
check("sync returns command list", "commands" in d, d.keys())

code, d = call("POST", "/api/sync", {"events": events}, dev_tok)
check("replay is idempotent", code == 200 and d["accepted"] == 0 and d["duplicates"] == 4, d)

code, d = call("POST", "/api/sync", {"events": [{"kind": "nope", "ts": now}]}, dev_tok)
check("invalid kind rejected by schema", code == 422, code)
code, d = call("POST", "/api/sync", {"events": []}, None)
check("sync without device token blocked", code == 401, code)

# ---------------------------------------------------------------- async queue work
code, d = call("GET", "/api/health")
check("health exposes queue stats", code == 200 and "queue" in d, d)
initial_done = d["queue"].get("done", 0)

alerts = wait_for(lambda: (lambda r: r[1]["alerts"] if r[0] == 200 and r[1]["alerts"] else None)(
    call("GET", "/api/alerts", token=tok)), timeout=15)
check("worker processed queued events (alerts appeared)", bool(alerts), "no alerts after 15s")
rules = {a["rule"] for a in (alerts or [])}
check("long-call rule fired via worker", "unusually_long_call" in rules, rules)
check("app-install rule fired via worker", "app_installed" in rules, rules)

code, d = call("GET", "/api/health")
check("queue drained to done", d["queue"].get("done", 0) > initial_done, d["queue"])

# ---------------------------------------------------------------- geofence transitions
code, d = call("GET", f"/api/devices/{dev_id}/zones", token=tok)
school = [z for z in d["zones"] if z["name"] == "School"][0]
check("first fix establishes zone baseline inside", school["inside"] == 1, school)

# leave the zone (move ~5km away) -> exit alert
far = [{"kind": "location", "ts": now - 20000, "lat": 19.1200, "lon": 72.9000, "accuracy": 10.0}]
call("POST", "/api/sync", {"events": far}, dev_tok)
exit_alert = wait_for(lambda: next((a for a in call("GET", "/api/alerts", token=tok)[1]["alerts"]
                                    if a["rule"] == "zone_exit"), None), timeout=15)
check("geofence exit alert fired", exit_alert is not None, "no zone_exit alert")
check("exit alert names the zone", exit_alert and "School" in exit_alert["message"], exit_alert)

# a low-accuracy fix inside the fence must NOT flip state (accuracy > radius)
noisy = [{"kind": "location", "ts": now - 10000, "lat": 19.0760, "lon": 72.8777, "accuracy": 900.0}]
call("POST", "/api/sync", {"events": noisy}, dev_tok)
time.sleep(2.5)
code, d = call("GET", f"/api/devices/{dev_id}/zones", token=tok)
school = [z for z in d["zones"] if z["name"] == "School"][0]
check("low-accuracy fix does not flip zone state", school["inside"] == 0, school)

# re-enter with a good fix -> enter alert
back = [{"kind": "location", "ts": now - 5000, "lat": 19.0761, "lon": 72.8778, "accuracy": 8.0}]
call("POST", "/api/sync", {"events": back}, dev_tok)
enter_alert = wait_for(lambda: next((a for a in call("GET", "/api/alerts", token=tok)[1]["alerts"]
                                     if a["rule"] == "zone_enter"), None), timeout=15)
check("geofence enter alert fired on return", enter_alert is not None, "no zone_enter alert")

# ---------------------------------------------------------------- SOS
sos = [{"kind": "sos", "ts": now - 1000, "body": "triggered from lock screen"}]
call("POST", "/api/sync", {"events": sos}, dev_tok)
sos_alert = wait_for(lambda: next((a for a in call("GET", "/api/alerts", token=tok)[1]["alerts"]
                                   if a["rule"] == "sos"), None), timeout=15)
check("SOS raises a critical alert", sos_alert is not None and sos_alert["severity"] == "critical", sos_alert)

# ---------------------------------------------------------------- command channel
code, d = call("POST", f"/api/devices/{dev_id}/commands", {"kind": "locate_now"}, tok)
check("create command", code == 201 and d["status"] == "pending", d)
cmd_id = d["command_id"]
code, d = call("POST", f"/api/devices/{dev_id}/commands", {"kind": "rm_rf"}, tok)
check("unknown command rejected", code == 400, code)

code, d = call("GET", "/api/devices/live", token=tok)
check("live endpoint requires device id", code in (404, 405, 422), code)

code, d = call("GET", f"/api/devices/{dev_id}/live", token=tok)
check("live endpoint returns location + zones", code == 200 and d["location"] is not None and len(d["zones"]) == 2, d)
check("live shows current zone membership", any(z["inside"] == 1 for z in d["zones"]), d["zones"])

code, d = call("POST", "/api/sync", {"events": []}, dev_tok)
delivered = [c for c in d.get("commands", []) if c["id"] == cmd_id]
check("command delivered on next sync", len(delivered) == 1 and delivered[0]["kind"] == "locate_now", d.get("commands"))
code, d = call("POST", "/api/sync", {"events": []}, dev_tok)
check("command not re-delivered twice", not any(c["id"] == cmd_id for c in d.get("commands", [])), d.get("commands"))

code, d = call("POST", "/api/device/commands/ack", {"command_id": cmd_id, "status": "acked",
                                                    "result": {"lat": 19.07, "lon": 72.87}}, dev_tok)
check("device acks command", code == 200, d)
code, d = call("GET", f"/api/devices/{dev_id}/commands", token=tok)
acked = [c for c in d["commands"] if c["id"] == cmd_id][0]
check("command status is acked", acked["status"] == "acked" and acked["acked_at"] is not None, acked)

code, d = call("POST", "/api/device/commands/ack", {"command_id": "cmd_nonexistent", "status": "acked"}, dev_tok)
check("cannot ack another device's command", code == 404, code)

# ---------------------------------------------------------------- policy
code, d = call("PUT", f"/api/devices/{dev_id}/policy",
               {"screen_time_start": "07:00", "screen_time_end": "21:30", "blocked_apps": ["com.tiktok"]}, tok)
check("set device policy", code == 200, d)
code, d = call("PUT", f"/api/devices/{dev_id}/policy", {"screen_time_start": "7am"}, tok)
check("malformed time rejected", code == 400, code)
code, d = call("GET", "/api/device/config", token=dev_tok)
check("device receives policy", code == 200 and d["policy"]["screen_time_end"] == "21:30" and
      d["policy"]["blocked_apps"] == ["com.tiktok"], d)
check("notification cannot be disabled by server", d["show_persistent_notification"] is True, d)

# ---------------------------------------------------------------- data reads
code, d = call("GET", f"/api/devices/{dev_id}/timeline", token=tok)
check("timeline returns events", code == 200 and d["total"] == 8, d.get("total"))
code, d = call("GET", f"/api/devices/{dev_id}/timeline?kind=sms", token=tok)
check("timeline kind filter", code == 200 and all(e["kind"] == "sms" for e in d["events"]), d.get("total"))
code, d = call("GET", f"/api/devices/{dev_id}/stats", token=tok)
check("stats aggregates by kind", code == 200 and d["by_kind"].get("location") == 4, d)

code, d = call("GET", "/api/devices", token=tok)
dev = [x for x in d["devices"] if x["id"] == dev_id][0]
check("device list includes last location", dev["last_location"] is not None, dev.get("last_location"))
check("device list includes zone count", dev["zone_count"] == 2, dev.get("zone_count"))
check("consent recorded on device", dev["consent_at"] is not None and dev["status"] == "active", dev)

code, d = call("GET", "/api/alerts", token=tok)
aid = d["alerts"][0]["id"]
code, d = call("POST", f"/api/alerts/{aid}/ack", token=tok)
check("alert ack works", code == 200, code)

code, d = call("GET", f"/api/export/{dev_id}", token=tok)
check("export omits credentials", code == 200 and "device_token" not in d["device"], "leak?")

code, d = call("GET", "/api/audit", token=tok)
actions = {e["action"] for e in d.get("entries", [])}
check("audit records reads", "device.read_timeline" in actions, actions)
check("audit records enrollment", "device.enroll" in actions, actions)
check("audit records commands", "command.create" in actions, actions)
check("audit records 2fa", "auth.2fa_enabled" in actions, actions)

# ---------------------------------------------------------------- kill switch + erasure
code, d = call("POST", f"/api/devices/{dev_id}/pause", token=tok)
check("pause succeeds", code == 200, code)
code, d = call("POST", "/api/sync", {"events": []}, dev_tok)
check("paused device cannot sync", code == 423, code)
code, d = call("POST", f"/api/devices/{dev_id}/resume", token=tok)
check("resume succeeds", code == 200, code)
code, d = call("POST", "/api/sync", {"events": []}, dev_tok)
check("resumed device can sync again", code == 200, code)

code, d = call("POST", f"/api/devices/{dev_id}/revoke", token=tok)
check("revoke succeeds", code == 200, code)
code, d = call("POST", "/api/sync", {"events": []}, dev_tok)
check("revoked device token rejected", code in (401, 403), code)

code, d = call("DELETE", f"/api/devices/{dev_id}", token=tok)
check("device delete succeeds", code == 200, code)
code, d = call("GET", f"/api/devices/{dev_id}/timeline", token=tok)
check("device gone after delete", code == 404, code)
code, d = call("GET", f"/api/alerts", token=tok)
check("alerts purged with device", all(a["device_id"] != dev_id for a in d["alerts"]), "orphan alerts")
code, d = call("GET", f"/api/devices/{dev_id}/zones", token=tok)
check("zones purged with device", code == 404, code)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
