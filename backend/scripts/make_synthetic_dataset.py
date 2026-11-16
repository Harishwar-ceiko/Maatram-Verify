"""Generate the synthetic evaluation corpus.

Usage:
    python scripts/make_synthetic_dataset.py [--keep]

`--keep` reuses an existing corpus. The default rewrites it from the configured
seed so every run is reproducible.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.synthetic import generate_dataset, load_dataset  # noqa: E402


def main() -> None:
    keep = "--keep" in sys.argv[1:]
    dataset = load_dataset() if keep else generate_dataset(force=True)
    if dataset is None:
        dataset = generate_dataset(force=True)
    print(f"{dataset['dataset']}: {len(dataset['cases'])} mark sheets, {len(dataset['photos'])} photo fixtures")
    print(f"root: {Path(__file__).resolve().parents[1] / 'synthetic'}")


if __name__ == "__main__":
    main()
