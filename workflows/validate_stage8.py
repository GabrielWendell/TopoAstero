"""Standalone Stage 8 acceptance entry point (also available in the package CLI)."""

from __future__ import annotations

import argparse
from pathlib import Path

from topoastero.stage8_validation import validate_stage8


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args()
    issues = validate_stage8(args.root, require_prior_stages=not args.without_prior_stages)
    if issues:
        raise SystemExit("\n".join(issues))
    print("G8 cylindrical geometry and bounded-inference contract: PASS")


if __name__ == "__main__":
    main()
