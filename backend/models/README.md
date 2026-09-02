# Model weights and evaluation

The API detects a checkpoint here at startup and switches off the placeholder
predictor automatically — no code or config change needed.

## What is in here

| File | What it is |
|---|---|
| `car_damage_classifier.pth` | The model in service. EfficientNet-B3, six damage classes, per-class thresholds baked in. |
| `car_damage_classifier.training.json` | How it was trained: epochs run, best epoch, device, loss history. |
| `evaluation.json` | Measured performance on the held-out test split. Served at `GET /api/v1/model/evaluation` and rendered on the dashboard's **Model** page. |
| `evaluation.pdf` | The same, as a report with individual predictions — including the failures. |
| `backup_positives_only/` | The earlier checkpoint trained **without** undamaged cars, kept for comparison. It raised false alarms on 88.5% of clean cars; see below. |

## Regenerating all of it

```bash
cd backend
.venv/bin/pip install -r requirements-ml.txt
.venv/bin/python training/download_dataset.py      # damaged cars (CarDD)
# undamaged cars — see USER_MANUAL.pdf §7b for the curl command
.venv/bin/python training/extract_negatives.py
.venv/bin/python training/train_classifier.py \
    --data-root data/CarDD_COCO --epochs 20 --patience 5
./finalize_demo.sh                                 # install, restart, verify, re-seed
```

## Why the negatives matter

CarDD contains **no undamaged vehicles** — all 4,000 images show damage. Trained
on it alone, the model has no representation of "no damage" and returns whichever
class clears its threshold first when shown a clean car.

Measured on 269 held-out clean cars:

| | Without negatives | With negatives |
|---|---|---|
| False alarms on clean cars | 238/269 (**88.5%**) | 0/269 (**0.0%**) |
| Damaged vs clean accuracy | 0.622 | **0.992** |
| Macro F1 | 0.677 | **0.780** |

`training/extract_negatives.py` is not optional. Both the training and evaluation
scripts warn if the `negatives/` folder is missing, and the evaluation refuses to
describe its headline figure as "damaged versus clean" without them.

## Backend selection

With `PREDICTOR_BACKEND=auto` (the default): **detector → classifier → mock**,
first one that loads wins.

| File | Backend | Produces |
|---|---|---|
| `car_damage_classifier.pth` | `classifier` | Image-level class scores |
| `yolov8_damage.pt` | `detector` | Class scores **with bounding boxes** (Phase 2) |

Check what is live at any time: `GET /api/v1/model`.

## Rolling back

```bash
cp models/backup_positives_only/car_damage_classifier.pth models/
# restart the backend
```
