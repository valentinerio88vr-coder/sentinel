#!/usr/bin/env bash
# Sentinel launcher (macOS / Linux). Same steps as run.bat.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${SENTINEL_PORT:-8000}"
URL="http://127.0.0.1:${PORT}"
VENV=".venv"
DATA="data"

echo
echo "  ############################################"
echo "  #   SENTINEL - Family Safety Console       #"
echo "  ############################################"
echo

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "  [X] python3 not found. Install Python 3.10+ and try again."
  exit 1
fi
echo "  [1/5] $($PYTHON --version)"

if [ -x "$VENV/bin/python" ]; then
  echo "  [2/5] Virtual environment ready"
else
  echo "  [2/5] Creating virtual environment (first run only)..."
  "$PYTHON" -m venv "$VENV"
fi
PY="$VENV/bin/python"

if [ -f "$VENV/.deps-ok" ]; then
  echo "  [3/5] Dependencies already installed"
else
  echo "  [3/5] Installing dependencies (needs internet, one time)..."
  "$PY" -m pip install --upgrade pip --quiet --disable-pip-version-check
  "$PY" -m pip install -r backend/requirements.txt --quiet --disable-pip-version-check
  touch "$VENV/.deps-ok"
fi

mkdir -p "$DATA"
if [ ! -f "$DATA/secret.key" ]; then
  echo "  [4/5] Generating a persistent signing secret..."
  "$PY" -c "import secrets;print(secrets.token_hex(32))" > "$DATA/secret.key"
else
  echo "  [4/5] Using existing signing secret"
fi
SENTINEL_SECRET="$(cat "$DATA/secret.key")"
export SENTINEL_SECRET

echo "  [5/5] Starting on ${URL}"
echo
echo "  Press Ctrl+C to stop."
echo

( sleep 3; (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true ) &

cd backend
exec "$OLDPWD/$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level info
