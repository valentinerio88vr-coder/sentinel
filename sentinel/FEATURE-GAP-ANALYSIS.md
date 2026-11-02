# Feature Gap Analysis — Sentinel vs mSpy vs FlexiSPY

What the two largest commercial monitoring products have that Sentinel does not, what Sentinel has
that neither does, and a triage of each gap into **build it**, **never build it**, or **not
applicable**.

- **Audited:** Sentinel v2.0.0
- **Sources:** current vendor feature pages and independent 2026 reviews (cited inline). Vendor
  marketing overstates capability; where reviewers contradict it, both are noted.
- **Companion document:** [`MISSING-FEATURES.md`](MISSING-FEATURES.md) — gaps that are *our* fault.
  This file is about gaps that are *a choice*.

---

## How to read this

| Verdict | Meaning |
|---|---|
| ✅ **BUILD** | Lawful, useful for a parent, and worth adding. Priority given (P0–P3). |
| ⚠️ **BUILD DIFFERENTLY** | The need is real but their implementation is unlawful or unethical. Build a safer version. |
| ❌ **NEVER** | Excluded on principle or law. Will not be built regardless of demand. |
| ➖ **N/A** | Depends on capability our platform doesn't have (root, iOS, desktop agents). |

The distinction that matters: **a feature is not the same as its method.** "Know if my child is
being bullied" is a legitimate need. "Read every keystroke they type" is one unlawful way to serve
it — and a screen-time report plus keyword alerts serve it almost as well without the harm.

---

## 1. What mSpy has that Sentinel doesn't

mSpy positions as the mainstream parental-control option. Current feature set per their site and
2026 reviews includes keylogger, screen recorder, live screen streaming, call recorder, monitoring
of 30+ messaging apps, browser history, media access, app blocking, geofencing and keyword alerts
[1](https://www.mspy.com/) [4](https://hirecyberexpert.com/mspy-review) [10](https://www.sales-hacking.com/en/post/comment-utiliser-mspy).

| # | mSpy feature | Sentinel today | Verdict |
|---|---|---|---|
| 1 | **Keylogger** — every keystroke, per app, incl. passwords [1](https://www.mspy.com/) | None | ❌ **NEVER** — credential harvesting. See §5. |
| 2 | **Screen recorder** — periodic screenshots of whatever is on screen [4](https://hirecyberexpert.com/mspy-review) | None | ❌ **NEVER** — captures private content and third parties who never consented. |
| 3 | **Live screen streaming** [1](https://www.mspy.com/) | None | ❌ **NEVER** — real-time surveillance of a child's screen. |
| 4 | **Call recording** (Android, root-only per some reviews) [4](https://hirecyberexpert.com/mspy-review) | None | ❌ **NEVER** — records the *other party*, who is not your child and has not consented. Illegal in many jurisdictions without all-party consent. |
| 5 | **Monitoring of 30+ messaging apps** — WhatsApp, Snapchat, Instagram, Telegram, Discord, Tinder, AI chatbots [1](https://www.mspy.com/) [2](https://m-spy.net/) | None | ❌ **NEVER** — requires root, accessibility abuse, or notification scraping; breaks E2E encryption. |
| 6 | **Browser history** — visited URLs, bookmarks, incl. incognito [4](https://hirecyberexpert.com/mspy-review) | None | ✅ **BUILD (P2)** — on-device `Browser.BOOKMARKS_URI` and the Chrome history provider, with disclosure. Lawful for your own minor child. |
| 7 | **Keyword alerts** — notify when a flagged word appears in messages or searches [10](https://www.sales-hacking.com/en/post/comment-utiliser-mspy) | None | ⚠️ **BUILD DIFFERENTLY (P1)** — alert on *your own collected SMS only*, keyword-match on-device, and never ship a default wordlist. High value for bullying/self-harm signals. |
| 8 | **App usage tracking** — time spent per app [4](https://hirecyberexpert.com/mspy-review) | App inventory only, and that collector is currently dead code (see `MISSING-FEATURES.md` §1.8) | ✅ **BUILD (P1)** — `UsageStatsManager`. Straightforward, lawful, and more useful to a parent than a raw app list. |
| 9 | **App blocking / restriction** — remote block of specific apps [4](https://hirecyberexpert.com/mspy-review) | Policy stored + delivered, **not enforced** | ✅ **ALREADY SPECIFIED (P1)** — needs `DevicePolicyManager`. Their version is the right idea; ours is unfinished, not absent. |
| 10 | **Website/content filtering** — block adult or gambling sites [10](https://www.sales-hacking.com/en/post/comment-utiliser-mspy) | None | ✅ **BUILD (P2)** — DNS-level filtering (NextDNS/AdGuard Home) or a local VPN service. Child-safety value is high. |
| 11 | **Screen time limits** — daily caps, schedules [6](https://umobix.com/blog/mspy-review/) — *reviews say mSpy lacks these* | Policy field exists, not enforced | ✅ **BUILD (P1)** — we're closer than they are. |
| 12 | **Media file access** — photos, videos, audio from the gallery [3](https://m-spy.net/android-tracking) | None | ❌ **NEVER** — gallery access exposes friends' images, intimate photos, and everything a child was entrusted with. |
| 13 | **Remote camera / microphone** (Extreme plan) [6](https://umobix.com/blog/mspy-review/) | None | ❌ **NEVER** — see §5. This is the defining stalkerware capability. |
| 14 | **SIM change alert** — notify when the SIM is swapped [4](https://hirecyberexpert.com/mspy-review) | None | ✅ **BUILD (P2)** — `TelephonyManager` + `SubscriptionManager`. Cheap, genuinely useful anti-theft signal. |
| 15 | **Contact list access** [4](https://hirecyberexpert.com/mspy-review) | Collector kind exists in the schema (`contact`), never implemented | ✅ **BUILD (P2)** — with a purpose (unknown-number alerts), not as a data dump. |
| 16 | **Calendar & notes access** [4](https://hirecyberexpert.com/mspy-review) | None | ❌ **NEVER** — no safety justification proportional to the intrusion. |
| 17 | **Email monitoring** (Gmail, default mail apps) [4](https://hirecyberexpert.com/mspy-review) | None | ❌ **NEVER** — same class as message interception. |
| 18 | **Wi-Fi / network logs** [4](https://hirecyberexpert.com/mspy-review) | `network` kind declared, never implemented | ✅ **BUILD (P3)** — connected network name only (not traffic). Useful for "did they arrive somewhere with Wi-Fi". |
| 19 | **Stealth mode / hidden app** [7](https://cybernews.com/best-parental-control-apps/mspy-review/) | Impossible by design — permanent notification | ❌ **NEVER** — see §5. |
| 20 | **Deleted message recovery** [4](https://hirecyberexpert.com/mspy-review) — *other reviews say unavailable* [6](https://umobix.com/blog/mspy-review/) | None | ❌ **NEVER** — root-dependent, and the reviews disagree on whether it works at all. |
| 21 | **Multi-device Family Kit** (3 devices) [10](https://www.sales-hacking.com/en/post/comment-utiliser-mspy) | Unlimited devices per account | ➖ **N/A** — no artificial cap exists to remove. Their limit is a billing construct. |
| 22 | **iOS monitoring** (iCloud, no jailbreak) [4](https://hirecyberexpert.com/mspy-review) | Android only | ➖ **N/A (XL)** — a separate product. iOS forbids background SMS/call-log access entirely. |
| 23 | **Weekly activity report** (Ultimate plan) [10](https://www.sales-hacking.com/en/post/comment-utiliser-mspy) | None | ✅ **BUILD (P2)** — already noted in our backlog. High perceived value, low technical risk. |
| 24 | **"Send a tracking link"** — track without installing [1](https://www.mspy.com/) | None | ❌ **NEVER** — covert tracking of a person rather than a consented device. This is anti-parenting. |

---

## 2. What FlexiSPY has that Sentinel doesn't

FlexiSPY is the power-user product. Its differentiators are in the EXTREME tier: call recording,
live call interception, ambient recording, remote camera, password cracking and SpoofSMS
[5](https://www.spyphonedude.com/reviews/should-i-buy-flexispy-extreme-or-premium/). It also covers
Windows and macOS [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/).

| # | FlexiSPY feature | Sentinel today | Verdict |
|---|---|---|---|
| 1 | **Live call interception (SpyCall)** — silently joined to a live call as a muted third party [5](https://www.spyphonedude.com/reviews/should-i-buy-flexispy-extreme-or-premium/) | None | ❌ **NEVER** — the single most indefensible feature in this market. Intercepts two people, one of whom is a stranger to you. |
| 2 | **Ambient recording** — remote mic, up to 20 min/session, schedulable [5](https://www.spyphonedude.com/reviews/should-i-buy-flexispy-extreme-or-premium/) | None | ❌ **NEVER** — recording a room captures everyone in it, including people who never consented and may be minors. |
| 3 | **RemCam / RemVid** — silent remote photo and video capture [2](https://xnspy.com/blog/flexispy-review.html) | None | ❌ **NEVER** — covert camera activation. Criminal in much of the world. |
| 4 | **SpoofSMS / SpySMS** — send SMS appearing to come from the child's phone [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) | None | ❌ **NEVER** — impersonation. Use case is deception of third parties. |
| 5 | **Password cracking / recovery** [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) | None | ❌ **NEVER** — credential theft, full stop. |
| 6 | **Call recording, incl. VoIP** (WhatsApp/Viber calls) [1](https://impulsec.com/parental-control-software/flexispy-2/) | None | ❌ **NEVER** — same all-party consent problem as mSpy §1.4. Also unreliable: reviewers measured ~30% of calls degrading or failing outright [3](https://www.vigilkids.com/best-alternative/flexispy-reviews/). |
| 7 | **IM tracking** — WhatsApp, Messenger, Viber, Skype, Telegram, LINE [3](https://www.vigilkids.com/best-alternative/flexispy-reviews/) | None | ❌ **NEVER** — as mSpy §1.5. |
| 8 | **Caller-ID alerts** — notify when a specific number calls or texts [7](https://www.techuntold.com/flexispy-review/) | Partial — a `watchlist_contact` rule exists in an early sketch, never wired up | ✅ **BUILD (P2)** — lawful and cheap: match against numbers you already collect from the call log. |
| 9 | **Location alerts** (in addition to geofencing) [7](https://www.techuntold.com/flexispy-review/) | Geofences + SOS | ➖ **N/A** — we already exceed this with hysteresis and zone-state tracking. |
| 10 | **Remote commands** — lock, restart, screenshot, mic activation [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) | locate_now, ring, sync_now | ⚠️ **BUILD DIFFERENTLY (P2)** — add `lock_device` (lawful, useful) and `locate_now`. Never screenshot, mic, or camera. |
| 11 | **Photos & videos** from the device [7](https://www.techuntold.com/flexispy-review/) | None | ❌ **NEVER** — as mSpy §1.12. |
| 12 | **Stealth / "hide rooting" / invisible on Android 11–15** [8](https://www.flexispy.com/en/mspy-vs-flexispy-review.htm) | Impossible by design | ❌ **NEVER** — and see §5 on whether it's even true. |
| 13 | **Pre-installed phones** — buy a device with it already on [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) | None | ❌ **NEVER** — a business model built on a person not knowing. |
| 14 | **Windows / macOS agents** [4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) | Android only | ⚠️ **BUILD DIFFERENTLY (P3)** — a transparent, user-visible desktop agent (location of nothing; just screen-time and app usage) is a legitimate separate product. Not a port of theirs. |
| 15 | **Scheduled ambient/recording triggers** [5](https://www.spyphonedude.com/reviews/should-i-buy-flexispy-extreme-or-premium/) | None | ❌ **NEVER** — scheduling covert recording is premeditated surveillance. |
| 16 | **Keyword alerts** (all plans) [7](https://www.techuntold.com/flexispy-review/) | None | ⚠️ **BUILD DIFFERENTLY (P1)** — as mSpy §1.7. |
| 17 | **Uninstall resistance / tamper controls** [1](https://impulsec.com/parental-control-software/flexispy-2/) | None, deliberately | ❌ **NEVER** — a child must always be able to remove it. |
| 18 | **App blocking** | Policy stored, not enforced | ➖ **N/A** — reviewers note FlexiSPY *lacks* app blocking and screen-time reporting entirely [3](https://www.vigilkids.com/best-alternative/flexispy-reviews/). We're ahead here. |

---

## 3. What Sentinel has that neither does

This is the part the comparison usually omits, and it's where the product's actual case lives.

| Capability | Sentinel | mSpy | FlexiSPY |
|---|---|---|---|
| **On-device consent screen** with an explicit checkbox before any collection | ✅ | ❌ [3](https://www.vigilkids.com/best-alternative/flexispy-reviews/) — "Consent workflow: not provided" | ❌ |
| **Permanent visible notification** the user can tap | ✅ | ❌ stealth mode is the selling point | ❌ |
| **Honest, one-tap stop** with no retaliation | ✅ | ❌ | ❌ |
| **Child can see what was shared** (in progress, `MISSING-FEATURES.md` §6.2) | 🔶 designed | ❌ | ❌ |
| **Self-hosted — no vendor holds your child's data** | ✅ | ❌ cloud only | ❌ cloud only |
| **No subscription, unlimited devices** | ✅ | ❌ $11–49/mo | ❌ $49.95–119/mo |
| **Full audit log** of every read of location data | ✅ | ❌ unknown to the user | ❌ |
| **Data export + hard delete** (portability/erasure) | ✅ | ❌ | ❌ |
| **OTP filtering on-device** — passcodes never transmitted | ✅ | ❌ keylogger captures them by design | ❌ |
| **Open source, inspectable** | ✅ | ❌ | ❌ |
| **Geofence hysteresis** — ignores low-accuracy fixes instead of alerting on noise | ✅ | ❌ not documented | ❌ not documented |
| **SOS button on the lock screen** | ✅ | ⚠️ not a documented feature | ⚠️ not a documented feature |
| **Legal exposure to the buyer** | Low, with disclosure | **High** | **Highest** |

Note the last row honestly: in several US states and EU member states, installing mSpy or FlexiSPY
on an adult's device is criminal. On your own minor child's phone with disclosure it is generally
defensible — which is exactly why Sentinel's consent architecture isn't a limitation, it's what
makes the product usable without a lawyer.

---

## 4. Triage: what to actually build

Distilled from §1 and §2. This supersedes the “borrow from spyware” instinct entirely.

### P0 — worth doing this month (small, lawful, obvious)
1. **App usage tracking** (`UsageStatsManager`) — mSpy §1.8.
2. **Screen-time enforcement** — already specified, exceeds both competitors.
3. **Keyword alerts on our own SMS**, on-device matching, no default wordlist — mSpy §1.7.

### P1 — next quarter
4. **Web filtering** at DNS level (NextDNS / AdGuard Home) — mSpy §1.10. Easier and safer than browser history.
5. **Browser history** with disclosure — mSpy §1.6.
6. **Weekly summary report** — mSpy §1.23.
7. **Contact list with unknown-number alerts** — mSpy §1.15.

### P2 — when the basics are solid
8. **SIM change alert** — mSpy §1.14. Ten lines of code, real theft value.
9. **Caller-ID watchlist alerts** — FlexiSPY §2.8.
10. **Remote lock** (not screenshot) — FlexiSPY §2.10.
11. **Wi-Fi network name logging** — mSpy §1.18.

### Never (repeated for emphasis)
Keylogger · screen recorder · live screen streaming · call recording · call interception · ambient
recording · remote camera · gallery access · message-app interception · SpoofSMS · password
cracking · stealth mode · deleted-message recovery · tracking links · pre-installed phones.

---

## 5. What the marketing doesn't say

Four claims worth checking before anyone pays for either product.

### "Completely hidden" is increasingly false
FlexiSPY advertises being invisible on Android 11–15 [8](https://www.flexispy.com/en/mspy-vs-flexispy-review.htm),
but independent reviewers report that "complete invisibility isn't guaranteed, particularly on newer
Android versions or non-jailbroken iPhones" [7](https://cybernews.com/best-parental-control-apps/mspy-review/).
Other reviews note the full feature set often depends on rooting, and that FlexiSPY's own support
materials now steer users away from live call listening toward ambient recording on modern
Android [3](https://www.vigilkids.com/best-alternative/flexispy-reviews/). You are paying
$119/month for capabilities that degrade with every OS release.

### Reliability is worse than the feature list implies
Reviewers measured roughly **30% of recorded calls either degraded or missing entirely** on FlexiSPY
[3](https://www.vigilkids.com/best-alternative/flexispy-reviews/). For a *safety* product, a
detection that misses a third of the time isn't a feature — it's a false sense of security. Contrast
with a geofence that ignores a 900 m cell-tower fix rather than firing on noise.

### The feature list hides who it's really for
mSpy operates a marketing page aimed at **private investigators** [1](https://www.mspy.com/), and
FlexiSPY sells the ability to silently record a room. The parental-control framing is a licensing
and marketing posture, not a description of the primary use case. Vendor positioning documents also
advise against promoting mic/camera features in family-safety content as an "extreme compliance risk"
[4](https://impulsec.com/parental-control-software/flexispy-vs-spyera/).

### The all-party consent trap
Call recording is the clearest example. Your child is one party to the call; their friend is the
other. In jurisdictions requiring **all-party consent** — much of the EU, several US states, and
India's own jurisprudence on recording without consent — recording that call is unlawful regardless
of whose phone it is. The same logic sinks ambient recording and remote camera: they capture people
who never agreed to anything. This is why those features are categorised as **NEVER** here and not
merely "risky" — it isn't a policy preference, it's the third-party problem.

---

## Sources

| Ref | Source |
|---|---|
| 1 | [mSpy — official feature page](https://www.mspy.com/) |
| 2 | [mSpy Review 2026 — m-spy.net](https://m-spy.net/) |
| 3 | [mSpy for Android — m-spy.net](https://m-spy.net/android-tracking) |
| 4 | [mSpy feature breakdown 2026 — hirecyberexpert](https://hirecyberexpert.com/mspy-review) |
| 5 | [FlexiSPY EXTREME vs PREMIUM — spyphonedude](https://www.spyphonedude.com/reviews/should-i-buy-flexispy-extreme-or-premium/) |
| 6 | [mSpy plan comparison — umobix](https://umobix.com/blog/mspy-review/) |
| 7 | [mSpy parental control review — cybernews](https://cybernews.com/best-parental-control-apps/mspy-review/) |
| 8 | [FlexiSPY vs mSpy — flexispy.com](https://www.flexispy.com/en/mspy-vs-flexispy-review.htm) |
| 9 | [FlexiSPY 2026 review — impulsec](https://impulsec.com/parental-control-software/flexispy-2/) |
| 10 | [mSpy feature/pricing table — sales-hacking](https://www.sales-hacking.com/en/post/comment-utiliser-mspy) |
| 11 | [FlexiSPY review & alternatives — vigilkids](https://www.vigilkids.com/best-alternative/flexispy-reviews/) |
| 12 | [FlexiSPY review — xnspy](https://xnspy.com/blog/flexispy-review.html) |
| 13 | [FlexiSPY review — techuntold](https://www.techuntold.com/flexispy-review/) |
| 14 | [FlexiSPY vs Spyera — impulsec](https://impulsec.com/parental-control-software/flexispy-vs-spyera/) |

Vendor pages describe **intended** capability. Where independent reviewers found the same feature
unreliable or contradicted the marketing, that is stated. Treat any single review — including these —
as a data point, not a verdict.

---

## Closing

Across both products, **42 distinct features** were assessed: 10 worth building, 5 to build
differently, 5 not applicable to our platform, and **25 that will never be built** — 60% of the
combined feature surface. Nearly all of the buildable remainder is already in
`MISSING-FEATURES.md` under our own priority ordering rather than theirs.

The honest summary: the commercial products win on *breadth of interception* — they can read a
child's keyboard, screen, camera, microphone, and every encrypted chat app. That breadth is why they
are banned from Google Play, why they require rooting, why they fail a third of the time, and why
buying one for an adult's phone is a criminal offence in much of the world.

Sentinel trades that breadth for something they cannot offer at any price: **a child who knows it is
there, can see what it does, and can switch it off.** For a safety product aimed at your own kids,
that is not the weaker position. It is the only one that survives contact with a teenager.

Full legal position: [`docs/LEGAL.md`](docs/LEGAL.md) · Our own technical debt:
[`MISSING-FEATURES.md`](MISSING-FEATURES.md)
