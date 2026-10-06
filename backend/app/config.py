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
    class_labels: tuple[str, ...] = (
        "csf_like", "saline_like", "saliva_like", "tear_like", "nasal_mucus_like", "other",
    )

    # --- Misc ---
    model_version: str = "demo-synthetic-v2"
    api_title: str = "Halo Scan Decision-Support API"

    # --- Research-mode auth ---
    # /api/research/* needs an admin session. A matching X-API-Key header is accepted as
    # an alternative for headless scripts, only when HALO_RESEARCH_API_KEY is set.
    research_api_key: str = ""

    # --- Security ---
    secrets_dir: Path = BACKEND_ROOT / "secrets"
    data_key: str = ""  # HALO_DATA_KEY; when empty a key is generated into secrets_dir
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    ip_max_failed_logins: int = 20  # per IP per lockout window, across all usernames
    cookie_secure: bool = False  # set True (HALO_COOKIE_SECURE) when served over HTTPS
    cors_origins: tuple[str, ...] = ()
    min_password_length: int = 10

    # Phone photos (e.g. 4032x3024) are downscaled to this longest side before analysis.
    # Without it, diagrams were rendered at full resolution (14 MB responses) and analysis
    # time grew with megapixels. 1280 keeps far more detail than the ring measurements need.
    max_analysis_dimension: int = 1280

    # --- Video ---
    max_upload_bytes: int = 25 * 1024 * 1024
    max_video_seconds: float = 15.0
    video_frames_to_sample: int = 8
    analysis_time_budget_seconds: float = 45.0


settings = Settings()
settings.uploads_dir.mkdir(parents=True, exist_ok=True)
settings.models_dir.mkdir(parents=True, exist_ok=True)
settings.secrets_dir.mkdir(parents=True, exist_ok=True)
