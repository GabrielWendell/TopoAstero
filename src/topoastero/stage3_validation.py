"""Offline validation for Stage 3 classical baselines and observation-model evidence."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage2_validation import validate_stage2

REQUIRED_SCHEMAS = {
    "classical_result.schema.json",
    "preprocessing_branch.schema.json",
    "tess_feasibility.schema.json",
    "stage3_run_manifest.schema.json",
}
REQUIRED_FILES = [
    "configs/stage3_classical.yaml",
    "registries/preprocessing_branches.csv",
    "schemas/classical_result.schema.json",
    "schemas/preprocessing_branch.schema.json",
    "schemas/tess_feasibility.schema.json",
    "schemas/stage3_run_manifest.schema.json",
    "docs/protocols/STAGE3_CLASSICAL_BASELINE_PROTOCOL.md",
    "docs/reproducibility/PLOTTING_STYLE_GUIDE.md",
    "docs/science/CLASSICAL_OBSERVATION_MODEL.md",
    "notebooks/03_rudy_classical_baseline.ipynb",
    "results/stage3/rudy_baseline.csv",
    "results/stage3/pipeline_comparison.csv",
    "results/stage3/background_models.csv",
    "results/stage3/window_atlas.csv",
    "results/stage3/echelle_trials.csv",
    "results/stage3/mode_audit.csv",
    "results/stage3/preprocessing_sensitivity.csv",
    "results/stage3/uncertainty_budget.csv",
    "results/stage3/tess_sector_feasibility.csv",
    "results/stage3/reduced_spectrum.csv",
    "results/stage3/run_manifest.json",
    "reports/stage3/STAGE3_REPORT.md",
    "reports/stage3/PIPELINE_COMPARISON.md",
    "reports/stage3/SENSITIVITY_REPORT.md",
    "reports/stage3/TESS_FEASIBILITY_NOTE.md",
    "reports/stage3/TRACEABILITY_MATRIX.md",
    "reports/stage3/G3_ACCEPTANCE.json",
    "reports/stage3/deliverable_manifest.csv",
    "reports/stage3/figures/rudy_power_spectrum.svg",
    "reports/stage3/figures/background_comparison.svg",
    "reports/stage3/figures/window_atlas.svg",
    "reports/stage3/figures/echelle_trials.svg",
    "reports/stage3/figures/mode_overlay_audit.svg",
    "reports/stage3/figures/tess_sector_feasibility.svg",
    "src/topoastero/classical.py",
    "src/topoastero/style.py",
    "workflows/acquire_stage3_inputs.py",
    "workflows/run_stage3_classical.py",
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
            errors.append(f"invalid Stage 3 schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_config(root: Path, errors: list[str]) -> None:
    config = load_yaml(root / "configs/stage3_classical.yaml")
    if config.get("config_id") != "TA-STAGE3-CLASSICAL-1.0":
        errors.append("Stage 3 config has an unexpected config_id")
    if config.get("software_version") != "TopoAstero-0.4.0":
        errors.append("Stage 3 config must freeze TopoAstero-0.4.0")
    if config.get("inputs", {}).get("kepler_quarters") != [2, 5, 6, 7]:
        errors.append("Stage 3 config must use tutorial quarters 2, 5, 6, and 7")
    if config.get("uncertainty", {}).get("resamples") != 500:
        errors.append("Stage 3 uncertainty must use 500 registered resamples")
    if config.get("gate", {}).get("topology_used_for_branch_selection") is not False:
        errors.append("Stage 3 branch selection must not use topology")
    if config.get("tess_pilot", {}).get("combine_for_detection") is not False:
        errors.append("Stage 3 must not force a combined TESS detection")


def validate_baselines(root: Path, errors: list[str]) -> None:
    rows = _read_csv(root / "results/stage3/rudy_baseline.csv")
    expected_quantities = {"numax", "dnu", "mass", "radius", "logg"}
    if len(rows) != 10 or len({row.get("result_id") for row in rows}) != 10:
        errors.append("Rudy baseline must contain 10 unique pipeline/quantity rows")
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("pipeline", ""), {})[row.get("quantity", "")] = row
        value = _float(row, "value", "baseline row", errors)
        reference = _float(row, "reference_value", "baseline row", errors)
        residual = _float(row, "residual", "baseline row", errors)
        if math.isfinite(value) and math.isfinite(reference) and not math.isclose(
            residual, value - reference, abs_tol=1e-8
        ):
            errors.append(f"baseline residual mismatch: {row.get('result_id')}")
        for field in (
            "random_uncertainty",
            "pipeline_choice_uncertainty",
            "reference_uncertainty_minus",
            "reference_uncertainty_plus",
            "joint_uncertainty",
        ):
            if _float(row, field, "baseline row", errors) < 0:
                errors.append(f"baseline uncertainty is negative: {row.get('result_id')}")
        if row.get("agreement_status") not in {
            "within_joint_uncertainty",
            "documented_convention_or_model_difference",
        }:
            errors.append(f"baseline agreement is undocumented: {row.get('result_id')}")
    if set(grouped) != {"lightkurve_acf2d", "independent_harvey_acf"}:
        errors.append("baseline must contain Lightkurve and independent pipelines")
        return
    if any(set(grouped[pipeline]) != expected_quantities for pipeline in grouped):
        errors.append("each baseline pipeline must report all five classical quantities")
    tutorial = {
        "numax": (2145.0, 0.1),
        "dnu": (103.11, 0.01),
        "mass": (1.08, 0.02),
        "radius": (1.23, 0.02),
        "logg": (4.29, 0.02),
    }
    for quantity, (expected, tolerance) in tutorial.items():
        value = float(grouped["lightkurve_acf2d"][quantity]["value"])
        if abs(value - expected) > tolerance:
            errors.append(f"Lightkurve tutorial reproduction drift: {quantity}")
    independent = grouped["independent_harvey_acf"]
    if not 2100 <= float(independent["numax"]["value"]) <= 2300:
        errors.append("independent numax lies outside its frozen defensible range")
    if not 102 <= float(independent["dnu"]["value"]) <= 104:
        errors.append("independent dnu lies outside its frozen defensible range")
    comparison = _read_csv(root / "results/stage3/pipeline_comparison.csv")
    if len(comparison) != 5 or {row["quantity"] for row in comparison} != expected_quantities:
        errors.append("pipeline comparison must reconcile the five classical quantities")
    elif any(row["status"] != "reconciled_distinct_estimators" for row in comparison):
        errors.append("pipeline comparison has an unreconciled convention")


def validate_observation_model(root: Path, errors: list[str]) -> None:
    backgrounds = _read_csv(root / "results/stage3/background_models.csv")
    if [row.get("component_count") for row in backgrounds] != ["0", "1", "2"]:
        errors.append("background comparison must retain H0, H1, and H2")
    selected = [row for row in backgrounds if row.get("selected_by_minimum_bic") == "true"]
    if len(selected) != 1 or selected[0].get("model_id") != "BG-H2":
        errors.append("the frozen minimum-BIC background must be BG-H2")
    for row in backgrounds:
        for field in ("white_noise_ppm2_per_uHz", "negative_log_likelihood", "aic", "bic"):
            if _float(row, field, "background row", errors) <= 0:
                errors.append(f"background {field} must be positive")

    windows = _read_csv(root / "results/stage3/window_atlas.csv")
    expected_windows = {"Q2", "Q5", "Q6", "Q7", "combined_absolute", "combined_compressed"}
    if len(windows) != 6 or {row.get("window_id") for row in windows} != expected_windows:
        errors.append("window atlas must cover four quarters and two combination choices")
    for row in windows:
        duty = _float(row, "duty_cycle", "window row", errors)
        resolution = _float(row, "resolution_uHz", "window row", errors)
        if not 0 < duty <= 1 or resolution <= 0:
            errors.append(f"invalid window metrics: {row.get('window_id')}")
    absolute = next((row for row in windows if row.get("window_id") == "combined_absolute"), {})
    compressed = next((row for row in windows if row.get("window_id") == "combined_compressed"), {})
    if absolute.get("time_treatment") != "absolute_time" or compressed.get("assessment") != "diagnostic_only_not_primary":
        errors.append("window stitching choices are not explicitly distinguished")

    echelle = _read_csv(root / "results/stage3/echelle_trials.csv")
    if len(echelle) != 3 or any(row.get("phase_boundary") != "circular_wrap" for row in echelle):
        errors.append("echelle suite must contain three circular-boundary trials")
    if any("bottom_to_top" not in row.get("orientation", "") for row in echelle):
        errors.append("echelle orientation is not standardized")


def validate_modes_branches_uncertainty(root: Path, errors: list[str]) -> None:
    modes = _read_csv(root / "results/stage3/mode_audit.csv")
    if len(modes) != 42 or len({row.get("row_id") for row in modes}) != 42:
        errors.append("mode audit must contain all 42 unique published modes")
    for row in modes:
        if abs(_float(row, "residual_uHz", "mode row", errors)) > 2.500001:
            errors.append(f"mode falls outside the frozen match window: {row.get('row_id')}")
        if row.get("published_to_echelle_order_offset") not in {"1", "2"}:
            errors.append(f"mode order convention is not reconciled: {row.get('row_id')}")

    branches = _read_csv(root / "registries/preprocessing_branches.csv")
    if len(branches) != 6 or len({row.get("branch_id") for row in branches}) != 6:
        errors.append("preprocessing registry must contain six unique branches")
    if any(row.get("selection_basis") != "classical_predeclared_no_topology" for row in branches):
        errors.append("a preprocessing branch was not frozen independently of topology")
    sensitivity = _read_csv(root / "results/stage3/preprocessing_sensitivity.csv")
    if {row.get("branch_id") for row in sensitivity} != {"PP-01", "PP-02", "PP-03", "PP-04"}:
        errors.append("the four registered Kepler branches were not executed")
    if any(row.get("selection_used_topology") != "false" for row in sensitivity):
        errors.append("sensitivity output indicates topological branch selection")

    uncertainty = _read_csv(root / "results/stage3/uncertainty_budget.csv")
    if len(uncertainty) != 5 or {row.get("quantity") for row in uncertainty} != {
        "numax", "dnu", "mass", "radius", "logg"
    }:
        errors.append("uncertainty budget must cover all five classical quantities")
    for row in uncertainty:
        if row.get("resamples") != "500" or row.get("master_seed") != "20260721":
            errors.append(f"uncertainty registration drift: {row.get('quantity')}")
        components = [
            _float(row, field, "uncertainty row", errors)
            for field in (
                "random_bootstrap_sigma",
                "pipeline_choice_half_range",
                "reference_interval_half_width",
            )
        ]
        expected = math.sqrt(sum(value * value for value in components))
        actual = _float(row, "combined_joint_uncertainty", "uncertainty row", errors)
        if not math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-9):
            errors.append(f"uncertainty quadrature mismatch: {row.get('quantity')}")


def validate_tess(root: Path, errors: list[str]) -> None:
    rows = _read_csv(root / "results/stage3/tess_sector_feasibility.csv")
    expected_sectors = {14, 15, 40, 41, 53, 55, 74, 75, 80, 81, 82}
    if len(rows) != 11 or {int(row.get("sector", 0)) for row in rows} != expected_sectors:
        errors.append("TESS pilot must cover the 11 frozen SPOC sectors individually")
    if any(row.get("author") != "SPOC" for row in rows):
        errors.append("TESS pilot mixes product authors")
    if any(row.get("combination_decision") != "do_not_combine_for_detection_at_G3" for row in rows):
        errors.append("TESS pilot forces or leaves ambiguous a combined detection")
    counts = Counter(row.get("classification") for row in rows)
    if counts != {"not_detected_individually": 10, "marginal_candidate_not_confirmation": 1}:
        errors.append(f"TESS feasibility classifications drifted: {dict(counts)}")


def validate_manifest_gate_and_notebook(root: Path, errors: list[str]) -> None:
    manifest = json.loads((root / "results/stage3/run_manifest.json").read_text(encoding="utf-8"))
    if "\\" in str(manifest.get("config_path", "")):
        errors.append("Stage 3 run manifest config path is not POSIX portable")
    if manifest.get("config_sha256") != configuration_hash(root / "configs/stage3_classical.yaml"):
        errors.append("Stage 3 run manifest has the wrong configuration hash")
    if manifest.get("software_version") != "TopoAstero-0.4.0" or manifest.get("topology_used") is not False:
        errors.append("Stage 3 run manifest software/topology declaration is invalid")
    if manifest.get("plot_style") != {
        "style_id": "TA-PLOT-1.0",
        "module": "topoastero.style",
        "context": "paper",
        "use_tex": False,
        "primary_format": "svg",
    }:
        errors.append("Stage 3 run manifest has an invalid plotting-style declaration")
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list) or len(inputs) != 21:
        errors.append("Stage 3 run manifest must contain 21 selected payloads")
    else:
        expected_rows = _read_csv(root / "data/manifests/stage2/rudy_kepler_products.csv")
        expected_rows.extend(
            row
            for row in _read_csv(root / "data/manifests/stage2/rudy_tess_products.csv")
            if row["author"] == "SPOC"
        )
        expected = {row["product_key"]: row["sha256"] for row in expected_rows}
        actual = {str(row.get("product_key")): str(row.get("sha256")) for row in inputs if isinstance(row, dict)}
        if actual != expected:
            errors.append("Stage 3 run inputs do not match the frozen Stage 2 product subset")
    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list) or len(outputs) < 16:
        errors.append("Stage 3 run manifest has too few outputs")
    else:
        for record in outputs:
            if not isinstance(record, dict):
                errors.append("Stage 3 run manifest has a malformed output")
                continue
            serialized_path = str(record.get("path", ""))
            if "\\" in serialized_path:
                errors.append(f"Stage 3 output path is not POSIX portable: {serialized_path}")
            path = root / serialized_path
            if not path.is_file() or record.get("sha256") != sha256_file(path):
                errors.append(f"Stage 3 output checksum mismatch: {record.get('path', '')}")

    for path in sorted((root / "reports/stage3/figures").glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        if (
            path.stat().st_size < 1000
            or "<svg" not in text
            or SOFTWARE_MARKER not in text
            or STYLE_MARKER not in text
            or "Machine-readable source:" not in text
        ):
            errors.append(f"Stage 3 figure lacks valid SVG/provenance metadata: {path.name}")

    notebook = json.loads(
        (root / "notebooks/03_rudy_classical_baseline.ipynb").read_text(encoding="utf-8")
    )
    notebook_metadata = notebook.get("metadata", {}).get("topoastero", {})
    if (
        notebook.get("nbformat") != 4
        or notebook_metadata.get("executed") is not True
        or notebook_metadata.get("plot_style") != STYLE_MARKER
    ):
        errors.append("Stage 3 benchmark notebook is not an executed nbformat-4 artifact")
    notebook_text = json.dumps(notebook)
    if not all(token in notebook_text for token in ("T3.1-T3.2", "T3.3-T3.8", "T3.9", "G3")):
        errors.append("Stage 3 notebook does not cover the required task groups")

    gate = json.loads((root / "reports/stage3/G3_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G3" or gate.get("decision") != "PASS" or gate.get("topology_inspected") is not False:
        errors.append("G3 acceptance must declare a topology-free PASS")
    clauses = gate.get("clauses", [])
    if not isinstance(clauses, list) or len(clauses) < 5 or any(
        not isinstance(clause, dict) or clause.get("status") != "pass" for clause in clauses
    ):
        errors.append("every G3 acceptance clause must pass")

    deliverables = _read_csv(root / "reports/stage3/deliverable_manifest.csv")
    if not deliverables or len({row.get("path") for row in deliverables}) != len(deliverables):
        errors.append("Stage 3 deliverable manifest is empty or has duplicate paths")
    for row in deliverables:
        path = root / row.get("path", "")
        if not path.is_file() or row.get("sha256") != sha256_file(path):
            errors.append(f"Stage 3 deliverable checksum mismatch: {row.get('path', '')}")


SOFTWARE_MARKER = "TopoAstero-0.4.0"
STYLE_MARKER = "TA-PLOT-1.0"


def validate_stage3(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Validate T3.1-T3.9, D3.1-D3.5, Gate G3, and optional earlier-stage regressions."""

    repository = Path(root).resolve()
    errors = [
        f"Required Stage 3 file missing: {relative}"
        for relative in REQUIRED_FILES
        if not (repository / relative).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_config(repository, errors)
    validate_baselines(repository, errors)
    validate_observation_model(repository, errors)
    validate_modes_branches_uncertainty(repository, errors)
    validate_tess(repository, errors)
    validate_manifest_gate_and_notebook(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1/2 regression: {error}"
            for error in validate_stage2(repository, require_prior_stages=True)
        )
    return errors
