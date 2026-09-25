"""Validate Stage 7 deliverables from the repository root."""

from __future__ import annotations

import argparse
from pathlib import Path

from topoastero.stage7_validation import validate_stage7


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args()
    errors = validate_stage7(
        args.root,
        require_prior_stages=not args.without_prior_stages,
    )
    if errors:
        raise SystemExit("\n".join(errors))
    print("Stage 7 delay-topology and phase-information contract: PASS")


if __name__ == "__main__":
    main()
