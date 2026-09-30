"""Texture features via GLCM and LBP (spec section 8 — Texture), computed on the ring
region's bounding-box crop since GLCM/LBP operate on 2D neighborhoods, not sparse masks.
"""
from __future__ import annotations

import cv2
import numpy as np
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from skimage.measure import shannon_entropy

from app.feature_engineering._masks import RegionMasks
from app.image_processing.preprocessing import to_grayscale

_GLCM_LEVELS = 16


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return None
    return int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1


def extract_texture_features(image_bgr: np.ndarray, masks: RegionMasks) -> dict[str, float]:
    gray = to_grayscale(image_bgr)
    box = _bbox(masks.ring)
    if box is None:
        return {
            "tex_glcm_contrast": 0.0, "tex_glcm_homogeneity": 0.0, "tex_glcm_energy": 0.0,
            "tex_glcm_correlation": 0.0, "tex_glcm_entropy": 0.0, "tex_lbp_entropy": 0.0,
        }
    y0, y1, x0, x1 = box
    crop = gray[y0:y1, x0:x1]
    if crop.size < 25:
        return {
            "tex_glcm_contrast": 0.0, "tex_glcm_homogeneity": 0.0, "tex_glcm_energy": 0.0,
            "tex_glcm_correlation": 0.0, "tex_glcm_entropy": 0.0, "tex_lbp_entropy": 0.0,
        }

    quantized = (crop.astype(np.float64) / 256.0 * _GLCM_LEVELS).astype(np.uint8)
    quantized = np.clip(quantized, 0, _GLCM_LEVELS - 1)
    glcm = graycomatrix(
        quantized, distances=[1, 2], angles=[0, np.pi / 4, np.pi / 2, 3 * np.pi / 4],
        levels=_GLCM_LEVELS, symmetric=True, normed=True,
    )
    contrast = float(graycoprops(glcm, "contrast").mean())
    homogeneity = float(graycoprops(glcm, "homogeneity").mean())
    energy = float(graycoprops(glcm, "energy").mean())
    correlation = float(np.nan_to_num(graycoprops(glcm, "correlation")).mean())
    entropy = float(shannon_entropy(crop))

    lbp = local_binary_pattern(crop, P=8, R=1, method="uniform")
    lbp_hist, _ = np.histogram(lbp, bins=10, range=(0, 10), density=True)
    lbp_entropy = float(-(lbp_hist * np.log2(lbp_hist + 1e-9)).sum())

    return {
        "tex_glcm_contrast": contrast,
        "tex_glcm_homogeneity": homogeneity,
        "tex_glcm_energy": energy,
        "tex_glcm_correlation": correlation,
        "tex_glcm_entropy": entropy,
        "tex_lbp_entropy": lbp_entropy,
    }
