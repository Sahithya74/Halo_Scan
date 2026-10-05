# Architecture

## Scope of this build

Hardware (phone stand, ring light, sample pad, macro lens) is deferred — see the project
brief. This build is software-only: a FastAPI backend implementing the full CV/ML pipeline,
and a Flutter app scaffold (unverified — no Flutter SDK on the dev machine; see
`flutter_app/README.md`).

## Pipeline

```
Smartphone camera (Flutter, or any HTTP client / scripts/predict.py)
        |
        v
POST /api/analyze  (multipart image upload)
        |
        v
+-------------------------------------------------------------+
| app/services/analysis_service.py  (the pipeline's spine)    |
|                                                               |
|  1. quality.py         -- blur/brightness/contrast/exposure  |
|     -> POOR? stop here, return RECAPTURE_NEEDED              |
|  2. roi_detection.py   -- locate the sample pad/drop region   |
|  3. halo_detection.py  -- Canny + Hough + radial profile +    |
|                            polar transform + adaptive seg.    |
|     -> not detected? stop here, return NO_HALO_DETECTED       |
|  4. spreading.py       -- normalized spread/diffusion metrics |
|  5. feature_vector.py  -- geometry+intensity+radial+color+    |
|                            texture+spreading -> fixed-order   |
|                            feature row                        |
|  6. models/registry.py -- ensemble predict (LogReg/RF/SVM,    |
|                            each calibrated) + uncertainty      |
|                            (Mahalanobis OOD + disagreement)    |
|                            + SHAP top features                |
|  7. visualization_service.py -- overlay PNG, radial-intensity |
|                                   plot, probability chart,     |
|                                   SHAP bar chart (all base64)  |
|  8. decision_support message -- research_classification only, |
|                                   never "diagnosis"; always     |
|                                   carries the disclaimer        |
+-------------------------------------------------------------+
        |
        v
storage_service.py (SQLite, no PII) -- analysis history
        |
        v
AnalysisResult JSON -> Flutter (or curl / scripts/predict.py)
```

## Why a quality gate and a halo-detection gate, not just one classifier

Feeding a blurry/dark photo or a flat, ring-less image straight into a classifier produces
a confident-sounding but meaningless label. Both gates short-circuit the pipeline instead:
`RECAPTURE_NEEDED` (fix the photo) and `NO_HALO_DETECTED` (no pattern to classify — note
this does NOT rule out CSF, since a real leak can fail to produce a visible halo).

## Why an ensemble of classical models instead of one model, and no CNN yet

Random Forest, SVM, and Logistic Regression are trained on the same hand-engineered
feature vector and combined by weighted-probability ensembling. Disagreement between them
is itself a signal (`models/ensemble.py`) — if the three models substantially disagree,
the result is routed to `uncertain: true` rather than picking whichever one happens to win.

A CNN (transfer learning branch) was scoped out for this build: it would be trained on the
same procedurally-generated synthetic images, and a CNN's accuracy on synthetic renders is
not a meaningful number — it would mostly measure how well the CNN memorizes the renderer's
own visual artifacts. The feature-based classical pipeline is more interpretable (SHAP) and
its inputs (ring geometry, radial profile, color, texture) are the same measurements a human
reviewer would reason about, which matters more here than raw accuracy on fake data. See
`docs/dataset.md` for the full reasoning and the plan for adding a CNN once real images exist.

## Data flow and storage

- No image is stored server-side beyond the request lifecycle (uploads are processed
  in-memory; see `analysis_service.load_image_from_bytes`). Only the JSON result is
  persisted, in `backend/analysis_history.db` (SQLite), keyed by a random `analysis_id`.
  No names, device IDs, or other identifiers are stored (spec section 23).
- Visualizations (overlay, graphs) are generated per-request and returned as base64 PNG
  inside the JSON response — nothing written to disk.

## Future hardware/scale path (not built yet)

- A physical reference marker (known-size fiducial on the sample pad) would replace the
  current ROI-radius-based scale normalization in `spreading_analysis/spreading.py` with a
  more robust true-physical-units normalization.
- On-device inference: the classical models here are small (a few hundred KB each via
  joblib) and could be exported and run via a lightweight on-device runtime if the target
  moves off a server call; not implemented in this pass since a Python server round-trip
  is sufficient for the current research prototype.

## v2: roles, video and security

```
Browser (web_app/)                         FastAPI (backend/app)
  index.html  login (3 portals)  ──POST /api/auth/login──▶ security/passwords (Argon2id)
                                                          security/sessions (hashed tokens)
  clinician.html  camera / 10s rec ─POST /api/analyze───▶ security/rbac (role + CSRF)
                                                          ├─ photo → analysis_service.analyze_frame
                                                          └─ video → video_service (8 frames →
                                                             analyze_frame each → averaged)
                                                          comparison_service (class profiles)
                                                          storage_service ─ Fernet ─▶ SQLite
  admin.html   users / audit     ──/api/admin/*────────▶ security/audit (SHA-256 hash chain)
  patient.html own results       ──/api/me/*───────────▶ own patient_id only
```

- **One pipeline for photos and video.** `analyze_frame` is the single per-image step; a
  video is 8 sampled frames through it, with probabilities averaged and frame agreement /
  stability reported. Frame timestamps come from decoding (pass 1), not container metadata,
  because browser-recorded WebM is variable-frame-rate.
- **Data at rest.** `patients` stores name/MRN/DOB as Fernet ciphertext plus an HMAC blind
  index of the MRN for lookups; `analyses.result_json` is encrypted (older plaintext rows are
  encrypted at startup). Only the fields needed to list history are in the clear.
- **Least privilege.** Administrators run the system but get 403 on patient results;
  patients get 404 on anything not theirs, so record ids can't be probed.
