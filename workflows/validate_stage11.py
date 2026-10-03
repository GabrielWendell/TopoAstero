"""Offline validator. --require-confirmation also enforces the scientific G11 gate."""

from __future__ import annotations

import argparse
from pathlib import Path

from topoastero.population_store import read_json
from topoastero.stage11_validation import validate_stage11


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--without-prior-stages", action="store_true")
    parser.add_argument("--require-confirmation", action="store_true")
    args = parser.parse_args()
    issues = validate_stage11(args.root, require_prior_stages=not args.without_prior_stages, require_confirmation=args.require_confirmation)
    if issues:
        raise SystemExit("\n".join(issues))
    gate = read_json(args.root / "reports/stage11/G11_ACCEPTANCE.json")
    print(f"Stage 11 implementation: PASS; scientific G11: {gate['status']}")


if __name__ == "__main__":
    main()
