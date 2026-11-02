# Sentinel — Family Safety

Self-hosted, consent-based location and safety monitoring for **your own children, on phones you own**.
FastAPI + SQLite backend, operator console with live map and geofences, native Android agent with an
SOS button.

The device **always knows it is being monitored** and can stop at any time. That is a design
constraint, not a limitation — see [Why transparency](#why-transparency).

---

## What it does

| Parent console | Android agent |
|---|---|
| Live map with home/school geofences and a movement trail | Last-known location at each sync |
| Arrival / departure alerts with GPS-noise hysteresis | Geofence state tracked server-side |
| **SOS** — critical alert, banner + push to the console | Lock-screen SOS tile + in-app SOS button |
| Screen-time window and blocked-apps policy | Policy delivered on sync |
| Remote commands: locate now, ring device, sync now | Executes visibly, acks with the result |
| Message/call/app activity feed | SMS + call log, **OTPs filtered on-device** |
| Audit log of every read of location data | Permanent notification with a Stop button |
| TOTP two-factor on the parent account | — |

---

## Quick start

**Windows** — double-click `run.bat`. It checks Python, builds a venv, installs dependencies,
generates a signing secret, starts the server and opens the console. First run needs internet;
later runs are instant.

Want a desktop icon? Double-click `install-desktop-icon.bat` once. See
[Desktop icon & autorun](#desktop-icon--autorun).

**macOS / Linux**

```bash
./run.sh                      # same five steps
SENTINEL_PORT=9000 ./run.sh   # different port
```

**Manual**

```bash
cd backend
pip install -r requirements.txt
export SENTINEL_SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000> → **Create account**.

> **New here? Read [`TUTORIAL.html`](TUTORIAL.html).** A 20-section, fully self-contained walkthrough:
> install, enrol a phone, geofences, SOS, alert meanings, API reference, troubleshooting and the
> legal position. Open it in any browser — no internet needed.

## Desktop icon & autorun

| File | What it does |
|---|---|
| `run.bat` | Windows launcher. Prereq checks, venv, deps, secret, port check, opens browser. |
| `run.sh` | macOS / Linux equivalent. |
| `install-desktop-icon.bat` | Creates **Sentinel** on your Desktop, pointed at `run.bat`, using `assets/sentinel.ico`. |
| `tools/make-shortcut.ps1` | The PowerShell behind it (also usable directly). |
| `tools/make-desktop-icon.sh` | Builds a `.app` bundle (macOS) or `.desktop` entry (Linux). |
| `tools/make_icon.py` | Regenerates the icon — writes a 7-size `.ico` and a 512px `.png`. |
| `assets/sentinel.ico` | 16/24/32/48/64/128/256 px icon. |
| `assets/sentinel.png` | 512px PNG for shortcuts and docs. |

To start Sentinel automatically at login on Windows: press `Win+R`, run `shell:startup`, and drop the
Desktop shortcut in that folder. The shortcut launches minimised.

<p align="center">
  <img src="assets/sentinel.png" alt="Sentinel icon" width="120">
</p>

Load a demo family (two children, geofences, a day of movement, SOS, alerts):

```bash
python3 tools/seed_demo.py
# parent@sentinel.example.com / SentinelDemo2026
# Local demo only. The address is IANA-reserved (example.com) and the password
# works only against a database you seed yourself. Never reuse it on a real deploy.
```

Verify the engine:

```bash
python3 tools/e2e_test.py     # 73 passed, 0 failed
```

---

## Architecture

```
┌────────────────┐   enroll + consent    ┌──────────────────────────────────────┐
│ Sentinel Agent │ ────────────────────► │  FastAPI                             │
│ (Android)      │ ◄──── device_token ── │                                      │
│                │                       │  POST /api/sync ──► events (deduped) │
│ • SMS          │   POST /api/sync      │        │                             │
│ • Call log     │ ────────────────────► │        ├──► job queue (SQLite)       │
│ • Location     │   ◄── commands ────── │        │      ├─ alert rules         │
│ • App list     │   ──► acks ─────────► │        │      ├─ geofence eval       │
│ • SOS tile     │                       │        │      └─ offline checks      │
│                │   GET /api/device/... │        ▼                             │
└────────────────┘                       │   WebSocket /ws ──► live console     │
        │                                │   audit_log (every read)             │
        │ permanent notification         └──────────────────────────────────────┘
        └► child can stop at any time
```

### Design decisions

**The ingest path stays fast.** `/api/sync` only inserts rows and enqueues a job. Alert rules,
geofence transitions and offline sweeps run in a separate worker thread, so a slow rule can never
stall a device's upload.

**The job queue is real, not a sleep loop.** Rows are claimed with
`UPDATE ... WHERE id = (SELECT ... WHERE status='queued')`, so two workers can't take the same job.
Failed jobs retry with exponential backoff, and a worker that dies mid-job has its lease reaped after
120 s. Recurring jobs (`check.offline`, `sweep.zone_staleness`) re-enqueue themselves.

**Geofences have hysteresis.** A fix whose accuracy circle is wider than the zone radius is ignored —
entering a 250 m school zone on a 900 m cell-tower fix is noise, not a school arrival. First
observation establishes a baseline without firing an alert. Alerts are deduped per zone+direction+hour,
so a flapping GPS can't spam a parent.

**Live updates over WebSocket.** The console subscribes to `/ws?token=…`; alerts and syncs are fanned
out per-org. A ping every 25 s keeps proxies from closing the socket, and the client auto-reconnects.

**Idempotent ingest.** Every event carries a SHA-256 dedupe key. Replays collapse instead of
duplicating the timeline. (SQLite treats `NULL` as distinct in `UNIQUE` — that's why the key is an
explicit column and not a tuple of nullable ones.)

**Versioned migrations.** `backend/app/migrations/*.sql` applied in order against a
`schema_version` table, plus additive column upgrades for older databases.

### API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` · `/login` | — | Account, login (returns `totp_required` if enabled) |
| POST | `/api/auth/2fa/setup` · `/enable` | operator | TOTP enrolment |
| GET/POST | `/api/devices` | operator | List (with last location + current zone) / create |
| POST | `/api/devices/{id}/pause` · `/resume` · `/revoke` | operator | Kill switch |
| DELETE | `/api/devices/{id}` | owner | Hard delete + purge events, zones, alerts |
| POST | `/api/enroll/claim` | code + consent | Trade code for device token |
| POST | `/api/sync` | device | Ingest (≤500 events), returns queued commands |
| GET | `/api/device/config` | device | Kill switch + policy |
| POST | `/api/device/commands/ack` | device | Command result |
| GET/POST | `/api/devices/{id}/zones` · DELETE `/api/zones/{id}` | operator | Geofences |
| POST/GET | `/api/devices/{id}/commands` | operator | locate_now · ring · sync_now |
| PUT | `/api/devices/{id}/policy` | operator | Screen-time window, blocked apps |
| GET | `/api/devices/{id}/live` | operator | Location, zones, policy |
| GET | `/api/devices/{id}/timeline` · `/stats` | operator | Paged feed, aggregates |
| GET | `/api/alerts` · POST `/api/alerts/{id}/ack` | operator | Rule matches |
| GET | `/api/audit` | owner | Access log |
| GET | `/api/export/{id}` | owner | JSON portability export |
| WS | `/ws?token=` | operator | Live push |

Interactive docs at `/api/docs`.

---

## Building the Android agent

```bash
cd android
# Android Studio: open this folder, or:
./gradlew assembleDebug          # requires Android SDK 34 + JDK 17
adb install app/build/outputs/apk/debug/app-debug.apk
```

`minSdk 26`, `targetSdk 34`. Modules:

- `EnrollActivity` — consent gate; nothing collects until the box is ticked
- `MonitorService` — foreground service, permanent notification, Stop action
- `SyncWorker` / `SyncScheduler` — 15-min WorkManager cycle, durable 5,000-record outbox
- `Collectors` — SMS / call log / location / apps, with the OTP filter
- `CommandRunner` — executes locate_now, ring (15 s at max volume), sync_now; acks results
- `SosTileService` — lock-screen quick-settings SOS
- `BootReceiver` — resumes after reboot, only if still opted in

**Generate your own release keystore.** Never ship a debug-signed APK.

---

## Why transparency

Every "monitoring" product eventually gets the same feature request: hide the icon, kill the
notification, survive uninstall. Those features are what separate a safety tool from stalkerware, and
they are why spyware is illegal to use on another adult in most jurisdictions.

For a parent this is also the practical choice. A child who finds a hidden tracking app has been lied
to, and will remove it — you end up with worse data and a broken relationship. A child who can see
what's shared, and can switch it off, is more likely to leave it on. The consent screen is written for
a 12-year-old, and `Stop sharing` works immediately.

Hard-coded refusals in this codebase:

- no icon hiding, no notification suppression
- no remote microphone, camera, or screen capture
- no reading of WhatsApp / Signal / Telegram messages
- no keylogging, screenshots, or credential capture
- **no OTP collection** — dropped on-device in `Collectors.looksLikeOtp()`

See [docs/LEGAL.md](docs/LEGAL.md) for the per-jurisdiction position (India DPDP, GDPR, US ECPA/CFAA)
and the pre-deployment checklist.

---

## Honest limitations

This is a working system, not a finished product. What is genuinely not done:

- **The Android app has never been compiled here.** No Android SDK in this environment; `./gradlew
  assembleDebug` has not been run. Expect a day of fixes to a clean build.
- **SQLite, single node.** Fine for a family (2–10 devices). Not for a fleet. Postgres + a real
  broker (Redis/Postgres `SKIP LOCKED`) is the swap for both the DB and the queue.
- **The map is a projected SVG, not tiles.** No basemap, no pan/zoom. Swapping in Leaflet +
  OpenStreetMap (or Google Maps) is a contained change to `renderMap()`.
- **No push notifications.** Alerts reach an open console tab via WebSocket. Closed tab = no alert.
  Needs FCM + web push for a real "you'll hear about it" guarantee.
- **No Docker / HTTPS / rate limiting.** Device tokens are bearer credentials — put this behind TLS
  before you point it at a real phone.
- **The Android agent does not enforce the app-blocking or screen-time policy.** The backend stores
  and delivers it; enforcement needs `DevicePolicyManager` / accessibility work on the device.

## Production checklist

- [ ] TLS termination (Caddy or nginx) — mandatory, tokens travel in headers
- [ ] `SENTINEL_SECRET` from a secret manager, rotated
- [ ] Postgres + Redis-backed queue
- [ ] FCM push for alerts (mobile + web)
- [ ] Retention purge job (keep 30/90 days, then delete automatically)
- [ ] Volume encryption at rest
- [ ] Rate-limit `/api/auth/login` and `/api/enroll/claim` at the proxy
- [ ] Backups tested by restoring, not by taking
