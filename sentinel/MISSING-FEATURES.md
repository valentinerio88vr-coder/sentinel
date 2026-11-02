# Missing & Needed Features — Sentinel

An honest, evidence-based audit of what is **not** built, what is **broken**, and what is needed
before this can be trusted with real data.

Compiled by reading the source, not from memory. Where a claim is checkable, the command or file is
cited so you can verify it.

- **Last audited:** v2.0.0
- **Test suite state:** 73 checks passing (`tools/e2e_test.py`)
- **Overall verdict:** a working prototype with a solid data engine. Not a finished product.

---

## How to read this

| Tier | Meaning |
|---|---|
| **P0 — Blocker** | Unsafe or non-functional for real use. Fix before a real phone is enrolled. |
| **P1 — Needed** | The product doesn't deliver its purpose without these. |
| **P2 — Should have** | Expected of a tool at this stage; degrades trust if absent. |
| **P3 — Roadmap** | Genuinely valuable, but deferrable. |
| **Never** | Deliberately out of scope. Listed so they stop being re-asked. |

Effort: **S** ≈ hours · **M** ≈ 1–3 days · **L** ≈ 1–2 weeks · **XL** ≈ months.

---

## Summary

| # | Area | Items | Worst severity |
|---|---|---|---|
| 1 | Android agent | 14 | **P0** |
| 2 | Notifications & alerting | 6 | **P0** |
| 3 | Security & auth | 12 | **P0** |
| 4 | Backend & data | 11 | **P1** |
| 5 | Parent console (UI) | 12 | **P1** |
| 6 | Child-facing app | 7 | **P1** |
| 7 | Policy & family features | 9 | **P1** |
| 8 | Ops, deployment & testing | 12 | **P1** |
| 9 | Documentation & onboarding | 6 | **P2** |
| 10 | Out of scope (never) | 8 | Never |

**Total open items: 89** — 7 P0, 29 P1, 37 P2, 16 P3. By effort: 61 small, 23 medium,
4 large, 1 extra-large.

### Start here (the only four that matter this month)

1. **Compile the Android app** (§1.1) — it has never been built. Everything else is theoretical until it runs.
2. **Push notifications** (§2.1) — alerts currently require an open browser tab. For a safety product this is the defining gap.
3. **Consent withdrawal reporting** (§6.1) — the child's Stop button silently wipes the token; the parent is never told.
4. **HTTPS + rate limiting** (§3.1, §3.2) — bearer tokens travel in plaintext today.

---

## 1. Android agent

> Entire directory `android/` — **never compiled.** No Android SDK existed in the environment where
> it was written. `./gradlew assembleDebug` has not been run. Treat the first build as a debugging
> session, not a formality.

### 1.1 First successful build — **P0 · M**
Written against API 34 / AGP 8.5 / Kotlin 1.9.24 but never verified. Expect some of:
missing `mipmap` launcher icons (`@mipmap/ic_launcher` is referenced in the manifest but no
`res/mipmap-*` folders exist — **this alone will fail the build**), Gradle wrapper files
(`gradlew`, `gradle/wrapper/*`) not present, `BuildConfig.VERSION_NAME` import, theme parent
resolution, and `AndroidManifest` merge conflicts on `QUERY_ALL_PACKAGES`.

**Needed:** add `res/mipmap-anydpi-v26/ic_launcher.xml` + generated PNGs (reuse `tools/make_icon.py`),
commit the Gradle wrapper, and produce a signed release APK path.

### 1.2 Continuous location — **P1 · M**
Only `LocationManager.getLastKnownLocation()` is read at each sync — a snapshot, not tracking.
**Missing:** `FusedLocationProviderClient` with `PRIORITY_BALANCED_POWER_ACCURACY` and a
`PendingIntent`-based `requestLocationUpdates`, plus a `LocationCallback` writing straight into the
outbox. Without this, a moving child's position can be 15+ minutes stale.

### 1.3 Policy enforcement — **P1 · L**
`PUT /api/devices/{id}/policy` stores a screen-time window and blocked-app list and delivers it to
the phone, and the phone stores it. **Nothing enforces it.** Verified absent:
`grep -rn "DevicePolicyManager\|setPackagesSuspended\|AccessibilityService" android/` → 0 results.

**Needed:** either device-owner provisioning (`DevicePolicyManager.setPackagesSuspended`) — the clean
route, requires a factory reset + ADB provisioning step — or an accessibility service (broad, hard to
justify). Also a `DeviceAdminReceiver`, a policy-application worker, and UI explaining why the app
needs device admin.

### 1.4 WorkManager reliability — **P1 · S**
`PeriodicWorkRequest` at the 15-minute floor is subject to Doze and OEM battery killers (Xiaomi,
Huawei, Samsung are notorious). **Missing:** boot-time `WorkManager` re-enqueue verification, a
`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` prompt with explanation, and an in-app "background sync may be
restricted on this phone" diagnostic that detects OEM and shows the exact settings path.

### 1.5 Scheduled exact sync — **P2 · S**
`AlarmManager` with `setExactAndAllowWhileIdle` as a supplement for high-priority windows (school
pickup). Currently the minimum latency to any alert is "up to 15 minutes" and there is no way to
narrow it.

### 1.6 SMS/MMS completeness — **P2 · S**
Only `Telephony.Sms.Inbox` is queried. **Missing:** `Sms.Sent` (outgoing messages are declared in the
event schema and rendered by the console, but the agent never produces them), and MMS entirely.

### 1.7 Call log filtering — **P2 · S**
Reads every row including blocked/spam numbers. **Missing:** respect `CallLog.Calls.BLOCKED_TYPE`,
de-duplicate voicemail entries, and a server-side contact-name resolution instead of bare numbers.

### 1.8 App inventory cost — **P2 · S**
`Collectors.apps()` calls `getInstalledPackages(0)` on every invocation but is **never called by
`SyncWorker`** — the function exists and is dead code. Also `QUERY_ALL_PACKAGES` is a
Play-Store-restricted permission; fine for sideloading, a rejection risk if this ever ships via Play.
**Needed:** call it once per day on a separate low-frequency schedule, not per sync.

### 1.9 Consent withdrawal → server — **P0 · S**
See §6.1. `MonitorService.stopSelfAndWipe()` calls `Prefs.wipe()` which clears the `device_token`
*before* any network call, so the server never learns the child opted out. The `devices` table has a
`consent_withdrawn_at` column that **nothing ever writes to**.

### 1.10 Firmware/agent update path — **P2 · M**
No self-update. A changed server API or a bug fix requires physically re-installing the APK.
**Needed:** version check in `/api/device/config`, an in-app download+install via
`PackageInstaller`, or at minimum a "your app is out of date" alert surfaced in the parent console.

### 1.11 Enrollment QR code — **P3 · S**
Server URL and code must be typed by hand (error-prone, especially the IP). **Needed:** render a QR
from `enroll_url` in the console and scan it in the app via ZXing/ML Kit.

### 1.12 Uninstall protection — **P3 · S**
There is none, and there should not be aggressive protection — but a child can uninstall and the
parent won't know for up to an hour (until `check.offline` fires). **Needed:** shorter offline
threshold for recently-enrolled devices, and a distinct "app was removed" alert (detectable via
`ACTION_PACKAGE_REMOVED` in a companion receiver — partially impossible once removed; a
`DeviceAdminReceiver` makes uninstall require deactivation first).

### 1.13 Accessibility & localisation in the agent — **P2 · S**
All UI strings are hard-coded English in Kotlin. No `strings.xml` extraction, no Hindi/Marathi.
Content descriptions are absent, so TalkBack users get an unusable consent screen — which is a legal
problem, not just a UX one.

### 1.14 SOS reachability — **P2 · S**
The quick-settings tile is the only lock-screen path. **Missing:** a lock-screen-visible shortcut via
`Activity.setShowWhenLocked`, a hardware-button fallback (5× power press where the OEM supports it),
and a loud confirmation tone so the child knows the SOS actually sent.

---

## 2. Notifications & alerting

### 2.1 Push notifications — **P0 · M**
**The single biggest gap.** Alerts are delivered over an in-process WebSocket
(`backend/app/bus.py`) to a browser tab that must already be open. Close the tab and an SOS produces
no sound, no banner, nothing.

Verified absent: `grep -rn "firebase\|FCM" android/ backend/` → 0 results.

**Needed:**
- FCM in the Android agent (`firebase-messaging`, token registration endpoint, `FirebaseMessagingService` with a high-importance channel that bypasses DND for `critical`)
- Web Push for the parent console (VAPID keys, service worker, `PushSubscription` storage)
- Email fallback (SMTP) for anyone who misses both
- SMS fallback for `critical` alerts — a real phone call for SOS is not unreasonable
- Per-channel user preferences (SOS → all channels; `zone_enter` → push only)

### 2.2 Live socket fallback — **P1 · S**
If the WebSocket drops, the console silently stops updating and shows "reconnecting…" forever with no
polling fallback. **Needed:** degrade to 30-second polling while disconnected, and a visible staleness
indicator ("updated 4 min ago") on every panel.

### 2.3 Alert delivery receipts — **P1 · S**
The server has no idea whether a parent ever saw an alert. **Needed:** `delivered_at` / `seen_at` on
`alerts`, surfaced in the UI ("not yet seen"), so "I didn't get it" is answerable.

### 2.4 Notification grouping & quiet hours — **P2 · S**
Nine zone alerts overnight = nine notifications. **Needed:** grouping by device, configurable quiet
hours that suppress `info` but never `critical`, and a daily digest option.

### 2.5 Misuse detection — **P2 · M**
No rate limiting on how often a parent can spam *Locate now* or *Ring device*. Those are visible,
audible intrusions on the child. **Needed:** per-device command cooldown (e.g. ring max 3/hour), and
an audit-visible "excessive monitoring" heuristic that warns the parent.

### 2.6 Webhook / automation — **P3 · S**
No way to push alerts to Home Assistant, ntfy, Slack or a Telegram bot. **Needed:** outbound webhook
with HMAC signature on selected rules. Cheap to add, disproportionately useful for a self-hosted tool.

---

## 3. Security & auth

### 3.1 HTTPS / TLS — **P0 · S**
Nothing terminates TLS. Device bearer tokens and session tokens travel in plaintext headers, so
anyone on the same Wi-Fi can read them and impersonate the phone or the account.
Verified: `grep -rn "ssl\|https\|cert" backend/app/*.py` → 0 results.

**Needed:** Caddy or nginx reverse proxy config, a documented self-signed-cert path for LAN use, and
certificate pinning in the Android agent for the non-public case. Also: reject `http://` server URLs
in the app when the host isn't a private range, with a warning the parent must dismiss.

### 3.2 Rate limiting / brute-force protection — **P0 · S**
`/api/auth/login` accepts unlimited attempts. `/api/enroll/claim` accepts unlimited code guesses —
an 8-hex-character code space (4.3 billion, so not trivially brute-forceable, but unmetered and
unlogged beyond the audit table). Verified: `grep -rniE "ratelimit|slowapi"` → 0.

**Needed:** `slowapi` or proxy-level limits (5 login attempts / 15 min / IP), account lockout with
exponential backoff, a `failed_login_attempts` column, and a per-IP cap on `enroll/claim`.

### 3.3 Password reset — **P0 · M**
There is no recovery path. Forget the password and every enrolled device is orphaned — the data is
still in SQLite but there is no UI or endpoint to regain access. **Needed:** email-based reset (SMTP
config), a single-use expiring token table, and a documented offline CLI recovery command
(`python -m app.cli reset-password`) for the self-hosted case where email isn't configured.

### 3.4 WebSocket token in the URL — **P1 · S**
`/ws?token=<session-token>` puts the session credential in a query string, which lands in reverse-proxy
access logs, browser history and any `Referer` header. Verified at `backend/app/main.py:729`.

**Needed:** authenticate via the `Sec-WebSocket-Protocol` header, a first-message auth frame, or a
short-lived one-time WS ticket issued by an authenticated REST call.

### 3.5 CORS wildcard — **P1 · S**
`allow_origins` defaults to `"*"` with `allow_credentials=True`. Browsers reject that combination for
credentialed requests, so it happens to be inert — but it's wrong and will break confusingly the
moment someone sets a cookie. **Needed:** default to the console's own origin, require explicit
opt-in via `SENTINEL_ORIGINS`.

### 3.6 Session revocation — **P1 · M**
Tokens are stateless HMAC with a 12-hour expiry. There is no logout-all, no "sign out other devices",
no session list. A stolen token is valid until it expires. **Needed:** a `sessions` table with
`jti`, revocation check on each request, device/IP/user-agent display, and a "sign out everywhere"
button.

### 3.7 Device token rotation — **P1 · S**
Device tokens never rotate and can only be destroyed by revoking the whole device. **Needed:**
`POST /api/device/rotate-token` with a grace window so the agent can swap without losing its queue.

### 3.8 Token storage on Android — **P1 · S**
`Prefs` uses plain `SharedPreferences`. A rooted device or a backup extraction reads the device token
directly. Manifest sets `allowBackup="false"`, which helps, but **needed:** `EncryptedSharedPreferences`
(androidx.security-crypto) with a Keystore-backed master key.

### 3.9 2FA recovery codes — **P1 · S**
Enable TOTP, lose the phone, lose the account permanently. **Needed:** ten single-use recovery codes,
shown once, stored hashed, individually invalidated on use.

### 3.10 XSS surface in the console — **P2 · S**
`web/index.html` uses `innerHTML` in 28 places. Every interpolation goes through `esc()` today, and I
verified that — but the pattern is fragile: one future `innerHTML` without `esc()` and a child's SMS
body becomes script execution in the parent's authenticated session. **Needed:** move to
`textContent` / `createElement`, or add a tiny tagged-template helper that escapes by default, plus a
CSP header (`script-src 'self'`, no `unsafe-inline`).

### 3.11 No CSRF consideration documented — **P2 · S**
Auth is a `Bearer` header in `localStorage`, so classic CSRF isn't applicable — but `localStorage` is
readable by any XSS. **Needed:** consider `HttpOnly` cookies + `SameSite=Strict` + explicit CSRF
tokens, and document the chosen trade-off.

### 3.12 Encryption at rest — **P2 · M**
`backend/data/sentinel.db` is a plain SQLite file. Anyone with disk access reads every message and
location. **Needed:** documented LUKS/FileVault/BitLocker setup at minimum; optionally
SQLCipher, or field-level encryption of `body` with a key from the OS keyring.

---

## 4. Backend & data

### 4.1 Postgres migration — **P1 · M**
SQLite with WAL and a busy timeout is fine for one family. It is a single-writer database with no
connection pooling. **Needed:** SQLAlchemy/Alembic port, `SKIP LOCKED` for the job queue (which also
removes the hand-rolled lease logic in `queue.py`), and a documented data-migration script.

### 4.2 Cursor pagination — **P1 · S**
`/api/devices/{id}/timeline` uses `LIMIT/OFFSET`, which degrades linearly and skips rows when new
events arrive mid-scroll. Verified: `grep -rniE "cursor|pagination"` → 0.
**Needed:** keyset pagination on `(ts, id)` with an opaque cursor.

### 4.3 Retention & purge job — **P1 · S**
Data accumulates forever. There is no retention policy, no purge job, no "delete data older than N
days". This is a legal duty under DPDP/GDPR (storage limitation), not a nice-to-have.
**Needed:** per-org configurable retention, a nightly `purge.retention` job, and an audit entry per
purge run.

### 4.4 Bulk export & account deletion — **P2 · S**
`GET /api/export/{device_id}` covers one device. **Missing:** whole-account export, and account
self-deletion (right to erasure). Also no scheduled automatic backups.

### 4.5 Idempotency keys on writes — **P2 · S**
`POST /api/sync` dedupes events, but `POST /api/devices`, `/commands` and `/alerts/{id}/ack` are not
idempotent. A double-tap creates two devices or two ring commands. **Needed:** `Idempotency-Key`
header support.

### 4.6 Event schema versioning — **P2 · S**
Payloads are unversioned `dict`s. Next time the location payload changes shape, old and new rows will
be indistinguishable. **Needed:** `schema_version` on events plus an upgrade path.

### 4.7 Time-zone correctness — **P2 · S**
Everything is epoch-milliseconds UTC, rendered in the browser's locale. **Missing:** a per-org time
zone, so zone-hour dedupe keys (`db.now() // 3600`) and "quiet hours" mean the right thing when the
server and the family are in different zones.

### 4.8 Geocoding / place search — **P2 · S**
Adding a place requires knowing latitude and longitude. The UI pre-fills the last position and asks
you to edit numbers. **Needed:** address/place search via Nominatim or Google Places, plus
reverse-geocoding so alerts read "arrived at school" rather than "19.10748, 72.83737".

### 4.9 Dwell time & route deviation — **P3 · M**
`geofence.evaluate_point` handles enter/exit only. **Missing:** "has been at this place for 3 hours"
and "left the usual route home". Both are far more useful than raw enter/exit for a parent.

### 4.10 Battery/connectivity monitoring — **P3 · S**
Battery is stored on each sync and shown, but nothing alerts on it. **Needed:** "battery below 15%",
"phone has been off charge for 8 hours", "no Wi-Fi and no mobile data".

### 4.11 SOS acknowledgement loop — **P3 · S**
The child presses SOS and gets no confirmation the parent saw it. **Needed:** a command channel
message back to the phone ("Mum has seen this"), shown in the app.

---

## 5. Parent console (UI)

### 5.1 Real map — **P1 · M**
`renderMap()` draws a hand-projected SVG: no streets, no place names, no pan, no zoom. Verified — it
is a 720×380 `viewBox` with a fitted bounding box.
**Needed:** Leaflet + OpenStreetMap tiles (offline-capable via a local tile server if privacy matters),
marker clustering, a proper trail polyline, and a "last updated" badge on the map itself.

### 5.2 Mobile layout — **P1 · M**
One `@media` breakpoint in the entire stylesheet. The sidebar collapses at 1080px, but the device page,
the map and the tables are not designed for a 390px screen. Parents will use this on a phone more than
a desktop.
**Needed:** a real responsive pass — bottom tab bar, stacked cards, table→card conversion, and larger
touch targets (44px minimum).

### 5.3 Accessibility — **P1 · M**
Zero `aria-*` attributes, zero explicit `role=`, and 28 `innerHTML` blocks that replace DOM without
announcing changes. Verified by grep.
**Needed:** semantic landmarks, `aria-live` for the alert list and toasts, keyboard navigation with
visible focus rings, a contrast audit (the `--dim` on `--bg` pair is borderline), and a skip link.

### 5.4 No loading / error / empty states — **P1 · S**
Timeouts and failures surface as raw `e.message` in a panel. There are no skeletons, no retry buttons,
no distinction between "no data yet" and "the request failed".

### 5.5 History depth — **P1 · S**
The map trail loads the last 40 location events; `loadTimeline` caps at 80 rows with no "load more".
There is no way to ask "where was she last Tuesday afternoon?" — the single most common real question.
**Needed:** a date/time range picker over the timeline, and playback of a day's route.

### 5.6 Self-hosted asset footprint — **P2 · S**
The console is one 40 KB HTML file with inline CSS and JS. Good for zero-build deployment, bad for
caching and code review. No minification, no source maps, no bundler.

### 5.7 Onboarding wizard — **P2 · S**
A new user lands on an empty Family page with a "+ Add a device" button and no guidance. **Needed:**
a three-step wizard (create account → add child → install app) with progress state.

### 5.8 Dark/light, and readability — **P2 · S**
Dark only. Fine as a default; no toggle. For a tool a worried parent reads at 2 a.m. it's low
priority, but the print stylesheet is the only light option.

### 5.9 i18n — **P2 · M**
Hard-coded English throughout (`translate`/`i18n` appears twice, both incidental). For a Mumbai user
this is a real gap: Hindi and Marathi are the obvious first targets. **Needed:** a message catalogue
(JSON per locale), `Accept-Language` negotiation for the server-side strings, and locale switching.

### 5.10 Time formatting — **P2 · S**
`ago()` is now correct (it treats input as a delta — a bug I fixed mid-build), but absolute timestamps
use the browser locale only. No "yesterday at 4pm" phrasing, which is how people actually think.

### 5.11 Session expiry UX — **P2 · S**
A 12-hour token expires mid-session and the app drops you to the login screen with no warning and no
return-to-where-you-were. **Needed:** silent refresh, or a "you've been signed out" notice.

### 5.12 Audit log filtering — **P3 · S**
`/api/audit` returns the last 200 rows as a flat table. No filter by action, actor or date; no export.

---

## 6. Child-facing app

### 6.1 Consent withdrawal is not reported — **P0 · S**
The most important gap in this section, and a trust bug rather than a legal one.

`MonitorService.stopSelfAndWipe()` → `Prefs.wipe()` deletes the device token, **then** stops. No
network call happens, so the parent's console shows the device as `active` until `check.offline`
fires an hour later, and the audit log records nothing. The schema has a
`consent_withdrawn_at` column that **no code ever writes**.

**Needed:** `POST /api/device/consent/withdraw` fired *before* wiping local state (queued and retried
if offline), a `consent_withdrawn_at` write, a distinct `consent_withdrawn` alert, and console UI
showing "Aarav stopped sharing at 14:32" instead of a vague offline warning.

### 6.2 "What has been shared with my parent" view — **P1 · M**
The status screen says what *will* be shared, in the abstract. It never shows the child their actual
recent data. **Needed:** a real list of the last N events sent, in plain language, so the child can
verify the app isn't lying. This is the single most trust-building feature available.

### 6.3 SOS acknowledgement — **P1 · S**
No feedback loop (§4.11). A child in trouble presses SOS and sees nothing change.

### 6.4 No pause / temporary-off — **P1 · S**
Only "stop everything permanently". No "pause for 2 hours" (a friend's house, an exam). Forcing an
all-or-nothing choice encourages the child to remove the app entirely.

### 6.5 Child-visible alert history — **P2 · S**
The child cannot see which alerts have fired about them. **Needed:** a plain list ("Mum was told you
arrived at school at 08:14"). Transparency cuts both ways and reduces the feeling of being spied on.

### 6.6 Reading level & tone — **P2 · S**
The consent notice is written for roughly a 12-year-old. It has not been tested with an actual child,
translated, or reviewed for reading level. **Needed:** a version at a 9-year-old level, Hindi/Marathi,
and a short "in one sentence" summary at the top.

### 6.7 Uninstall-is-obvious path — **P2 · S**
Currently uninstalling silently orphans the device server-side. **Needed:** detect removal via
`DeviceAdminReceiver` (requires device-admin) and at minimum explain to the child what uninstalling
does before they do it.

---

## 7. Policy & family features

### 7.1 Screen-time enforcement — **P1 · L**
Same root cause as §1.3. Stored, delivered, not applied.

### 7.2 App blocking — **P1 · L**
Same. Needs device owner or accessibility service.

### 7.3 Multiple parents / guardians — **P1 · M**
One `owner` per org, and registration creates a single user. There is no invite flow, no second
parent, no read-only grandparent account. Verified: `grep -rniE "invite"` → 0.
**Needed:** invitations with expiring tokens, a `viewer` role actually wired through, and per-device
access scoping.

### 7.4 Roles beyond `owner`/`operator` — **P2 · S**
`require_role()` exists and `viewer` is referenced, but nothing ever assigns it and no endpoint
distinguishes operator from viewer meaningfully.

### 7.5 Notification preferences per parent — **P2 · S**
Every user in the org gets the same alerts on the same channels.

### 7.6 Weekly summary reports — **P2 · M**
No digest: "Aarav arrived at school on time 4/5 days; 2 offline gaps". **Needed:** a scheduled
`report.weekly` job and an email/PDF output. High perceived value, low technical risk.

### 7.7 Safe-walk / journey monitoring — **P3 · L**
"Tell me if they don't arrive at school within 40 minutes of leaving home." No expected-journey model
exists at all. This is the feature parents actually want, and it is a genuine differentiator.

### 7.8 Contact allow/block lists — **P3 · M**
The `watchlist` concept is referenced in an early alert-rule sketch but never implemented or exposed.
**Needed:** a contacts list per device, alerts on contact with unknown/blocked numbers.

### 7.9 iOS — **P3 · XL**
Not feasible to parity. iOS forbids SMS and call-log access for third-party apps, and background
location requires continuous user-visible indication. A reduced iOS agent (location + SOS only, via
Sign in with Apple and a `CLLocationManager` background session) is possible but a separate product.

---

## 8. Ops, deployment & testing

### 8.1 Docker / Compose — **P1 · S**
No container. `docker-compose.yml` with the app + a Caddy TLS sidecar + Postgres + volume mounts would
remove most of the setup friction and make the HTTPS story (§3.1) one line.

### 8.2 CI — **P1 · M**
No pipeline. Tests are run by hand. **Needed:** GitHub Actions running `tools/e2e_test.py`, a lint
pass (`ruff`, `ktlint`), a migration-apply check against a fresh database, and Android
`assembleDebug` on every push — which is the only way §1.1 stays fixed once it's fixed.

### 8.3 Pinned dependencies — **P1 · S**
`requirements.txt` uses `>=` for all four packages. A major FastAPI or Pydantic release silently
breaks the install for a new user. Verified — no version pins, no lock file.
**Needed:** exact pins plus `pip-compile`/`uv` lock, and a documented upgrade cadence.

### 8.4 Structured logging — **P1 · S**
`print()` statements and uvicorn's default output. No request IDs, no log levels, no JSON, no
correlation between a device sync and its queued job. **Needed:** `structlog` or stdlib `logging`
with JSON output and a `request_id` / `device_id` contextvar.

### 8.5 Health and metrics — **P2 · S**
`/api/health` reports queue depth and subscriber count — a good start. **Missing:** `/api/metrics`
(Prometheus) for ingest rate, queue age, alert latency, sync failures; and a `/api/ready` distinct
from liveness.

### 8.6 Backups — **P2 · S**
Documented as "copy the data folder". No scheduled job, no restore test, no integrity check
(`PRAGMA integrity_check`). A backup that has never been restored is not a backup.

### 8.7 Load testing — **P2 · M**
Never tested beyond ~500 events. Unknown behaviour at 50 devices × 288 syncs/day. **Needed:** a
locust/k6 scenario, and a documented ceiling for SQLite.

### 8.8 Test coverage breadth — **P2 · M**
73 checks, all end-to-end over HTTP. No unit tests for `geofence.haversine`, `totp`, `queue.claim`
concurrency, or the dedupe key. No Android tests at all, no UI tests. **Needed:** unit tests for the
pure functions, a concurrency test for the queue claim, and Playwright tests for the console.

### 8.9 Migration rollback — **P3 · S**
Migrations are forward-only with no down-path and no tested restore between versions.

### 8.10 TLS certificate automation — **P2 · S**
No ACME/Let's Encrypt integration; renewals would be manual.

### 8.11 Multi-process correctness — **P2 · M**
`bus.py` is in-process only, and `_initialised` / thread-local connections assume one process. Running
`uvicorn --workers 4` breaks WebSocket fan-out silently. **Needed:** Redis pub/sub, or an explicit
single-worker guard that refuses to start.

### 8.12 Secrets management — **P3 · S**
`data/secret.key` on disk, permissions unmanaged. Fine for a home server; **needed:** documented
OS-keyring or Docker-secret path.

---

## 9. Documentation & onboarding

### 9.1 API documentation for the agent — **P2 · S**
`/api/docs` exists (FastAPI auto-docs), but there is no written contract for the device endpoints, no
example payloads for every event kind, and no versioning policy. A third-party agent couldn't be
written against it.

### 9.2 Recipes — **P2 · S**
No worked examples: "run on a Raspberry Pi", "access remotely via Tailscale", "expose via Cloudflare
Tunnel", "back up to a NAS". These are the questions self-hosters actually ask.

### 9.3 Screenshot freshness — **P3 · S**
`docs/img/*` are generated from the demo data. No automation ties them to the UI, so they will drift.

### 9.4 Video walkthrough — **P3 · M**
Not present. For a parental tool with a consent conversation at its heart, a 4-minute video would
outperform the 28,000-pixel document for most users.

### 9.5 In-app help — **P3 · S**
No contextual help, tooltips, or "what does this alert mean?" links inside the console.

### 9.6 CHANGELOG — **P3 · S**
No versioned change history.

---

## 10. Out of scope — deliberately never built

Listed so these stop being re-requested. Each one converts this from a safety tool into spyware, and
several are criminal in most jurisdictions even within a family.

| Feature | Why it stays out |
|---|---|
| Hiding the app icon / fake launcher | Removes the child's ability to know and to stop. Core stalkerware behaviour. |
| Suppressing or hiding the ongoing notification | Android requires it for foreground services; hiding it is deception. |
| Remote microphone / camera / screen recording | Captures private space and third parties who never consented. |
| Reading WhatsApp / Signal / Telegram content | Breaks end-to-end encryption via root or accessibility abuse. |
| Keylogging or screenshots | Harvests passwords and banking credentials. |
| Collecting one-time passcodes | Credential theft. Filtered on-device in `Collectors.looksLikeOtp()`. |
| Surviving uninstall / undeactivatable device admin | Turns the phone into something the child cannot control. |
| Covert "track another adult" mode | The most common stalkerware use case. Not a parental feature. |

Full reasoning and the per-jurisdiction legal position: [`docs/LEGAL.md`](docs/LEGAL.md).

---

## Appendix — verification commands

```bash
# Android never compiled: no gradle wrapper, no launcher icons
ls android/gradlew android/app/src/main/res/ 2>&1

# No push notification capability anywhere
grep -rn "firebase\|FCM\|FirebaseMessaging" android/ backend/ --include=*.kt --include=*.py

# Policy is stored, never enforced
grep -rn "DevicePolicyManager\|setPackagesSuspended\|AccessibilityService" android/

# No TLS, no rate limiting, no password reset, no invitations, no pagination
grep -rniE "ssl|https|cert" backend/app/*.py
grep -rniE "ratelimit|slowapi" backend/app/*.py
grep -rniE "password_reset|forgot" backend/app/*.py
grep -rniE "invite" backend/app/*.py
grep -rniE "cursor|pagination" backend/app/*.py

# Session token in the WebSocket query string
grep -n "token: str = Query" backend/app/main.py

# CORS wildcard by default
grep -n -A3 "add_middleware" backend/app/main.py

# Consent withdrawal never reported (column exists, nothing writes it)
grep -rn "consent_withdrawn" backend/ web/ android/

# Accessibility gaps in the console
grep -o "aria-" web/index.html | wc -l     # 0
grep -o 'role="' web/index.html | wc -l    # 0

# Unpinned dependencies
cat backend/requirements.txt
```

---

*Audit produced by reading the source at v2.0.0. If you fix an item, delete it here — a stale gap list
is worse than none.*
