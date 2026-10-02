from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
@pytest.mark.parametrize("schema,artifact", [
    ("stage10_capsule.schema.json", "results/stage10/benchmark_capsule.json"),
    ("stage10_freeze.schema.json", "reports/stage10/freeze_manifest.json"),
    ("stage10_gate.schema.json", "reports/stage10/G10_ACCEPTANCE.json"),
])
def test_stage10_schema(schema: str, artifact: str) -> None:
    document = json.loads((ROOT / "schemas" / schema).read_text())
    jsonschema.Draft202012Validator.check_schema(document)
    jsonschema.validate(json.loads((ROOT / artifact).read_text()), document)
