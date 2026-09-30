"""Color features in RGB/HSV/LAB per region (spec section 8 — Color)."""
from __future__ import annotations

import cv2
import numpy as np

from app.feature_engineering._masks import RegionMasks


def _channel_stats(channel: np.ndarray, mask: np.ndarray, name: str) -> dict[str, float]:
    vals = channel[mask == 1].astype(np.float64)
    if vals.size == 0:
        return {f"{name}_mean": 0.0, f"{name}_std": 0.0}
    return {f"{name}_mean": float(vals.mean()), f"{name}_std": float(vals.std())}


def extract_color_features(image_bgr: np.ndarray, masks: RegionMasks) -> dict[str, float]:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)

    features: dict[str, float] = {}
    for region_name, mask in (("center", masks.center), ("ring", masks.ring)):
        features.update(_channel_stats(image_bgr[:, :, 2], mask, f"color_{region_name}_r"))
        features.update(_channel_stats(image_bgr[:, :, 1], mask, f"color_{region_name}_g"))
        features.update(_channel_stats(image_bgr[:, :, 0], mask, f"color_{region_name}_b"))
        features.update(_channel_stats(hsv[:, :, 0], mask, f"color_{region_name}_hue"))
        features.update(_channel_stats(hsv[:, :, 1], mask, f"color_{region_name}_saturation"))
        features.update(_channel_stats(hsv[:, :, 2], mask, f"color_{region_name}_value"))
        features.update(_channel_stats(lab[:, :, 1], mask, f"color_{region_name}_lab_a"))
        features.update(_channel_stats(lab[:, :, 2], mask, f"color_{region_name}_lab_b"))

    features["color_saturation_gradient"] = (
        features.get("color_center_saturation_mean", 0.0) - features.get("color_ring_saturation_mean", 0.0)
    )
    return features
