#!/usr/bin/env bash
# Put the trained model into service and rebuild the demo around it.
#
#   ./finalize_demo.sh
#
# Steps: install the best checkpoint, restart the API on it, verify it against
# the held-out test split, then re-seed the demo so every inspection is scored
# by the real model.
set -euo pipefail
cd "$(dirname "$0")"

PY=.venv/bin/python
MODEL=models/car_damage_classifier.pth
INTERIM=models/car_damage_classifier.best.pth
PORT=8000

echo "=== 1. Install the checkpoint ==============================="
if [ -f "$MODEL" ]; then
  echo "  using $MODEL"
elif [ -f "$INTERIM" ]; then
  # Training saves its best epoch continuously; usable before the run ends.
  cp "$INTERIM" "$MODEL"
  echo "  promoted the best interim checkpoint to $MODEL"
else
  echo "  ERROR: no checkpoint found. Run training/train_classifier.py first." >&2
  exit 1
fi

echo
echo "=== 2. Restart the API on the trained model ================="
PIDS="$(lsof -ti tcp:$PORT 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  # shellcheck disable=SC2086
  kill $PIDS 2>/dev/null || true
  sleep 2
fi
nohup .venv/bin/uvicorn app.main:app --port $PORT > /tmp/cdi-backend.log 2>&1 &
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 1
done
BACKEND=$(curl -s "http://127.0.0.1:$PORT/api/v1/model" | $PY -c "import sys,json;d=json.load(sys.stdin);print(d['backend'],'real' if d['is_real'] else 'MOCK')")
echo "  API is up, serving: $BACKEND"

echo
echo "=== 3. Verify against the held-out test split ==============="
$PY training/evaluate.py --data-root data/CarDD_COCO --report

echo
echo "=== 4. Re-seed the demo with the trained model scoring ======"
$PY seed_demo.py --reset --rentals 6

echo
echo "=== Done ===================================================="
echo "  Dashboard : http://localhost:4200"
echo "  Sign in   : admin@drivetime.lk / ChangeMe123!"
echo "  Model page: sidebar -> Model  (measured accuracy)"
