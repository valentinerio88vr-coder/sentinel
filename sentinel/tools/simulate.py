#!/usr/bin/env python3
"""Virtual Sentinel device.

Proves the whole pipeline end-to-end without a phone: claims an enrollment code the same
way the Android agent does, then posts a realistic stream of SMS / call / location events
using the production ingest API.

    python3 tools/simulate.py --base http://127.0.0.1:8000 --code ABCD1234 --days 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.request

NOTICE = "Sentinel monitoring is being enabled on this device. (see Agent consent screen)"


def post(base: str, path: str, body: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--code", required=True, help="enrollment code from the console")
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--device-model", default="Pixel 7 (simulated)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    random.seed(args.seed)
    enroll = post(args.base, "/api/enroll/claim", {
        "code": args.code,
        "model": args.device_model,
        "os_version": "Android 14 (simulated)",
        "app_version": "1.0.0-sim",
        "consent": {"accepted": True, "consent_version": "v1",
                    "notice_hash": hashlib.sha256(NOTICE.encode()).hexdigest()[:32]},
    })
    token, device_id = enroll["device_token"], enroll["device_id"]
    print(f"enrolled: device={device_id} label={enroll['label']}")

    contacts = ["+91 00000 00001", "+91 00000 00002", "+91 00000 00003", "Asha Rao", "Vodafone IN"]
    sms_samples = [
        "Reached office, will call after the 4pm review.",
        "Your delivery will arrive between 6 and 8 pm today.",
        "Is the report ready? Client call is at 11.",
        "Don't forget mum's appointment on Thursday.",
        "Payment of INR 2,400 received. Ref 8841.",
        "Lunch tomorrow? There's a new place near the station.",
    ]
    now_ms = int(time.time() * 1000)
    span = args.days * 24 * 3600 * 1000
    events: list[dict] = []

    for _ in range(120):
        ts = now_ms - random.randint(0, span)
        events.append({"kind": "sms", "ts": ts,
                       "direction": random.choice(["in", "in", "out"]),
                       "counterpart": random.choice(contacts),
                       "body": random.choice(sms_samples)})

    for _ in range(60):
        ts = now_ms - random.randint(0, span)
        events.append({"kind": "call", "ts": ts,
                       "direction": random.choice(["in", "out"]),
                       "counterpart": random.choice(contacts),
                       "duration": random.choice([0, 34, 92, 210, 780, 4210]),
                       "payload": {"missed": random.random() < 0.2}})

    base_lat, base_lon = 19.0760, 72.8777  # Mumbai
    for _ in range(80):
        ts = now_ms - random.randint(0, span)
        events.append({"kind": "location", "ts": ts,
                       "lat": round(base_lat + random.uniform(-0.05, 0.05), 6),
                       "lon": round(base_lon + random.uniform(-0.05, 0.05), 6),
                       "accuracy": round(random.uniform(6, 45), 1),
                       "payload": {"provider": "gps"}})

    for pkg in ["com.whatsapp", "com.spotify.music", "com.linkedin.android", "in.amazon.mShop.android.shopping"]:
        events.append({"kind": "app", "ts": now_ms - random.randint(0, span),
                       "body": pkg, "payload": {"action": "inventory", "package": pkg}})

    events.sort(key=lambda e: e["ts"])
    sent = 0
    alerts_total = 0
    for i in range(0, len(events), 200):
        batch = events[i:i + 200]
        r = post(args.base, "/api/sync", {"events": batch, "battery": random.randint(24, 96),
                                         "app_version": "1.0.0-sim"}, token)
        sent += r.get("accepted", 0)
        alerts_total += len(r.get("alerts", []))
        print(f"  batch {i // 200 + 1}: accepted={r.get('accepted')} dupes={r.get('duplicates')}")
        time.sleep(0.2)

    print(f"done: {sent} events accepted, {alerts_total} alerts raised")


if __name__ == "__main__":
    main()
