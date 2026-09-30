# Halo Scan

A research/education decision-support prototype that analyzes a photo of a fluid-drop
halo/double-ring pattern (the classic gauze/filter-paper test for suspected CSF leaks) and
reports a research classification — **never a diagnosis**.

## Problem

The halo/double-ring sign is widely taught as a bedside indicator of CSF in bloody
drainage, but the clinical literature is clear that it is **not specific**: saline, tap
water, and normal nasal secretions mixed with blood can all produce the same visual
pattern (see `docs/dataset.md` for the sources). Beta-2 transferrin lab testing remains the
recognized specific confirmatory test. Any software that photographs this test has to make
that limitation structural, not a footnote.

## Proposed solution

A smartphone photo of the pad → a CV pipeline that detects and measures the ring pattern →
a calibrated ML ensemble that classifies it as CSF-like / saline-like / saliva-like / other
→ a decision-support message that always recommends lab confirmation rather than presenting
a label as a diagnosis. See `docs/architecture.md` for the full pipeline diagram.

## Status of this build

Software-only (hardware — phone stand, ring light, sample pad — deferred). Built and
verified in this pass:
- **Backend** (`backend/`): FastAPI + OpenCV + scikit-learn. Full pipeline implemented.
  Dependency installation was blocked in the dev environment by very slow network
  conditions — see `docs/validation.md` for reproduction steps and current status.
- **Flutter app** (`flutter_app/`): written as real Dart code but **unverified** — no
  Flutter SDK on the dev machine. See `flutter_app/README.md` before trusting it.
- **Dataset** (`backend/datasets/`, `docs/dataset.md`): no public dataset exists for this
  problem (confirmed by search); a procedural synthetic generator was built instead, with
  deliberately overlapping CSF-like/saline-like parameter distributions reflecting the
  real optical ambiguity, fully documented as synthetic/demo data.

## Hardware (future)

Smartphone + fixed stand + LED ring light + sample pad + optional macro lens. Not built in
this pass — the MVP only assumes a smartphone camera and controlled lighting.

## Software

- **Backend**: Python, FastAPI, OpenCV, NumPy, SciPy, scikit-image, scikit-learn, SHAP,
  Matplotlib, SQLite. See `backend/README.md`.
- **Mobile**: Flutter/Dart (unverified scaffold). See `flutter_app/README.md`.

## Architecture

See `docs/architecture.md`.

## AI pipeline / Algorithms

See `docs/algorithms.md` for the full list of CV algorithms, engineered features, and ML
models used, and what was deliberately left out (CNN/U-Net/Grad-CAM) and why.

## Dataset

See `docs/dataset.md` — the public-dataset search result, the literature grounding the
synthetic generator's parameters, and its limitations.

## Model

Ensemble of calibrated Logistic Regression / Random Forest / SVM on a hand-engineered
feature vector (geometry, intensity, radial profile, color, texture, spreading), with
Mahalanobis out-of-distribution detection and SHAP explainability. See `docs/algorithms.md`.

## API

See `docs/api.md`.

## Flutter app

See `flutter_app/README.md`.

## Security

- No PII stored — analysis history is keyed by random IDs only (`backend/app/services/storage_service.py`).
- Uploaded images are processed in-memory and not persisted to disk.
- Upload validation: content-type allowlist, 15MB size cap (`backend/app/api/routes_analysis.py`).
- CORS is wide-open (`allow_origins=["*"]`) for local development — tighten before any
  real deployment (`backend/app/main.py`).

## Limitations

This is a research/education prototype, not a medical device. See the disclaimer embedded
in every API response (`decision_support.disclaimer`) and `docs/dataset.md` /
`docs/validation.md` for the full scientific and dataset limitations.

## Installation

```
git clone <this repo>
cd Halo_Scan/backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Running the backend

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

## Training

```
cd backend
.venv/Scripts/python.exe ../scripts/generate_dataset.py
.venv/Scripts/python.exe ../scripts/train.py
.venv/Scripts/python.exe ../scripts/evaluate.py
```

## Testing

```
cd backend
.venv/Scripts/python.exe -m pytest -v
```

## Demo

```
cd backend
.venv/Scripts/python.exe ../scripts/predict.py path/to/image.png --save-overlay out.png
```
Runs the full pipeline on a single image and prints the JSON `AnalysisResult` — the
primary way to see the system work end-to-end without the (unverified) Flutter app.
