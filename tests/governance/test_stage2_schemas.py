from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from yaml import safe_load

ROOT = Path(__file__).parents[2]
SCHEMAS = ROOT / "schemas"


def schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def validator(name: str) -> Draft202012Validator:
    provenance = schema("derived_provenance.schema.json")
    registry = Registry().with_resource(
        provenance["$id"], Resource.from_contents(provenance)
    )
    return Draft202012Validator(
        schema(name), registry=registry, format_checker=FormatChecker()
    )


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.governance
def test_canonical_examples_validate_against_json_schemas() -> None:
    mapping = {
        "light_curve.jsonl": "light_curve.schema.json",
        "spectrum.jsonl": "spectrum.schema.json",
        "mode_frequency.jsonl": "mode_frequency.schema.json",
        "stellar_reference.jsonl": "stellar_reference.schema.json",
    }
    for example, schema_name in mapping.items():
        check = validator(schema_name)
        lines = (ROOT / "data/canonical/examples" / example).read_text(encoding="utf-8").splitlines()
        assert lines
        for line in lines:
            check.validate(json.loads(line))


@pytest.mark.governance
def test_alias_record_validates_against_json_schema() -> None:
    record = safe_load(
        (ROOT / "data/manifests/stage2/rudy_aliases.yaml").read_text(encoding="utf-8")
    )
    validator("identifier_record.schema.json").validate(record)


@pytest.mark.governance
def test_mission_and_split_rows_validate_against_json_schemas() -> None:
    integer_product_fields = {
        "segment_number",
        "row_count",
        "finite_flux_rows",
        "finite_uncertainty_rows",
        "nonphysical_uncertainty_rows",
        "quality_zero_rows",
        "duplicate_time_rows",
        "time_order_violations",
        "missing_cadence_gaps",
        "size_bytes",
    }
    numeric_product_fields = {
        "cadence_seconds",
        "exposure_seconds",
        "bjd_reference",
        "time_start",
        "time_stop",
        "crowding_metric",
        "flux_fraction",
    }
    product_validator = validator("mission_product_manifest.schema.json")
    directory = ROOT / "data/manifests/stage2"
    for filename in ("rudy_kepler_products.csv", "rudy_tess_products.csv"):
        for source in csv_rows(directory / filename):
            record: dict[str, Any] = dict(source)
            for field in integer_product_fields:
                record[field] = int(record[field])
            for field in numeric_product_fields:
                if record[field] != "not_provided":
                    record[field] = float(record[field])
            product_validator.validate(record)

    split_validator = validator("population_split.schema.json")
    for source in csv_rows(ROOT / "registries/population_partitions.csv"):
        record = dict(source)
        record["assignment_rank"] = int(record["assignment_rank"])
        record["master_seed"] = int(record["master_seed"])
        split_validator.validate(record)
