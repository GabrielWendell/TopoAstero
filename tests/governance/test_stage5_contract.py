from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from topoastero.stage5_validation import (
    RETAINED,
    RETAINED_FEATURES,
    validate_audits_selection,
    validate_backends_localization,
    validate_config_registries,
    validate_schemas,
    validate_stage5,
)

ROOT = Path(__file__).parents[2]


def _copy(relative: str, destination: Path) -> Path:
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
    return target


def test_stage5_contract_passes_with_all_prerequisites() -> None:
    assert validate_stage5(ROOT, require_prior_stages=True) == []


def test_g5_records_the_locked_small_retained_set() -> None:
    gate = json.loads((ROOT / "reports/stage5/G5_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G5" and gate["status"] == "pass"
    assert set(gate["retained_representations"]) == RETAINED
    assert set(gate["retained_feature_ids"]) == RETAINED_FEATURES
    assert gate["population_data_used"] is False
    assert gate["final_holdout_used"] is False
    assert gate["visual_interest_is_selection_criterion"] is False
    assert all(item["status"] == "pass" for item in gate["checks"])


def test_traceability_covers_all_tasks_and_deliverables() -> None:
    traceability = (ROOT / "reports/stage5/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 9):
        assert f"T5.{task}" in traceability
    for deliverable in range(1, 5):
        assert f"D5.{deliverable}" in traceability


def test_compact_registry_retained_rows_have_every_g5_field() -> None:
    with (ROOT / "registries/stage5_feature_registry.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 13
    retained = [row for row in rows if row["status"] in {"retained", "retained_exploratory"}]
    assert {row["feature_id"] for row in retained} == RETAINED_FEATURES
    for row in retained:
        assert row["physical_target"]
        assert row["null_family"]
        assert row["control_id"].startswith("CTL-")
        assert row["later_stage"] in {"S6", "S7", "S8"}
        assert row["essential_handling"] == "excluded_from_numeric_summary"


def test_config_validator_rejects_holdout_and_representation_drift(tmp_path: Path) -> None:
    config = _copy("configs/stage5_tda.yaml", tmp_path)
    _copy("registries/stage5_representation_parameters.yaml", tmp_path)
    _copy("registries/stage5_feature_registry.csv", tmp_path)
    text = config.read_text().replace(
        "population_or_final_holdout_allowed: false",
        "population_or_final_holdout_allowed: true",
    ).replace("coefficient_field: F2", "coefficient_field: Q", 1)
    config.write_text(text)
    errors: list[str] = []
    validate_config_registries(tmp_path, errors)
    assert any("bar population" in error for error in errors)
    assert any("coefficient field" in error for error in errors)


def test_backend_validator_detects_failure_and_artificial_essential_death(tmp_path: Path) -> None:
    check = _copy("results/stage5/backend_crosscheck.csv", tmp_path)
    catalog = _copy("results/stage5/localization_catalog.json", tmp_path)
    check.write_text(check.read_text().replace(",pass\n", ",fail\n", 1))
    records = json.loads(catalog.read_text())
    essential = next(row for row in records if row["essential"])
    essential["death"] = 0.0
    essential["persistence"] = 1.0
    catalog.write_text(json.dumps(records))
    errors: list[str] = []
    validate_backends_localization(tmp_path, errors)
    assert any("cross-check failed" in error for error in errors)
    assert any("artificial death" in error for error in errors)


def test_audit_validator_detects_null_and_selection_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage5/representation_features.csv",
        "registries/stage4_factorial_design.csv",
        "results/stage5/null_calibration.csv",
        "results/stage5/nuisance_sensitivity.csv",
        "results/stage5/redundancy_matrix.csv",
        "results/stage5/redundancy_pairs.csv",
        "results/stage5/ablation_results.csv",
        "registries/stage5_selection.yaml",
    ):
        _copy(relative, tmp_path)
    nulls = tmp_path / "results/stage5/null_calibration.csv"
    lines = nulls.read_text().splitlines()
    header = lines[0].split(",")
    fields = lines[1].split(",")
    fields[header.index("evaluation_false_positive_rate")] = "0.5"
    lines[1] = ",".join(fields)
    nulls.write_text("\n".join(lines) + "\n")
    selection = tmp_path / "registries/stage5_selection.yaml"
    selection.write_text(selection.read_text().replace("final_holdout_used: false", "final_holdout_used: true"))
    errors: list[str] = []
    validate_audits_selection(tmp_path, errors)
    assert any("null calibration failed" in error for error in errors)
    assert any("forbidden population/holdout" in error for error in errors)


def test_schema_validator_detects_wrong_draft_and_open_schema(tmp_path: Path) -> None:
    for name in (
        "representation_spec.schema.json",
        "topological_feature.schema.json",
        "localization.schema.json",
        "selection_record.schema.json",
        "stage5_run_manifest.schema.json",
    ):
        _copy(f"schemas/{name}", tmp_path)
    path = tmp_path / "schemas/representation_spec.schema.json"
    schema = json.loads(path.read_text())
    schema["$schema"] = "draft-old"
    schema["additionalProperties"] = True
    path.write_text(json.dumps(schema))
    errors: list[str] = []
    validate_schemas(tmp_path, errors)
    assert any("draft 2020-12" in error for error in errors)
    assert any("closed object" in error for error in errors)


def test_all_stage5_figures_use_the_project_visual_contract() -> None:
    figures = sorted((ROOT / "reports/stage5/figures").glob("*.svg"))
    assert len(figures) == 7
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        assert "TA-PLOT-1.0" in source
        assert "Machine-readable source:" in source
        assert "TopoAstero-0.6.0" in source

