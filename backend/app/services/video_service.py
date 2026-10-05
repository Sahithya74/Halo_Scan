"""Video analysis: sample frames from a short clip, analyse each, aggregate.

The upload is written to a temp file only because OpenCV's decoder needs a path; the file is
deleted as soon as decoding finishes. Analysis stops early if the time budget is spent, so a
result is always returned well inside a minute.
"""
from __future__ import annotations

import os
import tempfile
import time

import cv2
import numpy as np

from app.config import settings
from app.schemas.analysis import AnalysisResult, FrameResult, VideoSchema
from app.services.analysis_service import Aggregate, FrameAnalysis, analyze_frame, assemble_result, persist
from app.services.visualization_service import encode_jpeg, plot_frame_timeline

_SUFFIX = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}


class VideoError(ValueError):
    pass


def _read_sampled_frames(data: bytes, content_type: str) -> tuple[list[tuple[float, np.ndarray]], float, float]:
    fd, path = tempfile.mkstemp(suffix=_SUFFIX.get(content_type, ".mp4"))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        # Pass 1: grab (decode without converting/keeping) every frame to get real timestamps.
        # Browser MediaRecorder WebM is variable-frame-rate and often reports a bogus FPS and
        # frame count, so container metadata can't be trusted for duration or seeking.
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise VideoError("Could not decode the video. Try MP4 or WebM, or upload a photo instead.")
        reported_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        times: list[float] = []
        while cap.grab():
            times.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0)
            if len(times) > 120 * settings.max_video_seconds * 2:  # hard stop for absurd inputs
                break
        cap.release()
        n_frames = len(times)
        if n_frames == 0:
            raise VideoError("The video contains no readable frames.")
        fps_guess = reported_fps if 1.0 <= reported_fps <= 120.0 else 30.0
        duration = times[-1] + 1.0 / fps_guess if times[-1] > 0 else n_frames / fps_guess
        if duration > settings.max_video_seconds + 0.5:
            raise VideoError(f"Video is {duration:.1f}s long; the maximum is {settings.max_video_seconds:.0f}s.")

        n = min(settings.video_frames_to_sample, n_frames)
        # Skip the first/last 5% (camera settling, hand moving to stop) when long enough.
        lo, hi = (int(n_frames * 0.05), int(n_frames * 0.95) - 1) if n_frames > 20 else (0, n_frames - 1)
        wanted = set(np.linspace(lo, max(lo, hi), n).astype(int).tolist())

        # Pass 2: sequential read, keeping only the sampled frames (no seeking — unreliable on WebM).
        cap = cv2.VideoCapture(path)
        sampled = []
        for idx in range(max(wanted) + 1):
            if not cap.grab():
                break
            if idx in wanted:
                ok, img = cap.retrieve()
                if ok:
                    t = times[idx] if times[-1] > 0 else idx / fps_guess
                    sampled.append((t, img))
        cap.release()
        if not sampled:
            raise VideoError("Could not read frames from the video.")
        return sampled, duration, n_frames / duration if duration else fps_guess
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _aggregate(usable: list[FrameAnalysis]) -> tuple[Aggregate, float, float]:
    classes = list(usable[0].outcome.ensemble.class_probabilities)
    probs = np.array([[f.outcome.ensemble.class_probabilities[c] for c in classes] for f in usable])
    mean = probs.mean(axis=0)
    winner = int(np.argmax(mean))
    votes = [int(np.argmax(p)) for p in probs]
    agreement = votes.count(winner) / len(votes)
    stability = float(np.clip(1.0 - probs[:, winner].std() * 2, 0.0, 1.0))
    disagreement = float(np.mean([f.outcome.ensemble.disagreement for f in usable]))
    frames_uncertain = sum(f.outcome.uncertainty.is_uncertain for f in usable) / len(usable)

    reasons = []
    if agreement < 0.6:
        reasons.append("Frames disagree on the most likely class.")
    if frames_uncertain > 0.5:
        reasons.append("Most frames were individually flagged as uncertain.")
    uncertain = bool(reasons) or float(mean[winner]) < settings.min_confidence_for_confident_label
    return (
        Aggregate(class_probabilities={c: float(v) for c, v in zip(classes, mean)}, label=classes[winner],
                  confidence=float(mean[winner]), disagreement=disagreement, uncertain=uncertain,
                  extra_reasons=reasons),
        agreement, stability,
    )


def run_video_analysis(
    data: bytes, content_type: str, *, patient_id: int | None = None, patient_code: str | None = None,
    performed_by: int | None = None,
) -> AnalysisResult:
    started = time.perf_counter()
    sampled, duration, fps = _read_sampled_frames(data, content_type)

    analyzed: list[tuple[float, FrameAnalysis]] = []
    for t, img in sampled:
        if time.perf_counter() - started > settings.analysis_time_budget_seconds:
            break
        analyzed.append((t, analyze_frame(img)))

    usable = [f for _, f in analyzed if f.outcome is not None]
    # Best frame for the diagrams: highest quality among usable frames, else among all.
    pool = usable or [f for _, f in analyzed]
    best = max(pool, key=lambda f: f.quality.score)

    aggregate = agreement = stability = None
    if usable:
        aggregate, agreement, stability = _aggregate(usable)

    frame_results = []
    for i, (t, f) in enumerate(analyzed):
        o = f.outcome
        frame_results.append(FrameResult(
            index=i, time_s=round(t, 2), quality_status=f.quality.status,
            halo_detected=bool(f.halo and f.halo.detected),
            research_classification=o.ensemble.predicted_label if o else None,
            confidence=o.ensemble.confidence if o else None,
            thumbnail_jpeg_base64=encode_jpeg(f.image_bgr, max_dim=160, quality=70),
        ))
    timeline = plot_frame_timeline(
        [t for t, _ in analyzed],
        [f.outcome.ensemble.class_probabilities if f.outcome else None for _, f in analyzed],
    ) if usable else None

    video = VideoSchema(
        duration_s=round(duration, 2), fps=round(fps, 2), frames_sampled=len(analyzed),
        frames_used=len(usable), frame_agreement=round(agreement or 0.0, 3),
        stability=round(stability or 0.0, 3), frames=frame_results,
    )
    result = assemble_result(best, input_type="video", started=started, patient_code=patient_code,
                             aggregate=aggregate, video=video, frame_timeline_png=timeline)
    persist(result, patient_id, performed_by)
    return result
