"""Procedural synthetic halo-pattern generator.

No public dataset exists for CSF/saline/saliva halo classification (see docs/dataset.md
for the search that confirmed this). This module renders parametrized ring-pattern images
with class-specific but deliberately *overlapping* parameter distributions, grounded in
the literature's description of the chromatography-like halo test:

  - a central stain (blood, mixed with the test fluid)
  - an outer ring (the more-mobile clear/turbid fluid component)
  - a `mixture_ratio` below ~0.3 produces no separated ring at all (matches the reported
    minimum fluid:blood ratio needed for a visible halo)

CSF-like and saline-like classes intentionally overlap heavily (they are optically very
similar in real life — that is the whole point of the project's medical-safety framing).
Saliva-like is more distinct (higher viscosity/turbidity limits spread and adds texture).
`other` spans a wide, atypical parameter range as a catch-all/out-of-distribution stand-in.

Every image and every metadata row is explicitly tagged as synthetic.
"""
from __future__ import annotations

import csv
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

CANVAS_SIZE = 512
PAD_RADIUS_MAX = CANVAS_SIZE * 0.47
MIXTURE_RATIO_HALO_THRESHOLD = 0.30  # below this, no visible ring forms (literature-grounded)

CLASSES = ("csf_like", "saline_like", "saliva_like", "other", "invalid")

# (low, high) uniform ranges per class. Deliberately overlapping for csf_like/saline_like.
CLASS_PARAM_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "csf_like": dict(
        mixture_ratio=(0.55, 0.95), ring_width_ratio=(0.30, 0.45), spread_radius=(0.65, 0.95),
        decay_softness=(0.35, 0.55), texture_noise=(0.03, 0.08), center_disp=(0.0, 0.04),
        ring_hue_shift=(-6, 8),
    ),
    "saline_like": dict(
        mixture_ratio=(0.55, 0.95), ring_width_ratio=(0.28, 0.48), spread_radius=(0.60, 0.95),
        decay_softness=(0.35, 0.55), texture_noise=(0.03, 0.08), center_disp=(0.0, 0.04),
        ring_hue_shift=(-8, 6),
    ),
    "saliva_like": dict(
        mixture_ratio=(0.50, 0.90), ring_width_ratio=(0.15, 0.30), spread_radius=(0.35, 0.60),
        decay_softness=(0.10, 0.22), texture_noise=(0.10, 0.22), center_disp=(0.02, 0.08),
        ring_hue_shift=(5, 20),
    ),
    "other": dict(
        mixture_ratio=(0.40, 0.95), ring_width_ratio=(0.05, 0.55), spread_radius=(0.20, 0.98),
        decay_softness=(0.05, 0.60), texture_noise=(0.05, 0.30), center_disp=(0.0, 0.15),
        ring_hue_shift=(-25, 25),
    ),
    "invalid": dict(
        mixture_ratio=(0.05, 0.29), ring_width_ratio=(0.0, 0.0), spread_radius=(0.20, 0.55),
        decay_softness=(0.10, 0.30), texture_noise=(0.05, 0.20), center_disp=(0.0, 0.10),
        ring_hue_shift=(-10, 10),
    ),
}

BACKGROUND_COLOR_BGR = np.array([246.0, 243.0, 238.0])  # dry absorbent pad
CENTER_COLOR_BASE_BGR = np.array([28.0, 32.0, 118.0])   # blood stain


@dataclass
class SampleMeta:
    sample_id: str
    session_id: str
    label: str
    split: str
    mixture_ratio: float
    ring_width_ratio: float
    spread_radius: float
    decay_softness: float
    texture_noise: float
    center_dx: float
    center_dy: float
    ring_hue_shift: float
    halo_present: bool
    image_width: int
    image_height: int
    seed: int
    synthetic: bool = True


def _smoothstep(edge0: np.ndarray, edge1: np.ndarray, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - edge0) / np.maximum(edge1 - edge0, 1e-6), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def render_sample(rng: np.random.Generator, label: str) -> tuple[np.ndarray, dict[str, float]]:
    ranges = CLASS_PARAM_RANGES[label]
    params = {k: float(rng.uniform(lo, hi)) for k, (lo, hi) in ranges.items()}

    halo_present = params["mixture_ratio"] >= MIXTURE_RATIO_HALO_THRESHOLD and label != "invalid"

    dx_sign = rng.choice([-1.0, 1.0])
    dy_sign = rng.choice([-1.0, 1.0])
    center_dx = params["center_disp"] * dx_sign
    center_dy = params["center_disp"] * dy_sign
    cx = CANVAS_SIZE / 2 + center_dx * CANVAS_SIZE
    cy = CANVAS_SIZE / 2 + center_dy * CANVAS_SIZE

    outer_radius = params["spread_radius"] * PAD_RADIUS_MAX
    if halo_present:
        inner_radius = outer_radius * (1.0 - params["ring_width_ratio"])
    else:
        # No chromatographic separation: a single concentrated blob with NO separate ring
        # band at all (inner == outer exactly) — a soft-edged stain fading straight to
        # background. An earlier version used inner_radius = outer_radius * 0.92, which
        # left an ~8% "fuzzy edge" width that the halo detector's 5%-of-outer-radius
        # width threshold (halo_detection.py) then picked up as a genuine (if faint) ring,
        # causing ~50% of these samples to be wrongly flagged as having a halo (see
        # docs/validation.md). Zero width removes that artifact at the source.
        outer_radius = outer_radius * 0.55
        inner_radius = outer_radius

    softness = max(params["decay_softness"] * outer_radius, 3.0)

    yy, xx = np.mgrid[0:CANVAS_SIZE, 0:CANVAS_SIZE].astype(np.float64)
    dist = np.hypot(xx - cx, yy - cy)

    # ring hue shift -> tint applied to the ring color relative to background/center.
    hue_shift = params["ring_hue_shift"]
    ring_color = BACKGROUND_COLOR_BGR - np.array([hue_shift * 1.2, hue_shift * 0.6, -hue_shift * 0.3]) - 14.0
    ring_color = np.clip(ring_color, 0, 255)

    center_weight = 1.0 - _smoothstep(inner_radius - softness, inner_radius + softness, dist)
    outer_weight = _smoothstep(outer_radius - softness, outer_radius + softness, dist)
    ring_weight = np.clip(1.0 - center_weight - outer_weight, 0.0, 1.0)

    image = (
        center_weight[..., None] * CENTER_COLOR_BASE_BGR
        + ring_weight[..., None] * ring_color
        + outer_weight[..., None] * BACKGROUND_COLOR_BGR
    )

    # Texture noise: stronger for turbid/mucin-rich samples (e.g. saliva_like).
    noise_std = params["texture_noise"] * 40.0
    noise = rng.normal(0, noise_std, size=(CANVAS_SIZE, CANVAS_SIZE, 1))
    image = image + noise * (1.0 - outer_weight[..., None] * 0.7)

    # Mild sensor noise + camera-like blur everywhere (all classes, for realism).
    image = image + rng.normal(0, 3.0, size=image.shape)
    image = np.clip(image, 0, 255).astype(np.uint8)
    image = cv2.GaussianBlur(image, (3, 3), 0)

    return image, {**params, "center_dx": center_dx, "center_dy": center_dy, "halo_present": halo_present}


def generate_dataset(
    output_dir: Path,
    sessions_per_class: int = 40,
    images_per_session_range: tuple[int, int] = (1, 3),
    split_ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
) -> Path:
    """Generates train/validation/test folders + metadata.csv. Splitting is done by
    SESSION (a simulated capture session, 1-3 photos of the "same" underlying sample),
    never by individual image, to avoid near-duplicate leakage across splits.
    """
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[SampleMeta] = []
    sample_counter = 0
    session_counter = 0

    for label in CLASSES:
        n_sessions = sessions_per_class
        # Assign split at the SESSION level.
        session_splits = py_rng.choices(
            ["train", "validation", "test"], weights=split_ratios, k=n_sessions
        )
        for session_idx in range(n_sessions):
            session_counter += 1
            session_id = f"ses_{label}_{session_counter:05d}"
            split = session_splits[session_idx]
            n_images = py_rng.randint(*images_per_session_range)
            for _img_idx in range(n_images):
                sample_counter += 1
                sample_id = f"smp_{sample_counter:06d}"
                img_seed = seed * 1_000_003 + sample_counter
                img_rng = np.random.default_rng(img_seed)
                image, params = render_sample(img_rng, label)

                class_dir = output_dir / split / label
                class_dir.mkdir(parents=True, exist_ok=True)
                file_path = class_dir / f"{sample_id}.png"
                cv2.imwrite(str(file_path), image)

                all_rows.append(SampleMeta(
                    sample_id=sample_id, session_id=session_id, label=label, split=split,
                    mixture_ratio=round(params["mixture_ratio"], 4),
                    ring_width_ratio=round(params["ring_width_ratio"], 4),
                    spread_radius=round(params["spread_radius"], 4),
                    decay_softness=round(params["decay_softness"], 4),
                    texture_noise=round(params["texture_noise"], 4),
                    center_dx=round(params["center_dx"], 4),
                    center_dy=round(params["center_dy"], 4),
                    ring_hue_shift=round(params["ring_hue_shift"], 2),
                    halo_present=bool(params["halo_present"]),
                    image_width=CANVAS_SIZE, image_height=CANVAS_SIZE,
                    seed=img_seed,
                ))

    metadata_path = output_dir / "metadata.csv"
    with metadata_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(all_rows[0]).keys()))
        writer.writeheader()
        for row in all_rows:
            writer.writerow(asdict(row))

    return metadata_path
