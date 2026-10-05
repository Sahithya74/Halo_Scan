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


def _label(image: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    """Draws `text` with a filled background rectangle so it stays legible over any
    underlying image content, rather than relying on cv2's unreadable plain-text default."""
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
    (w, h), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = origin
    cv2.rectangle(image, (x - 4, y - h - 6), (x + w + 4, y + baseline + 2), (255, 255, 255), -1)
    cv2.rectangle(image, (x - 4, y - h - 6), (x + w + 4, y + baseline + 2), color, 1)
    cv2.putText(image, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_ring_overlay(image_bgr: np.ndarray, roi: ROI, halo: HaloDetectionResult) -> str:
    """Draws the ROI/ring circles plus text labels giving the actual measured radii —
    this is the "measurement diagram", not just a decorative overlay."""
    overlay = image_bgr.copy()
    h, w = overlay.shape[:2]
    roi_center = (int(roi.center_x), int(roi.center_y))
    halo_center = (int(halo.center_x), int(halo.center_y))
    roi_color = (255, 200, 0)
    inner_color = (0, 0, 220)
    outer_color = (0, 170, 0)

    cv2.circle(overlay, roi_center, int(roi.radius), roi_color, 2)
    if halo.detected:
        cv2.circle(overlay, halo_center, int(halo.inner_radius), inner_color, 2)
        cv2.circle(overlay, halo_center, int(halo.outer_radius), outer_color, 2)

        # Radius lines + labels: outer measured toward the upper-right, inner toward the
        # lower-right, so the two labels never sit on top of each other.
        for radius, color, text, dy_sign in (
            (halo.outer_radius, outer_color, f"outer r={halo.outer_radius:.0f}px", -1),
            (halo.inner_radius, inner_color, f"inner r={halo.inner_radius:.0f}px", 1),
        ):
            end = (
                int(halo_center[0] + radius * 0.707),
                int(halo_center[1] + dy_sign * radius * 0.707),
            )
            cv2.line(overlay, halo_center, end, color, 1, cv2.LINE_AA)
            label_pt = (
                int(np.clip(end[0] + 6, 8, w - 150)),
                int(np.clip(end[1] + (dy_sign * 14 if dy_sign > 0 else -4), 20, h - 40)),
            )
            _label(overlay, text, label_pt, color)
        _label(overlay, f"ring width={halo.halo_width:.0f}px", (12, h - 16), outer_color)
    else:
        _label(overlay, "no halo detected", (12, h - 16), inner_color)

    # Colour legend so the diagram reads on its own, without the web page around it.
    for i, (text, color) in enumerate((
        ("sample region", roi_color), ("outer ring", outer_color), ("inner stain", inner_color),
    )):
        y = 18 + i * 18
        cv2.circle(overlay, (16, y - 4), 5, color, -1)
        cv2.putText(overlay, text, (26, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (40, 40, 40), 1, cv2.LINE_AA)

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


LABEL_DISPLAY = {
    "csf_like": "CSF-like", "saline_like": "Saline-like", "saliva_like": "Saliva-like",
    "tear_like": "Tear-like", "nasal_mucus_like": "Nasal-mucus-like", "other": "Other / atypical",
}
CLASS_COLOR = {
    "csf_like": "#3d6e73", "saline_like": "#4f7fb0", "saliva_like": "#c17a3d",
    "tear_like": "#7a6fb3", "nasal_mucus_like": "#9a8a2e", "other": "#8d8378",
}


def plot_probability_distribution(class_probabilities: dict[str, float]) -> str:
    """The "which fluid, how confident" diagram — every predicted class's share of the
    probability mass, sorted so the winning class is immediately visible."""
    ranked = sorted(class_probabilities.items(), key=lambda kv: kv[1], reverse=True)
    labels = [LABEL_DISPLAY.get(k, k) for k, _ in ranked]
    values = [v * 100 for _, v in ranked]
    colors = [CLASS_COLOR.get(k, "#718096") for k, _ in ranked]

    fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=120)
    bars = ax.barh(labels, values, color=colors, height=0.55)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Probability (%)")
    ax.set_title("Predicted Class Probabilities", fontsize=12, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for bar, v in zip(bars, values):
        ax.text(min(v + 2.5, 92), bar.get_y() + bar.get_height() / 2, f"{v:.1f}%",
                 va="center", fontsize=9, fontweight="bold")
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


def encode_jpeg(image_bgr: np.ndarray, max_dim: int = 480, quality: int = 82) -> str:
    h, w = image_bgr.shape[:2]
    scale = min(1.0, max_dim / float(max(h, w)))
    if scale < 1.0:
        image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to encode JPEG")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def plot_comparison_radar(
    features: list[str], feature_labels: dict[str, str], sample_values: dict[str, float],
    class_profiles: dict[str, dict[str, dict[str, float]]], highlight: str | None = None,
) -> str:
    """Sample (black) vs each class's reference profile on the same normalized axes."""
    n = len(features)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles_closed = angles + angles[:1]

    def normalize(feat: str, value: float) -> float:
        values = [p[feat]["mean"] for p in class_profiles.values()] + [sample_values[feat]]
        lo, hi = min(values), max(values)
        span = (hi - lo) or 1.0
        return 0.1 + 0.9 * (value - lo) / span

    fig = plt.figure(figsize=(5.2, 4.4), dpi=120)
    ax = fig.add_subplot(111, polar=True)
    for cls, profile in class_profiles.items():
        pts = [normalize(f, profile[f]["mean"]) for f in features]
        pts += pts[:1]
        strong = cls == highlight
        ax.plot(angles_closed, pts, color=CLASS_COLOR.get(cls, "#888"),
                linewidth=2.2 if strong else 1.1, alpha=1.0 if strong else 0.55,
                label=LABEL_DISPLAY.get(cls, cls))
        if strong:
            ax.fill(angles_closed, pts, color=CLASS_COLOR.get(cls, "#888"), alpha=0.12)
    sample_pts = [normalize(f, sample_values[f]) for f in features]
    sample_pts += sample_pts[:1]
    ax.plot(angles_closed, sample_pts, color="#111", linewidth=2.6, label="This sample")
    ax.scatter(angles, sample_pts[:-1], color="#111", s=18, zorder=5)
    ax.set_xticks(angles)
    ax.set_xticklabels([feature_labels[f] for f in features], fontsize=7.5)
    ax.set_yticklabels([])
    ax.set_ylim(0, 1.05)
    ax.set_title("Sample vs class reference profiles", fontsize=11, fontweight="bold", pad=14)
    ax.legend(loc="upper right", bbox_to_anchor=(1.42, 1.12), fontsize=7, frameon=False)
    fig.tight_layout()
    return _fig_to_base64(fig)


def plot_frame_timeline(times: list[float], frame_probs: list[dict[str, float] | None]) -> str:
    """Probability of each class across the sampled video frames."""
    fig, ax = plt.subplots(figsize=(5.8, 3.2), dpi=120)
    classes = sorted({c for p in frame_probs if p for c in p})
    for cls in classes:
        xs = [t for t, p in zip(times, frame_probs) if p]
        ys = [p[cls] * 100 for p in frame_probs if p]
        ax.plot(xs, ys, marker="o", markersize=4, linewidth=1.8,
                color=CLASS_COLOR.get(cls, "#888"), label=LABEL_DISPLAY.get(cls, cls))
    skipped = [t for t, p in zip(times, frame_probs) if not p]
    for t in skipped:
        ax.axvline(t, color="#c53030", alpha=0.25, linewidth=6)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Video time (s)" + ("   (red bands = frames rejected)" if skipped else ""))
    ax.set_ylabel("Probability (%)")
    ax.set_title("Prediction across video frames", fontsize=11, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.28), frameon=False)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")
