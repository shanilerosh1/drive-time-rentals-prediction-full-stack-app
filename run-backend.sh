#!/usr/bin/env bash
# Start the FastAPI backend on http://localhost:8000
# Frees the port first, so a previous run left open does not block this one.
set -euo pipefail

PORT=8000
cd "$(dirname "$0")/backend"

# --- free the port ---------------------------------------------------------
PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  echo "Port $PORT is in use by PID(s): $PIDS - stopping them."
  # shellcheck disable=SC2086
  kill $PIDS 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    lsof -ti tcp:"$PORT" >/dev/null 2>&1 || break
    sleep 0.3
  done
  # Anything still holding the port after a polite request gets forced.
  STUBBORN="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
  if [ -n "$STUBBORN" ]; then
    # shellcheck disable=SC2086
    kill -9 $STUBBORN 2>/dev/null || true
    sleep 0.5
  fi
  echo "Port $PORT is free."
fi

# --- first-run setup -------------------------------------------------------
if [ ! -d .venv ]; then
  echo "Creating virtual environment (first run, this takes a minute)..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip --quiet
  .venv/bin/pip install -r requirements-dev.txt
fi

[ -f .env ] || cp .env.example .env

echo "Starting backend on http://localhost:$PORT  (API docs at /docs)"
exec .venv/bin/uvicorn app.main:app --reload --port "$PORT"
