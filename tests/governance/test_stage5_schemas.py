from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]


def _schema(name: str) -> dict[str, object]:
    value = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def _rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_representation_and_feature_registries_validate() -> None:
    representation_schema = _schema("representation_spec.schema.json")
    registry = yaml.safe_load(
        (ROOT / "registries/stage5_representation_parameters.yaml").read_text()
    )
    for record in registry["representations"]:
        Draft202012Validator(representation_schema).validate(record)

    feature_schema = _schema("topological_feature.schema.json")
    for record in _rows("registries/stage5_feature_registry.csv"):
        Draft202012Validator(feature_schema).validate(record)


def test_localization_and_selection_records_validate() -> None:
    localization_schema = _schema("localization.schema.json")
    records = json.loads((ROOT / "results/stage5/localization_catalog.json").read_text())
    for record in records:
        Draft202012Validator(localization_schema).validate(record)

    selection_schema = _schema("selection_record.schema.json")
    registry = yaml.safe_load((ROOT / "registries/stage5_selection.yaml").read_text())
    for record in registry["records"]:
        Draft202012Validator(selection_schema).validate(record)


def test_stage5_run_manifest_validates() -> None:
    schema = _schema("stage5_run_manifest.schema.json")
    manifest = json.loads((ROOT / "results/stage5/run_manifest.json").read_text())
    Draft202012Validator(schema).validate(manifest)

