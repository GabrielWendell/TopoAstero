"""Validate the complete Stage 1 evidence contract from a source checkout."""

from __future__ import annotations

from pathlib import Path

from topoastero.stage1_validation import validate_stage1


def main() -> None:
    errors = validate_stage1(Path(__file__).parents[1])
    if errors:
        raise SystemExit("Stage 1 validation failed:\n- " + "\n- ".join(errors))
    print("Stage 1 literature and benchmark contract: PASS")


if __name__ == "__main__":
    main()
