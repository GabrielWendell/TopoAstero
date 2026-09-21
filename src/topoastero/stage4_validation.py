"""Offline validation for Stage 4 analytic and stochastic laboratory evidence."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage3_validation import validate_stage3

REQUIRED_SCHEMAS = {
    "simulation_design.schema.json",
    "null_calibration.schema.json",
    "coverage_result.schema.json",
    "compute_profile.schema.json",
    "stage4_run_manifest.schema.json",
}
REQUIRED_FILES = [
    "configs/stage4_simulation.yaml",
    "registries/stage4_factorial_design.csv",
    "registries/stage4_confirmation_protocol.yaml",
    "data/derived/stage4/mission_window_templates.csv",
    "docs/derivations/STAGE4_ANALYTIC_CASES.md",
    "docs/science/STOCHASTIC_OSCILLATOR_MODEL.md",
    "docs/protocols/STAGE4_SIMULATION_PROTOCOL.md",
    "docs/protocols/STAGE4_CONFIRMATION_PROTOCOL.md",
    "notebooks/04_simulation_lab.ipynb",
    "results/stage4/analytic_cases.csv",
    "results/stage4/simulator_validation.csv",
    "results/stage4/mode_recovery.csv",
    "results/stage4/factorial_pilot.csv",
    "results/stage4/null_calibration.csv",
    "results/stage4/multiplicity_thresholds.csv",
    "results/stage4/uncertainty_coverage.csv",
    "results/stage4/compute_profile.csv",
    "results/stage4/precision_budget.json",
    "results/stage4/sample_spectrum.csv",
    "results/stage4/sample_light_curve.csv",
    "results/stage4/run_manifest.json",
    "reports/stage4/STAGE4_REPORT.md",
    "reports/stage4/SIMULATOR_VALIDATION.md",
    "reports/stage4/NULL_CALIBRATION_REPORT.md",
    "reports/stage4/UNCERTAINTY_AND_COMPUTE_REPORT.md",
    "reports/stage4/TRACEABILITY_MATRIX.md",
    "reports/stage4/G4_ACCEPTANCE.json",
    "reports/stage4/deliverable_manifest.csv",
    "reports/stage4/figures/analytic_cases.svg",
    "reports/stage4/figures/simulator_recovery.svg",
    "reports/stage4/figures/mission_observation_effects.svg",
    "reports/stage4/figures/null_calibration.svg",
    "reports/stage4/figures/coverage_map.svg",
    "reports/stage4/figures/compute_profile.svg",
    "src/topoastero/simulation_lab.py",
    "workflows/build_stage4_window_templates.py",
    "workflows/run_stage4_simulation_lab.py",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], field: str, context: str, errors: list[str]) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError):
        errors.append(f"{context} has invalid {field}")
        return math.nan
    if not math.isfinite(value):
        errors.append(f"{context} has non-finite {field}")
    return value


def validate_schemas(root: Path, errors: list[str]) -> None:
    for name in sorted(REQUIRED_SCHEMAS):
        try:
            schema = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid Stage 4 schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_config_protocol(root: Path, errors: list[str]) -> None:
    config = load_yaml(root / "configs/stage4_simulation.yaml")
    if config.get("config_id") != "TA-STAGE4-SIMULATION-1.0":
        errors.append("Stage 4 config has an unexpected config_id")
    if config.get("software_version") != "TopoAstero-0.5.0":
        errors.append("Stage 4 config must freeze TopoAstero-0.5.0")
    if config.get("factorial_pilot", {}).get("cells") != 72:
        errors.append("Stage 4 pilot must freeze 72 cells")
    nulls = config.get("null_calibration", {})
    required_nulls = {
        "background_only",
        "randomized_comb",
        "white_noise",
        "red_noise",
        "phase_randomized",
        "iaaft",
        "real_window",
    }
    if set(nulls.get("families", [])) != required_nulls:
        errors.append("Stage 4 config must register all seven null families")
    if nulls.get("calibration_realizations") != 256 or nulls.get("evaluation_realizations") != 256:
        errors.append("null calibration/evaluation must each use 256 realizations")
    if nulls.get("pointwise_thresholds_are_confirmatory") is not False:
        errors.append("pointwise thresholds cannot be confirmatory")
    protocol = load_yaml(root / "registries/stage4_confirmation_protocol.yaml")
    if (
        protocol.get("protocol_id") != "TA-STAGE4-CONFIRMATION-1.0"
        or protocol.get("status") != "locked"
    ):
        errors.append("Stage 4 confirmation protocol version 1.0 must be locked")
    if protocol.get("population_data_seen_for_topological_analysis") is not False:
        errors.append("confirmation protocol indicates population topological data were seen")
    if (
        protocol.get("representation_rule", {}).get("uncalibrated_action")
        != "diagnostic_only_or_drop"
    ):
        errors.append("uncalibrated representations must be diagnostic-only or dropped")
    stopping = " ".join(str(item) for item in protocol.get("stopping_rules", []))
    if "do not stop for significance" not in stopping:
        errors.append("confirmation stopping rule must prohibit significance stopping")


def validate_analytic_simulator(root: Path, errors: list[str]) -> None:
    analytic = _read_csv(root / "results/stage4/analytic_cases.csv")
    if len(analytic) != 12 or len({row.get("case_id") for row in analytic}) != 12:
        errors.append("analytic suite must contain 12 unique cases")
    if any(row.get("status") != "pass" for row in analytic):
        errors.append("an analytic regression failed")
    expected = {
        "constant_finite_H0_bars",
        "impulse_essential_birth",
        "peak_persistence_prominence",
        "sinusoid_delay_ellipse",
        "two_sinusoid_delay_rank",
        "comb_true_spacing_ridges",
        "comb_half_spacing_alias",
        "comb_double_spacing_alias",
        "gaussian_half_width",
        "lorentzian_half_width",
        "straight_ridge_mismatch_RMS",
        "curved_ridge_RMS",
    }
    if {row.get("construction") for row in analytic} != expected:
        errors.append("analytic suite does not cover all frozen constructions")
    for row in analytic:
        if (
            _float(row, "absolute_error", "analytic row", errors)
            > _float(row, "tolerance", "analytic row", errors) + 1e-14
        ):
            errors.append(f"analytic tolerance exceeded: {row.get('case_id')}")

    validation = _read_csv(root / "results/stage4/simulator_validation.csv")
    if len(validation) != 4 or any(row.get("status") != "pass" for row in validation):
        errors.append("the simulator distribution/variance validation is incomplete or failed")
    recovery = _read_csv(root / "results/stage4/mode_recovery.csv")
    if {row.get("parameter") for row in recovery} != {
        "frequency_uHz",
        "height_ppm2_per_uHz",
        "linewidth_uHz",
    } or any(row.get("status") != "pass" for row in recovery):
        errors.append("mode frequency, height, and linewidth must all recover within tolerance")
    if len(_read_csv(root / "results/stage4/sample_spectrum.csv")) != 1000:
        errors.append("sample spectrum must contain the frozen 1,000-row excerpt")
    if len(_read_csv(root / "results/stage4/sample_light_curve.csv")) < 1000:
        errors.append("sample light curve excerpt is unexpectedly short")


def validate_design_windows(root: Path, errors: list[str]) -> None:
    rows = _read_csv(root / "registries/stage4_factorial_design.csv")
    if len(rows) != 72 or len({row.get("cell_id") for row in rows}) != 72:
        errors.append("factorial pilot must contain 72 unique cells")
        return
    if len({row.get("seed") for row in rows}) != 72:
        errors.append("factorial pilot seeds must be unique")
    expected_levels = {
        "snr_level": {"low", "medium", "high"},
        "duration_days": {"27.4", "90.0", "109.6", "360.0"},
        "duty_cycle": {"0.5", "0.8", "0.95"},
        "lifetime_days": {"2.0", "10.0", "30.0"},
        "background_model": {"correct", "misspecified"},
        "gap_pattern": {"none", "random", "kepler_q5", "tess_s14"},
        "ridge_curvature": {"none", "weak", "strong"},
        "alias_target": {"none", "half_dnu", "double_dnu"},
    }
    for field, levels in expected_levels.items():
        observed = {row.get(field, "") for row in rows}
        if observed != levels:
            errors.append(f"factorial pilot has incomplete {field} levels")
        counts = Counter(row.get(field, "") for row in rows)
        if max(counts.values()) - min(counts.values()) > 1:
            errors.append(f"factorial pilot is not balanced for {field}")
    if any(row.get("design_role") != "pilot_only_no_population_data" for row in rows):
        errors.append("a Stage 4 design cell is not marked pilot-only")
    execution = _read_csv(root / "results/stage4/factorial_pilot.csv")
    if len(execution) != 72 or any(row.get("status") != "complete" for row in execution):
        errors.append("all 72 factorial cells must be completed")
    if {row["cell_id"] for row in execution} != {row["cell_id"] for row in rows}:
        errors.append("factorial execution does not match the frozen design")
    alias_multiplier = {"half_dnu": 0.5, "none": 1.0, "double_dnu": 2.0}
    for row in execution:
        expected_spacing = _float(row, "dnu_uHz", "factorial row", errors) * alias_multiplier.get(
            row.get("alias_target", ""), math.nan
        )
        if not math.isclose(
            _float(row, "injected_spacing_uHz", "factorial row", errors),
            expected_spacing,
            rel_tol=1e-10,
        ):
            errors.append(f"factorial alias injection drift: {row.get('cell_id')}")
        if _float(row, "effective_duty_cycle", "factorial row", errors) > _float(
            row, "duty_cycle", "factorial row", errors
        ):
            errors.append(f"effective duty exceeds registered duty: {row.get('cell_id')}")
    operators = {row.get("gap_pattern"): row.get("window_operator", "") for row in execution}
    if operators.get("none") != "ideal_exposure_weight":
        errors.append("gap-free pilot cells do not use the registered ideal operator")
    if operators.get("random") != "random_gap_local_leakage":
        errors.append("random-gap pilot cells do not use the registered leakage operator")
    for mission in ("kepler_q5", "tess_s14"):
        if not operators.get(mission, "").startswith("payload_window_alias_pair_"):
            errors.append(f"{mission} pilot cells do not use a payload-window alias operator")

    windows = _read_csv(root / "data/derived/stage4/mission_window_templates.csv")
    if {row.get("template_id") for row in windows} != {"kepler_q5", "tess_s14"}:
        errors.append("real-window table must cover Kepler Q5 and TESS sector 14")
    if any(len(row.get("source_sha256", "")) != 64 for row in windows):
        errors.append("a real-window interval lacks its source payload checksum")
    manifests = [
        *_read_csv(root / "data/manifests/stage2/rudy_kepler_products.csv"),
        *_read_csv(root / "data/manifests/stage2/rudy_tess_products.csv"),
    ]
    sources = {row["product_key"]: row["sha256"] for row in manifests}
    for row in windows:
        if sources.get(row.get("product_key", "")) != row.get("source_sha256"):
            errors.append(f"window interval source mismatch: {row.get('interval_id')}")
            break


def validate_null_coverage_compute(root: Path, errors: list[str]) -> None:
    nulls = _read_csv(root / "results/stage4/null_calibration.csv")
    if len(nulls) != 7 or len({row.get("null_family") for row in nulls}) != 7:
        errors.append("null calibration must contain seven unique families")
    for row in nulls:
        if row.get("status") != "pass" or _float(row, "empirical_fwer", "null row", errors) > 0.08:
            errors.append(f"null FWER gate failed: {row.get('null_family')}")
        if row.get("calibration_seed_range") == row.get("evaluation_seed_range"):
            errors.append(f"null seed streams overlap: {row.get('null_family')}")
        if row.get("registered_statistics") != "32":
            errors.append(f"null multiplicity scope drift: {row.get('null_family')}")
    thresholds = _read_csv(root / "results/stage4/multiplicity_thresholds.csv")
    if len(thresholds) != 14:
        errors.append("multiplicity table must have confirmatory and pointwise rows per null")
    for row in thresholds:
        if (
            row.get("scope") == "pointwise_median_illustration"
            and row.get("confirmatory") != "false"
        ):
            errors.append("a pointwise threshold is incorrectly marked confirmatory")

    coverage = _read_csv(root / "results/stage4/uncertainty_coverage.csv")
    if len(coverage) != 27:
        errors.append("coverage map must contain 27 cells")
    if (
        len(
            {
                (row.get("snr_level"), row.get("duration_days"), row.get("lifetime_days"))
                for row in coverage
            }
        )
        != 27
    ):
        errors.append("coverage map does not span the registered 3x3x3 cells")
    for row in coverage:
        value = _float(row, "empirical_coverage", "coverage row", errors)
        if row.get("status") != "pass" or not 0.90 <= value <= 0.99:
            errors.append(f"coverage gate failed: {row.get('cell_id')}")
        for component in ("realization_sigma_uHz", "pipeline_choice_sigma_uHz"):
            if _float(row, component, "coverage row", errors) < 0:
                errors.append(f"negative uncertainty component: {row.get('cell_id')}")

    compute = _read_csv(root / "results/stage4/compute_profile.csv")
    expected = {
        (representation, size)
        for representation in (
            "superlevel_H0",
            "delay_embedding",
            "FFT_spectrum",
            "null_score_ensemble",
        )
        for size in ("512", "2048", "8192")
    }
    if {(row.get("representation"), row.get("sample_size")) for row in compute} != expected:
        errors.append("compute profile is missing a representation/sample-size cell")
    if any(_float(row, "median_runtime_seconds", "compute row", errors) <= 0 for row in compute):
        errors.append("compute profile contains a nonpositive runtime")
    precision = json.loads(
        (root / "results/stage4/precision_budget.json").read_text(encoding="utf-8")
    )
    if (
        precision.get("minimum_fpr_repetitions") != 212
        or precision.get("selected_fpr_repetitions") != 256
    ):
        errors.append("FPR repetition budget is not derived from its registered MCSE")
    if (
        precision.get("minimum_coverage_repetitions") != 305
        or precision.get("selected_coverage_repetitions") != 320
    ):
        errors.append("coverage repetition budget is not recorded consistently")


def validate_manifest_gate_notebook(root: Path, errors: list[str]) -> None:
    manifest_path = root / "results/stage4/run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != "TA-S04-LAB-R001" or manifest.get("status") != "complete":
        errors.append("Stage 4 run manifest identity/status is invalid")
    if manifest.get("config_sha256") != configuration_hash(root / "configs/stage4_simulation.yaml"):
        errors.append("Stage 4 run manifest config hash is stale")
    if manifest.get("population_data_used") is not False:
        errors.append("Stage 4 run manifest indicates population data use")
    if manifest.get("style_id") != "TA-PLOT-1.0":
        errors.append("Stage 4 run manifest has the wrong plotting style")
    output_paths = {
        record.get("path") for record in manifest.get("outputs", []) if isinstance(record, dict)
    }
    if "registries/stage4_factorial_design.csv" not in output_paths:
        errors.append("Stage 4 run manifest does not seal the frozen factorial design")
    for record in manifest.get("inputs", []):
        target = root / record.get("path", "")
        if not target.is_file() or record.get("sha256") != sha256_file(target):
            errors.append(f"Stage 4 input seal is stale: {record.get('path')}")
    for record in manifest.get("outputs", []):
        target = root / record.get("path", "")
        if not target.is_file():
            errors.append(f"Stage 4 output is missing: {record.get('path')}")
        elif (
            record.get("sha256") != sha256_file(target)
            or record.get("size_bytes") != target.stat().st_size
        ):
            errors.append(f"Stage 4 output seal is stale: {record.get('path')}")
    for figure in sorted((root / "reports/stage4/figures").glob("*.svg")):
        source = figure.read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source:
            errors.append(f"Stage 4 figure lacks style/source metadata: {figure.name}")

    gate = json.loads((root / "reports/stage4/G4_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G4" or gate.get("status") != "pass":
        errors.append("G4 acceptance record must pass")
    if (
        gate.get("population_data_used") is not False
        or gate.get("uncalibrated_action") != "diagnostic_only_or_drop"
    ):
        errors.append("G4 guardrails are not explicit")
    notebook = json.loads((root / "notebooks/04_simulation_lab.ipynb").read_text(encoding="utf-8"))
    if notebook.get("nbformat") != 4 or not notebook.get("cells"):
        errors.append("Stage 4 notebook is not a valid nonempty nbformat-4 document")
    joined = " ".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    if "results/stage4" not in joined or "TA-S04-LAB-R001" not in joined:
        errors.append("Stage 4 notebook is not tied to the governed result set")

    deliverable = _read_csv(root / "reports/stage4/deliverable_manifest.csv")
    if not deliverable or {row.get("deliverable") for row in deliverable} != {
        "D4.1",
        "D4.2",
        "D4.3",
        "D4.4",
        "G4",
        "software",
    }:
        errors.append("Stage 4 deliverable manifest has incomplete groups")
    for row in deliverable:
        path = root / row.get("path", "")
        if not path.is_file():
            errors.append(f"Stage 4 deliverable is missing: {row.get('path')}")
        elif row.get("sha256") != sha256_file(path) or row.get("size_bytes") != str(
            path.stat().st_size
        ):
            errors.append(f"Stage 4 deliverable seal is stale: {row.get('path')}")


def validate_stage4(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Return Stage 4 contract violations; an empty list means G4 is reproducible."""

    repository = Path(root).resolve()
    errors = [
        f"missing required Stage 4 file: {path}"
        for path in REQUIRED_FILES
        if not (repository / path).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_config_protocol(repository, errors)
    validate_analytic_simulator(repository, errors)
    validate_design_windows(repository, errors)
    validate_null_coverage_compute(repository, errors)
    validate_manifest_gate_notebook(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1/2/3 regression: {error}"
            for error in validate_stage3(repository, require_prior_stages=True)
        )
    return errors
