from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from topoastero.stage4_validation import (
    validate_analytic_simulator,
    validate_config_protocol,
    validate_design_windows,
    validate_null_coverage_compute,
    validate_schemas,
    validate_stage4,
)

ROOT = Path(__file__).parents[2]


def _copy(relative: str, destination: Path) -> Path:
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
    return target


def test_stage4_contract_passes_with_all_prerequisites() -> None:
    assert validate_stage4(ROOT, require_prior_stages=True) == []


def test_g4_records_every_acceptance_clause() -> None:
    gate = json.loads((ROOT / "reports/stage4/G4_ACCEPTANCE.json").read_text())
    assert gate["gate"] == "G4"
    assert gate["status"] == "pass"
    assert gate["population_data_used"] is False
    assert gate["uncalibrated_action"] == "diagnostic_only_or_drop"
    assert len(gate["checks"]) == 7
    assert all(item["status"] == "pass" for item in gate["checks"])


def test_traceability_covers_all_stage4_tasks_and_deliverables() -> None:
    traceability = (ROOT / "reports/stage4/TRACEABILITY_MATRIX.md").read_text()
    for task in range(1, 10):
        assert f"T4.{task}" in traceability
    for deliverable in range(1, 5):
        assert f"D4.{deliverable}" in traceability


def test_factorial_design_is_balanced_and_population_free() -> None:
    with (ROOT / "registries/stage4_factorial_design.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 72
    assert len({row["seed"] for row in rows}) == 72
    for field in (
        "snr_level",
        "duration_days",
        "cadence_seconds",
        "duty_cycle",
        "background_model",
        "gap_pattern",
        "ridge_curvature",
        "alias_target",
    ):
        counts = {
            value: sum(row[field] == value for row in rows)
            for value in {row[field] for row in rows}
        }
        assert max(counts.values()) - min(counts.values()) <= 1
    assert {row["design_role"] for row in rows} == {"pilot_only_no_population_data"}


def test_config_validator_rejects_confirmatory_pointwise_threshold(tmp_path: Path) -> None:
    config = _copy("configs/stage4_simulation.yaml", tmp_path)
    _copy("registries/stage4_confirmation_protocol.yaml", tmp_path)
    config.write_text(
        config.read_text().replace(
            "pointwise_thresholds_are_confirmatory: false",
            "pointwise_thresholds_are_confirmatory: true",
        )
    )
    errors: list[str] = []
    validate_config_protocol(tmp_path, errors)
    assert any("pointwise" in error for error in errors)


def test_null_validator_detects_false_alarm_drift(tmp_path: Path) -> None:
    for relative in (
        "results/stage4/null_calibration.csv",
        "results/stage4/multiplicity_thresholds.csv",
        "results/stage4/uncertainty_coverage.csv",
        "results/stage4/compute_profile.csv",
        "results/stage4/precision_budget.json",
    ):
        _copy(relative, tmp_path)
    path = tmp_path / "results/stage4/null_calibration.csv"
    lines = path.read_text().splitlines()
    fields = lines[1].split(",")
    fields[6] = "0.2"
    lines[1] = ",".join(fields)
    path.write_text("\n".join(lines) + "\n")
    errors: list[str] = []
    validate_null_coverage_compute(tmp_path, errors)
    assert any("FWER gate failed" in error for error in errors)


def test_analytic_validator_detects_failed_and_incomplete_evidence(tmp_path: Path) -> None:
    for relative in (
        "results/stage4/analytic_cases.csv",
        "results/stage4/simulator_validation.csv",
        "results/stage4/mode_recovery.csv",
        "results/stage4/sample_spectrum.csv",
        "results/stage4/sample_light_curve.csv",
    ):
        _copy(relative, tmp_path)
    analytic = tmp_path / "results/stage4/analytic_cases.csv"
    analytic.write_text(analytic.read_text().replace(",pass,", ",fail,", 1))
    recovery = tmp_path / "results/stage4/mode_recovery.csv"
    recovery.write_text(recovery.read_text().replace(",pass\n", ",fail\n", 1))
    errors: list[str] = []
    validate_analytic_simulator(tmp_path, errors)
    assert any("analytic regression failed" in error for error in errors)
    assert any("frequency, height, and linewidth" in error for error in errors)


def test_design_validator_detects_duplicate_seed_and_incomplete_execution(tmp_path: Path) -> None:
    for relative in (
        "registries/stage4_factorial_design.csv",
        "results/stage4/factorial_pilot.csv",
        "data/derived/stage4/mission_window_templates.csv",
        "data/manifests/stage2/rudy_kepler_products.csv",
        "data/manifests/stage2/rudy_tess_products.csv",
    ):
        _copy(relative, tmp_path)
    design = tmp_path / "registries/stage4_factorial_design.csv"
    lines = design.read_text().splitlines()
    first_seed = lines[1].split(",")[1]
    fields = lines[2].split(",")
    fields[1] = first_seed
    lines[2] = ",".join(fields)
    design.write_text("\n".join(lines) + "\n")
    execution = tmp_path / "results/stage4/factorial_pilot.csv"
    execution_lines = execution.read_text().splitlines()[:-1]
    header = execution_lines[0].split(",")
    duty_index = header.index("effective_duty_cycle")
    injection_index = header.index("injected_spacing_uHz")
    operator_index = header.index("window_operator")
    for index in range(1, len(execution_lines)):
        fields = execution_lines[index].split(",")
        fields[operator_index] = "wrong_operator"
        if index == 1:
            fields[injection_index] = "999"
            fields[duty_index] = "1"
        execution_lines[index] = ",".join(fields)
    execution.write_text("\n".join(execution_lines) + "\n")
    errors: list[str] = []
    validate_design_windows(tmp_path, errors)
    assert any("seeds must be unique" in error for error in errors)
    assert any("72 factorial cells" in error for error in errors)
    assert any("alias injection drift" in error for error in errors)
    assert any("effective duty exceeds" in error for error in errors)
    assert any("registered ideal operator" in error for error in errors)
    assert any("registered leakage operator" in error for error in errors)
    assert any("payload-window alias operator" in error for error in errors)


def test_schema_validator_detects_open_and_wrong_draft_schema(tmp_path: Path) -> None:
    for name in (
        "simulation_design.schema.json",
        "null_calibration.schema.json",
        "coverage_result.schema.json",
        "compute_profile.schema.json",
        "stage4_run_manifest.schema.json",
    ):
        _copy(f"schemas/{name}", tmp_path)
    path = tmp_path / "schemas/simulation_design.schema.json"
    schema = json.loads(path.read_text())
    schema["$schema"] = "draft-old"
    schema["additionalProperties"] = True
    path.write_text(json.dumps(schema))
    errors: list[str] = []
    validate_schemas(tmp_path, errors)
    assert any("draft 2020-12" in error for error in errors)
    assert any("closed object" in error for error in errors)


def test_all_stage4_figures_use_the_project_visual_contract() -> None:
    figures = sorted((ROOT / "reports/stage4/figures").glob("*.svg"))
    assert len(figures) == 6
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        assert "TA-PLOT-1.0" in source
        assert "Machine-readable source:" in source
        assert "TopoAstero-0.5.0" in source
