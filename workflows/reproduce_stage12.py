"""One command: grouped development, supplied raw transfer, then honest report."""

import argparse
from pathlib import Path

from topoastero.hybrid.features import load_config
from topoastero.hybrid.pipeline import run_development, run_transfer
from topoastero.hybrid.plotting import build_figures
from topoastero.hybrid.reporting import build_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    cfg = load_config(root)
    run_development(root, cfg)
    run_transfer(root, args.cache_dir.resolve(), cfg)
    build_figures(root, cfg)
    print("Stage 12 reproduction complete; scientific G12: " + build_report(root, cfg)["status"])
