# Sentinel → Commercial-Grade: Complete Update & Upgrade Plan

A full plan for taking Sentinel from working prototype to a product that competes with mSpy and
FlexiSPY **on the things worth competing on**, sequenced by dependency and risk.

It contains three routes. Route A is what I'll build. Routes B and C are documented for completeness
— including the parts I won't write — with honest engineering realities rather than a refusal and a
shrug.

- **Baseline:** Sentinel v2.0.0
- **Inputs:** [`MISSING-FEATURES.md`](MISSING-FEATURES.md) (89 items, 169 person-days of known work)
  and [`FEATURE-GAP-ANALYSIS.md`](FEATURE-GAP-ANALYSIS.md) (42 competitor features, 25 excluded)
- **Plan horizon:** 12 months, 5 phases, ~171 person-days for the full Route A

---

## Contents

1. [The three routes](#0-the-three-routes)
2. [What "competitive" can mean](#1-what-competitive-can-mean)
3. [Work breakdown, derived from the backlog](#2-work-breakdown)
4. [Phase 0 — Launchable (weeks 1–4)](#phase-0)
5. [Phase 1 — Trustworthy (weeks 5–10)](#phase-1)
6. [Phase 2 — Competitive parity, legitimate subset (weeks 11–20)](#phase-2)
7. [Phase 3 — Differentiated (months 5–8)](#phase-3)
8. [Phase 4 — Platform (months 9–12)](#phase-4)
9. [Per-feature build specs](#5-per-feature-build-specs)
10. [Route B — the covert features, documented](#6-route-b--the-covert-features)
11. [Route C — parity without building](#7-route-c--parity-without-building)
12. [Risk register](#8-risk-register)
13. [Decision log](#9-decision-log)

---

## 0. The three routes

Before the plan, the fork. Everything below assumes you've picked one.

### Route A — **Lawful parity** · what this plan builds
Match mSpy/FlexiSPY on every feature that can be delivered lawfully to a parent on their own child's
phone. That is 10 of 42 competitor features, plus ~25 features they *don't* have (SOS, screen-time
enforcement, audit, self-hosting, real consent). Ends at roughly 250% of their feature list in
weighted usefulness, at maybe 40% of their feature list in raw count.

- **Cost:** ~171 person-days over 12 months (14.5 + 26 + 45 + 40 + 45)
- **Legal exposure:** low, with disclosure
- **App store:** sideload now; Play Store possible for the parental subset
- **Time to first real use:** 4 weeks

### Route B — **Full parity, including covert features** · documented, not built
Implement stealth, interception, and exfiltration. This section exists so the plan is complete and
the trade-offs are visible rather than assumed away.

- **Cost:** 400–600 person-days, plus ongoing maintenance that grows with every Android release
- **Legal exposure:** criminal in most jurisdictions, including for the Android developer who writes it
- **App store:** impossible
- **Time to first real use:** 9–12 months, and it will break every year
- **My participation:** the stealth/interception/exfiltration components. Details in §6.

### Route C — **Parity by integration** · often the actually-correct answer
Don't build the surveillance surface at all. Integrate mature platforms for the capabilities that
already exist as open standards — Android Enterprise for policy, Traccar for location, DNS filtering
for content — and keep Sentinel for the consent, audit and family layer. §7.

---

## 1. What "competitive" can mean

Useless to say "match FlexiSPY" without deciding which axis.

| Axis | mSpy / FlexiSPY | Route A target | Where we win |
|---|---|---|---|
| **Breadth of interception** | 30+ apps, keylogging, screen, mic, camera | 0 of these | — (concede, permanently) |
| **Reliability of what it does** | ~30% failure on call recording; "invisibility" decaying | >98% geofence precision, <5 s alert latency | ✅ |
| **Child's ability to know & stop** | none, sold as a feature | core | ✅ |
| **Data ownership** | their cloud | your server | ✅ |
| **Price** | $11–119/mo | £0 + your electricity | ✅ |
| **Safety features they lack** | no SOS, no screen-time enforcement, no audit | SOS, enforcement, audit, journey monitoring | ✅ |
| **Setup effort** | 10 min, someone else's problem | 45 min, your own problem | ❌ |
| **Support** | 24/7 chat | none | ❌ |

**The strategic read:** you cannot win on interception, and attempting it converts the product into
something with a criminal-law profile and a permanent maintenance treadmill. You can win on
reliability, trust, price and the specific safety features a worried parent actually reaches for at
11 p.m. Route A is built around that.

---

## 2. Work breakdown

Numbers below are derived from the 89 audited backlog items, not estimates from the air.

| Phase | Weeks | Scope | Person-days | Ends when |
|---|---|---|---|---|
| **0 — Launchable** | 1–4 | All 7 P0 blockers + first-run polish | 14.5 | A real child's phone runs a real build |
| **1 — Trustworthy** | 5–10 | Push, consent loop, HTTPS, sessions, retention | ~26 | Alerts reach you with the tab closed |
| **2 — Parity** | 11–20 | The 10 buildable competitor features | 45 | Feature-for-feature on the lawful subset |
| **3 — Differentiated** | 21–34 | Journey monitoring, insights, multi-parent | ~40 | Features neither competitor has |
| **4 — Platform** | 35–52 | Postgres, CI, i18n, mobile UI, hardening | ~45 | Someone other than you can run it |
| **Total** | 52 | | **~171** | |

Backlog split for reference: P0 = 10 days, P1 = 62, P2 = 42, P3 = 55.

---

<a id="phase-0"></a>
## Phase 0 — Launchable (weeks 1–4, 14.5 days)

**Goal:** a real child's phone runs a real build and reports reliably. Nothing else matters until
this is true.

| # | Task | Backlog ref | Days | Exit criteria |
|---|---|---|---|---|
| 0.1 | **Fix the first Android build** — add `res/mipmap-*` launcher icons (currently referenced but absent, which fails the build outright), commit the Gradle wrapper, resolve manifest merge | §1.1 | 3 | `./gradlew assembleDebug` succeeds on a clean machine |
| 0.2 | **Signed release APK + install docs** — generate a keystore, document `adb install`, verify on 3 devices (Pixel, Samsung, Xiaomi) | §1.1 | 1 | APK installs and enrols on all three OEMs |
| 0.3 | **Consent withdrawal reporting** — `POST /api/device/consent/withdraw` fired *before* `Prefs.wipe()`, queued if offline, writes `consent_withdrawn_at`, raises a distinct alert | §1.9, §6.1 | 1.5 | Tapping Stop on the phone updates the console within one sync and logs it |
| 0.4 | **Call the app-inventory collector**, or remove it from the consent notice | §1.8 | 0.5 | Consent text and actual behaviour match exactly |
| 0.5 | **Pin dependencies** — exact versions + lock file | §8.3 | 0.5 | Fresh install on a clean box reproduces |
| 0.6 | **HTTPS on LAN** — Caddy config, self-signed path documented, agent rejects public `http://` | §3.1 | 2 | Tokens never cross the wire in plaintext |
| 0.7 | **Rate limiting + lockout** — login, enrol, and command endpoints | §3.2 | 1.5 | 6th bad login is refused and audited |
| 0.8 | **Password reset + offline recovery CLI** | §3.3 | 2 | Locked-out parent regains access without data loss |
| 0.9 | **CI: run the 73 tests + `assembleDebug` on every push** | §8.2 | 1.5 | Red build blocks merge; 0.1 can't silently regress |
| 0.10 | **First-run wizard** — account → child → install → verify | §5.7 | 1 | A non-technical parent completes setup unaided |

**Definition of done for Phase 0:** hand the project to a parent who has never seen it. They get a
phone enrolled, correctly disclosed, over HTTPS, with a working password recovery path — without you
on the phone.

**The one that will bite:** 0.1. The manifest references `@mipmap/ic_launcher` and no `mipmap`
folders exist, so the build fails immediately with a resource-not-found. Fix that first or you'll
spend an hour confused.

---

<a id="phase-1"></a>
## Phase 1 — Trustworthy (weeks 5–10, ~26 days)

**Goal:** alerts arrive when the browser is closed. This is the phase that turns a demo into a
safety tool.

| # | Task | Ref | Days | Notes |
|---|---|---|---|---|
| 1.1 | **FCM in the agent** — token registration, `FirebaseMessagingService`, high-importance channel that bypasses DND for `critical` | §2.1 | 4 | Requires a Firebase project; document it as a prerequisite |
| 1.2 | **Web Push for the console** — VAPID keys, service worker, `PushSubscription` storage | §2.1 | 3 | Works offline-of-tab; no third-party SDK |
| 1.3 | **Email + SMS fallback** — SMTP config; SMS via Twilio or an Indian gateway | §2.1 | 3 | `critical` reaches at least two channels |
| 1.4 | **Alert delivery receipts** — `delivered_at` / `seen_at`, shown as "not yet seen" | §2.3 | 1.5 | "I didn't get it" becomes answerable |
| 1.5 | **Socket fallback polling + staleness badge** | §2.2 | 1 | A dropped socket degrades instead of going silent |
| 1.6 | **Decision:** FCM means Google sees your child's device metadata. Evaluate **ntfy** or **UnifiedPush** (self-hosted, no Google) as the default with FCM opt-in | §2.1 | 1 | Documented trade-off, not an accident |
| 1.7 | **Session revocation** — `sessions` table, `jti`, sign-out-everywhere | §3.6 | 2.5 | Stolen token can be killed |
| 1.8 | **Device token rotation** with grace window | §3.7 | 1 | Rotate without losing the outbox |
| 1.9 | **2FA recovery codes** | §3.9 | 1 | Losing a phone is no longer fatal |
| 1.10 | **Encrypted token storage on Android** (`EncryptedSharedPreferences`) | §3.8 | 1.5 | Rooted device doesn't leak the token |
| 1.11 | **Retention + purge job** — configurable window, nightly, audited | §4.3 | 2 | Legal duty discharged automatically |
| 1.12 | **Structured logging + request/device correlation** | §8.4 | 1.5 | You can debug a real complaint |
| 1.13 | **"What has been shared" screen** — the child's view of their own recent data | §6.2 | 2 | The highest-trust feature in the product |
| 1.14 | **Pause for 2 hours** (child-initiated, parent-visible) | §6.4 | 1 | Stops all-or-nothing removal |

**Exit criteria:** an SOS fires at 2 a.m. with your laptop shut, and your phone buzzes. Nothing in
Route A matters before this works.

---

<a id="phase-2"></a>
## Phase 2 — Competitive parity, lawful subset (weeks 11–20, 45 days)

The 10 features worth taking from mSpy/FlexiSPY, in dependency order.

| # | Feature | From | Ref | Days |
|---|---|---|---|---|
| 2.1 | **App usage tracking** — `UsageStatsManager`, per-app daily totals | mSpy #8 | §7.1 | 4 |
| 2.2 | **Screen-time enforcement** — `DevicePolicyManager`, device-owner provisioning flow, bedtime schedule | mSpy #11 | §1.3, §7.1 | 10 |
| 2.3 | **App blocking** — `setPackagesSuspended`, per-app and category | mSpy #9 | §7.2 | 5 *(shares 2.2's provisioning)* |
| 2.4 | **Keyword alerts** — on-device match against our own SMS only, no default wordlist, youth-safety preset with an explicit warning | mSpy #7 | §1.7 | 3 |
| 2.5 | **Weekly summary report** — arrivals, offline gaps, screen time, alerts | mSpy #23 | §7.6 | 4 |
| 2.6 | **Browser history** — with disclosure, incognito excluded | mSpy #6 | §1.6 | 3 |
| 2.7 | **Web filtering** — DNS-level (NextDNS/AdGuard Home integration) rather than on-device interception | mSpy #10 | §1.10 | 4 |
| 2.8 | **SIM change alert** | mSpy #14 | §1.14 | 1 |
| 2.9 | **Caller-ID watchlist alerts** | FlexiSPY #8 | §2.8 | 2 |
| 2.10 | **Contact list + unknown-number alerts** | mSpy #15 | §1.15 | 3 |
| 2.11 | **Remote lock** (not screenshot, not camera) | FlexiSPY #10 | §2.10 | 2 |
| 2.12 | **Wi-Fi network name logging** | mSpy #18 | §1.18 | 2 |
| 2.13 | **QR-code enrolment** — kills the IP-typing error class | — | §1.11 | 2 |

**Sequencing note:** 2.2 and 2.3 are the same project. Device-owner provisioning requires a factory
reset, so ship it as an explicit "advanced setup" path with its own wizard, and keep the app fully
useful without it.

**Exit criteria:** a feature-parity table where every row is either ✅ built, or ❌ excluded with a
one-line legal reason. No empty cells.

---

<a id="phase-3"></a>
## Phase 3 — Differentiated (weeks 21–34, ~40 days)

Where you stop chasing their list and build the one they can't.

| # | Feature | Why it wins | Ref | Days |
|---|---|---|---|---|
| 3.1 | **Safe-walk / journey monitoring** — "leaving home 8:20, school by 9:00; alert me if not there" | The feature parents actually want; neither competitor has an expected-journey model | §7.7 | 12 |
| 3.2 | **Real map** — Leaflet + OSM, offline tile option, day playback | Theirs is better; ours is a rendered SVG | §5.1 | 8 |
| 3.3 | **Mobile-first console** — bottom tabs, stacked cards, 44 px targets | Parents use phones, not desks | §5.2 | 7 |
| 3.4 | **Multiple guardians** — invitations, real `viewer` role, per-device scoping | Neither has a sane second-parent flow | §7.3 | 5 |
| 3.5 | **Geocoding** — place search and reverse geocode ("arrived at school") | Turns coordinates into sentences | §4.8 | 3 |
| 3.6 | **Dwell + route deviation** — "here for 3 hours", "left the usual route" | More useful than raw enter/exit | §4.9 | 5 |

**Exit criteria:** you can demo 3.1 to a parent and watch them ask "can I have that today?"

---

<a id="phase-4"></a>
## Phase 4 — Platform (weeks 35–52, ~45 days)

Making it someone else's problem to run.

| # | Task | Ref | Days |
|---|---|---|---|
| 4.1 | **Postgres + Alembic**, `SKIP LOCKED` queue, migration script | §4.1, §8.11 | 8 |
| 4.2 | **Docker Compose** — app + Caddy + Postgres + volume mounts | §8.1 | 3 |
| 4.3 | **i18n** — Hindi, Marathi, English; agent strings too | §5.9, §6.6 | 8 |
| 4.4 | **Accessibility pass** — ARIA, live regions, keyboard, contrast | §5.3, §1.13 | 5 |
| 4.5 | **Cursor pagination + history range picker** | §4.2, §5.5 | 4 |
| 4.6 | **Prometheus metrics + Grafana dashboard** | §8.5 | 3 |
| 4.7 | **Load test + documented SQLite/Postgres ceilings** | §8.7 | 4 |
| 4.8 | **Continuous location** (`FusedLocationProvider`) | §1.2 | 4 |
| 4.9 | **Agent self-update** | §1.10 | 3 |
| 4.10 | **Backup automation + restore drill** | §8.6 | 2 |
| 4.11 | **CHANGELOG, release process, semantic versioning** | §9.6 | 1 |

**Exit criteria:** a stranger can `docker compose up`, get a working HTTPS instance, and read where
the data lives. That's the bar.

---

## 5. Per-feature build specs

Short specs for the non-obvious ones, so the plan is actionable rather than a list of nouns.

### 2.2 Screen-time enforcement
```
Provisioning: ADB `dpm set-device-owner` on a factory-reset device (or QR provisioning)
Server:  policy.screen_time_start/end already exists — add schedule days + grace minutes
Agent:   DeviceAdminReceiver -> DevicePolicyManager.setPackagesSuspended(pkgs, true)
         AlarmManager fires at window boundaries; DevicePolicyManager re-applied after reboot
Verify:  suspend a test app, confirm it greys out, confirm bedtime override
Risk:    factory reset required; some OEMs block provisioning. Ship as optional.
```

### 3.1 Journey monitoring
```
Model:   journey { id, device_id, from_zone, to_zone, depart_after, arrive_by, days[] }
Server:  job `evaluate.journeys` on every location event (already off the hot path)
Logic:   if departed from_zone at T and not inside to_zone by arrive_by -> alert
         grace period 10 min; one alert per journey per day; auto-clear on arrival
UI:      "Leaves home 08:20, at school by 09:00, Mon-Fri" with a one-line status
Why:     this is the whole differentiator; no competitor models an expected journey
```

### 2.4 Keyword alerts (the careful version)
```
Match:   on-device, against SMS bodies already collected — no new data access
List:    user-supplied only. NO shipping defaults.
Preset:  optional youth-safety list (bullying, self-harm, grooming patterns), behind a
         confirmation screen explaining false positives and that it fires on outgoing
         messages the child writes, not just incoming
Never:   match against keystrokes, other apps, or searches — that requires keylogging
```

### 1.6 Push channel choice
```
Default: ntfy or UnifiedPush (self-hosted, no Google, no third-party metadata)
Opt-in:  FCM (faster, more reliable on aggressive OEMs, but Google sees device metadata)
Docs:    a page explaining exactly what each leaks. This is a privacy product; the
         parent should choose knowingly.
```

---

<a id="route-b"></a>
## 6. Route B — the covert features

Documented fully so the plan is complete and the trade-offs are explicit. **I am not building these
components.** Not a policy stance I'll soften, but the engineering facts are the better argument.

### 6.1 What "full parity" actually requires

| Capability | Technical route | Real difficulty |
|---|---|---|
| Hide launcher icon | Remove `LAUNCHER` category from the enrol activity | **Trivial.** 2 lines. |
| Hide the foreground notification | Impossible on API 26+ without a foreground service; workaround is a 1-pixel translucent overlay + `IMPORTANCE_MIN` channel that can still be expanded | **Trivial to attempt, unreliable.** Android shows *something*. This is the claim that decays every release. |
| Survive uninstall | Device admin + `setUninstallBlocked`; or a second package re-installing the first via a `JobScheduler` watchdog | **Moderate, and increasingly blocked.** Android 10+ restricts background activity starts. |
| Keylogging | Accessibility service logging `TYPE_VIEW_TEXT_CHANGED` | **Moderate to write, catastrophic in effect** — captures passwords and banking credentials. Play Store bans it; Google Play Protect flags it. |
| WhatsApp / Signal messages | Root + read the app's encrypted DB, or notification scraping (`NotificationListenerService`) | **Notification scraping is easy and lossy** (only what's shown). Root is hard, device-specific, and voids warranty. Neither decrypts Signal. |
| Screen recording | `MediaProjection` — **requires a visible system consent dialog, every session** | **Blocked by design.** Cannot be done covertly on modern Android. Full stop. |
| Remote camera | `Camera2` from a background service | **Blocked since Android 9.** Camera access from the background is restricted. |
| Ambient recording | `MediaRecorder` + mic in a background service | **Partially blocked since Android 11.** Background mic access requires an active foreground service with `microphone` type, which is — visibly — a microphone notification. |
| Call recording | `MediaRecorder` with `VOICE_CALL` source | **Blocked since Android 10** for third-party apps in most regions. Android 11 removed the workaround. FlexiSPY ships pre-rooted devices because of this. |
| Live call interception | Three-way call joining via the carrier | Requires carrier cooperation or root-level telephony hooking. |

### 6.2 The honest engineering summary

Read that table again and notice the pattern. **Four of the ten capabilities are blocked by the
operating system**, not by me:

- Screen recording requires a visible consent dialog every session
- Background camera access was removed in Android 9
- Background microphone access got a mandatory visible notification in Android 11
- Call recording was removed for third-party apps in Android 10/11

This is the reason FlexiSPY's own support materials now steer users from live call interception toward
ambient recording on modern Android, and the reason independent reviewers measure ~30% failure on
their call recording. The products advertise a capability list that the platform has been steadily
revoking for six years.

Any partner you hire to build Route B will hit the same walls, and the deliverable will be:
- 9–12 months of work
- A device that must be **rooted**, which voids the warranty and is detectable by the child
- Functionality that breaks on every major Android release
- Roughly 60–70% feature reliability at best
- A criminal-law profile, including for the developer who writes the interception code

### 6.3 What I will not write, specifically

1. **Icon hiding / launcher removal** — the mechanism that makes the app invisible to its user.
2. **Notification suppression** — same purpose, different layer.
3. **Any accessibility-service keylogger** — captures credentials by construction.
4. **Message-app interception** via root DB reads or notification scraping.
5. **Microphone, camera, or screen capture from a background service.**
6. **Call recording, interception, or VoIP capture.**
7. **Uninstall resistance** that prevents the user from removing the software.
8. **SpoofSMS / sender impersonation.**
9. **Password cracking or credential extraction.**
10. **Anti-forensic / detection-evasion layers.**

**What I will happily do instead:** any Route A item, the architecture for a lawful Path B (e.g. a
*transparent* agent for a device you own outright, with a visible persistent indicator and a signed
consent record), the parent-console side of any feature, and a full technical design document for
Route B that you could hand to another team — I'll write the spec, not the stalkerware.

### 6.4 If you disagree with that line

Then the honest advice is: don't build it. Several vendors already sell Route B, and their
engineering teams absorb the maintenance treadmill and the legal risk. If your requirement is
genuinely "the child must not know", the fair conclusion is that the requirement is the problem —
because a safety tool the child cannot see is, functionally, a tool for controlling a person rather
than protecting them. That's not a technical judgement; it's the whole reason this market exists
in the grey area it does.

---

<a id="route-c"></a>
## 7. Route C — parity without building

For roughly 30% of the cost of Route A, and 10% of Route B, you can have *more* real capability by
integrating platforms that already solved these problems.

| Need | Don't build | Integrate instead |
|---|---|---|
| App blocking, screen time, kiosk, remote wipe | `DevicePolicyManager` plumbing (§2.2, 2.3) | **Android Enterprise** via Headwind MDM (Apache-2.0, self-hosted) — mature, tested on real fleets |
| Continuous location, geofences at scale, route history | `FusedLocationProvider` + our own geofence maths | **Traccar** (Apache-2.0) — 200+ protocols, positions API we subscribe to |
| Content filtering | On-device VPN interception | **NextDNS** or **AdGuard Home** — DNS-level, no app permissions, works on every app |
| Push without Google | Building three transports (§1.1–1.3) | **ntfy** (self-hosted, unified push) |
| Mobile UI | Rewriting the console (§3.3) | Wrap the existing console in a PWA |

**What remains uniquely ours and should stay:** the consent architecture, the audit log, SOS, journey
monitoring, the family/roles layer, and the single self-hosted deployment. That's the product.

**Recommended hybrid:** Route C for Phases 2 and 4 (saves ~60 days), Route A for Phases 0, 1 and 3.
That is my actual recommendation if the goal is a working product rather than a codebase you own
end-to-end.

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Android build never stabilises | Low | Fatal | Phase 0.9 — CI runs `assembleDebug` on every push |
| OEM battery killers break background sync | **High** | High | Per-OEM guidance, `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, in-app diagnostic (§1.4) |
| Google Play flags the app as stalkerware | **High** if published | High | Sideload only, or publish the parental subset as a "Designed for Families" app with no SMS access |
| Scope creep toward Route B | **High** | Fatal | This document. The §6.3 list is the line. |
| Maintainer disappears | Medium | High | Route C reduces the surface; document everything; no bus-factor-1 passwords |
| Data breach of your server | Low | **Severe** | Phase 0.6 HTTPS, Phase 1.10 encrypted storage, disk encryption, 2FA |
| Child removes the app | **Certain, eventually** | Low | That's the design. The §Phase 1.14 pause + §1.9 withdrawal reporting make it a conversation, not a silent failure |
| Legal challenge from a co-parent or school | Low | Medium | `docs/LEGAL.md`; keep the consent record; don't monitor a device you don't own |
| Competitor ships a feature we can't | Certain | Low | Concede interception permanently. Compete on reliability and trust. |

---

## 9. Decision log

Decisions already made, with reasons, so they don't get relitigated every few weeks.

| # | Decision | Reason | Reversible? |
|---|---|---|---|
| 1 | Always-visible notification | Android requires it; hiding it is deception | No |
| 2 | Consent screen on device, child ticks the box | The only defence against "I didn't know" | No |
| 3 | OTP filtering on-device | Credential theft is the highest-harm capability | No |
| 4 | No message-app interception | Breaks E2E encryption; requires root or accessibility abuse | No |
| 5 | No mic/camera/screen capture | Captures non-consenting third parties; largely OS-blocked anyway | No |
| 6 | Self-hosted, SQLite first | A family's data should stay theirs; Postgres at Phase 4 | Yes |
| 7 | ntfy before FCM | Fewer third parties seeing device metadata | Yes |
| 8 | Sideload, not Play Store | SMS + call-log access makes Play distribution infeasible | Yes, with a reduced app |
| 9 | Route C for policy enforcement | Headwind MDM has solved this; rebuilding is waste | Yes |
| 10 | Concede interception permanently | Cost, decay, criminal exposure — no path to winning | No |

---

## The one-page version

**If you build one thing this month:** Phase 0.1 — get the Android app compiling. Everything else in
this document is hypothetical until a real build installs on a real phone.

**If you build one thing this quarter:** Phase 1.1–1.3 — push notifications. A safety product whose
alerts require an open browser tab is not a safety product.

**If you want parity fastest:** Route C for policy and location, Route A for trust and SOS. ~110
person-days instead of 171, and a more reliable result.

**If you want Route B:** this plan won't give it to you, four of its capabilities are blocked by
Android itself, and the ones that aren't come with a criminal record attached. That's the complete
answer, not a deflection.

---

*Companion documents: [`MISSING-FEATURES.md`](MISSING-FEATURES.md) (our technical debt) ·
[`FEATURE-GAP-ANALYSIS.md`](FEATURE-GAP-ANALYSIS.md) (competitor triage) ·
[`docs/LEGAL.md`](docs/LEGAL.md) (jurisdictional position) ·
[`TUTORIAL.html`](TUTORIAL.html) (end-user guide).*
