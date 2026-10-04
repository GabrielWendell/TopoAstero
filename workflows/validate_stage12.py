"""Validate Stage 12 and previous-stage contracts offline."""

import argparse
from pathlib import Path

from topoastero.hybrid.validation import validate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args()
    issues = validate(args.root.resolve(), prior=not args.without_prior_stages)
    if issues:
        raise SystemExit("\n".join(issues))
    print("Stage 12 implementation: PASS; scientific claims remain evidence-dependent")
