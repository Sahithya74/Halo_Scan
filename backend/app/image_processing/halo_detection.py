"""Halo/double-ring detection — the core CV module.

Combines several independent methods (spec section 7) rather than trusting one algorithm,
then reconciles them into a single result with an explicit agreement/confidence score:

  A. Canny edge detection + contour circle fit on the edge map
  B. Hough Circle Transform for inner/outer radius
  C. Radial intensity profiling I(r) with peak-based transition detection
  D. Cartesian -> polar transform (also reused by feature_engineering/visualization)
  E. Adaptive threshold + morphology segmentation into center/transition/outer regions
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from scipy.signal import find_peaks, savgol_filter

from app.config import settings
from app.image_processing.preprocessing import gaussian_blur, to_grayscale, to_polar
from app.image_processing.roi_detection import ROI


@dataclass
class RadialProfile:
    radii: np.ndarray
    mean_intensity: np.ndarray
    std_intensity: np.ndarray  # angular std at each radius -> symmetry


@dataclass
class HaloDetectionResult:
    detected: bool
    center_x: float
    center_y: float
    inner_radius: float
    outer_radius: float
    halo_width: float
    circularity: float
    symmetry_score: float
    confidence: float
    method_agreement: dict = field(default_factory=dict)
    radial_profile: RadialProfile | None = None
    polar_image: np.ndarray | None = None
    messages: list[str] = field(default_factory=list)


def _radial_profile(gray: np.ndarray, roi: ROI, max_radius: float) -> tuple[RadialProfile, np.ndarray]:
    polar = to_polar(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), (roi.center_x, roi.center_y),
                      max_radius, settings.radial_profile_samples)
    polar_gray = cv2.cvtColor(polar, cv2.COLOR_BGR2GRAY).astype(np.float64)
    mean_intensity = polar_gray.mean(axis=0)
    std_intensity = polar_gray.std(axis=0)
    radii = np.arange(mean_intensity.shape[0], dtype=np.float64)
    return RadialProfile(radii=radii, mean_intensity=mean_intensity, std_intensity=std_intensity), polar


def _transitions_from_profile(profile: RadialProfile) -> tuple[float | None, float | None]:
    n = len(profile.mean_intensity)
    if n < 15:
        return None, None
    window = min(21, n - (1 - n % 2))
    if window < 5:
        window = 5
    if window % 2 == 0:
        window += 1
    smoothed = savgol_filter(profile.mean_intensity, window_length=window, polyorder=2)
    gradient = np.abs(np.gradient(smoothed))
    peaks, props = find_peaks(gradient, distance=max(3, n // 20), prominence=gradient.std() * 0.5)
    if len(peaks) == 0:
        return None, None
    # Rank peaks by prominence, take up to two strongest, order by radius.
    order = np.argsort(props["prominences"])[::-1]
    top = sorted(peaks[order[:2]].tolist())
    if len(top) == 1:
        return float(top[0]), None
    return float(top[0]), float(top[1])


def _edge_circle_estimate(gray: np.ndarray, roi: ROI) -> tuple[float | None, float | None]:
    blurred = gaussian_blur(gray, 5)
    edges = cv2.Canny(blurred, settings.canny_low, settings.canny_high)
    ys, xs = np.nonzero(edges)
    if len(xs) < 20:
        return None, None
    dists = np.hypot(xs - roi.center_x, ys - roi.center_y)
    max_r = roi.radius * 1.6
    dists = dists[dists <= max_r]
    if len(dists) < 20:
        return None, None
    hist, edges_bins = np.histogram(dists, bins=30)
    peak_idx = np.argsort(hist)[::-1][:2]
    radii = sorted(float((edges_bins[i] + edges_bins[i + 1]) / 2) for i in peak_idx)
    if len(radii) == 1:
        return radii[0], None
    return radii[0], radii[1]


def _hough_ring_estimate(gray: np.ndarray, roi: ROI) -> tuple[float | None, float | None]:
    blurred = gaussian_blur(gray, 7)
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT, dp=settings.hough_dp,
        minDist=roi.radius * 0.5,
        param1=settings.canny_high, param2=30,
        minRadius=int(roi.radius * 0.2), maxRadius=int(roi.radius * 1.5),
    )
    if circles is None:
        return None, None
    circles = np.round(circles[0]).astype(float)
    near = [c for c in circles if np.hypot(c[0] - roi.center_x, c[1] - roi.center_y) < roi.radius * 0.4]
    candidates = near if near else list(circles)
    radii = sorted(c[2] for c in candidates)[:2]
    if len(radii) == 0:
        return None, None
    if len(radii) == 1:
        return radii[0], None
    return radii[0], radii[1]


def _segmentation_estimate(gray: np.ndarray, roi: ROI) -> tuple[float | None, float | None, float]:
    """Adaptive-threshold segmentation into center stain vs outer halo; returns
    (inner_radius, outer_radius, circularity) of the outer segmented blob."""
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None, 0.0
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area <= 0:
        return None, None, 0.0
    (_, _), outer_r = cv2.minEnclosingCircle(c)
    circle_area = np.pi * outer_r * outer_r
    circularity = float(area / circle_area) if circle_area > 0 else 0.0

    # Inner stain: threshold the darkest core within the outer blob (double Otsu-like split).
    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [c], -1, 255, -1)
    masked_vals = gray[mask == 255]
    if masked_vals.size < 10:
        return None, outer_r, circularity
    core_thresh = np.percentile(masked_vals, 25)
    core_mask = ((gray <= core_thresh) & (mask == 255)).astype(np.uint8) * 255
    core_contours, _ = cv2.findContours(core_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    inner_r = None
    if core_contours:
        core_c = max(core_contours, key=cv2.contourArea)
        if cv2.contourArea(core_c) > 0:
            (_, _), inner_r = cv2.minEnclosingCircle(core_c)
    return inner_r, float(outer_r), circularity


def detect_halo(image_bgr: np.ndarray, roi: ROI) -> HaloDetectionResult:
    gray = to_grayscale(image_bgr)
    max_radius = min(roi.radius * 1.6, min(gray.shape[:2]) / 2.0 - 1)
    max_radius = max(max_radius, 10.0)

    profile, polar_image = _radial_profile(gray, roi, max_radius)
    profile_inner, profile_outer = _transitions_from_profile(profile)

    edge_inner, edge_outer = _edge_circle_estimate(gray, roi)
    hough_inner, hough_outer = _hough_ring_estimate(gray, roi)
    seg_inner, seg_outer, circularity = _segmentation_estimate(gray, roi)

    inner_candidates = [v for v in (profile_inner, edge_inner, hough_inner, seg_inner) if v is not None]
    outer_candidates = [v for v in (profile_outer, edge_outer, hough_outer, seg_outer) if v is not None]

    messages: list[str] = []
    if not inner_candidates or not outer_candidates:
        return HaloDetectionResult(
            detected=False, center_x=roi.center_x, center_y=roi.center_y,
            inner_radius=0.0, outer_radius=0.0, halo_width=0.0, circularity=0.0,
            symmetry_score=0.0, confidence=0.0,
            method_agreement={"profile": profile_inner is not None, "edge": edge_inner is not None,
                               "hough": hough_inner is not None, "segmentation": seg_inner is not None},
            radial_profile=profile, polar_image=polar_image,
            messages=["No halo/ring pattern could be detected in the sample region."],
        )

    inner_radius = float(np.median(inner_candidates))
    outer_radius = float(np.median(outer_candidates))
    if outer_radius <= inner_radius:
        outer_radius, inner_radius = max(outer_radius, inner_radius), min(outer_radius, inner_radius)
    halo_width = outer_radius - inner_radius

    # Agreement: how tightly the independent methods cluster (lower spread = higher confidence).
    def _agreement(vals: list[float]) -> float:
        if len(vals) < 2:
            return 0.4
        spread = float(np.std(vals)) / (float(np.mean(vals)) + 1e-6)
        return float(np.clip(1.0 - spread, 0.0, 1.0))

    inner_agreement = _agreement(inner_candidates)
    outer_agreement = _agreement(outer_candidates)
    n_methods_agreeing = len(inner_candidates) + len(outer_candidates)
    confidence = float(np.clip(
        0.5 * (inner_agreement + outer_agreement) * (n_methods_agreeing / 8.0) + 0.1, 0.0, 1.0
    ))

    # Symmetry from angular std of the radial profile near the outer ring.
    outer_idx = int(np.clip(outer_radius, 0, len(profile.mean_intensity) - 1))
    local_std = float(profile.std_intensity[max(0, outer_idx - 3):outer_idx + 3].mean())
    local_mean = float(profile.mean_intensity[max(0, outer_idx - 3):outer_idx + 3].mean()) + 1e-6
    symmetry_score = float(np.clip(1.0 - (local_std / local_mean), 0.0, 1.0))

    detected = halo_width > max(2.0, 0.05 * outer_radius) and confidence > 0.25
    if not detected:
        messages.append("Ring boundary too weak/ambiguous to confirm a halo pattern.")

    return HaloDetectionResult(
        detected=detected,
        center_x=roi.center_x, center_y=roi.center_y,
        inner_radius=round(inner_radius, 2), outer_radius=round(outer_radius, 2),
        halo_width=round(halo_width, 2),
        circularity=round(circularity, 4) if circularity else round(symmetry_score, 4),
        symmetry_score=round(symmetry_score, 4),
        confidence=round(confidence, 4),
        method_agreement={
            "profile": (profile_inner, profile_outer),
            "edge": (edge_inner, edge_outer),
            "hough": (hough_inner, hough_outer),
            "segmentation": (seg_inner, seg_outer),
            "inner_agreement": round(inner_agreement, 3),
            "outer_agreement": round(outer_agreement, 3),
        },
        radial_profile=profile,
        polar_image=polar_image,
        messages=messages,
    )
