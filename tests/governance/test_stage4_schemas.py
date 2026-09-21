from __future__ import annotations

import csv
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]


def _schema(name: str) -> dict[str, object]:
    value = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_simulation_design_schema_validates_all_frozen_cells() -> None:
    schema = _schema("simulation_design.schema.json")
    integer = {"seed", "visible_orders"}
    numeric = {
        "duration_days",
        "cadence_seconds",
        "duty_cycle",
        "numax_uHz",
        "dnu_uHz",
        "lifetime_days",
        "mission_template_duty",
    }
    for raw in _rows("registries/stage4_factorial_design.csv"):
        record = {
            key: int(value) if key in integer else float(value) if key in numeric else value
            for key, value in raw.items()
        }
        Draft202012Validator(schema).validate(record)


def test_null_calibration_schema_validates_all_families() -> None:
    schema = _schema("null_calibration.schema.json")
    integer = {
        "calibration_realizations",
        "evaluation_realizations",
        "registered_statistics",
        "evaluation_exceedances",
    }
    numeric = {"threshold", "empirical_fwer", "fwer_standard_error", "alpha"}
    for raw in _rows("results/stage4/null_calibration.csv"):
        record = {
            key: int(value) if key in integer else float(value) if key in numeric else value
            for key, value in raw.items()
        }
        Draft202012Validator(schema).validate(record)


def test_coverage_schema_validates_all_cells() -> None:
    schema = _schema("coverage_result.schema.json")
    integer = {"calibration_realizations", "evaluation_realizations"}
    numeric = {
        "duration_days",
        "lifetime_days",
        "bias_uHz",
        "realization_sigma_uHz",
        "pipeline_choice_sigma_uHz",
        "interval_half_width_uHz",
        "empirical_coverage",
        "nominal_coverage",
    }
    for raw in _rows("results/stage4/uncertainty_coverage.csv"):
        record = {
            key: int(value) if key in integer else float(value) if key in numeric else value
            for key, value in raw.items()
        }
        Draft202012Validator(schema).validate(record)


def test_compute_schema_and_run_manifest_are_valid() -> None:
    compute_schema = _schema("compute_profile.schema.json")
    for raw in _rows("results/stage4/compute_profile.csv"):
        record = {
            **raw,
            "sample_size": int(raw["sample_size"]),
            "median_runtime_seconds": float(raw["median_runtime_seconds"]),
            "peak_memory_bytes": int(raw["peak_memory_bytes"]),
            "timing_repetitions": int(raw["timing_repetitions"]),
        }
        Draft202012Validator(compute_schema).validate(record)
    manifest_schema = _schema("stage4_run_manifest.schema.json")
    manifest = json.loads((ROOT / "results/stage4/run_manifest.json").read_text())
    Draft202012Validator(manifest_schema).validate(manifest)
