"""Regenerate source-backed Stage 12 figures offline."""
import argparse
from pathlib import Path

from topoastero.hybrid.features import load_config
from topoastero.hybrid.plotting import build_figures

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    result = build_figures(root, load_config(root))
    print(f"Stage 12 figures: {len(result['figures'])} source-backed sets")
