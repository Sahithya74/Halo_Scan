"""Sample gate: respond ONLY to photos of a halo test sample (fluid drop on a pad).

Runs before any analysis. Without it, any photo — a face, a cat, a coffee cup — went through
the pipeline and came back "HALO DETECTED" with a confident classification.

Rather than only ruling things out, the gate requires positive evidence of a fluid stain.
Checks, in order (first failure wins):

  1. face            — a face is detected (YuNet DNN + LBP cascade; either one is enough)
  2. no_sample_pad   — the image border isn't a pale, low-saturation absorbent pad
  3. no_stain        — no darker, roughly round stain on the pad
  4. not_fluid_stain — the stain doesn't look like soaked-in fluid: fluid wicks into the pad,
                       leaving a SOFT edge, a SMOOTH interior and a red-brown (blood) colour.
                       Solid objects (coins, stickers, buttons, caps), heads and silhouettes
                       have sharp outlines, internal detail, or neutral/black colour.
  5. cluttered_scene — too much edge detail around the stain for a plain pad

Calibration (docs/validation.md): every one of 1,116 dataset images (all 7 classes plus JPEG,
phone-size, warm-light, dim and fibre-texture variants) is accepted; every natural photo,
tilted/partial/low-light selfie, and stain look-alike (stickers, coins, caps, backlit head)
is refused. Margins are deliberately wide on the sample side because real gauze photos are
messier than the synthetic set — recalibrate once real sample photos exist; refused images
log their measured values for exactly that purpose.

Known limitation: a halo test is blood mixed with the test fluid, so a stain with no blood at
all (clear fluid only) is refused as not_fluid_stain.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from app.image_processing.preprocessing import resize_max_dimension, to_grayscale

logger = logging.getLogger(__name__)

# --- thresholds (observed sample ranges in comments) ---
PAD_MIN_BRIGHTNESS = 120          # samples >= 187
PAD_MAX_SATURATION = 60           # samples <= 17
STAIN_MIN_CIRCULARITY = 0.66      # samples >= 0.94; natural photos <= 0.60; a square is 0.64
STAIN_MIN_CONTRAST = 20           # pad brightness minus stain brightness
STAIN_AREA_RANGE = (0.002, 0.85)
STAIN_MIN_WARM_FRACTION = 0.40    # samples >= 0.66; black/grey objects, silhouettes = 0
STAIN_MIN_SATURATION = 50         # samples >= 78; backlit silhouette 36
STAIN_MAX_INTERIOR_EDGES = 0.05   # samples <= 0.031; faces/animals/objects up to 0.09+
STAIN_MAX_RIM_SHARPNESS = 1.20    # samples <= 0.85; every solid object/selfie tested >= 1.49
MAX_EDGE_DENSITY_OUTSIDE = 0.02   # samples 0.000; most natural photos 0.02-0.25
FACE_MIN_SCORE = 0.6              # YuNet: 0 of 1,668 sample images scored above 0.0

_YUNET_PATH = Path(__file__).resolve().parent.parent / "models_bin" / "face_detection_yunet_2023mar.onnx"
_YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

MESSAGES = {
    "face": "This looks like a photo of a person's face. Only photos of a halo test sample "
            "(fluid drop on an absorbent pad or gauze) can be analysed.",
    "no_sample_pad": "No sample pad was found. The sample should sit on a pale, plain absorbent "
                     "pad or gauze that fills most of the photo.",
    "no_stain": "No round fluid stain was found on the pad. Centre the drop in the frame and "
                "make sure the stain is visible.",
    "not_fluid_stain": "The dark spot doesn't look like a fluid stain. A halo test stain is blood "
                       "mixed with fluid soaked into the pad — red-brown, with a soft edge and no "
                       "internal detail. This looks like a solid object, a person, or a non-blood mark.",
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


# ---------------- faces ----------------

@lru_cache(maxsize=1)
def _lbp_cascade():
    from skimage.data import lbp_frontal_face_cascade_filename
    from skimage.feature import Cascade
    return Cascade(lbp_frontal_face_cascade_filename())


@lru_cache(maxsize=1)
def _yunet():
    """YuNet face detector (OpenCV Zoo, MIT licence). Pinned by SHA-256 so a swapped model file
    is refused; if unavailable the LBP cascade alone is used and a warning is logged."""
    try:
        data = _YUNET_PATH.read_bytes()
    except OSError:
        logger.warning("YuNet model missing at %s — face detection falls back to LBP only.", _YUNET_PATH)
        return None
    if hashlib.sha256(data).hexdigest() != _YUNET_SHA256:
        logger.error("YuNet model hash mismatch — refusing to load it; using LBP only.")
        return None
    return cv2.FaceDetectorYN.create(str(_YUNET_PATH), "", (320, 320), 0.5, 0.3, 50)


def _count_faces(image_bgr: np.ndarray) -> int:
    count = 0
    detector = _yunet()
    if detector is not None:
        small, _ = resize_max_dimension(image_bgr, 640)
        detector.setInputSize((small.shape[1], small.shape[0]))
        _, faces = detector.detect(small)
        if faces is not None:
            count += int((faces[:, -1] >= FACE_MIN_SCORE).sum())
    if count:
        return count
    gray_small, _ = resize_max_dimension(to_grayscale(image_bgr), 512)
    return len(_lbp_cascade().detect_multi_scale(
        img=gray_small, scale_factor=1.2, step_ratio=1, min_size=(48, 48), max_size=(400, 400),
        min_neighbor_number=4,
    ))


# ---------------- pad and stain ----------------

def _border_hsv(image_bgr: np.ndarray) -> tuple[float, float]:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    b = max(4, int(0.06 * min(h, w)))
    border = np.concatenate([hsv[:b].reshape(-1, 3), hsv[-b:].reshape(-1, 3),
                             hsv[:, :b].reshape(-1, 3), hsv[:, -b:].reshape(-1, 3)])
    return float(np.median(border[:, 2])), float(np.median(border[:, 1]))


def _largest_dark_blob(blurred: np.ndarray):
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area <= 0:
        return None
    (cx, cy), radius = cv2.minEnclosingCircle(contour)
    blob_mask = np.zeros_like(blurred)
    cv2.drawContours(blob_mask, [contour], -1, 255, -1)
    return {
        "area_fraction": area / blurred.size, "circularity": area / (np.pi * radius * radius + 1e-9),
        "mean_gray": float(blurred[blob_mask > 0].mean()), "center": (cx, cy), "radius": radius,
        "mask": blob_mask,
    }


def _fluid_character(image_bgr: np.ndarray, gray: np.ndarray, blurred: np.ndarray, blob: dict) -> dict:
    """Colour, interior smoothness and rim softness of the stain."""
    mask, r = blob["mask"], blob["radius"]
    k = max(3, int(r * 0.15)) | 1
    core = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    if not core.any():
        core = mask
    px = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)[core > 0]
    warm = ((px[:, 0] <= 25) | (px[:, 0] >= 155)) & (px[:, 1] >= 60)  # red-brown hues, OpenCV 0-180 scale

    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120) > 0

    # Rim sharpness: steepest gradient across the stain boundary relative to the stain's contrast,
    # scaled by radius so a soft edge on a big stain isn't mistaken for a sharp one.
    f = blurred.astype(np.float32)
    mag = np.hypot(cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3))
    band = cv2.dilate(mask, np.ones((7, 7), np.uint8)) - cv2.erode(mask, np.ones((7, 7), np.uint8))
    ring_out = cv2.dilate(mask, np.ones((31, 31), np.uint8)) - cv2.dilate(mask, np.ones((15, 15), np.uint8))
    outside_level = float(np.median(blurred[ring_out > 0])) if ring_out.any() else 255.0
    contrast = max(1.0, outside_level - float(np.median(blurred[core > 0])))
    rim = float(np.percentile(mag[band > 0], 90)) / contrast * (r / 100.0) if band.any() else 99.0

    return {
        "stain_warm_fraction": round(float(warm.mean()), 3),
        "stain_saturation": float(np.median(px[:, 1])),
        "stain_interior_edges": round(float(edges[core > 0].mean()), 4),
        "stain_rim_sharpness": round(rim, 3),
    }


def validate_sample(image_bgr: np.ndarray) -> SampleCheck:
    image_bgr, _ = resize_max_dimension(image_bgr, 1024)
    gray = to_grayscale(image_bgr)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    h, w = gray.shape
    m: dict = {}

    m["faces"] = _count_faces(image_bgr)
    if m["faces"] > 0:
        return SampleCheck(False, "face", m)

    m["pad_brightness"], m["pad_saturation"] = _border_hsv(image_bgr)
    if m["pad_brightness"] < PAD_MIN_BRIGHTNESS or m["pad_saturation"] > PAD_MAX_SATURATION:
        return SampleCheck(False, "no_sample_pad", m)

    blob = _largest_dark_blob(blurred)
    if blob is None:
        return SampleCheck(False, "no_stain", m)
    m["stain_area_fraction"] = round(blob["area_fraction"], 4)
    m["stain_circularity"] = round(blob["circularity"], 3)
    m["stain_contrast"] = round(m["pad_brightness"] - blob["mean_gray"], 1)
    if (not STAIN_AREA_RANGE[0] <= blob["area_fraction"] <= STAIN_AREA_RANGE[1]
            or blob["circularity"] < STAIN_MIN_CIRCULARITY or m["stain_contrast"] < STAIN_MIN_CONTRAST):
        return SampleCheck(False, "no_stain", m)

    m.update(_fluid_character(image_bgr, gray, blurred, blob))
    if (m["stain_warm_fraction"] < STAIN_MIN_WARM_FRACTION or m["stain_saturation"] < STAIN_MIN_SATURATION
            or m["stain_interior_edges"] > STAIN_MAX_INTERIOR_EDGES
            or m["stain_rim_sharpness"] > STAIN_MAX_RIM_SHARPNESS):
        return SampleCheck(False, "not_fluid_stain", m)

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
