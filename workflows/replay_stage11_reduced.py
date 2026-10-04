"""Recompute available headline estimates from archived monthly spectra, offline."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from topoastero.population import estimate_points, fit_population_background
from topoastero.population_acquisition import load_config
from topoastero.population_store import contained, read_json


def replay(root: Path) -> int:
    cfg = load_config(root)
    checked = 0
    for path in sorted(contained(root, cfg["output"]).glob("*/stars/*/monthly_spectra.npz")):
        original = read_json(path.parent / "analysis.json")
        with np.load(path, allow_pickle=False) as stored:
            f, matrix, weights = stored["frequency_uHz"], stored["spectra"], stored["exposure_cadences"]
        mean = np.average(matrix, axis=0, weights=weights)
        background = fit_population_background(f, mean, cfg)[0]
        diagnostic = estimate_points(f, mean, background, cfg)
        for key in ("classical_numax", "classical_dnu", "topology_numax", "topology_dnu", "prominence_max_absolute_difference"):
            if not np.isclose(original[key], diagnostic[key], atol=1e-8, rtol=1e-9):
                raise ValueError(f"Stage 11 reduced replay mismatch: {original['stable_star_id']} {key}")
        checked += 1
    if not checked:
        raise ValueError("no observational monthly spectra available for reduced replay")
    return checked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    count = replay(args.root.resolve())
    print(f"Stage 11 reduced replay: PASS ({count} stars); not a raw-product or population confirmation reproduction")


if __name__ == "__main__":
    main()
