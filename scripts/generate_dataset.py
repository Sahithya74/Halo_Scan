#!/usr/bin/env python
"""CLI: generate the synthetic halo-pattern dataset. See docs/dataset.md for methodology."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.research_service import generate_synthetic_dataset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-per-class", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = generate_synthetic_dataset(sessions_per_class=args.sessions_per_class, seed=args.seed)
    print(f"Generated {result['n_samples']} synthetic samples -> {result['metadata_path']}")
    print("Reminder: this is SYNTHETIC/DEMO data. See docs/dataset.md for limitations.")


if __name__ == "__main__":
    main()
