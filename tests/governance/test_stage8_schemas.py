"""Closed draft-2020-12 schemas validate the serialized Stage 8 products."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]


def _schema(name: str) -> Draft202012Validator:
    payload = json.loads((ROOT / "schemas" / name).read_text())
    Draft202012Validator.check_schema(payload)
    return Draft202012Validator(payload)


def _csv(name: str) -> list[dict[str, str]]:
    with (ROOT / "results/stage8" / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_registered_trial_score_schema() -> None:
    validator = _schema("echelle_score.schema.json")
    for row in _csv("score_curves.csv"):
        validator.validate({
            key: int(value) if key in {"trial_index", "valid_orders", "finite_h0_count"}
            else float(value) if key.endswith("_score") or key.endswith("_component") or key == "spacing_uHz"
            else value for key, value in row.items()
        })


def test_cylindrical_localized_pairs_schema() -> None:
    validator = _schema("cylindrical_pair.schema.json")
    suite = json.loads((ROOT / "results/stage8/diagram_suite.json").read_text())
    for pair in suite["pairs"]:
        validator.validate(pair)


def test_stochastic_interval_schema() -> None:
    validator = _schema("stage8_interval.schema.json")
    for row in _csv("intervals.csv"):
        validator.validate({
            key: int(value) if key in {"replicates", "ridge_draws_available"}
            else (float(value) if value else None) if key in {"ridge_phase_lower_cycles", "ridge_phase_upper_cycles"}
            else float(value) if key.endswith("_uHz") or key == "interval_level"
            else value == "true" if key in {"covers_truth", "ridge_phase_interval_wraps"}
            else value for key, value in row.items()
        })


def test_gate_and_manifest_schema() -> None:
    _schema("stage8_gate.schema.json").validate(
        json.loads((ROOT / "reports/stage8/G8_ACCEPTANCE.json").read_text())
    )
    _schema("stage8_run_manifest.schema.json").validate(
        json.loads((ROOT / "results/stage8/run_manifest.json").read_text())
    )
