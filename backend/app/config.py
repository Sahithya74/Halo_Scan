"""Central configuration for the Halo Scan backend.

All thresholds live here so the pipeline's behavior can be tuned/audited in one place
instead of being scattered as magic numbers through the image-processing and ML code.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HALO_", env_file=".env", extra="ignore")

    # --- Paths ---
    dataset_dir: Path = BACKEND_ROOT / "datasets" / "synthetic"
    models_dir: Path = BACKEND_ROOT / "trained_models"
    uploads_dir: Path = BACKEND_ROOT / "uploads"
    history_db_path: Path = BACKEND_ROOT / "analysis_history.db"

    # --- Image quality thresholds ---
    blur_laplacian_var_min_good: float = 120.0
    blur_laplacian_var_min_acceptable: float = 60.0
    brightness_min: float = 40.0
    brightness_max: float = 238.0
    contrast_std_min: float = 15.0
    overexposed_pixel_fraction_max: float = 0.15
    underexposed_pixel_fraction_max: float = 0.15
    min_image_dimension: int = 300

    # Overall quality score (0-1) bands
    quality_score_good_min: float = 0.75
    quality_score_acceptable_min: float = 0.45

    # --- Halo/ROI detection ---
    hough_dp: float = 1.2
    hough_min_dist_ratio: float = 0.5  # fraction of image min-dimension
    canny_low: int = 50
    canny_high: int = 150
    radial_profile_samples: int = 180  # angular samples around the circle

    # --- Ensemble / uncertainty ---
    disagreement_uncertain_threshold: float = 0.35
    ood_mahalanobis_threshold: float = 4.0
    min_confidence_for_confident_label: float = 0.55

    # --- Classes ---
    class_labels: tuple[str, ...] = ("csf_like", "saline_like", "saliva_like", "other")

    # --- Misc ---
    model_version: str = "demo-synthetic-v1"
    api_title: str = "Halo Scan Decision-Support API"


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.models_dir.mkdir(parents=True, exist_ok=True)
