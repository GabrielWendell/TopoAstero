"""Validate the complete offline Stage 6 contract."""

from __future__ import annotations

from pathlib import Path

from topoastero.stage6_validation import validate_stage6


def main() -> None:
    root = Path(__file__).parents[1]
    errors = validate_stage6(root, require_prior_stages=True)
    if errors:
        print("Stage 6 PSD-topology contract: FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print("Stage 6 persistent power-spectrum topology contract: PASS")


if __name__ == "__main__":
    main()

