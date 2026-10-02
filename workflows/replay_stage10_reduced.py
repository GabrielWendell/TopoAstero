"""Offline reduced-spectrum replay; does not substitute for raw-product reproduction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from run_stage10_rudy import ROOT, full_diagnostics, read_csv

from topoastero.config import load_yaml


def replay(root: Path) -> None:
    cfg = load_yaml(root / "configs/stage10_rudy.yaml")
    spectra = read_csv(root / "results/stage10/branch_spectra.csv")
    summary = json.loads((root / "results/stage10/summary.json").read_text())
    primary = [row for row in spectra if row["branch_id"] == "PP-01"]
    frequency, power, background = (np.array([float(row[key]) for row in primary]) for key in ("frequency_uHz", "power_ppm2_per_uHz", "background_ppm2_per_uHz"))
    actual = full_diagnostics(frequency, power, background, cfg)
    if any(not np.isclose(value, summary["primary"][key], atol=1e-8, rtol=1e-9) for key, value in actual.items()):
        raise ValueError("reduced-spectrum replay differs from the frozen headline diagnostics")
    print("Stage 10 offline reduced replay: PASS (not a raw-product or human reproduction)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    replay(args.root)


if __name__ == "__main__":
    main()
