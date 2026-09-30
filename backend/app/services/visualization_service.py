"""Overlay images and graphs (spec sections 18-19). Everything returned as base64 PNG so
the API stays a plain JSON contract usable by Flutter, curl, or the predict.py CLI alike.
"""
from __future__ import annotations

import base64
import io

import cv2
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.image_processing.halo_detection import HaloDetectionResult, RadialProfile
from app.image_processing.roi_detection import ROI


def _encode_png(image_bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("Failed to encode overlay image")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def draw_ring_overlay(image_bgr: np.ndarray, roi: ROI, halo: HaloDetectionResult) -> str:
    overlay = image_bgr.copy()
    roi_center = (int(roi.center_x), int(roi.center_y))
    halo_center = (int(halo.center_x), int(halo.center_y))

    cv2.circle(overlay, roi_center, int(roi.radius), (255, 200, 0), 2)  # ROI: cyan-ish
    if halo.detected:
        cv2.circle(overlay, halo_center, int(halo.inner_radius), (0, 0, 255), 2)   # inner: red
        cv2.circle(overlay, halo_center, int(halo.outer_radius), (0, 220, 0), 2)   # outer: green
    cv2.drawMarker(overlay, halo_center, (0, 165, 255), markerType=cv2.MARKER_CROSS,
                    markerSize=14, thickness=2)
    return _encode_png(overlay)


def plot_radial_intensity(profile: RadialProfile, inner_radius: float, outer_radius: float) -> str:
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=110)
    ax.plot(profile.radii, profile.mean_intensity, color="#2b6cb0", linewidth=1.6, label="mean intensity")
    ax.fill_between(
        profile.radii,
        profile.mean_intensity - profile.std_intensity,
        profile.mean_intensity + profile.std_intensity,
        color="#2b6cb0", alpha=0.15, label="angular std",
    )
    if inner_radius > 0:
        ax.axvline(inner_radius, color="#c53030", linestyle="--", linewidth=1, label="inner radius")
    if outer_radius > 0:
        ax.axvline(outer_radius, color="#2f855a", linestyle="--", linewidth=1, label="outer radius")
    ax.set_xlabel("Radius (px)")
    ax.set_ylabel("Intensity")
    ax.set_title("Radial Intensity Profile")
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    return _fig_to_base64(fig)


def plot_probability_distribution(class_probabilities: dict[str, float]) -> str:
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=110)
    labels = list(class_probabilities.keys())
    values = [class_probabilities[k] * 100 for k in labels]
    colors = ["#2b6cb0", "#2f855a", "#c53030", "#805ad5", "#718096"][: len(labels)]
    ax.bar(labels, values, color=colors)
    ax.set_ylabel("Probability (%)")
    ax.set_title("Research Classification Probabilities")
    ax.set_ylim(0, 100)
    for i, v in enumerate(values):
        ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=8)
    fig.autofmt_xdate(rotation=20)
    fig.tight_layout()
    return _fig_to_base64(fig)


def plot_feature_importance(top_features: list[dict[str, float]]) -> str:
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=110)
    names = [f["feature"] for f in top_features][::-1]
    values = [f["shap_value"] for f in top_features][::-1]
    colors = ["#2f855a" if v >= 0 else "#c53030" for v in values]
    ax.barh(names, values, color=colors)
    ax.set_xlabel("SHAP value (impact on predicted class)")
    ax.set_title("Top Contributing Features")
    fig.tight_layout()
    return _fig_to_base64(fig)


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")
