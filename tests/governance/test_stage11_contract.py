from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from topoastero.population_acquisition import load_config
from topoastero.population_pipeline import cohort
from topoastero.population_store import read_json, read_table
from topoastero.stage11_validation import validate_stage11

ROOT = Path(__file__).parents[2]


@pytest.mark.governance
def test_stage11_additive_snapshot_and_honest_population_hold() -> None:
    assert validate_stage11(ROOT) == []
    assert validate_stage11(ROOT, require_prior_stages=False, require_confirmation=True) == ["scientific G11 confirmation is pending"]
    gate = read_json(ROOT / "reports/stage11/G11_ACCEPTANCE.json")
    assert gate["status"] == "population_pending" and gate["holdout_opening_count"] == 0
    assert gate["publication_ready"] is False and not gate["scientific_population_gate_passed"]
    assert not (ROOT / "registries/stage11_confirmation.json").exists()


def test_corrected_reference_edition_and_duplicates_resolved() -> None:
    refs = read_json(ROOT / "data/reference/stage11/reference_manifest.json")
    assert refs["edition"] == "Lund2017-erratum-ApJ850-110-CDS"
    assert refs["identical_duplicate_mode_rows"] == 45 and refs["covariance_available"] is False
    modes = read_table(ROOT / "data/reference/stage11/mode_frequencies.csv")
    assert len(modes) == 2843 and len({(r["stable_star_id"], r["radial_order_n"], r["angular_degree_l"]) for r in modes}) == len(modes)
    assert len(cohort(ROOT, load_config(ROOT))) == 66


def test_machine_readable_gate_and_catalogs_have_valid_schemas() -> None:
    schema = read_json(ROOT / "schemas/stage11_gate.schema.json")
    jsonschema.validate(read_json(ROOT / "reports/stage11/G11_ACCEPTANCE.json"), schema)
    catalog_schema = read_json(ROOT / "schemas/stage11_catalog.schema.json")
    for role in ("development", "internal_validation", "descriptive_benchmark"):
        catalog = read_json(ROOT / f"results/stage11/{role}/catalog.json")
        jsonschema.validate(catalog, catalog_schema)
        assert len(catalog["rows"]) % 4 == 0
        assert all(r["role"] != "final_holdout" for r in catalog["rows"])


def test_missing_stage11_is_an_explicit_failure(tmp_path: Path) -> None:
    issues = validate_stage11(tmp_path, require_prior_stages=False)
    assert issues and all(i.startswith("missing Stage 11 artifact") for i in issues)


def test_task_register_is_complete() -> None:
    tasks = read_table(ROOT / "reports/stage11/task_traceability.csv")
    assert {r["task_id"] for r in tasks} == {f"T11.{n}" for n in range(1, 12)}
    assert next(r for r in tasks if r["task_id"] == "T11.6")["status"] == "ready_unopened"
    status = json.loads((ROOT / "results/stage11/descriptive_benchmark/summary.json").read_text())
    assert status["stars_with_estimates"] == 1 and status["holdout_used"] is False
