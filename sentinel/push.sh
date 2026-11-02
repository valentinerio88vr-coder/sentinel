#!/usr/bin/env bash
# Push Sentinel to GitHub.
#
# Prompts for a Personal Access Token without echoing it, sets the remote, and pushes.
# The token is used for this one command only — it is never written to disk, never
# stored in .git/config, and never appears in shell history.
#
#   ./push.sh
#
# Get a token: GitHub -> Settings -> Developer settings -> Personal access tokens
#              -> Tokens (classic) -> Generate new token -> tick "repo" only.
set -uo pipefail
cd "$(dirname "$0")"

REMOTE_URL="${1:-https://github.com/valentinerio88vr-coder/sentinel.git}"
USER_NAME="valentinerio88vr-coder"
BRANCH="$(git branch --show-current 2>/dev/null || echo main)"

echo
echo "  Sentinel -> GitHub"
echo "  ------------------"
echo "  Remote: $REMOTE_URL"
echo "  Branch: $BRANCH"
echo "  Commits to push: $(git rev-list --count HEAD 2>/dev/null || echo 0)"
echo

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "  [X] Not a git repository. Run this from inside the sentinel folder."
  exit 1
fi

if [ -z "$(git log --oneline -1 2>/dev/null)" ]; then
  echo "  [X] No commits yet."
  exit 1
fi

# Safety: refuse if anything secret is tracked.
LEAKS="$(git ls-files | grep -iE '\.db$|secret\.key|\.venv/|\.apk$|\.keystore$|(^|/)\.env$' || true)"
if [ -n "$LEAKS" ]; then
  echo "  [X] Refusing to push — these files are tracked and must not be public:"
  echo "$LEAKS" | sed 's/^/        /'
  echo "      Run: git rm --cached <file>  then re-commit."
  exit 1
fi
echo "  [1/3] No secrets tracked"

git remote remove origin >/dev/null 2>&1
git remote add origin "$REMOTE_URL"
echo "  [2/3] Remote configured"

PUSH_STATUS=1

if [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "  [3/3] Using GITHUB_TOKEN from the environment"
  PUSH_URL="https://${USER_NAME}:${GITHUB_TOKEN}@github.com/valentinerio88vr-coder/sentinel.git"
  git -c credential.helper= push "$PUSH_URL" "$BRANCH" 2>&1 | sed "s|${GITHUB_TOKEN}|***|g"
  PUSH_STATUS="${PIPESTATUS[0]}"
else
  echo
  echo "  Paste your Personal Access Token below (input is hidden)."
  echo "  Leave blank to abort."
  echo
  printf "  Token: "
  read -rs TOKEN
  echo
  if [ -z "$TOKEN" ]; then
    echo "  Aborted. No token entered."
    exit 1
  fi
  PUSH_URL="https://${USER_NAME}:${TOKEN}@github.com/valentinerio88vr-coder/sentinel.git"
  # -c credential.helper= stops git from caching the token on disk.
  git -c credential.helper= push "$PUSH_URL" "$BRANCH" 2>&1 | sed "s|${TOKEN}|***|g"
  PUSH_STATUS="${PIPESTATUS[0]}"
  unset TOKEN
fi

# Only report success if git actually exited 0 — a failed push must never look like a win.
if [ "$PUSH_STATUS" -ne 0 ]; then
  echo
  echo "  [X] Push failed (git exit $PUSH_STATUS). Nothing was published."
  echo "      Common causes:"
  echo "        - token lacks the 'repo' scope"
  echo "        - token expired or was revoked"
  echo "        - the repository does not exist yet (create it first, empty)"
  echo "        - the repo already has commits, so this is not a fast-forward:"
  echo "            git fetch origin && git rebase origin/$BRANCH && ./push.sh"
  exit "$PUSH_STATUS"
fi

git branch --set-upstream-to="origin/$BRANCH" "$BRANCH" >/dev/null 2>&1
echo
echo "  Done — pushed $(git rev-list --count HEAD) commits to https://github.com/valentinerio88vr-coder/sentinel"
