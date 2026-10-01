# API

Base URL: `http://localhost:8000` (default `uvicorn` dev server). All endpoints are under
`/api`. FastAPI auto-generates interactive docs at `/docs` when the server is running.

## Analysis

### `POST /api/analyze`
Primary endpoint — full pipeline in one call. `multipart/form-data`, field `file` (JPEG/PNG/WebP, ≤15MB).

Response: `AnalysisResult` (see `backend/app/schemas/analysis.py`). Key shape:
```json
{
  "analysis_id": "an_...",
  "timestamp": "2026-...",
  "status": "OK",
  "quality": {"status": "GOOD", "score": 0.91, "reasons": []},
  "halo": {"detected": true, "inner_radius": 62.0, "outer_radius": 118.0, "halo_width": 56.0,
           "circularity": 0.9, "symmetry_score": 0.87, "confidence": 0.81, "messages": []},
  "spreading": {"spread_radius_normalized": 0.78, "spread_area_normalized": 0.55,
                "central_stain_area_normalized": 0.11, "outer_diffusion_area_normalized": 0.44,
                "diffusion_index": 0.63, "directional_variance": 0.09},
  "classification": {
    "research_classification": "csf_like",
    "confidence": 0.64,
    "class_probabilities": {"csf_like": 0.64, "saline_like": 0.24, "saliva_like": 0.07, "other": 0.05},
    "uncertain": false,
    "disagreement": 0.11,
    "model_version": "demo-synthetic-v1",
    "synthetic_training_data": true
  },
  "explainability": {"top_features": [{"feature": "spread_radius_normalized", "shap_value": 0.42}, "..."]},
  "visualizations": {"overlay_png_base64": "...", "radial_profile_png_base64": "...",
                      "probability_chart_png_base64": "...", "feature_importance_png_base64": "..."},
  "decision_support": {
    "message": "Pattern is compatible with a CSF-like halo pattern. Image analysis alone cannot confirm or exclude CSF — this is a research decision-support result, not a diagnosis.",
    "recommend_lab_confirmation": true,
    "disclaimer": "AI image analysis is a decision-support screening tool and is NOT a medical diagnosis or confirmation of CSF. ..."
  }
}
```
`status` is one of `OK`, `RECAPTURE_NEEDED` (quality gate failed — no further fields
populated), `NO_HALO_DETECTED` (halo gate failed — `classification`/`explainability` absent).

**There is no field called `diagnosis` anywhere in this API, by design** — see
`docs/validation.md` and the project's medical-safety constraint. Use
`research_classification`.

### `POST /api/quality-check`
Same upload contract, returns just the `QualityAssessment` fields. Used by the Flutter
preview screen to warn before committing to a full analysis.

### `POST /api/detect-halo`, `POST /api/extract-features`, `POST /api/classify`
Granular, single-stage versions of the pipeline (debugging/research-mode inspection). Each
reruns the pipeline up to that stage independently — `/api/analyze` is the efficient,
primary path and is what the app actually uses.

### `GET /api/analysis/{analysis_id}`
Returns the stored `AnalysisResult` JSON for a past analysis, or 404.

### `GET /api/history?limit=50`
Returns a list of `{analysis_id, timestamp, quality_status, research_classification,
confidence, uncertain}` — no images, no PII.

### `GET /api/model-info`
Returns model version, classes, training timestamp, and the full metrics report (see
`docs/validation.md`). 503 if no model has been trained yet.

### `GET /api/health`
`{"status": "ok", "model_version": "...", "model_loaded": true|false}`.

## Research mode (`/api/research/*`, spec Page 8 — not a clinical interface)

**Authentication**: every `/api/research/*` endpoint requires an `X-API-Key` header
matching the `HALO_RESEARCH_API_KEY` environment variable, since these endpoints can
retrain the live model. If that env var is unset (the local-dev default), the endpoints
are open and the server logs a one-time startup warning — set it before exposing this
service beyond localhost:
```
export HALO_RESEARCH_API_KEY=some-long-random-value   # or set in backend/.env
curl -X POST http://localhost:8000/api/research/train -H "X-API-Key: some-long-random-value"
```

### `POST /api/research/upload-dataset?sessions_per_class=40`
No real labeled dataset exists yet (see `docs/dataset.md`); this (re)generates the
synthetic dataset. Will be replaced by an actual upload endpoint once real, ethically
sourced labeled data exists.

### `POST /api/research/train`
Trains + calibrates the ensemble on the synthetic training split, saves artifacts under
`backend/trained_models/`.

### `POST /api/research/evaluate`
Evaluates the trained ensemble on the synthetic test split, writes the metrics into
`trained_models/metadata.json`, and returns the full report.
