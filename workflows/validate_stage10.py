"""Standalone offline Stage 10 completion and independent-review gate validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from topoastero.stage10_validation import validate_stage10


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args()
    errors = validate_stage10(args.root, require_prior_stages=not args.without_prior_stages)
    if errors:
        raise SystemExit("\n".join(errors))
    gate = json.loads((args.root / "reports/stage10/G10_ACCEPTANCE.json").read_text())
    print(f"Stage 10 implementation: PASS; scientific G10: {gate['status']}")


if __name__ == "__main__":
    main()
