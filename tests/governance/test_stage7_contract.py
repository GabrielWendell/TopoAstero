from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from topoastero.stage7_validation import (
    validate_config_registries,
    validate_delay_embeddings_diagrams,
    validate_manifest_gate_notebook,
    validate_phase_controls_stability,
    validate_schemas,
    validate_stage7,
)

ROOT = Path(__file__).parents[2]


def _copy(relative: str, destination: Path) -> Path:
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
    return target


def test_stage7_contract_passes_with_all_prerequisites() -> None:
    assert validate_stage7(ROOT, require_prior_stages=True) == []


def test_g7_records_the_frozen_negative_result() -> None:
    gate = json.loads((ROOT / "reports/stage7/G7_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G7" and gate["status"] == "pass"
    assert gate["decision"] == "drop"
    assert gate["claim"] == "calibrated_negative_result"
    assert gate["critical_path_action"] == "remove_delay_PH_from_critical_path"
    assert gate["phase_path_passed"] is False
    assert gate["predictive_path_passed"] is False
    assert gate["population_data_used"] is False
    assert gate["final_holdout_used"] is False


def test_traceability_covers_every_stage7_task() -> None:
    traceability = (ROOT / "reports/stage7/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 9):
        assert f"T7.{task}" in traceability
    decision = (ROOT / "reports/stage7/RETAIN_DROP_DECISION.md").read_text()
    assert "DROP" in decision and "calibrated_negative_result" in decision


def test_config_validator_rejects_scope_policy_and_seal_drift(tmp_path: Path) -> None:
    config = _copy("configs/stage7_delay_topology.yaml", tmp_path)
    for relative in (
        "registries/stage7_delay_policy.yaml",
        "registries/stage7_decision_policy.yaml",
        "registries/stage7_simulation_lock.yaml",
        "registries/stage4_factorial_design.csv",
        "results/stage4/run_manifest.json",
        "results/stage5/run_manifest.json",
        "registries/stage5_selection.yaml",
    ):
        _copy(relative, tmp_path)
    config.write_text(
        config.read_text()
        .replace("population_data_allowed: false", "population_data_allowed: true")
        .replace("primary: multiscale_consensus", "primary: acf_first_minimum")
        .replace("PCA_visualization_only_never_PH", "PCA_before_PH")
    )
    lock = tmp_path / "registries/stage7_simulation_lock.yaml"
    lock.write_text(lock.read_text().replace("4fba72f8", "00000000", 1))
    errors: list[str] = []
    validate_config_registries(tmp_path, errors)
    assert any("holdout" in error for error in errors)
    assert any("delay policy" in error for error in errors)
    assert any("dimensionality" in error for error in errors)
    assert any("simulation-lock" in error for error in errors)


def test_delay_validator_detects_selection_embedding_and_convergence_drift(
    tmp_path: Path,
) -> None:
    for relative in (
        "results/stage7/delay_parameter_audit.csv",
        "results/stage7/delay_policy_summary.csv",
        "results/stage7/embedding_audit.csv",
        "results/stage7/diagram_suite.json",
        "results/stage7/convergence_audit.csv",
    ):
        _copy(relative, tmp_path)
    delay = tmp_path / "results/stage7/delay_parameter_audit.csv"
    rows = list(csv.DictReader(delay.open(newline="")))
    rows[0]["lag_samples"] = "0"
    rows[1]["selected"] = "true"
    with delay.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    embeddings = tmp_path / "results/stage7/embedding_audit.csv"
    embeddings.write_text(embeddings.read_text().replace(",18,farthest", ",17,farthest", 1))
    convergence = tmp_path / "results/stage7/convergence_audit.csv"
    convergence.write_text(convergence.read_text().replace(",0,reference", ",0.1,reference", 1))
    errors: list[str] = []
    validate_delay_embeddings_diagrams(tmp_path, errors)
    assert any("delay selection" in error or "invalid lag" in error for error in errors)
    assert any("embedding contract" in error for error in errors)
    assert any("convergence distance" in error for error in errors)


def test_phase_validator_detects_psd_ablation_and_stability_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage7/phase_tests.csv",
        "results/stage7/surrogate_draw_maxima.csv",
        "results/stage7/coherence_response_surfaces.csv",
        "results/stage7/response_correlations.csv",
        "results/stage7/classical_controls.csv",
        "results/stage7/predictive_ablation.csv",
        "results/stage7/segmentation_stability.csv",
        "results/stage7/vineyard_tracks.csv",
    ):
        _copy(relative, tmp_path)
    phase = tmp_path / "results/stage7/phase_tests.csv"
    rows = list(csv.DictReader(phase.open(newline="")))
    rows[0]["median_psd_amplitude_error"] = "0.5"
    rows[0]["bh_rejected"] = "true"
    with phase.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    ablation = tmp_path / "results/stage7/predictive_ablation.csv"
    ablation.write_text(ablation.read_text().replace("topology,12,12", "topology,11,13", 1))
    stability = tmp_path / "results/stage7/segmentation_stability.csv"
    stability.write_text(stability.read_text().replace(",0,", ",-1,", 1))
    errors: list[str] = []
    validate_phase_controls_stability(tmp_path, errors)
    assert any("PSD was not preserved" in error for error in errors)
    assert any("evaluation cells" in error for error in errors)
    assert any("split" in error for error in errors)


def test_schema_validator_detects_wrong_draft_and_open_schema(tmp_path: Path) -> None:
    for name in (
        "delay_embedding.schema.json",
        "delay_diagram.schema.json",
        "phase_test.schema.json",
        "stage7_decision.schema.json",
        "stage7_run_manifest.schema.json",
    ):
        _copy(f"schemas/{name}", tmp_path)
    path = tmp_path / "schemas/delay_embedding.schema.json"
    schema = json.loads(path.read_text())
    schema["$schema"] = "draft-old"
    schema["additionalProperties"] = True
    path.write_text(json.dumps(schema))
    errors: list[str] = []
    validate_schemas(tmp_path, errors)
    assert any("draft 2020-12" in error for error in errors)
    assert any("closed object" in error for error in errors)


def test_manifest_validator_detects_gate_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage7/run_manifest.json",
        "configs/stage7_delay_topology.yaml",
        "reports/stage7/G7_ACCEPTANCE.json",
        "notebooks/07_delay_embedding_phase_test.ipynb",
        "reports/stage7/deliverable_manifest.csv",
        "results/stage7/phase_tests.csv",
        "results/stage7/predictive_ablation.csv",
    ):
        _copy(relative, tmp_path)
    for figure in (ROOT / "reports/stage7/figures").glob("*.svg"):
        _copy(str(figure.relative_to(ROOT)), tmp_path)
    gate = tmp_path / "reports/stage7/G7_ACCEPTANCE.json"
    payload = json.loads(gate.read_text())
    payload["decision"] = "retain"
    gate.write_text(json.dumps(payload))
    errors: list[str] = []
    validate_manifest_gate_notebook(tmp_path, errors)
    assert any("retain/drop rule" in error for error in errors)


def test_all_stage7_figures_use_the_project_visual_contract() -> None:
    figures = sorted((ROOT / "reports/stage7/figures").glob("*.svg"))
    assert len(figures) == 6
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        assert "TA-PLOT-1.0" in source
        assert "Machine-readable source:" in source
        assert "TopoAstero-0.8.0" in source

