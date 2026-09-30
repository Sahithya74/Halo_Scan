# Algorithms

Only algorithms actually used are listed — see docs/dataset.md and architecture.md for
what was deliberately left out (CNN/U-Net/Grad-CAM) and why.

## Computer vision (`backend/app/image_processing/`)

| Algorithm | Where | Purpose |
|---|---|---|
| Laplacian variance | `quality.py` | Blur detection |
| Gaussian blur | `preprocessing.py` | Noise reduction before thresholding/edges |
| Adaptive threshold (Gaussian) | `roi_detection.py` | Segment sample pad from background under uneven lighting |
| Otsu threshold | `halo_detection.py` (`_segmentation_estimate`) | Split central stain from surrounding pad |
| Morphological open/close | `roi_detection.py`, `halo_detection.py` | Clean up thresholded masks |
| Contour detection + `minEnclosingCircle` | `roi_detection.py`, `halo_detection.py` | Fit circular regions to detected blobs |
| Canny edge detection | `halo_detection.py` (`_edge_circle_estimate`) | Independent ring-boundary estimate from edges |
| Hough Circle Transform | `roi_detection.py`, `halo_detection.py` | Independent ring/ROI estimate |
| Cartesian→polar transform (`cv2.warpPolar`) | `preprocessing.py` → `halo_detection.py` | Turns radial ring structure into a simple 1D profile |
| Radial intensity profiling + peak detection (`scipy.signal.find_peaks`, Savitzky-Golay smoothing) | `halo_detection.py` | Finds inner/outer ring transitions from I(r) |

Halo detection deliberately combines all of the above (spec section 7, Methods A-E) and
takes the median across whichever methods succeed, rather than trusting one algorithm —
see `HaloDetectionResult.method_agreement` for the per-method raw estimates.

## Feature engineering (`backend/app/feature_engineering/`)

- **Geometry**: radii, ring width/ratio, circularity, symmetry, center displacement.
- **Intensity**: per-region (center/ring/background) mean/median/std/gradient.
- **Radial**: derived from the I(r) profile — peak position, slope, uniformity, range,
  transition count.
- **Color**: RGB/HSV/LAB per region (`scikit-image`/OpenCV color conversions).
- **Texture**: GLCM (`skimage.feature.graycomatrix/graycoprops`: contrast, homogeneity,
  energy, correlation) + Shannon entropy + Local Binary Pattern histogram entropy, computed
  on the ring region's bounding-box crop.
- **Spreading**: normalized (by detected sample-pad radius) spread radius/area, diffusion
  index, directional variance — `spreading_analysis/spreading.py`.

All of the above are assembled into one fixed-order feature vector
(`feature_engineering/feature_vector.py:FEATURE_COLUMNS`) — the single source of truth used
identically by training and inference.

## Machine learning (`backend/app/models/`)

- **Logistic Regression** (`sklearn.linear_model.LogisticRegression`, `class_weight="balanced"`) — linear baseline.
- **Random Forest** (`sklearn.ensemble.RandomForestClassifier`) — non-linear, and the one
  explained via SHAP TreeExplainer.
- **SVM** (`sklearn.svm.SVC`, RBF kernel, `probability=True`) — margin-based.
- XGBoost/LightGBM were **not** used — see `backend/requirements.txt` comment: native build
  friction on Windows for marginal gain over sklearn's own ensembles at this dataset scale.

### Ensemble

Weighted average of the three calibrated models' probabilities
(`models/ensemble.py:ensemble_predict`), plus a disagreement score (mean per-class
probability std across the three models) that feeds into uncertainty routing.

### Calibration

`sklearn.calibration.CalibratedClassifierCV` (isotonic regression, 5-fold internal CV) per
model. Reported alongside Brier score and Expected Calibration Error
(`models/calibration.py`) — see `docs/validation.md` for the actual numbers on the
synthetic test set.

### Uncertainty / out-of-distribution detection

Per-class Gaussian fit on training features + Mahalanobis distance
(`models/uncertainty.py`) flags samples that don't resemble any training class at all,
combined with low ensemble confidence and high model disagreement. Any one signal routes
the result to `uncertain: true`.

### Explainability

SHAP `TreeExplainer` on the Random Forest branch (`explainability/shap_explainer.py`) —
top-5 contributing features per prediction, rendered as a bar chart
(`services/visualization_service.py:plot_feature_importance`).

## What was deliberately not implemented, and why

- **CNN transfer learning / U-Net segmentation / Grad-CAM** — would need far more images
  per class than a procedurally generated set can meaningfully provide; a CNN trained on
  synthetic renders mostly learns the renderer's artifacts, not anything transferable. See
  `docs/dataset.md`.
- **XGBoost/LightGBM** — native-dependency install friction on Windows; sklearn's own
  ensemble models cover the same modeling need for this dataset size.
