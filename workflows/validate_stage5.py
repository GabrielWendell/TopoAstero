"""Validate the complete offline Stage 5 contract."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from topoastero.stage5_validation import validate_stage5


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_stage5(args.root, require_prior_stages=not args.without_prior_stages)
    if errors:
        raise SystemExit("\n".join(errors))
    print("Stage 5 TDA core and representation-audit contract: PASS")


if __name__ == "__main__":
    main()
