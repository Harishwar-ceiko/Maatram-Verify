"""Run the accuracy evaluation and print the headline metrics.

Usage:
    python scripts/evaluate.py [--dataset-only]

`--dataset-only` regenerates the synthetic corpus without running OCR.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.init_db import init_db  # noqa: E402
from app.services.evaluation import run_evaluation  # noqa: E402
from app.services.synthetic import generate_dataset  # noqa: E402


def main() -> int:
    if "--dataset-only" in sys.argv[1:]:
        data = generate_dataset(force=True)
        print(f"{data['dataset']}: {len(data['cases'])} cases, {len(data['photos'])} photos")
        return 0

    init_db()
    run_id = run_evaluation()
    print(f"stored accuracy run {run_id}")
    print("report: backend/reports/accuracy.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
