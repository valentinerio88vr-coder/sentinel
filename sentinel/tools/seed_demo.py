#!/usr/bin/env python3
"""Creates a demo family: two children, geofences, a day of movement, SOS, alerts."""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

_ap = argparse.ArgumentParser(description="Seed a demo family into a running Sentinel server.")
_ap.add_argument("--base", default=os.environ.get("SENTINEL_BASE", "http://127.0.0.1:8000"),
                 help="server URL (default: %(default)s)")
BASE = _ap.parse_args().base.rstrip("/")
EMAIL = "parent@sentinel.example.com"
PASSWORD = "SentinelDemo2026"

HOME = (19.1130, 72.8690)      # Andheri
SCHOOL = (19.1075, 72.8371)    # ~3.5km west
MUMBAI = (19.0760, 72.8777)


def call(method, path, body=None, token=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def jitter(pt, meters=120):
    lat, lon = pt
    lat += random.uniform(-meters, meters) / 111_000
    lon += random.uniform(-meters, meters) / (111_000 * math.cos(math.radians(lat)))
    return round(lat, 6), round(lon, 6)


code, d = call("POST", "/api/auth/register", {"org_name": "The Sharma Family", "email": EMAIL, "password": PASSWORD})
if code == 201:
    tok = d["token"]
    print(f"created demo account → {EMAIL} / {PASSWORD}")
else:
    code, d = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
    tok = d["token"]
    print("demo account exists, logged in")

for label, child, email_addr, seed in [
    ("Aarav's phone", "Aarav Sharma", "aarav@example.com", 11),
    ("Meera's phone", "Meera Sharma", "meera@example.com", 22),
]:
    random.seed(seed)
    code, d = call("POST", "/api/devices", {"label": label, "owner_name": child,
                                            "owner_email": email_addr, "lawful_basis": "parental"}, tok)
    if code != 201:
        print("device create failed:", d)
        sys.exit(1)
    dev_id, enroll = d["device_id"], d["enroll_code"]
    print(f"  {label} → enroll code {enroll}")

    # Enroll this simulated device directly (the enrollment code is single-use).
    code, d = call("POST", "/api/enroll/claim", {
        "code": enroll, "model": "Pixel 7a", "os_version": "Android 14", "app_version": "2.0.0",
        "consent": {"accepted": True, "consent_version": "v1", "notice_hash": "seed"},
    })
    if code != 200:
        continue
    dtok = d["device_token"]

    for name, kind, pt, radius in [
        ("School", "school", SCHOOL, 250),
        ("Home", "home", HOME, 180),
    ]:
        call("POST", f"/api/devices/{dev_id}/zones",
             {"name": name, "kind": kind, "lat": pt[0], "lon": pt[1], "radius_m": radius}, tok)

    # A believable day: home → school → home, with geofence transitions.
    now = int(time.time() * 1000)
    day = 24 * 3600 * 1000
    events = []

    def add(lat, lon, ts, acc):
        events.append({"kind": "location", "ts": ts, "lat": lat, "lon": lon,
                       "accuracy": acc, "payload": {"provider": "gps"}})

    # overnight at home
    for i in range(6):
        ts = now - day + i * 3600_000
        add(*jitter(HOME, 60), ts=ts, acc=round(random.uniform(6, 20), 1))
    # commute to school
    for i, frac in enumerate([0.2, 0.45, 0.7, 1.0]):
        lat = HOME[0] + (SCHOOL[0] - HOME[0]) * frac
        lon = HOME[1] + (SCHOOL[1] - HOME[1]) * frac
        add(*jitter((lat, lon), 40), ts=now - day + (7 * 3600 + i * 300) * 1000, acc=12.0)
    # at school
    for i in range(5):
        add(*jitter(SCHOOL, 45), ts=now - day + (9 * 3600 + i * 3600) * 1000, acc=round(random.uniform(6, 25), 1))
    # back home
    for i, frac in enumerate([0.3, 0.65, 1.0]):
        lat = SCHOOL[0] + (HOME[0] - SCHOOL[0]) * frac
        lon = SCHOOL[1] + (HOME[1] - SCHOOL[1]) * frac
        add(*jitter((lat, lon), 40), ts=now - day + (15 * 3600 + i * 420) * 1000, acc=15.0)
    # evening at home
    for i in range(3):
        add(*jitter(HOME, 50), ts=now - day + (19 * 3600 + i * 3600) * 1000, acc=10.0)
    # current position, minutes ago
    add(*jitter(SCHOOL if seed == 11 else HOME, 30), ts=now - 240_000, acc=8.0)

    # messages and calls for the activity feed
    for ts_off, direction, number, text in [
        (10, "in", "+91 00000 00001", "Reached school, all good."),
        (250, "in", "+91 00000 00002", "Can I come over after tuition?"),
        (400, "out", "+91 00000 00001", "Picking you up at 5."),
    ]:
        events.append({"kind": "sms", "ts": now - ts_off * 60_000, "direction": direction,
                       "counterpart": number, "body": text})
    events.append({"kind": "call", "ts": now - 180 * 60_000, "direction": "in",
                   "counterpart": "+91 00000 00001", "duration": 184})
    events.append({"kind": "call", "ts": now - 95 * 60_000, "direction": "out",
                   "counterpart": "+91 00000 00002", "duration": 62})
    for pkg in ["com.whatsapp", "com.google.android.youtube", "com.duolingo"]:
        events.append({"kind": "app", "ts": now - 300 * 60_000, "body": pkg,
                       "payload": {"action": "inventory", "package": pkg}})

    events.sort(key=lambda e: e["ts"])
    for i in range(0, len(events), 100):
        call("POST", "/api/sync", {"events": events[i:i + 100], "battery": random.randint(38, 92),
                                   "app_version": "2.0.0"}, dtok)
    print(f"    {len(events)} events, 2 geofences")

    if seed == 11:
        call("POST", "/api/sync", {"events": [
            {"kind": "sos", "ts": now - 600_000, "body": "triggered from lock screen"}]}, dtok)
        print("    SOS event pushed")

    # screen-time policy
    call("PUT", f"/api/devices/{dev_id}/policy",
         {"screen_time_start": "06:30", "screen_time_end": "21:30",
          "blocked_apps": ["com.tiktok", "com.zhiliaoapp.musically"]}, tok)

print(f"\nDone. Sign in with {EMAIL} / {PASSWORD}")
