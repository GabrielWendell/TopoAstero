"""Offline validation for Stage 6 persistent power-spectrum topology evidence."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage5_validation import validate_stage5

REQUIRED_SCHEMAS = {
    "psd_persistence_pair.schema.json",
    "numax_estimate.schema.json",
    "comb_candidate.schema.json",
    "spectral_quality.schema.json",
    "stage6_run_manifest.schema.json",
}

REQUIRED_FILES = [
    "configs/stage6_psd_topology.yaml",
    "registries/stage6_normalization_contract.yaml",
    "registries/stage6_quality_flags.yaml",
    "registries/stage6_simulation_lock.yaml",
    "docs/science/PSD_PERSISTENCE_METHOD.md",
    "docs/protocols/STAGE6_PSD_TOPOLOGY_PROTOCOL.md",
    "notebooks/06_psd_persistence.ipynb",
    "results/stage6/normalization_audit.csv",
    "results/stage6/peak_diagram.json",
    "results/stage6/equivalence_audit.csv",
    "results/stage6/numax_benchmark.csv",
    "results/stage6/numax_summary.csv",
    "results/stage6/comb_candidates.csv",
    "results/stage6/comb_benchmark.csv",
    "results/stage6/null_calibration.csv",
    "results/stage6/null_draw_maxima.csv",
    "results/stage6/robustness_atlas.csv",
    "results/stage6/quality_flags.csv",
    "results/stage6/pysyd_adapter_audit.json",
    "results/stage6/environment.json",
    "results/stage6/run_manifest.json",
    "reports/stage6/EQUIVALENCE_AND_ABLATION_REPORT.md",
    "reports/stage6/NULL_CALIBRATION_AND_QC_REPORT.md",
    "reports/stage6/ROBUSTNESS_ATLAS.md",
    "reports/stage6/STAGE6_REPORT.md",
    "reports/stage6/TRACEABILITY_MATRIX.md",
    "reports/stage6/G6_ACCEPTANCE.json",
    "reports/stage6/deliverable_manifest.csv",
    "reports/stage6/figures/normalized_spectrum_and_diagram.svg",
    "reports/stage6/figures/prominence_equivalence.svg",
    "reports/stage6/figures/numax_comparison.svg",
    "reports/stage6/figures/comb_alias_atlas.svg",
    "reports/stage6/figures/null_calibration.svg",
    "reports/stage6/figures/robustness_atlas.svg",
    "reports/stage6/figures/quality_flags.svg",
    "src/topoastero/spectral_topology.py",
    "workflows/run_stage6_psd_topology.py",
]

NORMALIZATIONS = {"ratio", "log_ratio", "whitened_residual", "uncertainty_zscore"}
QUALITY_FLAGS = {
    "absent_envelope",
    "alias_ambiguity",
    "insufficient_orders",
    "window_contamination",
    "unstable_background",
}
NUMAX_METHODS = {"persistence_centroid", "smoothed_envelope", "pysyd_style_control"}
COMB_METHODS = {"persistence_comb", "acf", "psps"}


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
            errors.append(f"invalid Stage 6 schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_config_registries(root: Path, errors: list[str]) -> None:
    config = load_yaml(root / "configs/stage6_psd_topology.yaml")
    if config.get("config_id") != "TA-STAGE6-PSD-1.0":
        errors.append("Stage 6 config has an unexpected config_id")
    if config.get("software_version") != "TopoAstero-0.7.0":
        errors.append("Stage 6 config must freeze TopoAstero-0.7.0")
    scope = config.get("data_scope", {})
    if scope.get("expected_cells") != 72 or scope.get("role") != "locked_simulation_confirmation":
        errors.append("Stage 6 must use the locked 72-cell simulation panel")
    if scope.get("population_data_allowed") is not False or scope.get("final_holdout_allowed") is not False:
        errors.append("Stage 6 config must bar population and final-holdout access")
    normalization = config.get("normalization", {})
    observed = {normalization.get("primary"), *normalization.get("sensitivities", [])}
    if observed != NORMALIZATIONS or normalization.get("primary") != "log_ratio":
        errors.append("Stage 6 normalization set or primary method drifted")
    persistence = config.get("persistence", {})
    if persistence.get("backend") != "exact_path_H0" or persistence.get("coefficient_field") != "F2":
        errors.append("Stage 6 exact H0/F2 contract drifted")
    if persistence.get("essential_rule") != "retain_localization_exclude_numeric_summaries":
        errors.append("Stage 6 essential-class rule drifted")
    if set(config.get("comb", {}).get("alternatives", [])) != {"half", "nominal", "double"}:
        errors.append("Stage 6 must preserve all three spacing alternatives")
    if config.get("comb", {}).get("force_single_spacing") is not False:
        errors.append("Stage 6 must not force a single spacing")
    if set(config.get("quality", {}).get("flags", [])) != QUALITY_FLAGS:
        errors.append("Stage 6 quality-flag set drifted")

    contract = load_yaml(root / "registries/stage6_normalization_contract.yaml")
    records = contract.get("methods", [])
    if contract.get("status") != "locked" or {row.get("method") for row in records} != NORMALIZATIONS:
        errors.append("normalization registry must lock all four methods")
    if sum(row.get("role") == "primary" for row in records) != 1:
        errors.append("normalization registry must have exactly one primary")
    flags = load_yaml(root / "registries/stage6_quality_flags.yaml")
    if flags.get("status") != "locked" or {row.get("code") for row in flags.get("flags", [])} != QUALITY_FLAGS:
        errors.append("quality registry must lock all five reason codes")

    lock = load_yaml(root / "registries/stage6_simulation_lock.yaml")
    if lock.get("status") != "locked_before_stage6_execution":
        errors.append("Stage 6 simulation lock is not frozen")
    for key in ("source_design", "source_execution", "stage5_selection"):
        record = lock.get(key, {})
        path = root / str(record.get("path", ""))
        if not path.is_file() or record.get("sha256") != sha256_file(path):
            errors.append(f"Stage 6 simulation-lock seal is stale: {key}")
    policy = lock.get("inspection_policy", {})
    if policy.get("population_data_used") is not False or policy.get("final_holdout_used") is not False:
        errors.append("Stage 6 simulation lock indicates forbidden data use")


def validate_persistence_equivalence(root: Path, errors: list[str]) -> None:
    normalization = _read_csv(root / "results/stage6/normalization_audit.csv")
    if len(normalization) != 4 or {row.get("method") for row in normalization} != NORMALIZATIONS:
        errors.append("normalization audit must cover four registered alternatives")
    if any(row.get("status") != "pass" for row in normalization):
        errors.append("a Stage 6 normalization sensitivity failed")

    payload = json.loads((root / "results/stage6/peak_diagram.json").read_text(encoding="utf-8"))
    pairs = payload.get("pairs", [])
    if payload.get("normalization") != "log_ratio" or len(pairs) < 20:
        errors.append("representative peak diagram is incomplete or not primary-normalized")
    if sum(bool(pair.get("essential")) for pair in pairs) != 1:
        errors.append("peak diagram must contain exactly one essential H0 class")
    for pair in pairs:
        if pair.get("essential"):
            if any(pair.get(field) is not None for field in ("saddle_index", "saddle_frequency_uHz", "death_value", "persistence")):
                errors.append("essential PSD class received an artificial death")
        elif pair.get("saddle_index") is None or pair.get("saddle_frequency_uHz") is None or not isinstance(pair.get("persistence"), (int, float)) or pair["persistence"] <= 0:
            errors.append(f"finite PSD class is not localized: {pair.get('pair_id')}")

    equivalence = _read_csv(root / "results/stage6/equivalence_audit.csv")
    if len(equivalence) < 16 or {row.get("domain") for row in equivalence} != {"analytic", "locked_realistic_spectrum"}:
        errors.append("prominence equivalence must cover analytic and realistic spectra")
    for row in equivalence:
        if row.get("status") != "pass" or _float(row, "maximum_absolute_error", "equivalence row", errors) > 1e-10:
            errors.append(f"persistence/prominence equivalence failed: {row.get('case_id')}")
        if row.get("interpretation") != "exact_equivalence_organization_only":
            errors.append(f"equivalence claim is overstated: {row.get('case_id')}")


def validate_estimators(root: Path, errors: list[str]) -> None:
    numax = _read_csv(root / "results/stage6/numax_benchmark.csv")
    design = _read_csv(root / "registries/stage4_factorial_design.csv")
    cell_ids = {row.get("cell_id") for row in design}
    if len(numax) != 216 or {row.get("cell_id") for row in numax} != cell_ids or {row.get("method") for row in numax} != NUMAX_METHODS:
        errors.append("nu_max benchmark must contain three paired methods for all 72 cells")
    external = [row for row in numax if row.get("method") == "pysyd_style_control"]
    if any(row.get("external_pysyd_executed") != "false" or row.get("implementation") != "offline_style_control_not_pysyd_package" for row in external):
        errors.append("pySYD style controls are mislabeled as external executions")
    topological_evaluation = [row for row in numax if row.get("method") == "persistence_centroid" and row.get("role") == "evaluation"]
    coverage = sum(row.get("covered") == "true" for row in topological_evaluation) / len(topological_evaluation)
    if not 0.85 <= coverage <= 1.0:
        errors.append("Stage 6 evaluation interval coverage is outside the gate")

    summaries = _read_csv(root / "results/stage6/numax_summary.csv")
    factors = {row.get("factor") for row in summaries}
    if not {"overall", "snr_level", "duration_days", "duty_cycle", "lifetime_days"}.issubset(factors):
        errors.append("nu_max summaries omit a required paired factor")

    candidates = _read_csv(root / "results/stage6/comb_candidates.csv")
    if len(candidates) != 216 or {row.get("cell_id") for row in candidates} != cell_ids:
        errors.append("comb candidate table must contain three rows for all 72 cells")
    for cell_id in cell_ids:
        rows = [row for row in candidates if row.get("cell_id") == cell_id]
        if {row.get("alias") for row in rows} != {"half", "nominal", "double"} or {row.get("rank") for row in rows} != {"1", "2", "3"}:
            errors.append(f"comb aliases/ranks are incomplete: {cell_id}")
    benchmark = _read_csv(root / "results/stage6/comb_benchmark.csv")
    if len(benchmark) != 216 or {row.get("method") for row in benchmark} != COMB_METHODS:
        errors.append("comb benchmark must pair persistence, ACF, and PSPS on all cells")

    adapter = json.loads((root / "results/stage6/pysyd_adapter_audit.json").read_text(encoding="utf-8"))
    if adapter.get("status") != "pass" or adapter.get("external_package_executed") is not False or adapter.get("style_control_is_external_pysyd") is not False:
        errors.append("external pySYD adapter/style-control boundary is not explicit")


def validate_null_robustness_quality(root: Path, errors: list[str]) -> None:
    nulls = _read_csv(root / "results/stage6/null_calibration.csv")
    expected = {
        "envelope_detection_avg1",
        "envelope_detection_avg2",
        "envelope_detection_avg7",
        "comb_detection",
    }
    if len(nulls) != 4 or {row.get("claim") for row in nulls} != expected:
        errors.append("null calibration must cover three averaging strata and the comb scan")
    for row in nulls:
        if row.get("calibration_seed_range") == row.get("evaluation_seed_range"):
            errors.append(f"null seed streams overlap: {row.get('claim')}")
        fpr = _float(row, "evaluation_false_positive_rate", "null row", errors)
        false_confidence = _float(row, "evaluation_false_confidence_rate", "null row", errors)
        if row.get("status") != "pass" or max(fpr, false_confidence) > 0.08:
            errors.append(f"Stage 6 null calibration failed: {row.get('claim')}")

    robustness = _read_csv(root / "results/stage6/robustness_atlas.csv")
    factors = {
        "background_posterior_low",
        "background_posterior_high",
        "background_model_slope",
        "smoothing",
        "resolution",
        "window_features",
    }
    if len(robustness) != 72 or {row.get("factor") for row in robustness} != factors:
        errors.append("robustness atlas must contain six branches for 12 locked cells")
    if any(_float(row, "diagram_bottleneck", "robustness row", errors) < 0 for row in robustness):
        errors.append("robustness atlas contains an invalid diagram distance")

    quality = _read_csv(root / "results/stage6/quality_flags.csv")
    if len(quality) != 72 or len({row.get("cell_id") for row in quality}) != 72:
        errors.append("quality table must retain all 72 simulation cells")
    statuses = {row.get("status") for row in quality}
    if statuses != {"reliable", "limited", "not_detected"}:
        errors.append("quality table must demonstrate all three failure-return states")
    for row in quality:
        try:
            flags = set(json.loads(row.get("flags_json", "")))
        except json.JSONDecodeError:
            errors.append(f"quality row has invalid flags JSON: {row.get('cell_id')}")
            continue
        if not flags.issubset(QUALITY_FLAGS):
            errors.append(f"quality row has an unknown reason code: {row.get('cell_id')}")
        if row.get("status") == "not_detected" and "absent_envelope" not in flags:
            errors.append(f"not-detected row lacks absent-envelope flag: {row.get('cell_id')}")


def validate_manifest_gate_notebook(root: Path, errors: list[str]) -> None:
    manifest = json.loads((root / "results/stage6/run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("run_id") != "TA-S06-PSD-R001" or manifest.get("status") != "complete":
        errors.append("Stage 6 run manifest identity/status is invalid")
    if manifest.get("config_sha256") != configuration_hash(root / "configs/stage6_psd_topology.yaml"):
        errors.append("Stage 6 run manifest config hash is stale")
    if manifest.get("population_data_used") is not False or manifest.get("final_holdout_used") is not False:
        errors.append("Stage 6 run manifest indicates forbidden data use")
    if manifest.get("style_id") != "TA-PLOT-1.0" or manifest.get("normalization") != "log_ratio" or manifest.get("coefficient_field") != "F2":
        errors.append("Stage 6 style/normalization/topology contract drifted")
    for kind in ("inputs", "outputs"):
        for record in manifest.get(kind, []):
            target = root / record.get("path", "")
            if not target.is_file():
                errors.append(f"Stage 6 {kind[:-1]} is missing: {record.get('path')}")
            elif record.get("sha256") != sha256_file(target) or record.get("size_bytes") != target.stat().st_size:
                errors.append(f"Stage 6 {kind[:-1]} seal is stale: {record.get('path')}")
    figures = sorted((root / "reports/stage6/figures").glob("*.svg"))
    if len(figures) != 7:
        errors.append("Stage 6 must provide seven governed figures")
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source or "TopoAstero-0.7.0" not in source:
            errors.append(f"Stage 6 figure lacks style/source/version metadata: {figure.name}")

    gate = json.loads((root / "reports/stage6/G6_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G6" or gate.get("status") != "pass" or any(item.get("status") not in {"pass", "pass_with_qc_value"} for item in gate.get("checks", [])):
        errors.append("G6 acceptance record must pass every registered check")
    if gate.get("claim") != "equivalence_limited_localization_and_calibrated_reliability" or gate.get("prominence_identity") != "exact_on_shared_elder_rule_path_domain":
        errors.append("G6 does not preserve the prominence-equivalence claim limit")
    if gate.get("external_pysyd_executed") is not False:
        errors.append("G6 incorrectly claims an external pySYD execution")

    notebook = json.loads((root / "notebooks/06_psd_persistence.ipynb").read_text(encoding="utf-8"))
    joined = " ".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    if notebook.get("nbformat") != 4 or not notebook.get("cells") or "TA-S06-PSD-R001" not in joined or "results/stage6" not in joined:
        errors.append("Stage 6 notebook is invalid or not tied to the governed result set")

    deliverable = _read_csv(root / "reports/stage6/deliverable_manifest.csv")
    if {row.get("deliverable") for row in deliverable} != {"D6.1", "D6.2", "D6.3", "D6.4", "G6", "software"}:
        errors.append("Stage 6 deliverable manifest has incomplete groups")
    if any(str(row.get("path", "")).replace("\\", "/").startswith("dist/") for row in deliverable):
        errors.append("Stage 6 deliverable manifest must not seal ignored dist/ build artifacts")
    for row in deliverable:
        path = root / row.get("path", "")
        if not path.is_file():
            errors.append(f"Stage 6 deliverable is missing: {row.get('path')}")
        elif row.get("sha256") != sha256_file(path) or row.get("size_bytes") != str(path.stat().st_size):
            errors.append(f"Stage 6 deliverable seal is stale: {row.get('path')}")


def validate_stage6(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Return Stage 6 contract violations; an empty list means G6 is reproducible."""

    repository = Path(root).resolve()
    errors = [
        f"missing required Stage 6 file: {path}"
        for path in REQUIRED_FILES
        if not (repository / path).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_config_registries(repository, errors)
    validate_persistence_equivalence(repository, errors)
    validate_estimators(repository, errors)
    validate_null_robustness_quality(repository, errors)
    validate_manifest_gate_notebook(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1/2/3/4/5 regression: {error}"
            for error in validate_stage5(repository, require_prior_stages=True)
        )
    return errors

