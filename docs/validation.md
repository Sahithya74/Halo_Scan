# Validation

**These are not clinical validation results.** Every number below comes from
`scripts/evaluate.py` run against the held-out `test` split of the **procedurally
generated synthetic dataset** described in `docs/dataset.md` (385 samples total, 128
sessions across 5 classes, split by session 70/15/15). They measure how well the pipeline
recovers known synthetic generation parameters — not how it would perform on real CSF,
saline, or saliva samples.

## Results (synthetic test split, n=47 classifier-eligible samples)

| Metric | Value |
|---|---|
| Accuracy | 0.745 |
| Macro precision | 0.737 |
| Macro recall | 0.753 |
| Macro F1 | 0.738 |
| Expected Calibration Error | 0.098 |
| Brier score | 0.091 |

Confusion matrix (rows = true, columns = predicted; order: csf_like, saline_like,
saliva_like, other):

```
                csf_like  saline_like  saliva_like  other
csf_like             5          4           0         0
saline_like          5          9           0         0
saliva_like          0          0           8         0
other                1          0           2        13
```

**This confusion matrix is the result the dataset design was built to produce**: csf_like
and saline_like are confused with each other almost evenly (5 of each misclassified as the
other), while saliva_like and other are both classified perfectly or near-perfectly. That
matches `docs/dataset.md`'s deliberately overlapping csf_like/saline_like parameter ranges,
which in turn reflect the real literature finding that these two are not visually
distinguishable. A model that could cleanly separate csf_like from saline_like on this
dataset would indicate a bug in the generator's overlap, not a good model.

### `csf_like`-specific (spec section 17 — the class the medical-safety framing cares about most)

| Metric | Value |
|---|---|
| Sensitivity | 0.556 |
| Specificity | 0.842 |
| PPV | 0.455 |
| NPV | 0.889 |

Per-class ROC-AUC: csf_like 0.836, saline_like 0.890, saliva_like 0.971, other 0.966.
Per-class PR-AUC: csf_like 0.414, saline_like 0.808, saliva_like 0.760, other 0.956.
csf_like's lower PR-AUC/PPV is the expected consequence of its overlap with saline_like,
not a defect to "fix" — see above.

### Halo-detection gate check (synthetic `invalid`/no-halo class, n=8)

Correctly rejected (NO_HALO_DETECTED, never reaches the classifier): **5/8 (62.5%)**,
up from an initial 50%. Investigated and partially fixed in this pass:

**Root cause #1 (fixed, generator-level):** `datasets/synthetic_generator.py`'s `invalid`
class used to render `inner_radius = outer_radius * 0.92` — an intentional-but-wrong ~8%
"fuzzy edge" width, which happened to exceed `halo_detection.py`'s own 5%-of-outer-radius
width threshold for calling something a ring. Fixed by setting `inner_radius = outer_radius`
exactly (a single soft-edged stain with no separate ring band at all). This alone improved
rejection from 50% to 62.5% with **zero effect on the classifier's metrics** (confirmed:
re-running training/evaluation after the fix reproduced the exact same confusion matrix,
ROC-AUC, and calibration numbers above, since the fix only touches the `invalid` class,
which the classifier never trains or evaluates on).

**Root cause #2 (diagnosed, not fixed — see below):** the remaining 3/8 false positives
all share the same pattern: `app/image_processing/halo_detection.py`'s Canny-edge and
Hough-circle methods contribute nothing (`None, None`) — and diagnosis against a sample of
genuine `csf_like` training images found this is actually true for **essentially all**
images this generator produces (soft `smoothstep`-blended gradients don't give Canny or
Hough the crisp edges they need), not just the `invalid` class. That leaves the radial-profile
and segmentation (Otsu + percentile) methods as the only two that ever contribute, and
`_segmentation_estimate`'s "inner stain" sub-threshold (darkest 25% of masked pixels) turns
out to be mostly a **geometric artifact**: for any region with a monotonically increasing
radial intensity gradient, the 25%-of-area darkest pixels fall at approximately 50% of the
radius purely from area ∝ r² scaling — independent of whether a real second ring exists.
Observed inner/outer ratios from this sub-threshold cluster around ~0.51-0.53 for genuine
double rings and ~0.60-0.79 for the remaining false-positive `invalid` blobs — a real but
subtle difference, not yet confidently separable with 8 test samples.

**A more aggressive fix was tried and reverted.** Requiring at least 2 independent methods
to agree on the outer radius (not just segmentation alone) correctly rejected all 8/8
invalid samples, but since Canny/Hough never contribute for *any* class on this generator's
renders, it also meant "only segmentation found an outer radius" is the *normal* case for
genuine halos too — applying that requirement dropped 197 of 220 training samples and
reduced `csf_like`/`saline_like` to **zero** training examples each, breaking calibration
entirely. Reverted. This is recorded so the same fix isn't tried again without first making
Canny/Hough (or a replacement edge method) actually work on soft gradients.

**A second fix was tried and also found not to work.** The natural next idea — replace
the percentile cut with a proper bimodality test (manual Otsu between-class-variance
maximization on the masked region's intensity histogram, rejecting the inner-radius
estimate when the achieved separation score is low) — was implemented as a standalone
diagnostic (not yet wired into `halo_detection.py`) and measured against 20 samples per
class. Result: separation scores are essentially indistinguishable between genuine halos
and invalid blobs (csf_like 0.772 mean, saline_like 0.768, saliva_like 0.842, other 0.797,
**invalid 0.843** — invalid actually scores slightly *higher* than csf_like/saline_like).
Otsu's between-class-variance maximization finds *a* good split point on essentially any
distribution, monotonic gradient or genuinely bimodal — it doesn't test for real structure,
so it can't discriminate here. Not implemented; recorded so this isn't tried again either.

**Status: not pursued further.** Two independent fix attempts (method-count corroboration,
bimodality testing) both failed on contact with real data after the one genuine bug
(the generator's fuzzy-edge artifact) was already fixed. The remaining ~37% false-positive
rate on `invalid` samples looks like it needs a structurally different approach — e.g. a
small classifier trained on the radial-intensity-profile *shape* itself, rather than another
hand-tuned OpenCV heuristic — which is a bigger undertaking than this gate's current
priority justifies. Left as a known, documented limitation.

### Observed: the out-of-distribution check flags `uncertain=true` often

Live end-to-end runs (`scripts/predict.py`, live `POST /api/analyze`) on held-out test
images that the classifier labels correctly and confidently (e.g. 0.66-0.87 winning-class
probability) are still frequently flagged `uncertain: true` — traced to the Mahalanobis
out-of-distribution check in `app/models/uncertainty.py`, not to low confidence or model
disagreement. With ~50 training samples per class against a 72-dimensional feature vector,
the per-class covariance estimate is likely unstable, inflating Mahalanobis distances. For
this application erring toward "uncertain" is a safe failure mode (it pushes toward
recommending lab confirmation rather than overclaiming), so this was left as-is rather than
loosened — but `ood_mahalanobis_threshold` (`app/config.py`) should be re-tuned once there
are enough real samples for the covariance estimate to be trustworthy.

## How to reproduce

```
cd backend
.venv/Scripts/python.exe ../scripts/generate_dataset.py
.venv/Scripts/python.exe ../scripts/train.py
.venv/Scripts/python.exe ../scripts/evaluate.py
```

## What would change before any real-world claim could be made

1. Real, ethically-sourced labeled images (IRB-approved collection, beta-2 transferrin or
   equivalent as ground truth — never the halo sign itself as its own label).
2. Re-run this entire evaluation on real data and report it separately from the synthetic
   numbers above — the two are not comparable.
3. External validation on a separate cohort/site before any sensitivity/specificity number
   is used to inform an actual clinical or triage decision.
