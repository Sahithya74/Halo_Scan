"""Shared pytest fixtures: hand-drawn synthetic test images (not the full generator) for
fast, deterministic unit tests of the CV modules."""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_ring_image(size: int = 400, center=None, inner_r: int = 60, outer_r: int = 120,
                      background=(250, 248, 245), ring_color=(150, 150, 130),
                      center_color=(28, 32, 118)) -> np.ndarray:
    # Background vs ring vs center are deliberately high-contrast (~100+ gray levels apart
    # at each boundary) so this represents a genuinely *visible* ring — the low-contrast
    # case (ring barely distinguishable from background) is a real failure mode worth its
    # own test, not what "detects_clear_ring" is meant to exercise.
    if center is None:
        center = (size // 2, size // 2)
    image = np.full((size, size, 3), background, dtype=np.uint8)
    cv2.circle(image, center, outer_r, ring_color, -1)
    cv2.circle(image, center, inner_r, center_color, -1)
    image = cv2.GaussianBlur(image, (5, 5), 0)
    return image


@pytest.fixture
def ring_image() -> np.ndarray:
    return _make_ring_image()


@pytest.fixture
def ring_image_factory():
    return _make_ring_image


@pytest.fixture
def blurry_dark_image() -> np.ndarray:
    image = np.full((400, 400, 3), (20, 20, 20), dtype=np.uint8)
    noise = np.random.default_rng(0).normal(0, 2, image.shape)
    image = np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    return cv2.GaussianBlur(image, (25, 25), 0)


@pytest.fixture
def good_quality_flat_image() -> np.ndarray:
    rng = np.random.default_rng(1)
    base = np.full((500, 500, 3), 150, dtype=np.uint8)
    noise = rng.normal(0, 25, base.shape)
    image = np.clip(base.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    cv2.circle(image, (250, 250), 100, (60, 60, 60), -1)
    return image
