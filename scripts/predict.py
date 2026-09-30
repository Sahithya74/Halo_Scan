#!/usr/bin/env python
"""CLI: run the full analysis pipeline on a single image file.

This is the primary way to verify the whole spine (quality -> ROI -> halo -> features ->
ensemble -> calibration -> uncertainty -> SHAP -> decision message) end-to-end without
Flutter, since Flutter isn't installed on this machine yet.

Usage: python scripts/predict.py path/to/image.png [--save-overlay out.png]
"""
import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.models.registry import registry  # noqa: E402
from app.services.analysis_service import run_full_analysis  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_path", type=Path)
    parser.add_argument("--save-overlay", type=Path, default=None)
    args = parser.parse_args()

    if not args.image_path.exists():
        print(f"File not found: {args.image_path}", file=sys.stderr)
        sys.exit(1)

    registry.load()
    if not registry.loaded:
        print("WARNING: trained models not found — run scripts/train.py first. "
              "Continuing with CV-only output (no classification).", file=sys.stderr)

    image_bytes = args.image_path.read_bytes()
    result = run_full_analysis(image_bytes)

    result_dict = result.model_dump()
    overlay_b64 = None
    if result_dict.get("visualizations"):
        overlay_b64 = result_dict["visualizations"].pop("overlay_png_base64", None)
        result_dict["visualizations"].pop("radial_profile_png_base64", None)
        result_dict["visualizations"].pop("probability_chart_png_base64", None)
        result_dict["visualizations"].pop("feature_importance_png_base64", None)
        result_dict["visualizations"]["_note"] = "base64 image payloads omitted from console output"

    print(json.dumps(result_dict, indent=2))

    if args.save_overlay and overlay_b64:
        args.save_overlay.write_bytes(base64.b64decode(overlay_b64))
        print(f"\nOverlay saved to {args.save_overlay}")


if __name__ == "__main__":
    main()
