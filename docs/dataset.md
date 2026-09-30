# Dataset

## 1. Public dataset search

Before writing any training code we searched for existing public datasets of the
halo/double-ring sign (filter-paper or gauze fluid tests for CSF leak detection).

Queries run (2026-09-30):
- "halo sign CSF rhinorrhea dataset images kaggle machine learning classification"
- '"double ring sign" OR "halo sign" cerebrospinal fluid filter paper test image dataset public'

**Result: no suitable public dataset was identified for direct CSF-vs-saline-vs-saliva
halo-pattern classification.** The halo/double-ring sign is documented extensively in the
clinical literature (case reports, review articles, StatPearls figures) but not as a
labeled, licensable image dataset suitable for training a classifier. What does exist:

| Source | Content | Suitable for training? |
|---|---|---|
| StatPearls / NCBI Bookshelf halo-sign figure | Single illustrative photo | No — one image, not licensed for reuse/redistribution, no class balance |
| Case reports (Annals of Emergency Medicine, KJNT, PMC case series) | Individual clinical photos embedded in papers | No — not a dataset, copyrighted journal figures, far too few images per class |
| Kaggle medical-imaging search | General CT/MRI/dermatology/radiology datasets | No — none address filter-paper fluid halo patterns |
| ML papers on CSF rhinorrhea (e.g. PMC10076706) | Tabular clinical/surgical risk-factor data, not halo images | No — different modality (structured clinical features, not halo photographs) |

Given this, we are not downloading ad-hoc images from search engines and presenting them
as ground truth (the project's own scientific-integrity constraint). Instead we built a
**procedural synthetic dataset generator** (`backend/datasets/synthetic_generator.py`) so
that the full pipeline — feature extraction, classical ML, calibration, evaluation — can
be built and honestly tested against data whose ground truth we actually control, while
being explicit everywhere that results are synthetic/demo, not clinical validation.

## 2. What the literature actually establishes (used to design the generator)

The halo/double-ring test works by a chromatography-like mechanism: a mixed
blood+fluid drop is placed on absorbent paper/gauze; as it is wicked outward, blood
(higher-viscosity, particulate) travels less far and stays central, while the clear
component (CSF, saline, tears, saliva, or plain water) travels further and forms an
outer ring — producing a visible double ring when the mixture and paper allow separation.

Key facts pulled from the literature and encoded as generator parameters/limitations:

- **The halo sign is not specific to CSF.** Saline, tap water, and normal nasal
  secretions mixed with blood can all produce a halo indistinguishable by eye from a
  CSF-positive halo (Annals of Emergency Medicine: "Halo Sign Is Neither Sensitive Nor
  Specific For Cerebrospinal Fluid Leak"; *ScienceDirect*, "The 'ring sign': is it a
  reliable indicator for cerebral spinal fluid?"). → the generator gives **CSF-like and
  Saline-like classes deliberately overlapping ring-width, spread-radius and radial-decay
  distributions**, so a classifier trained on it cannot trivially separate them — matching
  the real-world difficulty and justifying why the app frames results as decision support,
  never diagnosis.
- **A minimum fluid:blood mixture ratio (reported ~30% CSF:blood) is needed to reliably
  produce a visible halo at all.** Below that, no separation occurs. → the generator
  includes a `mixture_ratio` parameter; low values produce `Invalid/no-halo` samples,
  matching the clinical caveat that "absence of halo does not exclude a leak."
  Sources: Wikipedia "Halo sign"; Peripheral Brain summary of the gauze test.
- **Saliva has substantially higher viscosity/mucin content than CSF or saline**, which
  measurably changes spreading rate and produces more textured, less uniform staining. →
  the generator gives Saliva-like samples a distinct (less overlapping) viscosity/texture
  parameter range.
- **Beta-2 transferrin testing is the recognized specific confirmatory laboratory test**
  for CSF, precisely because the visual halo test is not specific. This is why the app's
  decision-support message always recommends lab confirmation rather than presenting a
  classification as diagnostic.

Sources consulted: [Halo Sign Is Neither Sensitive Nor Specific For Cerebrospinal Fluid
Leak (Annals of Emergency Medicine)](https://www.annemergmed.com/article/S0196-0644(08)01848-9/abstract),
[The 'ring sign': is it a reliable indicator for cerebral spinal fluid? (PubMed)](https://pubmed.ncbi.nlm.nih.gov/8457102/),
[Halo sign (Wikipedia)](https://en.wikipedia.org/wiki/Halo_sign),
[StatPearls halo sign figure](https://www.ncbi.nlm.nih.gov/books/NBK562192/figure/article-20116.image.f2/?report=objectonly),
[Letter to the Editor: Double ring sign does not... (Emergency Medicine News)](https://journals.lww.com/em-news/fulltext/2021/03000/letter_to_the_editor__double_ring_sign_does_not.8.aspx).

## 3. Synthetic dataset design

`backend/datasets/synthetic_generator.py` procedurally renders sample-pad images with a
central stain and an outer ring, parametrized per class. Parameters are sampled from
per-class distributions (not fixed constants) so within-class variation and between-class
overlap are both present — an easy, hand-crafted dataset would defeat the point of
building a real evaluation pipeline.

### Classes

| Class | Ring width ratio | Spread radius (norm.) | Radial decay rate | Turbidity/texture noise | Center displacement | Notes |
|---|---|---|---|---|---|---|
| `csf_like` | 0.30–0.45 | 0.65–0.95 | slow | low | low | Overlaps heavily with `saline_like` by design |
| `saline_like` | 0.28–0.48 | 0.60–0.95 | slow | low | low | Overlaps heavily with `csf_like` by design |
| `saliva_like` | 0.15–0.30 | 0.35–0.60 | fast | high (mucin texture) | moderate | Distinct — higher viscosity limits spread |
| `other` | wide random range spanning/exceeding the above | — | — | high | high | Catch-all / out-of-distribution stand-in |
| `invalid` | ring absent or mixture_ratio below threshold | n/a | n/a | high (blur/noise/poor exposure) | n/a | No usable halo — quality gate should reject before classification |

### Per-sample metadata (`metadata.csv`)

`sample_id, class, split, session_id, mixture_ratio, ring_width_ratio, spread_radius,
decay_rate, texture_noise, center_dx, center_dy, image_width, image_height, seed`

`session_id` groups samples generated from the same simulated "capture session" so that
train/validation/test splitting is done **by session, not by individual image**
(`scripts/train.py`), preventing near-duplicate leakage across splits (spec §16).

### Explicit labeling

- Every generated file lives under `backend/datasets/synthetic/` and every API/model
  response that touches this data carries a `"synthetic": true` /
  `"disclaimer": "SYNTHETIC/DEMO DATA — not derived from real biological samples"` field.
- `backend/trained_models/metadata.json` (written by `scripts/train.py`) stamps the model
  version with the same disclaimer plus the metrics from `docs/validation.md`.

## 4. Limitations

- This is **not** a substitute for a clinically collected dataset. Reported model metrics
  describe how well the pipeline recovers *known synthetic generation parameters*, not how
  well it would classify real biological fluids.
- Real CSF, saline, and saliva halo patterns on real gauze/paper under real smartphone
  camera conditions (lighting, pad texture, camera noise, focus) will differ from the
  rendered synthetic images in ways this generator cannot capture (true chromatographic
  physics, real paper fiber texture, real protein/mucin optical scattering).
- Before any real-world or clinical use, this system requires: IRB-approved data
  collection with trained personnel and appropriate biosafety procedures, real labeled
  images (ground truth via beta-2 transferrin or equivalent confirmatory testing, not the
  halo sign itself), and a real accuracy/sensitivity/specificity validation study.
