"""Offline validation for Stage 7 delay topology and phase-information evidence."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage6_validation import validate_stage6

REQUIRED_SCHEMAS = {
    "delay_embedding.schema.json",
    "delay_diagram.schema.json",
    "phase_test.schema.json",
    "stage7_decision.schema.json",
    "stage7_run_manifest.schema.json",
}

REQUIRED_FILES = [
    "configs/stage7_delay_topology.yaml",
    "registries/stage7_delay_policy.yaml",
    "registries/stage7_simulation_lock.yaml",
    "registries/stage7_decision_policy.yaml",
    "docs/science/DELAY_EMBEDDING_PHASE_TEST.md",
    "docs/protocols/STAGE7_DELAY_TOPOLOGY_PROTOCOL.md",
    "notebooks/07_delay_embedding_phase_test.ipynb",
    "results/stage7/delay_parameter_audit.csv",
    "results/stage7/delay_policy_summary.csv",
    "results/stage7/embedding_audit.csv",
    "results/stage7/diagram_suite.json",
    "results/stage7/convergence_audit.csv",
    "results/stage7/coherence_response_surfaces.csv",
    "results/stage7/response_correlations.csv",
    "results/stage7/phase_tests.csv",
    "results/stage7/surrogate_draw_maxima.csv",
    "results/stage7/classical_controls.csv",
    "results/stage7/predictive_ablation.csv",
    "results/stage7/segmentation_stability.csv",
    "results/stage7/vineyard_tracks.csv",
    "results/stage7/environment.json",
    "results/stage7/run_manifest.json",
    "reports/stage7/COHERENCE_AND_ABLATION_REPORT.md",
    "reports/stage7/PHASE_INFORMATION_TEST.md",
    "reports/stage7/RETAIN_DROP_DECISION.md",
    "reports/stage7/SEGMENTATION_STABILITY_REPORT.md",
    "reports/stage7/STAGE7_REPORT.md",
    "reports/stage7/TRACEABILITY_MATRIX.md",
    "reports/stage7/G7_ACCEPTANCE.json",
    "reports/stage7/deliverable_manifest.csv",
    "reports/stage7/figures/classical_control_ablation.svg",
    "reports/stage7/figures/coherence_response_surface.svg",
    "reports/stage7/figures/delay_policy_comparison.svg",
    "reports/stage7/figures/embedding_and_h1_diagram.svg",
    "reports/stage7/figures/phase_surrogate_tests.svg",
    "reports/stage7/figures/segmentation_stability.svg",
    "src/topoastero/delay_topology.py",
    "workflows/run_stage7_delay_topology.py",
]

DELAY_METHODS = {
    "physics_quarter_period",
    "acf_first_minimum",
    "mutual_information_first_minimum",
    "multiscale_consensus",
}
METRICS = {"euclidean", "standardized_euclidean", "cosine_chord"}
NULL_FAMILIES = {"phase_randomized", "iaaft"}


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
            errors.append(f"invalid Stage 7 schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_config_registries(root: Path, errors: list[str]) -> None:
    config = load_yaml(root / "configs/stage7_delay_topology.yaml")
    if config.get("config_id") != "TA-STAGE7-DELAY-1.0":
        errors.append("Stage 7 config has an unexpected config_id")
    if config.get("software_version") != "TopoAstero-0.8.0":
        errors.append("Stage 7 config must freeze TopoAstero-0.8.0")
    scope = config.get("data_scope", {})
    if scope.get("expected_cells") != 24 or scope.get("selection") != "first_24_balanced_simulation_cells":
        errors.append("Stage 7 must use the locked 24-cell simulation panel")
    if scope.get("population_data_allowed") is not False or scope.get("final_holdout_allowed") is not False:
        errors.append("Stage 7 config must bar population and final-holdout access")
    delay = config.get("delay_policy", {})
    methods = {delay.get("primary"), *delay.get("alternatives", [])}
    if methods != DELAY_METHODS or delay.get("primary") != "multiscale_consensus":
        errors.append("Stage 7 delay policy drifted")
    embedding = config.get("embedding", {})
    if embedding.get("dimensionality_reduction") != "PCA_visualization_only_never_PH":
        errors.append("Stage 7 dimensionality-reduction boundary drifted")
    persistence = config.get("persistence", {})
    if persistence.get("complex") != "Vietoris_Rips" or persistence.get("coefficient_field") != "F2":
        errors.append("Stage 7 VR/F2 contract drifted")
    if {persistence.get("primary_metric"), *persistence.get("metric_sensitivities", [])} != METRICS:
        errors.append("Stage 7 metric audit is incomplete")
    phase = config.get("phase_test", {})
    if set(phase.get("surrogate_families", [])) != NULL_FAMILIES or phase.get("draws_per_cell_family") != 24:
        errors.append("Stage 7 phase-null contract drifted")

    delay_registry = load_yaml(root / "registries/stage7_delay_policy.yaml")
    if delay_registry.get("status") != "locked_before_stage7_execution" or {
        record.get("method") for record in delay_registry.get("methods", [])
    } != DELAY_METHODS:
        errors.append("Stage 7 delay registry is incomplete or unlocked")
    decision = load_yaml(root / "registries/stage7_decision_policy.yaml")
    if decision.get("status") != "locked_before_stage7_execution" or decision.get("decision_rule") != "retain_if_either_positive_path_passes_else_drop":
        errors.append("Stage 7 retain/drop policy is incomplete or unlocked")

    lock = load_yaml(root / "registries/stage7_simulation_lock.yaml")
    if lock.get("status") != "locked_before_stage7_execution" or lock.get("expected_cells") != 24:
        errors.append("Stage 7 simulation lock is invalid")
    for record in lock.get("sealed_inputs", []):
        path = root / str(record.get("path", ""))
        if not path.is_file() or record.get("sha256") != sha256_file(path):
            errors.append(f"Stage 7 simulation-lock seal is stale: {record.get('label')}")
    policy = lock.get("inspection_policy", {})
    if policy.get("population_data_used") is not False or policy.get("final_holdout_used") is not False:
        errors.append("Stage 7 simulation lock indicates forbidden data use")


def validate_delay_embeddings_diagrams(root: Path, errors: list[str]) -> None:
    delay = _read_csv(root / "results/stage7/delay_parameter_audit.csv")
    cells = {row.get("cell_id") for row in delay}
    if len(delay) != 96 or len(cells) != 24 or {row.get("method") for row in delay} != DELAY_METHODS:
        errors.append("delay audit must contain four methods for all 24 cells")
    for cell_id in cells:
        rows = [row for row in delay if row.get("cell_id") == cell_id]
        if len(rows) != 4 or sum(row.get("selected") == "true" for row in rows) != 1:
            errors.append(f"delay selection is incomplete for {cell_id}")
        if any(_float(row, "lag_samples", "delay row", errors) < 1 for row in rows):
            errors.append(f"delay audit contains an invalid lag for {cell_id}")
    summary = _read_csv(root / "results/stage7/delay_policy_summary.csv")
    if len(summary) != 4 or {row.get("method") for row in summary} != DELAY_METHODS:
        errors.append("delay policy summary is incomplete")

    embeddings = _read_csv(root / "results/stage7/embedding_audit.csv")
    if len(embeddings) != 24 or {row.get("cell_id") for row in embeddings} != cells:
        errors.append("embedding audit must retain all 24 cells")
    for row in embeddings:
        fraction = _float(row, "valid_fraction", "embedding row", errors)
        retained = _float(row, "retained_points", "embedding row", errors)
        if not 0 < fraction <= 1 or retained != 18 or row.get("normalization") != "robust_global":
            errors.append(f"embedding contract failed: {row.get('cell_id')}")

    suite = json.loads((root / "results/stage7/diagram_suite.json").read_text(encoding="utf-8"))
    if suite.get("coefficient_field") != "F2" or suite.get("dimensionality_reduction_used_for_persistence") is not False:
        errors.append("diagram suite violates the topology/PCA boundary")
    if len(suite.get("cells", [])) != 4 or len(suite.get("h2_audit", [])) != 4:
        errors.append("diagram suite must contain four bounded H2 diagnostics")
    pairs = suite.get("pairs", [])
    if not pairs or not any(pair.get("dimension") == 1 for pair in pairs):
        errors.append("diagram suite lacks localized H1 pairs")
    for pair in pairs:
        if pair.get("essential"):
            if pair.get("death") is not None or pair.get("persistence") is not None:
                errors.append(f"essential delay class received a finite death: {pair.get('pair_id')}")
        elif pair.get("death") is None or not isinstance(pair.get("persistence"), (int, float)):
            errors.append(f"finite delay class is incomplete: {pair.get('pair_id')}")

    convergence = _read_csv(root / "results/stage7/convergence_audit.csv")
    if len(convergence) != 54 or {row.get("metric") for row in convergence} != METRICS:
        errors.append("convergence audit must cover 6 cells x 3 metrics x 3 landmark counts")
    for row in convergence:
        distance = _float(row, "normalized_bottleneck_to_reference", "convergence row", errors)
        if distance < 0 or (row.get("status") == "reference" and distance > 1e-12):
            errors.append(f"invalid convergence distance: {row.get('cell_id')}")


def validate_phase_controls_stability(root: Path, errors: list[str]) -> None:
    phase = _read_csv(root / "results/stage7/phase_tests.csv")
    if len(phase) != 48 or len({row.get("cell_id") for row in phase}) != 24 or {row.get("surrogate_family") for row in phase} != NULL_FAMILIES:
        errors.append("phase tests must cover two null families for all 24 cells")
    for row in phase:
        pvalue = _float(row, "pvalue", "phase-test row", errors)
        error = _float(row, "median_psd_amplitude_error", "phase-test row", errors)
        if not 0 < pvalue <= 1 or row.get("null_draws") != "24" or row.get("trials") != "4":
            errors.append(f"invalid maximum-statistic test: {row.get('cell_id')}")
        if row.get("surrogate_family") == "phase_randomized" and error > 1e-10:
            errors.append(f"phase-randomized PSD was not preserved: {row.get('cell_id')}")
        if row.get("surrogate_family") == "iaaft" and error > 0.20:
            errors.append(f"IAAFT PSD approximation is outside tolerance: {row.get('cell_id')}")
        if row.get("role") == "calibration" and row.get("bh_rejected") != "false":
            errors.append("BH decisions must be restricted to evaluation cells")
    draws = _read_csv(root / "results/stage7/surrogate_draw_maxima.csv")
    if len(draws) != 24 * 2 * 24:
        errors.append("surrogate draw table has incomplete paired maxima")

    response = _read_csv(root / "results/stage7/coherence_response_surfaces.csv")
    correlations = _read_csv(root / "results/stage7/response_correlations.csv")
    if len(response) != 24 or len(correlations) != 15:
        errors.append("coherence response surfaces must cover 24 cells and 15 target-feature pairs")
    controls = _read_csv(root / "results/stage7/classical_controls.csv")
    if len(controls) != 24 or {row.get("cell_id") for row in controls} != {row.get("cell_id") for row in response}:
        errors.append("classical controls are not paired to every topology row")
    ablation = _read_csv(root / "results/stage7/predictive_ablation.csv")
    if len(ablation) != 3 or {row.get("method") for row in ablation} != {"topology", "classical", "combined"}:
        errors.append("predictive ablation must compare topology, classical, and combined models")
    if any(row.get("train_cells") != "12" or row.get("evaluation_cells") != "12" for row in ablation):
        errors.append("predictive ablation split is not 12/12")

    stability = _read_csv(root / "results/stage7/segmentation_stability.csv")
    if len(stability) != 72 or {row.get("window_fraction") for row in stability} != {"0.25", "0.5", "1"}:
        errors.append("segmentation audit must contain three scales for all 24 cells")
    for row in stability:
        if _float(row, "coefficient_of_variation", "stability row", errors) < 0:
            errors.append(f"segmentation variability is invalid: {row.get('cell_id')}")
    vineyard = _read_csv(root / "results/stage7/vineyard_tracks.csv")
    if len(vineyard) < 5 or len({row.get("cell_id") for row in vineyard}) != 1:
        errors.append("representative rolling vineyard track is incomplete")


def validate_manifest_gate_notebook(root: Path, errors: list[str]) -> None:
    manifest = json.loads((root / "results/stage7/run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("run_id") != "TA-S07-DELAY-R001" or manifest.get("status") != "complete":
        errors.append("Stage 7 run manifest identity/status is invalid")
    if manifest.get("config_sha256") != configuration_hash(root / "configs/stage7_delay_topology.yaml"):
        errors.append("Stage 7 run manifest config hash is stale")
    if manifest.get("population_data_used") is not False or manifest.get("final_holdout_used") is not False:
        errors.append("Stage 7 run manifest indicates forbidden data use")
    if manifest.get("style_id") != "TA-PLOT-1.0" or manifest.get("coefficient_field") != "F2":
        errors.append("Stage 7 style/topology contract drifted")
    for kind in ("inputs", "outputs"):
        for record in manifest.get(kind, []):
            target = root / record.get("path", "")
            if not target.is_file():
                errors.append(f"Stage 7 {kind[:-1]} is missing: {record.get('path')}")
            elif record.get("sha256") != sha256_file(target) or record.get("size_bytes") != target.stat().st_size:
                errors.append(f"Stage 7 {kind[:-1]} seal is stale: {record.get('path')}")

    figures = sorted((root / "reports/stage7/figures").glob("*.svg"))
    if len(figures) != 6:
        errors.append("Stage 7 must provide six governed figures")
    for figure in figures:
        source = figure.read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source or "TopoAstero-0.8.0" not in source:
            errors.append(f"Stage 7 figure lacks style/source/version metadata: {figure.name}")

    gate = json.loads((root / "reports/stage7/G7_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G7" or gate.get("status") != "pass":
        errors.append("G7 acceptance record is not passing")
    phase_rows = _read_csv(root / "results/stage7/phase_tests.csv")
    rates = {
        family: sum(
            row.get("bh_rejected") == "true"
            for row in phase_rows
            if row.get("role") == "evaluation" and row.get("surrogate_family") == family
        )
        / 12
        for family in NULL_FAMILIES
    }
    phase_path = min(rates.values()) >= 0.25
    ablation = _read_csv(root / "results/stage7/predictive_ablation.csv")
    improvement = float(next(row["improvement_over_classical"] for row in ablation if row["method"] == "combined"))
    predictive_path = improvement >= 0.10
    expected_decision = "retain" if phase_path or predictive_path else "drop"
    expected_claim = (
        "positive_phase_information"
        if phase_path
        else "positive_predictive_increment"
        if predictive_path
        else "calibrated_negative_result"
    )
    if gate.get("decision") != expected_decision or gate.get("claim") != expected_claim:
        errors.append("G7 decision does not follow the locked retain/drop rule")
    if gate.get("phase_path_passed") is not phase_path or gate.get("predictive_path_passed") is not predictive_path:
        errors.append("G7 positive-path flags disagree with serialized evidence")
    if any(item.get("status") == "fail" for item in gate.get("checks", [])):
        errors.append("G7 contains a failed integrity check")

    notebook = json.loads((root / "notebooks/07_delay_embedding_phase_test.ipynb").read_text(encoding="utf-8"))
    joined = " ".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    code_cells = [cell for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"]
    if notebook.get("nbformat") != 4 or "TA-S07-DELAY-R001" not in joined or "results/stage7" not in joined:
        errors.append("Stage 7 notebook is invalid or detached from governed results")
    if not code_cells or any(cell.get("execution_count") is None or not cell.get("outputs") for cell in code_cells):
        errors.append("Stage 7 notebook is not saved with executed outputs")

    deliverable = _read_csv(root / "reports/stage7/deliverable_manifest.csv")
    if {row.get("deliverable") for row in deliverable} != {"D7.1", "D7.2", "D7.3", "D7.4", "G7", "software"}:
        errors.append("Stage 7 deliverable manifest has incomplete groups")
    for row in deliverable:
        path = root / row.get("path", "")
        if not path.is_file():
            errors.append(f"Stage 7 deliverable is missing: {row.get('path')}")
        elif row.get("sha256") != sha256_file(path) or row.get("size_bytes") != str(path.stat().st_size):
            errors.append(f"Stage 7 deliverable seal is stale: {row.get('path')}")


def validate_stage7(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Return Stage 7 contract violations; an empty list means G7 is reproducible."""

    repository = Path(root).resolve()
    errors = [
        f"missing required Stage 7 file: {path}"
        for path in REQUIRED_FILES
        if not (repository / path).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_config_registries(repository, errors)
    validate_delay_embeddings_diagrams(repository, errors)
    validate_phase_controls_stability(repository, errors)
    validate_manifest_gate_notebook(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1/2/3/4/5/6 regression: {error}"
            for error in validate_stage6(repository, require_prior_stages=True)
        )
    return errors
