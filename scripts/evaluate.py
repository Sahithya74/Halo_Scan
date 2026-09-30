#!/usr/bin/env python
"""CLI: evaluate the trained ensemble on the synthetic test split. Writes metrics into
backend/trained_models/metadata.json — used to fill in docs/validation.md by hand."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services.research_service import evaluate_models  # noqa: E402


def main() -> None:
    report = evaluate_models()
    print(json.dumps(report, indent=2))
    print("\nReminder: metrics above are computed on SYNTHETIC data only — not a clinical "
          "validation study. See docs/validation.md.")


if __name__ == "__main__":
    main()
