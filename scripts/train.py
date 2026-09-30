#!/usr/bin/env python
"""CLI: train + calibrate the classical ML ensemble on the synthetic training split."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.research_service import train_models  # noqa: E402


def main() -> None:
    metadata = train_models()
    print(json.dumps(metadata, indent=2))
    print(f"\nTrained on {metadata['n_train_samples']} samples "
          f"({metadata['n_dropped_no_halo']} dropped — halo not detected).")
    print("Models saved under backend/trained_models/. Run scripts/evaluate.py next.")


if __name__ == "__main__":
    main()
