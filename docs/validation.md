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

Correctly rejected (NO_HALO_DETECTED, never reaches the classifier): 4/8 (50%). This is a
genuine, currently-mediocre result worth being honest about: half of the synthetic
"insufficient mixture ratio" samples still produced a detectable-enough ring for
`halo_detection.py` to accept. Two plausible causes, not yet root-caused: (1) the
generator's `invalid` class still renders a soft central-stain edge that the radial-profile
method's peak detector picks up as a weak transition, or (2) the `halo_width` detection
threshold (`5% of outer_radius`, `app/image_processing/halo_detection.py:209`) is too
permissive for small rings. Tightening this is a reasonable next step before trusting the
gate on real photos — tracked here rather than silently left out of the report.

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
