"""Validate the complete Stage 2 contract from a source checkout."""

from __future__ import annotations

from pathlib import Path

from topoastero.stage2_validation import validate_stage2


def main() -> None:
    root = Path(__file__).parents[1]
    errors = validate_stage2(root, require_prior_stages=True)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Stage 2 data, provenance, and canonical-model contract: PASS")


if __name__ == "__main__":
    main()
