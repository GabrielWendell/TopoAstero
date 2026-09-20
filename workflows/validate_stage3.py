"""Validate Stage 3 and all prerequisite-stage contracts."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from topoastero.stage3_validation import validate_stage3


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_stage3(args.root, require_prior_stages=not args.without_prior_stages)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Stage 3 classical baseline and observation-model contract: PASS")


if __name__ == "__main__":
    main()
