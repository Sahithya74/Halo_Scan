"""Shared region-mask builder used by intensity/color/texture feature extractors.

Builds three disjoint masks from the detected halo geometry: the central stain,
the ring (halo) band, and a thin annulus of background just outside the ring —
so every feature module works from the same region definitions.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.image_processing.halo_detection import HaloDetectionResult


@dataclass
class RegionMasks:
    center: np.ndarray
    ring: np.ndarray
    background: np.ndarray


def build_region_masks(image_shape: tuple[int, int], halo: HaloDetectionResult) -> RegionMasks:
    h, w = image_shape[:2]
    yy, xx = np.ogrid[:h, :w]
    dist = np.hypot(xx - halo.center_x, yy - halo.center_y)

    inner = max(halo.inner_radius, 1.0)
    outer = max(halo.outer_radius, inner + 1.0)
    bg_outer = outer + max(0.25 * (outer - inner), 5.0)

    center_mask = (dist <= inner).astype(np.uint8)
    ring_mask = ((dist > inner) & (dist <= outer)).astype(np.uint8)
    background_mask = ((dist > outer) & (dist <= bg_outer)).astype(np.uint8)
    return RegionMasks(center=center_mask, ring=ring_mask, background=background_mask)
