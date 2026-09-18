"""Cross-platform semantic regression check for the Stage 0 smoke workflow."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_ABS_TOL = 1.0e-12


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _assert_close(left: float, right: float, *, abs_tol: float, label: str) -> None:
    if not math.isclose(left, right, rel_tol=0.0, abs_tol=abs_tol):
        raise AssertionError(f"{label}: {left!r} != {right!r} within abs_tol={abs_tol:g}")


def _compare_summary(reference_dir: Path, candidate_dir: Path, *, abs_tol: float) -> list[str]:
    reference = _load_json(reference_dir / "summary.json")
    candidate = _load_json(candidate_dir / "summary.json")

    exact_keys = (
        "workflow",
        "config_hash",
        "random_seed",
        "samples",
        "finite_pair_count",
        "essential_pair_count",
    )
    for key in exact_keys:
        if reference.get(key) != candidate.get(key):
            raise AssertionError(
                f"summary.{key}: {reference.get(key)!r} != {candidate.get(key)!r}"
            )

    _assert_close(
        float(reference["largest_finite_persistence"]),
        float(candidate["largest_finite_persistence"]),
        abs_tol=abs_tol,
        label="summary.largest_finite_persistence",
    )

    hash_differences = [
        key
        for key in ("signal_hash", "pairs_hash", "result_hash")
        if reference.get(key) != candidate.get(key)
    ]
    return hash_differences


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _compare_signal(reference_dir: Path, candidate_dir: Path, *, abs_tol: float) -> None:
    reference = _read_csv(reference_dir / "signal.csv")
    candidate = _read_csv(candidate_dir / "signal.csv")
    if len(reference) != len(candidate):
        raise AssertionError(f"signal row count: {len(reference)} != {len(candidate)}")

    for index, (left, right) in enumerate(zip(reference, candidate, strict=True)):
        if left["sample"] != right["sample"]:
            raise AssertionError(
                f"signal row {index} sample: {left['sample']!r} != {right['sample']!r}"
            )
        for field in ("time_normalized", "amplitude"):
            _assert_close(
                float(left[field]),
                float(right[field]),
                abs_tol=abs_tol,
                label=f"signal row {index} {field}",
            )


def _compare_pairs(reference_dir: Path, candidate_dir: Path, *, abs_tol: float) -> None:
    reference = _read_csv(reference_dir / "persistence_pairs.csv")
    candidate = _read_csv(candidate_dir / "persistence_pairs.csv")
    if len(reference) != len(candidate):
        raise AssertionError(f"pair row count: {len(reference)} != {len(candidate)}")

    exact_fields = ("birth_index", "death_index", "essential")
    float_fields = ("birth", "death", "persistence")
    for index, (left, right) in enumerate(zip(reference, candidate, strict=True)):
        for field in exact_fields:
            if left[field] != right[field]:
                raise AssertionError(
                    f"pair row {index} {field}: {left[field]!r} != {right[field]!r}"
                )
        for field in float_fields:
            left_value = left[field]
            right_value = right[field]
            if left_value == "" or right_value == "":
                if left_value != right_value:
                    raise AssertionError(
                        f"pair row {index} {field}: {left_value!r} != {right_value!r}"
                    )
                continue
            _assert_close(
                float(left_value),
                float(right_value),
                abs_tol=abs_tol,
                label=f"pair row {index} {field}",
            )


def compare(reference_dir: Path, candidate_dir: Path, *, abs_tol: float) -> list[str]:
    """Compare smoke outputs by scientific content, not cross-platform float bytes."""

    if abs_tol <= 0.0:
        raise ValueError("abs_tol must be positive")
    hash_differences = _compare_summary(reference_dir, candidate_dir, abs_tol=abs_tol)
    _compare_signal(reference_dir, candidate_dir, abs_tol=abs_tol)
    _compare_pairs(reference_dir, candidate_dir, abs_tol=abs_tol)
    return hash_differences


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_dir", type=Path)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--abs-tol", type=float, default=DEFAULT_ABS_TOL)
    args = parser.parse_args()

    hash_differences = compare(
        args.reference_dir.resolve(),
        args.candidate_dir.resolve(),
        abs_tol=args.abs_tol,
    )
    print(f"Smoke semantic regression passed (abs_tol={args.abs_tol:g}).")
    if hash_differences:
        print(
            "Platform-sensitive audit hashes differ as expected: " + ", ".join(hash_differences)
        )


if __name__ == "__main__":
    main()
