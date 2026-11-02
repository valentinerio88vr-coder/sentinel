# Publicity audit — before this repo goes public

Run on the working tree immediately before the first push, because the repository
`valentinerio88vr-coder/sentinel` is **public** (`private: false`, confirmed via the GitHub API).

Verdict: **safe to publish after the images were regenerated** — which is now done. Everything below
was found and fixed, or is a deliberate decision.

---

## Fixed

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | **Screenshot `04-device.png` showed real-looking contact numbers** — `+91 98XXX XXXXX` and `+91 99XXX XXXXX` (full values in git history of the pre-fix seed only), presented as a child's SMS and call history | **High** | Demo data moved to the non-routable `+91 00000 000XX` range; all 8 screenshots regenerated from a clean seed |
| 2 | Demo phone numbers in `seed_demo.py` / `simulate.py` source | Medium | Same substitution |
| 3 | `.bat` files were LF — broken on Windows | Medium | Converted to CRLF + `.gitattributes` |
| 4 | SQLite DB, WAL, SHM in the working tree | **Critical** if committed | `.gitignore`; `push.sh` refuses to push if any is tracked |
| 5 | No licence / contribution / security docs | Low | `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` added |

## Found while doing the work — and fixed

These were real product bugs, not audit items. They surfaced because regenerating the screenshots
meant driving the console end to end.

| Bug | Impact | Fix |
|---|---|---|
| **Enrolment code vanished on creation** — `renderHome()` rebuilt `#new-form` empty after the code arrived | A parent clicks "Get code" and the screen goes blank. Complete blocker for enrolment through the UI. | Refresh only the device cards; leave the code panel alone |
| **`seed_demo.py` ignored `--base`** and always wrote to port 8000 | Worse than it looks: it printed "created demo account" while writing to a *different server*, so a seed that appears to work leaves an empty database | `--base` / `SENTINEL_BASE` honoured |
| A stray comment inside a tuple broke `seed_demo.py` entirely | `SyntaxError` on run | Removed |
| `capture_screenshots.py` selectors didn't match the DOM (`.card` vs `.kid`, etc.) | No screenshots possible | Corrected; new reusable tool committed |

## Reviewed and deliberately kept

| Item | Decision |
|---|---|
| `parent@sentinel.example.com` / `SentinelDemo2026` | Kept. `example.com` is IANA-reserved and cannot receive mail; the password only works against a demo DB you seed yourself. It is the documented demo login. |
| `192.168.1.42` in the tutorial | Kept. RFC 1918 private range, and it is an *example* the reader is told to replace with their own IP. Publishing it leaks nothing. |
| `19.1075, 72.8371` (Andheri / a Mumbai school) | Kept. Public coordinates of a neighbourhood, not a child's home. The demo family's house is jittered per-run and is not any real address. |
| `C:\Users\You\Desktop\Sentinel.lnk` | Kept. Literal placeholder text. |
| Git identity `Sentinel <dev@sentinel.local>` | Kept. Contains no personal email. |
| `tools/e2e_test.py` uses `example.com` addresses | Kept. Reserved domain, generated per run. |

## Known and accepted (not fixable by editing)

| Item | Why it stays |
|---|---|
| `README.md`, `ROADMAP.md` and `MISSING-FEATURES.md` document the product's **unfixed weaknesses** (Android never compiled, no push notifications, policy not enforced) | Deliberate. An honest engineering readme stops anyone over-trusting v2.0.0. If you'd rather not publish a weakness map, make the repo private instead — but I'd argue against it. |
| `docs/LEGAL.md` states a jurisdictional position | Publicly quotable, and intended to be. It is the product's defence, not a liability. |
| `SECURITY.md` lists limitations | Standard practice; helps rather than harms. |

## One thing worth a second thought

The `LICENSE` is MIT, which permits commercial and closed-source reuse — including by someone who
takes this code and removes the visible consent screen. The additional notice in `LICENSE` states the
intent, but **MIT does not legally prevent that**.

If that matters to you, **AGPL-3.0** is the stronger choice for this kind of project: it requires
anyone running a modified version as a network service to publish their source, which makes a covert
fork much less attractive. Say the word and I'll swap it — better decided now than after the first
public commit.

---

## Verification performed

```
grep sweep for passwords, tokens, API keys, private IPs,
  home directories, personal emails, real phone patterns
git log --all --name-only | grep -Ei '\.db|secret|\.venv|\.apk|keystore'   -> clean
fresh clone -> .bat is CRLF, .py is LF, .db/.env ignored, app imports
all 8 screenshots re-read visually -> non-routable numbers confirmed
e2e suite after console changes -> 73 passed, 0 failed
```
