# Contributing to Sentinel

Thanks for looking. This project has one rule that everything else follows from.

## The rule

**Sentinel is built to be visible to the person carrying the device.** A permanent notification, an
on-device consent screen, an honest one-tap stop. Pull requests that add hidden operation, message-app
interception, keylogging, remote camera or microphone access, call interception or recording, or
uninstall resistance **will be closed without review** — regardless of how well written they are.
See [`ROADMAP.md` §6.3](ROADMAP.md#6-the-covert-features) for the complete list and why.

That is not a moral flourish; it is the product's entire legal basis and the reason a parent can put
it on a phone without a lawyer.

## Before you start

| Document | What it covers |
|---|---|
| [`README.md`](README.md) | Architecture, quick start, API surface |
| [`ROADMAP.md`](ROADMAP.md) | The 5-phase plan and where work is needed |
| [`MISSING-FEATURES.md`](MISSING-FEATURES.md) | Every known gap, prioritised — **pick from here** |
| [`docs/LEGAL.md`](docs/LEGAL.md) | Jurisdictional position |
| [`TUTORIAL.html`](TUTORIAL.html) | End-user guide |

The most useful contributions right now are the P0 and P1 items in `MISSING-FEATURES.md` — particularly
getting the Android project to compile (item 1.1) and push notifications (item 2.1).

## Development setup

```bash
git clone https://github.com/valentinerio88vr-coder/sentinel.git
cd sentinel

# Server
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate          # Windows: ..\.venv\Scripts\activate
pip install -r requirements.txt
export SENTINEL_SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>, create an account, then load demo data:

```bash
python3 tools/seed_demo.py
```

## Before opening a pull request

Run the suite. It must pass — 73 checks against a live server:

```bash
python3 tools/e2e_test.py
# → 73 passed, 0 failed
```

If you touched the console, check it renders without console errors in a real browser. If you touched
the schema, add a migration file in `backend/app/migrations/` rather than editing an existing one —
existing databases must upgrade in place.

## Code conventions

**Python** — stdlib first. The backend deliberately has four dependencies; adding a fifth needs a
reason in the PR description. Parameterised SQL only, no exceptions. Comments explain *why*, not what.

**Kotlin** — keep the agent auditable. No obfuscation, no reflection tricks, no dynamic code loading.

**Console** — `web/index.html` is a single file with no build step on purpose (it must work when
served straight from the API). Keep it that way unless there's a strong argument otherwise. Escape
every interpolation with `esc()`.

**Commits** — imperative mood, one logical change each:

```
Add mipmap launcher icons so the Android build succeeds
Fix ago() treating a duration as an epoch timestamp
```

## Reporting a security issue

Don't open a public issue. Email the maintainer, or use GitHub's private vulnerability reporting.
Anything that leaks monitored data, bypasses consent, or defeats the kill switch is treated as
critical.

## What "done" means here

Every item in `ROADMAP.md` has explicit exit criteria. "It works on my machine" is not done;
"the criteria in the phase table are met and the test suite passes" is.
