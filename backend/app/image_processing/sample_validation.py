"""Sample gate: is this image actually a halo test sample?

Runs before any analysis. Without it, any photo — a face, a cat, a coffee cup — went
through the pipeline and came back "HALO DETECTED" with a confident classification, and
was stored in the patient's record.

A halo test photo is a pale, neutral absorbent pad with one roughly round, darker stain
on it and little else. Checks, in order (first failure wins):

  1. face            — a human face is detected (LBP frontal-face cascade, scikit-image)
  2. no_sample_pad   — the image border isn't a pale, low-saturation pad
  3. no_stain        — no darker, roughly round stain found on the pad
  4. cluttered_scene — too much edge detail around the stain for a plain pad

Calibration (see docs/validation.md): 1,114 / 1,114 dataset images accepted (all 7 classes
plus JPEG, phone-size, rotation, dim, warm-light and fibre-texture variants); 110 / 110
natural photos rejected (portrait, animals, objects, textures, phone-size copies and crops,
and deliberately circular hard negatives: retina, clock, colour wheel, phantom). Margins are
deliberately wide on the sample side because real gauze photos are messier than the
synthetic set; recalibrate once real sample photos exist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from app.image_processing.preprocessing import resize_max_dimension, to_grayscale

PAD_MIN_BRIGHTNESS = 120      # samples: >= 187 observed
PAD_MAX_SATURATION = 60       # samples: <= 17 observed
STAIN_MIN_CIRCULARITY = 0.66  # samples: >= 0.94; natural photos: <= 0.60; a square is 0.64
STAIN_MIN_CONTRAST = 20       # pad brightness minus stain brightness
STAIN_AREA_RANGE = (0.002, 0.85)
MAX_EDGE_DENSITY_OUTSIDE = 0.02  # samples: 0.000; most natural photos: 0.02-0.25

MESSAGES = {
    "face": "This looks like a photo of a person's face. Only photos of a halo test sample "
            "(fluid drop on an absorbent pad or gauze) can be analysed.",
    "no_sample_pad": "No sample pad was found. The sample should sit on a pale, plain absorbent "
                     "pad or gauze that fills most of the photo.",
    "no_stain": "No round fluid stain was found on the pad. Centre the drop in the frame and "
                "make sure the stain is visible.",
    "cluttered_scene": "The photo contains too much other detail around the sample. Photograph "
                       "only the pad, close up, against a plain surface.",
}


class NotASampleError(Exception):
    def __init__(self, reason: str, metrics: dict | None = None):
        super().__init__(MESSAGES[reason])
        self.reason = reason
        self.metrics = metrics or {}  # numeric check values only — safe to log, no image content


@dataclass
class SampleCheck:
    ok: bool
    reason: str | None = None
    metrics: dict = field(default_factory=dict)

    @property
    def message(self) -> str | None:
        return MESSAGES.get(self.reason) if self.reason else None


@lru_cache(maxsize=1)
def _face_cascade():
    from skimage.data import lbp_frontal_face_cascade_filename
    from skimage.feature import Cascade
    return Cascade(lbp_frontal_face_cascade_filename())


def _count_faces(gray: np.ndarray) -> int:
    small, _ = resize_max_dimension(gray, 512)
    detections = _face_cascade().detect_multi_scale(
        img=small, scale_factor=1.2, step_ratio=1, min_size=(48, 48), max_size=(400, 400),
        min_neighbor_number=4,
    )
    return len(detections)


def _border_hsv(image_bgr: np.ndarray) -> tuple[float, float]:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    b = max(4, int(0.06 * min(h, w)))
    border = np.concatenate([hsv[:b].reshape(-1, 3), hsv[-b:].reshape(-1, 3),
                             hsv[:, :b].reshape(-1, 3), hsv[:, -b:].reshape(-1, 3)])
    return float(np.median(border[:, 2])), float(np.median(border[:, 1]))


def _largest_dark_blob(gray: np.ndarray):
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    (cx, cy), radius = cv2.minEnclosingCircle(contour)
    blob_mask = np.zeros_like(gray)
    cv2.drawContours(blob_mask, [contour], -1, 255, -1)
    return {
        "area_fraction": area / gray.size,
        "circularity": area / (np.pi * radius * radius + 1e-9),
        "mean_gray": float(gray[blob_mask > 0].mean()) if area > 0 else 255.0,
        "center": (cx, cy), "radius": radius,
    }


def validate_sample(image_bgr: np.ndarray) -> SampleCheck:
    image_bgr, _ = resize_max_dimension(image_bgr, 1024)
    gray = to_grayscale(image_bgr)
    h, w = gray.shape
    m: dict = {}

    m["faces"] = _count_faces(gray)
    if m["faces"] > 0:
        return SampleCheck(False, "face", m)

    m["pad_brightness"], m["pad_saturation"] = _border_hsv(image_bgr)
    if m["pad_brightness"] < PAD_MIN_BRIGHTNESS or m["pad_saturation"] > PAD_MAX_SATURATION:
        return SampleCheck(False, "no_sample_pad", m)

    blob = _largest_dark_blob(gray)
    if blob is None:
        return SampleCheck(False, "no_stain", m)
    m["stain_area_fraction"] = round(blob["area_fraction"], 4)
    m["stain_circularity"] = round(blob["circularity"], 3)
    m["stain_contrast"] = round(m["pad_brightness"] - blob["mean_gray"], 1)
    if (not STAIN_AREA_RANGE[0] <= blob["area_fraction"] <= STAIN_AREA_RANGE[1]
            or blob["circularity"] < STAIN_MIN_CIRCULARITY or m["stain_contrast"] < STAIN_MIN_CONTRAST):
        return SampleCheck(False, "no_stain", m)

    # Edge detail outside the stain, leaving room for the halo ring itself (outer ring radius
    # can reach ~1.9x the stain radius when the stain blob is only the inner core).
    yy, xx = np.ogrid[:h, :w]
    cx, cy = blob["center"]
    outside = np.hypot(xx - cx, yy - cy) > blob["radius"] * 2.2
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 60, 150) > 0
    m["edge_density_outside"] = round(float(edges[outside].mean()) if outside.any() else 0.0, 4)
    if m["edge_density_outside"] > MAX_EDGE_DENSITY_OUTSIDE:
        return SampleCheck(False, "cluttered_scene", m)

    return SampleCheck(True, None, m)
