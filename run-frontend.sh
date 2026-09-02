#!/usr/bin/env bash
# Start the Angular dashboard on http://localhost:4200
# Frees the port first, so a previous run left open does not block this one.
set -euo pipefail

PORT=4200
cd "$(dirname "$0")/frontend"

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
  STUBBORN="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
  if [ -n "$STUBBORN" ]; then
    # shellcheck disable=SC2086
    kill -9 $STUBBORN 2>/dev/null || true
    sleep 0.5
  fi
  echo "Port $PORT is free."
fi

# --- first-run setup -------------------------------------------------------
if [ ! -d node_modules ]; then
  echo "Installing Angular dependencies (first run, this takes a few minutes)..."
  npm install
fi

echo "Starting frontend on http://localhost:$PORT"
exec npx ng serve --port "$PORT"
