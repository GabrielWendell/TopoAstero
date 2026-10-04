"""Reconcile, acquire, run non-holdout batches and build evidence with one command.

No confirmation is opened automatically. Complete data acquisition/development QA
and sign the exact release before using open-confirmation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from topoastero.population_acquisition import acquire_population, load_config
from topoastero.population_pipeline import run_role
from topoastero.population_reporting import build_report
from topoastero.population_store import contained


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    root, cache = args.root.resolve(), args.cache_dir.resolve()
    cfg = load_config(root)
    acquire_population(root, cache, cfg, download=args.download)
    for role in ("development", "internal_validation", "descriptive_benchmark"):
        run_role(root, cache, cfg, role, contained(root, cfg["output"]) / role)
    gate = build_report(root, cfg)
    print(f"Stage 11 non-holdout reproduction complete; G11: {gate['status']}")


if __name__ == "__main__":
    main()
