from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from topoastero.stage6_validation import (
    QUALITY_FLAGS,
    validate_config_registries,
    validate_estimators,
    validate_manifest_gate_notebook,
    validate_null_robustness_quality,
    validate_persistence_equivalence,
    validate_schemas,
    validate_stage6,
)

ROOT = Path(__file__).parents[2]


def _copy(relative: str, destination: Path) -> Path:
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
    return target


def test_stage6_contract_passes_with_all_prerequisites() -> None:
    assert validate_stage6(ROOT, require_prior_stages=True) == []


def test_g6_records_the_equivalence_limited_claim() -> None:
    gate = json.loads((ROOT / "reports/stage6/G6_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G6" and gate["status"] == "pass"
    assert gate["claim"] == "equivalence_limited_localization_and_calibrated_reliability"
    assert gate["prominence_identity"] == "exact_on_shared_elder_rule_path_domain"
    assert gate["population_data_used"] is False
    assert gate["final_holdout_used"] is False
    assert gate["external_pysyd_executed"] is False
    assert all(item["status"] in {"pass", "pass_with_qc_value"} for item in gate["checks"])


def test_traceability_covers_all_tasks_and_deliverables() -> None:
    traceability = (ROOT / "reports/stage6/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 9):
        assert f"T6.{task}" in traceability
    for deliverable in range(1, 5):
        assert f"D6.{deliverable}" in traceability


def test_localized_diagram_preserves_essential_and_finite_rules() -> None:
    diagram = json.loads((ROOT / "results/stage6/peak_diagram.json").read_text())
    pairs = diagram["pairs"]
    essential = [pair for pair in pairs if pair["essential"]]
    finite = [pair for pair in pairs if not pair["essential"]]
    assert len(essential) == 1
    assert essential[0]["death_value"] is None
    assert essential[0]["persistence"] is None
    assert finite and all(pair["persistence"] > 0 for pair in finite)
    assert all(pair["saddle_frequency_uHz"] is not None for pair in finite)


def test_all_quality_reason_codes_are_registered_and_nonexclusive() -> None:
    with (ROOT / "results/stage6/quality_flags.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    observed = {flag for row in rows for flag in json.loads(row["flags_json"])}
    assert observed.issubset(QUALITY_FLAGS)
    assert {row["status"] for row in rows} == {"reliable", "limited", "not_detected"}
    assert any(len(json.loads(row["flags_json"])) > 1 for row in rows)


def test_config_validator_rejects_holdout_normalization_and_lock_drift(tmp_path: Path) -> None:
    config = _copy("configs/stage6_psd_topology.yaml", tmp_path)
    for relative in (
        "registries/stage6_normalization_contract.yaml",
        "registries/stage6_quality_flags.yaml",
        "registries/stage6_simulation_lock.yaml",
        "registries/stage4_factorial_design.csv",
        "results/stage4/factorial_pilot.csv",
        "registries/stage5_selection.yaml",
    ):
        _copy(relative, tmp_path)
    config.write_text(
        config.read_text()
        .replace("population_data_allowed: false", "population_data_allowed: true")
        .replace("primary: log_ratio", "primary: ratio")
    )
    lock = tmp_path / "registries/stage6_simulation_lock.yaml"
    lock.write_text(lock.read_text().replace("4fba72f8", "00000000", 1))
    errors: list[str] = []
    validate_config_registries(tmp_path, errors)
    assert any("holdout" in error for error in errors)
    assert any("normalization" in error for error in errors)
    assert any("simulation-lock" in error for error in errors)


def test_equivalence_validator_detects_overstatement_and_numeric_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage6/normalization_audit.csv",
        "results/stage6/peak_diagram.json",
        "results/stage6/equivalence_audit.csv",
    ):
        _copy(relative, tmp_path)
    path = tmp_path / "results/stage6/equivalence_audit.csv"
    rows = list(csv.DictReader(path.open(newline="")))
    rows[0]["maximum_absolute_error"] = "0.1"
    rows[0]["interpretation"] = "novel_peak_statistic"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    errors: list[str] = []
    validate_persistence_equivalence(tmp_path, errors)
    assert any("equivalence failed" in error for error in errors)
    assert any("overstated" in error for error in errors)


def test_estimator_validator_detects_pysyd_mislabel_and_missing_alias(tmp_path: Path) -> None:
    for relative in (
        "results/stage6/numax_benchmark.csv",
        "results/stage6/numax_summary.csv",
        "results/stage6/comb_candidates.csv",
        "results/stage6/comb_benchmark.csv",
        "results/stage6/pysyd_adapter_audit.json",
        "registries/stage4_factorial_design.csv",
    ):
        _copy(relative, tmp_path)
    numax = tmp_path / "results/stage6/numax_benchmark.csv"
    numax.write_text(numax.read_text().replace("offline_style_control_not_pysyd_package,false", "external_pysyd,true", 1))
    candidates = tmp_path / "results/stage6/comb_candidates.csv"
    lines = candidates.read_text().splitlines()
    candidates.write_text("\n".join([lines[0], *lines[2:]]) + "\n")
    errors: list[str] = []
    validate_estimators(tmp_path, errors)
    assert any("mislabeled" in error for error in errors)
    assert any("candidate" in error or "aliases" in error for error in errors)


def test_null_validator_detects_false_alarm_and_unknown_flag(tmp_path: Path) -> None:
    for relative in (
        "results/stage6/null_calibration.csv",
        "results/stage6/robustness_atlas.csv",
        "results/stage6/quality_flags.csv",
    ):
        _copy(relative, tmp_path)
    nulls = tmp_path / "results/stage6/null_calibration.csv"
    nulls.write_text(nulls.read_text().replace(",0.0546875,0.0546875,", ",0.5,0.5,", 1))
    quality = tmp_path / "results/stage6/quality_flags.csv"
    quality.write_text(quality.read_text().replace("[]", '["invented_flag"]', 1))
    errors: list[str] = []
    validate_null_robustness_quality(tmp_path, errors)
    assert any("null calibration failed" in error for error in errors)
    assert any("unknown reason" in error for error in errors)


def test_schema_validator_detects_wrong_draft_and_open_schema(tmp_path: Path) -> None:
    for name in (
        "psd_persistence_pair.schema.json",
        "numax_estimate.schema.json",
        "comb_candidate.schema.json",
        "spectral_quality.schema.json",
        "stage6_run_manifest.schema.json",
    ):
        _copy(f"schemas/{name}", tmp_path)
    path = tmp_path / "schemas/psd_persistence_pair.schema.json"
    schema = json.loads(path.read_text())
    schema["$schema"] = "draft-old"
    schema["additionalProperties"] = True
    path.write_text(json.dumps(schema))
    errors: list[str] = []
    validate_schemas(tmp_path, errors)
    assert any("draft 2020-12" in error for error in errors)
    assert any("closed object" in error for error in errors)


def test_manifest_validator_detects_gate_and_figure_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage6/run_manifest.json",
        "configs/stage6_psd_topology.yaml",
        "reports/stage6/G6_ACCEPTANCE.json",
        "notebooks/06_psd_persistence.ipynb",
        "reports/stage6/deliverable_manifest.csv",
    ):
        _copy(relative, tmp_path)
    for figure in (ROOT / "reports/stage6/figures").glob("*.svg"):
        _copy(str(figure.relative_to(ROOT)), tmp_path)
    gate = tmp_path / "reports/stage6/G6_ACCEPTANCE.json"
    payload = json.loads(gate.read_text())
    payload["status"] = "fail"
    gate.write_text(json.dumps(payload))
    errors: list[str] = []
    validate_manifest_gate_notebook(tmp_path, errors)
    assert any("acceptance" in error for error in errors)


def test_all_stage6_figures_use_the_project_visual_contract() -> None:
    figures = sorted((ROOT / "reports/stage6/figures").glob("*.svg"))
    assert len(figures) == 7
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        assert "TA-PLOT-1.0" in source
        assert "Machine-readable source:" in source
        assert "TopoAstero-0.7.0" in source

