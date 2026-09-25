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


def test_embedding_records_validate() -> None:
    schema = _schema("delay_embedding.schema.json")
    with (ROOT / "results/stage7/embedding_audit.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        Draft202012Validator(schema).validate(
            {
                "cell_id": row["cell_id"],
                "role": row["role"],
                "delay": int(row["delay"]),
                "dimension": int(row["dimension"]),
                "normalization": row["normalization"],
                "total_windows": int(row["total_windows"]),
                "rejected_windows": int(row["rejected_windows"]),
                "valid_fraction": float(row["valid_fraction"]),
                "retained_points": int(row["retained_points"]),
                "sampling": row["sampling"],
            }
        )


def test_diagram_records_validate() -> None:
    schema = _schema("delay_diagram.schema.json")
    payload = json.loads((ROOT / "results/stage7/diagram_suite.json").read_text())
    for record in payload["pairs"]:
        Draft202012Validator(schema).validate(record)


def test_phase_records_validate() -> None:
    schema = _schema("phase_test.schema.json")
    with (ROOT / "results/stage7/phase_tests.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        Draft202012Validator(schema).validate(
            {
                "cell_id": row["cell_id"],
                "role": row["role"],
                "surrogate_family": row["surrogate_family"],
                "observed_maximum": float(row["observed_maximum"]),
                "null_draws": int(row["null_draws"]),
                "pvalue": float(row["pvalue"]),
                "alpha": float(row["alpha"]),
                "rejected": row["rejected"] == "true",
                "bh_rejected": row["bh_rejected"] == "true",
                "trials": int(row["trials"]),
                "median_psd_amplitude_error": float(row["median_psd_amplitude_error"]),
            }
        )


def test_stage7_gate_and_run_manifest_validate() -> None:
    decision_schema = _schema("stage7_decision.schema.json")
    gate = json.loads((ROOT / "reports/stage7/G7_ACCEPTANCE.json").read_text())
    Draft202012Validator(decision_schema).validate(gate)
    manifest_schema = _schema("stage7_run_manifest.schema.json")
    manifest = json.loads((ROOT / "results/stage7/run_manifest.json").read_text())
    Draft202012Validator(manifest_schema).validate(manifest)

