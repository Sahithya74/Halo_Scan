# Halo Scan Backend

FastAPI + OpenCV + scikit-learn research/decision-support API for halo/double-ring
fluid-pattern image analysis. **Not a diagnostic system** — see `docs/dataset.md` and
`docs/architecture.md` at the project root for the full medical-safety framing.

## Setup

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

> If dependency installation is very slow in your environment: the heaviest packages are
> `opencv-python-headless`, `scipy`, `scikit-image`, `scikit-learn`, `pandas`, `matplotlib`,
> `shap`. Installing in smaller batches (e.g. `pip install fastapi pydantic-settings numpy`
> first, then the CV/ML packages) can help isolate which package is slow/failing.

## Generate the synthetic dataset, train, and evaluate

No real labeled dataset exists (see `docs/dataset.md`) — this generates one procedurally.

```
.venv/Scripts/python.exe ../scripts/generate_dataset.py
.venv/Scripts/python.exe ../scripts/train.py
.venv/Scripts/python.exe ../scripts/evaluate.py
```

## Run the API

```
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```
Then open `http://localhost:8000/docs` for interactive API docs, or:
```
curl http://localhost:8000/api/health
```

## Run a single image through the full pipeline without Flutter

```
.venv/Scripts/python.exe ../scripts/predict.py path/to/image.png --save-overlay out.png
```

## Tests

```
.venv/Scripts/python.exe -m pytest -v
```

## Layout

See `docs/architecture.md` at the project root for the full pipeline diagram. Short version:
`app/image_processing/` (quality/ROI/halo CV) → `app/feature_engineering/` (structured
feature vector) → `app/spreading_analysis/` → `app/models/` (classical ML ensemble +
calibration + uncertainty) → `app/explainability/` (SHAP) → `app/services/` (orchestration,
storage, visualization) → `app/api/` (FastAPI routes) → `app/main.py`.
