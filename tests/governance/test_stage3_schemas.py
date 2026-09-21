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


def test_classical_result_schema_validates_all_baseline_rows() -> None:
    schema = _schema("classical_result.schema.json")
    numeric = {
        "value",
        "random_uncertainty",
        "pipeline_choice_uncertainty",
        "reference_value",
        "reference_uncertainty_minus",
        "reference_uncertainty_plus",
        "residual",
        "joint_uncertainty",
    }
    for raw in _rows("results/stage3/rudy_baseline.csv"):
        record = {key: (float(value) if key in numeric else value) for key, value in raw.items()}
        Draft202012Validator(schema).validate(record)


def test_preprocessing_schema_validates_frozen_registry() -> None:
    schema = _schema("preprocessing_branch.schema.json")
    rows = _rows("registries/preprocessing_branches.csv")
    assert len(rows) == 6
    for row in rows:
        Draft202012Validator(schema).validate(row)


def test_tess_schema_validates_every_individual_sector() -> None:
    schema = _schema("tess_feasibility.schema.json")
    numeric = {
        "cadence_seconds",
        "duration_days",
        "resolution_uHz",
        "duty_cycle",
        "candidate_numax_uHz",
        "envelope_peak_snr",
        "candidate_dnu_uHz",
        "dnu_autocorrelation_peak",
    }
    for raw in _rows("results/stage3/tess_sector_feasibility.csv"):
        record = {
            key: (int(value) if key == "sector" else float(value) if key in numeric else value)
            for key, value in raw.items()
        }
        Draft202012Validator(schema).validate(record)


def test_stage3_manifest_is_schema_valid() -> None:
    schema = _schema("stage3_run_manifest.schema.json")
    manifest = json.loads((ROOT / "results/stage3/run_manifest.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)
