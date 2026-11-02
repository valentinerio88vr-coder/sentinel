# Pushing Sentinel to GitHub

The repository is **committed and ready** — 57 files, one clean commit on `main`, nothing secret
included. The only step left is the push, which needs your GitHub credentials.

**Target:** https://github.com/valentinerio88vr-coder/sentinel.git

---

## Option 1 — Push from this workspace (fastest)

Open a terminal in the workspace and run:

```bash
cd sentinel
git remote add origin https://github.com/valentinerio88vr-coder/sentinel.git
git push -u origin main
```

When prompted:
- **Username:** `valentinerio88vr-coder`
- **Password:** a **Personal Access Token**, not your account password

### Creating the token

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token (classic)**
3. Scope: tick **`repo`** only. Nothing else is needed.
4. Expiry: 30 days is sensible for a one-off push.
5. Copy it immediately — GitHub shows it once.

Paste that token when git asks for the password.

> **Security note:** a PAT is a password for your account. Don't paste it into chat, a commit, or a
> file in this repo. If it leaks, revoke it at the same page immediately.

---

## Option 2 — Download and push from your own machine (safest)

If you'd rather not put a token into this environment:

1. Download the `sentinel/` folder from the workspace.
2. On your machine:

```bash
cd sentinel
git remote add origin https://github.com/valentinerio88vr-coder/sentinel.git
git push -u origin main
```

The `.git` directory is included, so the commit history comes with it. If it doesn't survive the
download, re-init:

```bash
git init
git add -A
git commit -m "Sentinel v2.0.0 — self-hosted child-safety monitoring"
git branch -M main
git remote add origin https://github.com/valentinerio88vr-coder/sentinel.git
git push -u origin main
```

The included `.gitignore` prevents the database, signing key, venv and build outputs from being
committed, so re-initialising is safe.

---

## Option 3 — GitHub Desktop / web upload

1. **GitHub Desktop** → File → Add local repository → select the `sentinel` folder → **Publish**.
2. Or on github.com, create an empty repo (no README, no .gitignore — this project already has both),
   then **Add file → Upload files** and drag the folder contents in.

---

## If the remote already has commits

The repository may have been initialised with a README. If the push is rejected:

```bash
git pull --rebase origin main    # replay your commit on top
git push -u origin main
```

If you'd rather overwrite whatever is there:

```bash
git push -u origin main --force
```

`--force` destroys remote history. Only do this if the remote is empty or you know what's in it.

---

## After pushing — recommended repository settings

| Setting | Value | Why |
|---|---|---|
| **Description** | `Self-hosted, consent-based safety monitoring for your own children's phones` | It's what the project actually is |
| **Topics** | `parental-control` `self-hosted` `android` `fastapi` `child-safety` `privacy` | Discoverability |
| **Issues** | On | The backlog in `MISSING-FEATURES.md` maps well to issues |
| **Private vulnerability reporting** | On (Settings → Code security) | `SECURITY.md` points to it |
| **Dependabot alerts** | On | You have 4 dependencies; worth watching |
| **Pages** | Optional — serve `TUTORIAL.html` | It's self-contained, so it works as-is |
| **License** | Detected automatically from `LICENSE` | MIT with an intended-use notice |

### Suggested issues to open from the backlog

Copy these in as the first issues, so the roadmap is visible to anyone who lands on the repo:

- [ ] **P0:** Add missing `mipmap` launcher icons — the Android build currently fails (1.1)
- [ ] **P0:** Push notifications — alerts require an open browser tab (2.1)
- [ ] **P0:** Report consent withdrawal to the server before wiping local state (1.9 / 6.1)
- [ ] **P0:** HTTPS + rate limiting before any real deployment (3.1, 3.2)
- [ ] **P1:** Enforce screen-time and app-blocking policy on-device (1.3)

---

## What was cleaned before committing

Things that would have caused problems, fixed before the first commit:

| Issue | Fix |
|---|---|
| `.bat` files were LF — cmd.exe mis-parses `goto` labels with LF endings | Converted to CRLF, and `.gitattributes` now enforces it on every clone |
| SQLite database, `-wal` and `-shm` files present | Excluded via `.gitignore`; nothing under `backend/data/` is tracked |
| Signing key `data/secret.key` | Ignored — never committed, never should be |
| Demo data used plausible-looking Indian mobile numbers | Replaced with the non-routable `+91 00000 000XX` range |
| No licence, no contribution guide, no security policy | Added `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` |
| `.venv`, `__pycache__`, APK, keystore paths | Ignored |

**Verified after committing:** a fresh `git clone` gives CRLF `.bat` files and LF Python, ignores
`.db`/`.env`/`local.properties`, and the app imports cleanly. Tested, not assumed.

---

## Caveats worth knowing

- **`.git/config` is not included** in the workspace snapshot (credential paths are excluded for
  security). Your `git remote` will need adding — the command above does that.
- **The Android app has never been compiled.** There is no `gradlew` wrapper committed yet and no
  `mipmap` icons, so a clone will fail `assembleDebug` until item 1.1 is done. That's transparently
  documented in `README.md`, `MISSING-FEATURES.md` and `TUTORIAL.html` — don't be surprised by it,
  and don't let a contributor be either.
- **No CI yet.** Item 8.2 in the backlog adds a GitHub Actions workflow that runs the 73 tests and
  `assembleDebug` on every push.
