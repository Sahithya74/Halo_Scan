"""Shared low-level image utilities used across the quality/ROI/halo modules."""
from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr.ndim == 2:
        return image_bgr
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def gaussian_blur(gray: np.ndarray, ksize: int = 5) -> np.ndarray:
    if ksize % 2 == 0:
        ksize += 1
    return cv2.GaussianBlur(gray, (ksize, ksize), 0)


def clahe_equalize(gray: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return clahe.apply(gray)


def resize_max_dimension(image_bgr: np.ndarray, max_dim: int = 900) -> tuple[np.ndarray, float]:
    """Downscale for consistent, fast processing. Returns (image, scale_applied)."""
    h, w = image_bgr.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image_bgr, 1.0
    scale = max_dim / float(longest)
    resized = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return resized, scale


def to_polar(image_bgr: np.ndarray, center: tuple[float, float], max_radius: float,
             angular_samples: int = 360) -> np.ndarray:
    """Cartesian -> polar transform centered on the detected drop center.

    Output rows = angle (0..angular_samples-1), columns = radius (0..max_radius-1).
    """
    flags = cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS + cv2.WARP_POLAR_LINEAR
    polar = cv2.warpPolar(
        image_bgr,
        (int(max_radius), angular_samples),
        center,
        max_radius,
        flags,
    )
    return polar
