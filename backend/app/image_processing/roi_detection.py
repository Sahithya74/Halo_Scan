"""Sample/drop region-of-interest detection.

Pipeline: grayscale -> Gaussian blur -> adaptive threshold -> morphology -> contours,
cross-checked with a Hough circle pass. Falls back to an image-centered ROI (with low
confidence) if neither method finds a plausible region, and the caller may override with
a manual ROI (spec section 6).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.config import settings
from app.image_processing.preprocessing import gaussian_blur, to_grayscale


@dataclass
class ROI:
    center_x: float
    center_y: float
    radius: float
    method: str  # "contour" | "hough" | "fallback_center" | "manual"
    confidence: float


def _contour_candidate(gray: np.ndarray) -> ROI | None:
    blurred = gaussian_blur(gray, 7)
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 35, 5
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = gray.shape[:2]
    image_area = h * w
    best = None
    best_score = -1.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 0.01 * image_area or area > 0.95 * image_area:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(c)
        circle_area = np.pi * radius * radius
        circularity = area / circle_area if circle_area > 0 else 0
        # Prefer large, roughly circular, centrally located contours.
        center_dist = np.hypot(cx - w / 2, cy - h / 2) / (0.5 * min(h, w))
        score = circularity * 0.6 + (area / image_area) * 0.3 - center_dist * 0.1
        if score > best_score:
            best_score = score
            best = ROI(center_x=cx, center_y=cy, radius=radius, method="contour",
                       confidence=float(np.clip(circularity, 0, 1)))
    return best


def _hough_candidate(gray: np.ndarray) -> ROI | None:
    blurred = gaussian_blur(gray, 9)
    h, w = gray.shape[:2]
    min_dist = min(h, w) * settings.hough_min_dist_ratio
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=settings.hough_dp,
        minDist=min_dist,
        param1=settings.canny_high,
        param2=40,
        minRadius=int(0.05 * min(h, w)),
        maxRadius=int(0.48 * min(h, w)),
    )
    if circles is None:
        return None
    circles = np.round(circles[0]).astype(int)
    # Prefer the circle closest to image center (the sample pad is expected roughly centered).
    center = np.array([w / 2, h / 2])
    best = min(circles, key=lambda c: np.hypot(c[0] - center[0], c[1] - center[1]))
    return ROI(center_x=float(best[0]), center_y=float(best[1]), radius=float(best[2]),
               method="hough", confidence=0.7)


def detect_sample_region(image_bgr: np.ndarray, manual_roi: ROI | None = None) -> ROI:
    if manual_roi is not None:
        return manual_roi

    gray = to_grayscale(image_bgr)
    contour_roi = _contour_candidate(gray)
    hough_roi = _hough_candidate(gray)

    if contour_roi and hough_roi:
        dist = np.hypot(contour_roi.center_x - hough_roi.center_x,
                         contour_roi.center_y - hough_roi.center_y)
        agree = dist < 0.15 * min(gray.shape[:2])
        chosen = contour_roi if contour_roi.confidence >= hough_roi.confidence else hough_roi
        chosen.confidence = min(1.0, chosen.confidence + (0.2 if agree else 0.0))
        return chosen
    if contour_roi:
        return contour_roi
    if hough_roi:
        return hough_roi

    h, w = gray.shape[:2]
    return ROI(center_x=w / 2, center_y=h / 2, radius=min(h, w) * 0.35,
               method="fallback_center", confidence=0.2)
