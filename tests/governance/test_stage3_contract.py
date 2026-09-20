from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from topoastero.stage3_validation import (
    validate_baselines,
    validate_config,
    validate_modes_branches_uncertainty,
    validate_observation_model,
    validate_stage3,
    validate_tess,
)

ROOT = Path(__file__).parents[2]


def _copy(relative: str, destination: Path) -> Path:
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
    return target


def test_stage3_contract_passes_with_all_prerequisites() -> None:
    assert validate_stage3(ROOT, require_prior_stages=True) == []


def test_g3_declares_topology_free_pass_and_unopened_holdout() -> None:
    gate = json.loads((ROOT / "reports/stage3/G3_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G3"
    assert gate["decision"] == "PASS"
    assert gate["topology_inspected"] is False
    assert gate["holdout_access_state"] == "unopened_for_analysis"
    assert all(clause["status"] == "pass" for clause in gate["clauses"])


def test_stage3_outputs_cover_every_agenda_task() -> None:
    traceability = (ROOT / "reports/stage3/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 10):
        assert f"T3.{task}" in traceability
    baseline = list(csv.DictReader((ROOT / "results/stage3/rudy_baseline.csv").open()))
    lightkurve = {row["quantity"]: float(row["value"]) for row in baseline if row["pipeline"] == "lightkurve_acf2d"}
    assert lightkurve["numax"] == 2145.0
    assert lightkurve["dnu"] == 103.112102282
    assert lightkurve["mass"] == 1.08156432687
    assert lightkurve["radius"] == 1.22908312665
    assert lightkurve["logg"] == 4.29295746876


def test_config_validator_detects_topology_selection(tmp_path: Path) -> None:
    path = _copy("configs/stage3_classical.yaml", tmp_path)
    text = path.read_text().replace(
        "topology_used_for_branch_selection: false",
        "topology_used_for_branch_selection: true",
    )
    path.write_text(text)
    errors: list[str] = []
    validate_config(tmp_path, errors)
    assert any("must not use topology" in error for error in errors)


def test_baseline_validator_detects_reproduction_drift(tmp_path: Path) -> None:
    path = _copy("results/stage3/rudy_baseline.csv", tmp_path)
    _copy("results/stage3/pipeline_comparison.csv", tmp_path)
    text = path.read_text().replace(
        "lightkurve_acf2d-numax,lightkurve_acf2d,numax,2145,",
        "lightkurve_acf2d-numax,lightkurve_acf2d,numax,2000,",
    )
    path.write_text(text)
    errors: list[str] = []
    validate_baselines(tmp_path, errors)
    assert any("reproduction drift" in error for error in errors)
    assert any("residual mismatch" in error for error in errors)


def test_observation_model_validator_detects_wrong_background(tmp_path: Path) -> None:
    path = _copy("results/stage3/background_models.csv", tmp_path)
    _copy("results/stage3/window_atlas.csv", tmp_path)
    _copy("results/stage3/echelle_trials.csv", tmp_path)
    path.write_text(path.read_text().replace(",true\n", ",false\n"))
    errors: list[str] = []
    validate_observation_model(tmp_path, errors)
    assert any("minimum-BIC" in error for error in errors)


def test_branch_validator_detects_topological_selection(tmp_path: Path) -> None:
    for relative in (
        "results/stage3/mode_audit.csv",
        "results/stage3/preprocessing_sensitivity.csv",
        "results/stage3/uncertainty_budget.csv",
        "registries/preprocessing_branches.csv",
    ):
        _copy(relative, tmp_path)
    path = tmp_path / "registries/preprocessing_branches.csv"
    path.write_text(path.read_text().replace(
        "classical_predeclared_no_topology", "selected_by_topological_appearance", 1
    ))
    errors: list[str] = []
    validate_modes_branches_uncertainty(tmp_path, errors)
    assert any("independently of topology" in error for error in errors)


def test_tess_validator_detects_forced_combination(tmp_path: Path) -> None:
    path = _copy("results/stage3/tess_sector_feasibility.csv", tmp_path)
    path.write_text(path.read_text().replace("do_not_combine_for_detection_at_G3", "combine", 1))
    errors: list[str] = []
    validate_tess(tmp_path, errors)
    assert any("combined detection" in error for error in errors)
