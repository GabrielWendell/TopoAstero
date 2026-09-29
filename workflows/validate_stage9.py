"""Standalone Stage 9 implementation and independent-review gate validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from topoastero.stage9_validation import validate_stage9


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--without-prior-stages", action="store_true")
    args = parser.parse_args()
    issues = validate_stage9(args.root, require_prior_stages=not args.without_prior_stages)
    if issues:
        raise SystemExit("\n".join(issues))
    gate = json.loads((args.root / "reports/stage9/G9_ACCEPTANCE.json").read_text())
    print(f"Stage 9 implementation: PASS; scientific G9: {gate['status']}")


if __name__ == "__main__":
    main()
