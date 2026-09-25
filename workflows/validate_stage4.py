"""Validate the complete Stage 4 gate from the repository root."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from topoastero.stage4_validation import validate_stage4


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_stage4(args.root, require_prior_stages=not args.without_prior_stages)
    if errors:
        print("Stage 4 analytic/simulation contract: FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Stage 4 analytic/simulation contract: PASS")


if __name__ == "__main__":
    main()
