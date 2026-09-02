# Automated Pre- and Post-Rental Car Damage Inspection

Full-stack prototype for the MSc dissertation *"Developing a Deep Learning-Based
Computer Vision Framework for Automated Pre- and Post-Rental Passenger Car
Damage Inspection"* (CB016792, APIIT).

A **Python/FastAPI** backend serves damage inference, inspection records and
evidentiary PDF reporting to an **Angular 17** staff dashboard.

---

## Quick start

Two terminals — one per half of the system.

**macOS / Linux**
```bash
./run-backend.sh     # http://localhost:8000  (API docs at /docs)
./run-frontend.sh    # http://localhost:4200
```

**Windows** (double-click, or from Command Prompt)
```bat
run-backend.bat
run-frontend.bat
```

Each script creates its own environment on first run, and **frees its port
before starting** — a server left running in another window is stopped
automatically instead of causing "address already in use".

Then open **http://localhost:4200** and sign in with either seeded account:

| Email | Password | Role |
|---|---|---|
| `admin@drivetime.lk` | `ChangeMe123!` | Administrator |
| `inspector@drivetime.lk` | `Inspector123!` | Inspector |

Five fleet vehicles are seeded automatically. To fill the system with rentals
built from **real damage photographs**, run the seeder (see
[step 5](#5-load-the-demo-with-real-damage-photographs)):

```bash
cd backend && .venv/bin/python seed_demo.py --reset
```

It pairs a handover photograph with a return photograph carrying additional
damage, so the comparison screen has genuine new damage to find, and writes the
dataset's ground-truth labels into each inspection's notes — which turns the
dashboard itself into a spot-check of the model.

---

## What it does

1. **Register fleet vehicles** — registration is normalised and used as the key.
2. **Open an inspection** — pre-rental or post-rental, tagged with a rental
   reference that pairs the two halves.
3. **Upload walk-around photographs** — validated, hashed (SHA-256),
   thumbnailed, and scored per damage class.
4. **Read the findings** — each class shown against *its own* F1-optimised
   threshold, with a severity hint and the class's test-set F1 so a reader can
   weigh it.
5. **Compare pre against post** — the core deliverable: which damage is **new
   this rental**, which was **pre-existing**, which is **no longer detected**.
6. **Export a PDF** — for the rental file or a damage dispute.

### Damage taxonomy and measured accuracy

The six CarDD classes (Wang et al., 2023). These figures are **measured**, not
transcribed — produced by `training/evaluate.py` over 643 held-out images (269 of them undamaged), through the same code path the API uses:

| Class | Threshold | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| dent | 0.687 | 0.809 | 0.834 | 0.821 | 0.962 |
| scratch | 0.641 | 0.750 | 0.885 | 0.812 | 0.954 |
| crack | 0.883 | 0.579 | 0.458 | 0.512 | 0.923 |
| glass_shatter | 0.955 | 1.000 | 0.915 | 0.956 | 0.987 |
| lamp_broken | 0.788 | 0.658 | 0.769 | 0.709 | 0.961 |
| tire_flat | 0.539 | 0.789 | 0.968 | 0.870 | 0.995 |
| **macro** | — | **0.764** | **0.805** | **0.780** | **0.964** |

**Damaged vs clean 0.992** · **false alarms 0/269 (0.0%)** · exact match 0.743 · 213 ms mean latency.

Each class is reported positive only above its own F1-optimised threshold — a
single flat 0.5 measurably underperforms on the rarer classes. The backend owns
this table and serves it at `GET /api/v1/damage-classes`, so the dashboard can
never drift from the model.

Re-run the evaluation and this table is regenerated; the PDFs read the same
`evaluation.json`.

---

## Architecture

```
┌────────────────────────┐   HTTPS/JSON    ┌──────────────────────────────────┐
│  Angular 17 dashboard  │ ──────────────► │  FastAPI backend                 │
│  standalone components │ ◄────────────── │                                  │
│  signals, lazy routes  │   JWT bearer    │  ├── api/v1     REST + OpenAPI   │
└────────────────────────┘                 │  ├── services  storage, analysis,│
                                           │  │              comparison, PDF  │
                                           │  ├── ml        Predictor ABC ────┼──┐
                                           │  └── models    SQLAlchemy ORM    │  │
                                           └───────────────┬──────────────────┘  │
                                                           │                     │
                                            ┌──────────────┴──────┐   ┌──────────┴────────┐
                                            │ SQLite (→ Postgres) │   │ mock │ classifier │
                                            │ storage/ (→ Blob)   │   │      │ detector   │
                                            └─────────────────────┘   └───────────────────┘
```

### Deviation from the proposal, and why

The proposal (Section 3.7) specifies a **.NET 8 Web API** between the Angular
client and a **FastAPI inference microservice**. This implementation collapses
those two tiers into one Python service.

The architectural argument in Section 2.6 rests on Sculley et al. (2015): keep
the model from becoming *entangled* with the surrounding application. That
isolation is preserved here — and arguably more cleanly. Inference sits behind
the `Predictor` abstract base class in `app/ml/base.py`, and nothing outside
`app/ml/` knows whether a prediction came from a mock, an EfficientNet
classifier or a YOLOv8 detector. Swapping the backend is a config change.

What is removed is a network hop and a language boundary that bought no
isolation the ABC does not already provide. What is lost is the .NET/Angular
integration pattern named in research sub-question 3 — worth stating explicitly
in the dissertation as a deliberate scope decision rather than leaving the
reader to notice it.

Other proposal choices deferred for the prototype, all swappable behind one
module each:

| Proposal | Here | Swap point |
|---|---|---|
| SQL Server + EF Core | SQLite + SQLAlchemy | `DATABASE_URL` — no model changes needed |
| Azure Blob Storage | Local filesystem | `app/services/storage.py` |
| YOLOv8 (boxes) | EfficientNet-B3 (image-level) | `app/ml/detector.py`, already written |

---

## The model gap, honestly stated

Your proposal promises **YOLOv8 object detection** with localised bounding
boxes. Your notebook delivers an **EfficientNet-B3 multi-label classifier** with
image-level scores. These are different tasks and the dissertation will need to
account for the difference.

This codebase is built so that gap costs nothing to close:

- `Detection` rows carry four nullable bbox columns from day one.
- The API returns `bbox: null` for classifier results and a normalised box for
  detector results — **the same response shape either way**.
- `AnnotatedImageComponent` already draws boxes when `bbox` is present and
  degrades to corner labels when it is not.

Drop a YOLOv8 checkpoint at `backend/models/yolov8_damage.pt`, install
`ultralytics`, restart — the dashboard starts drawing localised damage. No
schema migration, no API version bump, no frontend change.

### A bug found in the notebook

Cell 51 intends to unfreeze the last three EfficientNet blocks:

```python
if 'feature.6' in name or 'feature.7' in name or 'feature.8' in name:
    param.requires_grad = True
```

torchvision names these modules `features.6`, not `feature.6` — **the condition
never matches**. The notebook's own output confirms it: 790,022 trainable
parameters, which is exactly the new classifier head
(1536×512 + 512 + 512×6 + 6) and nothing else. The entire backbone stayed
frozen, so no fine-tuning of the visual features actually took place, and the
reported metrics are those of a linear probe on frozen ImageNet features.

This is most likely why `crack` scored so poorly (F1 0.47, AP 0.37): cracks are
the class most dependent on adapting low-level texture features, which is
precisely what was never trained.

`backend/training/train_classifier.py` fixes this (it matches on `features.{i}.`)
and is otherwise a faithful port. **Retraining with the fix should raise your
numbers**, and the before/after is a genuine result worth reporting in Chapter 4
rather than a mistake to bury — run `training/evaluate.py` against each
checkpoint to get a like-for-like comparison on the same held-out split.

---

## The model: train, verify, use

The whole point of the project is the model, so the pipeline to produce and
*verify* one is part of the repo rather than a notebook you have to babysit.

### 1. Get the dataset

```bash
cd backend
.venv/bin/pip install -r requirements-ml.txt     # torch, torchvision, scikit-learn
.venv/bin/python training/download_dataset.py
```

Pulls **CarDD** (Wang et al., 2023) — the dataset named in the proposal — from
its public Apache-2.0 mirror on Hugging Face, in the same COCO layout the
notebook used: `annotations/instances_{train,val,test}2017.json` plus the image
folders. Images are downscaled to a 640 px long edge on the way in (the model
trains at 224², so nothing is lost) which cuts ~3 GB to ~300 MB and makes each
epoch noticeably faster.

### 1b. Add undamaged cars — do not skip

**CarDD contains no undamaged vehicles.** All 4,000 images show damage, so a
model trained on it alone never sees a clean car and cannot answer "no damage" —
it returns whichever class clears its threshold first. Measured, a model trained
without this step raised false alarms on **88.5% of clean cars**.

```bash
mkdir -p data/negatives_raw
curl -L -o data/negatives_raw/part0.parquet \
  "https://huggingface.co/datasets/Multimodal-Fatima/StanfordCars_test/resolve/main/data/test-00000-of-00003-18db3ba1d2223f87.parquet"
.venv/bin/python training/extract_negatives.py
```

2,681 photographs of ordinary vehicles, added with an all-zero label and split
70/20/10 like CarDD itself, so the false-alarm rate is measured on clean cars the
model never saw. Training and evaluation pick the folder up automatically, and
both warn if it is missing.

### 2. Train

```bash
.venv/bin/python training/train_classifier.py \
    --data-root data/CarDD_COCO --epochs 20 --patience 5
```

EfficientNet-B3, ImageNet-pretrained, last three blocks plus a new head
unfrozen, `BCEWithLogitsLoss` with class-balanced positive weights, cosine LR
schedule — the notebook's recipe, **with its unfreezing bug fixed** (see below).
Picks up CUDA, then Apple Silicon MPS, then CPU automatically. After training it
sweeps the precision-recall curve per class to find F1-optimal thresholds and
writes them into the checkpoint, so serving uses the same cut-offs that were
tuned.

Two properties worth knowing:

- **The best checkpoint is written the moment it improves**, not at the end of
  the run. An interrupted run leaves a usable
  `car_damage_classifier.best.pth` rather than nothing.
- **Early stopping** (`--patience`, default 8) ends the run when validation
  stops improving, so over-requesting epochs costs nothing.

With the unfreezing bug fixed, 9.3M parameters converge in well under ten epochs
and then overfit — the notebook's 60 epochs made sense only while its backbone
was frozen and just 790k parameters had to converge.

Output: `models/car_damage_classifier.pth` (+ `car_damage_classifier.training.json`).

### 3½. Or do the whole switch-over in one command

```bash
cd backend && ./finalize_demo.sh
```

Promotes the best checkpoint, restarts the API on it, runs the held-out
verification, and re-seeds the demo so every inspection is scored by the real
model. Covers steps 3 and 4 below.

### 4. Verify

```bash
.venv/bin/python training/evaluate.py --data-root data/CarDD_COCO --report
```

This is the part that answers *"how do I know it actually works?"*. Two
properties make it a real check rather than a self-report:

- It loads the model **through `app.ml.get_predictor()`** — the exact object the
  API calls to answer a request. If preprocessing, thresholds or the checkpoint
  were wrong in the running service, they are wrong here too.
- It scores the **held-out test split only** — images never seen in training or
  validation — against CarDD's own annotations.

You get per-class precision / recall / F1 / AP / ROC-AUC, the raw TP-FP-FN
counts behind them, exact-match and any-damage accuracy, and latency
percentiles. It writes `models/evaluation.json`, and with `--report` a PDF
showing individual predictions beside the annotations — **including the
failures**, because a report that only showed successes would prove nothing.

The API serves the report at `GET /api/v1/model/evaluation`, and the dashboard
renders it under **Model** in the sidebar: headline metrics, a per-class table,
and a spot-check list with a "mistakes only" filter.

#### Checking it by hand

Metrics are one answer; feeding it photographs whose answer you already know is
the other. Generate an answer-key pack from the held-out split:

```bash
.venv/bin/python training/make_verify_pack.py
#  -> data/verify_samples/  (14 images + ANSWER_KEY.md)
```

Drag them into a new inspection and compare. Reference run: **caught the real
damage in 13 of 14; exactly right on all six classes in 7 of 14**. Near-misses
add an *extra* class rather than miss the real one — the safer direction for a
tool whose findings a human confirms.

Two more checks worth doing:

- **Reproducibility** — upload the same photograph twice; scores must be
  identical (they are, to four decimal places, with the same SHA-256). Without
  this no report could be defended.
- **The negative control** — the evaluation now includes held-out undamaged cars
  and reports an explicit **false-alarm rate**, shown on the Model page and
  coloured red above 15%. If that card is missing, clean cars were not tested —
  which is an unmeasured risk, not a pass. Also upload a photo of an undamaged
  car from your own fleet: your lighting is a harder test than any dataset.

> **How this check earned its place.** An early build scored macro F1 0.786 and
> looked excellent — then reported a dent on a pristine Ford Mustang. Measured
> properly it was raising false alarms on 88.5% of clean cars, and no existing
> metric could reveal it, because every test image contained damage.

### 5. Load the demo with real damage photographs

```bash
.venv/bin/python seed_demo.py --reset
```

Builds rentals out of **real CarDD photographs from the test split**, pairing a
pre-rental image with a post-rental image that carries additional damage, so the
comparison view has genuine new damage to find. Each inspection's notes record
the dataset's ground-truth labels, which turns the dashboard itself into a
spot-check: what the model said, next to what the annotation says.

If the dataset has not been downloaded, it falls back to generated placeholder
imagery and says so.

### Without weights

Everything still runs. The API falls back to a deterministic stub predictor, and
every screen and PDF is marked as non-evidential. That is a starting state, not
the destination.

## Layout

```
backend/
  app/
    api/v1/        auth, users, vehicles, inspections, images,
                   comparisons, dashboard, system
    core/          config, security (JWT/bcrypt), damage taxonomy
    db/            engine, session, schema creation + seeding
    ml/            base.py (Predictor ABC), mock, classifier, detector, registry
    models/        SQLAlchemy: User, Vehicle, Inspection, InspectionImage, Detection
    schemas/       Pydantic request/response contracts
    services/      storage, analysis, comparison, PDF reporting
  training/        notebook reproduction script
  tests/           20 tests covering auth, RBAC, upload, analysis, comparison, PDFs
frontend/
  src/app/
    core/          models, api/auth services, JWT interceptor, route guards
    features/      auth, dashboard, vehicles, inspections, comparison
    layout/        app shell
    shared/        confidence bar, damage chip, status badge, annotated image
docs/              architecture and API notes
```

## Documentation

| Document | Audience |
|---|---|
| [`docs/FEATURE_GUIDE.pdf`](docs/FEATURE_GUIDE.pdf) | **Non-technical users** — what the system does, and a 12-step test script with tick boxes. Start here if you just want to use it. |
| [`docs/USER_MANUAL.pdf`](docs/USER_MANUAL.pdf) | Whoever installs and runs it — setup, training the model, verification, troubleshooting |
| [`docs/TECH_STACK.pdf`](docs/TECH_STACK.pdf) | Technical readers and the dissertation — architecture, components, design decisions |
| `backend/models/evaluation.pdf` | Evidence — measured accuracy with individual predictions, including the failures |

All are generated from source; edit the generator and re-run rather than the
PDFs:

```bash
cd docs
../backend/.venv/bin/python build_docs.py           # manual + tech stack
../backend/.venv/bin/python build_feature_guide.py  # feature guide
```

The feature guide and tech-stack doc read `backend/models/evaluation.json`, so
they always quote the accuracy that was actually measured.

## Database migrations

Alembic is configured against the application's own settings and models, so a
migration can never be generated against a stale schema. The initial migration
is committed and verified to apply and roll back.

```bash
cd backend
.venv/bin/alembic upgrade head                        # apply
.venv/bin/alembic revision --autogenerate -m "note"   # after a model change
```

Day to day the app calls `create_all` at startup, which is why the prototype
needs no migration step to run.

## Tests

```bash
# Backend — 22 tests: auth, roles, upload validation, the full
# create/upload/analyse/report flow, analysis idempotency, comparison outcomes
cd backend && .venv/bin/python -m pytest tests -q

# Frontend — 17 tests: session persistence, the JWT interceptor, route guards
cd frontend && npm run test:ci

# Frontend production build
cd frontend && npx ng build
```

The frontend suite runs in headless Chrome. `test:ci` uses a no-sandbox launcher
so it also works in a container. What it protects:

| Area | Why it is worth a test |
|---|---|
| Session restore | A reload must not sign the user out mid-inspection. |
| Corrupt stored session | A bad `localStorage` entry must be discarded, not crash the app on boot. |
| Interceptor | The token must reach our API and **not** third-party URLs. |
| 401 handling | An expired token signs you out; a **mistyped password must not**, or a typo would look like a session expiry. |
| Guards | Signed-out users are redirected *and their destination remembered*; a non-admin goes to the dashboard, not the login page. |

## Configuration

Everything is environment-driven; see `backend/.env.example`. The settings that
matter most:

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | dev placeholder | **Change before any shared deployment.** |
| `DATABASE_URL` | `sqlite:///./data/app.db` | Postgres works unchanged |
| `PREDICTOR_BACKEND` | `auto` | `auto` degrades to mock; an explicit value never does |
| `CLASSIFIER_WEIGHTS` | `./models/car_damage_classifier.pth` | |
| `MAX_UPLOAD_MB` | `15` | |
| `SEED_DEMO_DATA` | `true` | Set `false` for a clean instance |

## Known limitations

- **Inference is synchronous.** Uploading many images blocks the request. On CPU
  with real weights that is roughly 0.3–1 s per image; a batch of twelve will
  feel slow. A task queue is the fix if the usability study exercises large
  batches.
- **`create_all` at startup, alongside migrations.** Alembic is configured with
  an initial migration, but the app still creates tables directly on boot for
  convenience. Delete `backend/data/app.db` to reset.
- **Local storage only.** Fine for a prototype; not durable or shared.
- **Severity is a heuristic**, derived from how far a score clears its
  threshold. The model has no severity supervision. Labelled as a hint
  everywhere it appears, including in PDFs.
- **No inter-image deduplication.** Photographing the same dent from four
  angles counts as four pieces of evidence for that class.
