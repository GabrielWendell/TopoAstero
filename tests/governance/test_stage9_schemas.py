"""Closed Stage 9 result schemas and real output validation."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[2]


def test_stage9_serialized_products_validate_under_closed_schemas() -> None:
    products = {
        "stage9_numerical_audit.schema.json": "results/stage9/numerical_audit.json",
        "stage9_counterexamples.schema.json": "results/stage9/counterexamples.json",
        "stage9_gate.schema.json": "reports/stage9/G9_ACCEPTANCE.json",
        "stage9_run_manifest.schema.json": "results/stage9/run_manifest.json",
    }
    for schema_name, product_name in products.items():
        schema = json.loads((ROOT / "schemas" / schema_name).read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(json.loads((ROOT / product_name).read_text()))
        assert schema["additionalProperties"] is False

