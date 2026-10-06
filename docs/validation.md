# Validation

**These are not clinical validation results.** Every number below comes from
`scripts/evaluate.py` run against the held-out `test` split of the **procedurally
generated synthetic dataset** described in `docs/dataset.md` (556 samples, 280 sessions
across 7 generator classes, split by session 70/15/15). They measure how well the pipeline
recovers known synthetic generation parameters — not how it would perform on real fluids.

**Why there is no "100% accuracy".** No image-based method can reach it for this task: CSF,
saline and tears form optically near-identical halos (the literature result the whole
project is built around). The app shows the calibrated confidence of each result and this
page's real measured accuracy in its model card instead.

## Results — model v2, 6 classes (synthetic test split, n=77)

| Metric | v2 (6 classes) | v1 (4 classes) |
|---|---|---|
| Accuracy | **0.688** | 0.745 |
| Macro precision | 0.671 | 0.737 |
| Macro recall | 0.686 | 0.753 |
| Macro F1 | 0.667 | 0.738 |
| Expected Calibration Error | **0.054** | 0.098 |
| Brier score | 0.068 | 0.091 |

Accuracy dropped after adding tear-like and nasal-mucus-like, exactly as expected: tear-like
was designed to overlap saline/CSF. Calibration *improved* — the confidences the app shows
are closer to true probabilities than before.

Confusion matrix (rows = true, columns = predicted):

```
                   csf  saline  saliva  tear  nasal_mucus  other
csf_like             4      4       0     1        0         0
saline_like          5      4       0     5        0         0
saliva_like          0      0       7     0        1         0
tear_like            4      0       0    17        0         0
nasal_mucus_like     0      0       1     0        7         0
other                0      0       2     0        1        14
```

Two clusters, as designed: the **clear fluids** (CSF / saline / tear) confuse with each
other, and the **mucin-rich fluids** (saliva / nasal mucus) occasionally swap. Clear vs
mucin-rich is almost never confused. A model that cleanly separated CSF from saline here
would indicate a generator bug, not a good model.

Per-class ROC-AUC: csf 0.891, saline 0.802, saliva 0.984, tear 0.924, nasal mucus 0.989, other 0.996.
Per-class PR-AUC: csf 0.382, saline 0.496, saliva 0.887, tear 0.818, nasal mucus 0.925, other 0.989.

### `csf_like`-specific (the class the medical-safety framing cares about most)

| Metric | v2 | v1 |
|---|---|---|
| Sensitivity | 0.444 | 0.556 |
| Specificity | 0.868 | 0.842 |
| PPV | 0.308 | 0.455 |
| NPV | 0.922 | 0.889 |

Low CSF sensitivity is why every CSF-like or uncertain result in the app carries a
"lab confirmation required" stamp — the image result must never be the last word.

### Sample gate: refusing images that aren't halo samples

**Problem found:** before this gate, any photo was analysed. A portrait came back
"HALO DETECTED", classified "Other / atypical" at 84% confidence, and was stored in the
patient's record (a cat and a coffee cup behaved the same). Separately, phone-size photos
(4032×3024) produced ~14 MB responses because diagrams were drawn at full resolution; images
are now downscaled to 1280 px before analysis.

`app/image_processing/sample_validation.py` now runs before any analysis and refuses the
image with HTTP 422 (nothing analysed, nothing stored, an `analysis_rejected` audit entry
with only the reason). It requires **positive evidence of a fluid stain**, not just the
absence of obvious non-samples:

1. **No face** — YuNet DNN detector (OpenCV Zoo, hash-pinned) or the LBP cascade.
2. **Pale, neutral pad** filling the image border.
3. **A darker, roughly round stain** on it.
4. **The stain looks like soaked-in fluid**: red-brown (blood + fluid), smooth interior, and a
   soft rim from wicking. This is what separates a drop from a coin, sticker, bottle cap,
   button, backlit head or face that is also "dark and round on white".
5. **Little edge detail** around the stain.

| Calibration set | Result |
|---|---|
| 1,114 halo images (556 dataset images, all 7 classes, + JPEG q60, 1600 px, ±20° rotation, dim + noise, warm indoor light, fibre texture variants) | **1,114 accepted (100%)** |
| 233 non-samples: 22 natural photos + 3 crops + a phone-size copy each; 9 stain look-alikes (black/red stickers, dark-red button, brown coin — sharp and slightly blurred — bottle cap, backlit head silhouette); 113 webcam-style selfies (close-up, tilted 15–45°, upper/lower/left half of the face, dim, blurred, noisy low-res webcam, and 100 low-resolution faces from LFW) | **233 refused (100%)** — 125 identified as a face |
| The same 113 selfies with face detection **disabled** | **113 refused (100%)** by the pad/stain checks alone |

Earlier version (LBP face cascade only) missed 5 of 11 hard selfie variants — faces tilted
30–45° and half faces — which is exactly what hand-held webcam captures produce. YuNet found
all 11 and made zero detections on 1,668 halo images. The gate costs ~0.4 s per image.

**Known limitation:** the halo test is blood mixed with the test fluid, so a stain containing
no blood at all (clear fluid only) is refused as `not_fluid_stain`.

Caveat: the positives are synthetic. Real gauze photos are messier (weave texture, uneven
light, table edges), so thresholds were set with wide margins on the sample side (e.g. pad
brightness ≥ 120 where samples measured ≥ 187; stain roundness ≥ 0.66 where samples measured
≥ 0.94). They should be re-checked against the first batch of real sample photos; when a
sample is refused, the server log records the measured check values (numbers only, no image)
to make that recalibration possible.

### Live timing (embedded-system target: result within one minute)

Measured against the running server on the development laptop: photo **7.8 s**,
10-second video (8 frames sampled and analysed) **17.5 s**. A 45-second budget in
`video_service.py` stops frame analysis early if a slow device would otherwise exceed it.

### Halo-detection gate check (synthetic `invalid`/no-halo class)

v2 test split: **3/4 (75%)** correctly rejected. Only 4 invalid samples landed in this
split, so this number is noisy; the v1 split measured 5/8 (62.5%). History of the
investigation:

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
