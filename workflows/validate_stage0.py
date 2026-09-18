"""Fail with a compact list when the frozen Stage 0 contract is incomplete."""

from __future__ import annotations

from topoastero.validation import validate_stage0

if __name__ == "__main__":
    failures = validate_stage0(".")
    if failures:
        raise SystemExit("\n".join(failures))

