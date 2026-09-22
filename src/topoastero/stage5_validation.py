"""Offline validation for Stage 5 TDA core and representation-audit evidence."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.stage4_validation import validate_stage4

REQUIRED_SCHEMAS = {
    "representation_spec.schema.json",
    "topological_feature.schema.json",
    "localization.schema.json",
    "selection_record.schema.json",
    "stage5_run_manifest.schema.json",
}

REQUIRED_FILES = [
    "configs/stage5_tda.yaml",
    "registries/stage5_representation_parameters.yaml",
    "registries/stage5_feature_registry.csv",
    "registries/stage5_selection.yaml",
    "docs/science/TDA_REPRESENTATION_SPECIFICATION.md",
    "docs/science/LOCALIZATION_AND_INTERPRETATION.md",
    "docs/protocols/STAGE5_REPRESENTATION_AUDIT_PROTOCOL.md",
    "notebooks/05_tda_representation_audit.ipynb",
    "results/stage5/backend_crosscheck.csv",
    "results/stage5/representation_features.csv",
    "results/stage5/localization_catalog.json",
    "results/stage5/null_calibration.csv",
    "results/stage5/nuisance_sensitivity.csv",
    "results/stage5/redundancy_matrix.csv",
    "results/stage5/redundancy_pairs.csv",
    "results/stage5/ablation_results.csv",
    "results/stage5/selection_scores.csv",
    "results/stage5/environment.json",
    "results/stage5/run_manifest.json",
    "reports/stage5/BACKEND_CROSSCHECK_REPORT.md",
    "reports/stage5/SENSITIVITY_REPORT.md",
    "reports/stage5/REDUNDANCY_AND_ABLATION_REPORT.md",
    "reports/stage5/REPRESENTATION_SELECTION_MEMO.md",
    "reports/stage5/STAGE5_REPORT.md",
    "reports/stage5/TRACEABILITY_MATRIX.md",
    "reports/stage5/G5_ACCEPTANCE.json",
    "reports/stage5/deliverable_manifest.csv",
    "reports/stage5/figures/backend_crosschecks.svg",
    "reports/stage5/figures/representation_atlas.svg",
    "reports/stage5/figures/localization_atlas.svg",
    "reports/stage5/figures/nuisance_sensitivity.svg",
    "reports/stage5/figures/redundancy_matrix.svg",
    "reports/stage5/figures/ablation_utility.svg",
    "reports/stage5/figures/selection_summary.svg",
    "src/topoastero/tda.py",
    "src/topoastero/representations.py",
    "workflows/run_stage5_tda_audit.py",
]

REPRESENTATIONS = {"REP-LC", "REP-DELAY", "REP-PSD", "REP-MODE", "REP-ECHELLE"}
RETAINED = {"REP-DELAY", "REP-PSD", "REP-ECHELLE"}
RETAINED_FEATURES = {
    "S5-DELAY-H1-MAX",
    "S5-PSD-H0-MAX",
    "S5-PSD-H0-CENTROID",
    "S5-ECH-H0-RIDGE",
}


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
            errors.append(f"invalid Stage 5 schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_config_registries(root: Path, errors: list[str]) -> None:
    config = load_yaml(root / "configs/stage5_tda.yaml")
    if config.get("config_id") != "TA-STAGE5-TDA-1.0":
        errors.append("Stage 5 config has an unexpected config_id")
    if config.get("software_version") != "TopoAstero-0.6.0":
        errors.append("Stage 5 config must freeze TopoAstero-0.6.0")
    if config.get("data_scope", {}).get("expected_cells") != 72:
        errors.append("Stage 5 must use all 72 frozen simulation-development cells")
    if config.get("data_scope", {}).get("population_or_final_holdout_allowed") is not False:
        errors.append("Stage 5 config must bar population and final-holdout topology")
    topology = config.get("topology", {})
    if topology.get("coefficient_field") != "F2":
        errors.append("Stage 5 coefficient field must be F2")
    if topology.get("essential_policy") != "retain_localization_exclude_numeric_summaries":
        errors.append("Stage 5 essential-class policy drifted")
    configured = {
        value.get("representation_id")
        for value in config.get("representations", {}).values()
        if isinstance(value, dict)
    }
    if configured != REPRESENTATIONS:
        errors.append("Stage 5 config must register exactly five candidate representations")

    specifications = load_yaml(root / "registries/stage5_representation_parameters.yaml")
    records = specifications.get("representations", [])
    if len(records) != 5 or {record.get("representation_id") for record in records} != REPRESENTATIONS:
        errors.append("representation parameter registry must specify all five representations")
    for record in records:
        for field in ("domain", "scalar_or_distance", "physical_target", "null_family", "simple_control", "later_claim_role"):
            if not str(record.get(field, "")).strip():
                errors.append(f"{record.get('representation_id')} lacks {field}")

    features = _read_csv(root / "registries/stage5_feature_registry.csv")
    if len(features) != 13 or len({row.get("feature_id") for row in features}) != 13:
        errors.append("compact feature registry must contain 13 unique candidates")
    observed_retained = {
        row["feature_id"]
        for row in features
        if row.get("status") in {"retained", "retained_exploratory"}
    }
    if observed_retained != RETAINED_FEATURES:
        errors.append("retained feature set differs from the locked four-statistic set")
    for row in features:
        if row.get("status") in {"retained", "retained_exploratory"}:
            required = ("physical_target", "null_family", "control_id", "later_stage", "later_claim_role")
            if any(not row.get(field) or row.get(field) == "none" for field in required):
                errors.append(f"retained feature lacks a G5 field: {row.get('feature_id')}")
            if row.get("essential_handling") != "excluded_from_numeric_summary":
                errors.append(f"retained feature has unsafe essential handling: {row.get('feature_id')}")


def validate_backends_localization(root: Path, errors: list[str]) -> None:
    checks = _read_csv(root / "results/stage5/backend_crosscheck.csv")
    if len(checks) != 6 or {row.get("case_id") for row in checks} != {f"BC-{index:02d}" for index in range(1, 7)}:
        errors.append("backend cross-check suite must contain BC-01 through BC-06")
    for row in checks:
        if row.get("status") != "pass" or _float(row, "absolute_error", "backend check", errors) > _float(row, "tolerance", "backend check", errors) + 1e-14:
            errors.append(f"backend cross-check failed: {row.get('case_id')}")
        if row.get("deterministic_ordering") != "filtration_dimension_lexicographic":
            errors.append(f"backend ordering policy drift: {row.get('case_id')}")

    catalog = json.loads((root / "results/stage5/localization_catalog.json").read_text(encoding="utf-8"))
    if len(catalog) < 20 or {row.get("representation_id") for row in catalog} != REPRESENTATIONS:
        errors.append("localization catalog does not cover every physical representation")
    for row in catalog:
        if not row.get("birth_vertices") or not row.get("birth_location"):
            errors.append(f"localized pair lacks a birth mapping: {row.get('pair_id')}")
        if row.get("essential"):
            if row.get("death") is not None or row.get("persistence") is not None:
                errors.append(f"essential pair was assigned an artificial death: {row.get('pair_id')}")
        elif row.get("death") is None or not isinstance(row.get("persistence"), (int, float)) or row["persistence"] <= 0:
            errors.append(f"finite localized pair is invalid: {row.get('pair_id')}")


def validate_audits_selection(root: Path, errors: list[str]) -> None:
    features = _read_csv(root / "results/stage5/representation_features.csv")
    design = _read_csv(root / "registries/stage4_factorial_design.csv")
    if len(features) != 72 or {row.get("cell_id") for row in features} != {row.get("cell_id") for row in design}:
        errors.append("representation feature panel must match all 72 Stage 4 cells")

    nulls = _read_csv(root / "results/stage5/null_calibration.csv")
    if len(nulls) != 5 or {row.get("representation_id") for row in nulls} != REPRESENTATIONS:
        errors.append("null calibration must cover all five representations")
    for row in nulls:
        if row.get("calibration_seed_range") == row.get("evaluation_seed_range"):
            errors.append(f"null seed streams overlap: {row.get('representation_id')}")
        if row.get("status") != "pass" or _float(row, "evaluation_false_positive_rate", "null row", errors) > 0.125:
            errors.append(f"Stage 5 null calibration failed: {row.get('representation_id')}")

    sensitivity = _read_csv(root / "results/stage5/nuisance_sensitivity.csv")
    expected_nuisance = {
        "amplitude_scaling",
        "additive_offset",
        "monotone_transform",
        "cadence",
        "sample_density",
        "embedding_dimension",
        "smoothing",
        "grid_resolution",
        "periodic_boundary",
    }
    if len(sensitivity) != 9 or {row.get("nuisance") for row in sensitivity} != expected_nuisance:
        errors.append("nuisance audit does not contain the nine registered perturbations")
    if any(row.get("status") != "pass" for row in sensitivity):
        errors.append("a registered nuisance audit failed")
    periodic = next((row for row in sensitivity if row.get("nuisance") == "periodic_boundary"), {})
    if periodic.get("baseline_statistic") != "0" or periodic.get("perturbed_statistic") != "1":
        errors.append("periodic boundary audit must distinguish disk Betti-1=0 from cylinder Betti-1=1")

    matrix = _read_csv(root / "results/stage5/redundancy_matrix.csv")
    if len(matrix) != 12 or len({row.get("feature_id") for row in matrix}) != 12:
        errors.append("redundancy matrix must cover the 12 numeric compact candidates")
    pairs = _read_csv(root / "results/stage5/redundancy_pairs.csv")
    if len(pairs) != 66:
        errors.append("redundancy pair table must contain 12 choose 2 comparisons")
    ablation = _read_csv(root / "results/stage5/ablation_results.csv")
    if len(ablation) != 5 or {row.get("representation_id") for row in ablation} != REPRESENTATIONS:
        errors.append("conditional ablation must cover all five representations")
    if any(row.get("folds") != "6" or row.get("interpretation") != "development_selection_diagnostic_not_confirmatory_performance" for row in ablation):
        errors.append("ablation scope/fold policy drifted")

    selection = load_yaml(root / "registries/stage5_selection.yaml")
    records = selection.get("records", [])
    if selection.get("status") != "locked" or len(records) != 5:
        errors.append("Stage 5 selection registry must be locked with five records")
    if selection.get("population_data_used") is not False or selection.get("final_holdout_used") is not False:
        errors.append("selection registry indicates forbidden population/holdout use")
    retained = {
        row.get("representation_id")
        for row in records
        if row.get("status") in {"retained", "retained_exploratory"}
    }
    if retained != RETAINED:
        errors.append("retained representation set differs from the G5 lock")
    locked_features = {item for row in records for item in row.get("retained_features", [])}
    if locked_features != RETAINED_FEATURES:
        errors.append("selection registry and feature registry disagree")


def validate_manifest_gate_notebook(root: Path, errors: list[str]) -> None:
    manifest = json.loads((root / "results/stage5/run_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("run_id") != "TA-S05-TDA-R001" or manifest.get("status") != "complete":
        errors.append("Stage 5 run manifest identity/status is invalid")
    if manifest.get("config_sha256") != configuration_hash(root / "configs/stage5_tda.yaml"):
        errors.append("Stage 5 run manifest config hash is stale")
    if manifest.get("population_data_used") is not False or manifest.get("final_holdout_used") is not False:
        errors.append("Stage 5 run manifest indicates forbidden data use")
    if manifest.get("style_id") != "TA-PLOT-1.0" or manifest.get("coefficient_field") != "F2":
        errors.append("Stage 5 style or coefficient-field contract drifted")
    for kind in ("inputs", "outputs"):
        for record in manifest.get(kind, []):
            target = root / record.get("path", "")
            if not target.is_file():
                errors.append(f"Stage 5 {kind[:-1]} is missing: {record.get('path')}")
            elif record.get("sha256") != sha256_file(target) or record.get("size_bytes") != target.stat().st_size:
                errors.append(f"Stage 5 {kind[:-1]} seal is stale: {record.get('path')}")
    for figure in sorted((root / "reports/stage5/figures").glob("*.svg")):
        source = figure.read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source:
            errors.append(f"Stage 5 figure lacks style/source metadata: {figure.name}")

    gate = json.loads((root / "reports/stage5/G5_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G5" or gate.get("status") != "pass":
        errors.append("G5 acceptance record must pass")
    if set(gate.get("retained_representations", [])) != RETAINED or set(gate.get("retained_feature_ids", [])) != RETAINED_FEATURES:
        errors.append("G5 retained set disagrees with the locked selection")
    if gate.get("visual_interest_is_selection_criterion") is not False:
        errors.append("G5 must explicitly reject visual-interest-only selection")

    notebook = json.loads((root / "notebooks/05_tda_representation_audit.ipynb").read_text(encoding="utf-8"))
    joined = " ".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    if notebook.get("nbformat") != 4 or not notebook.get("cells") or "TA-S05-TDA-R001" not in joined or "results/stage5" not in joined:
        errors.append("Stage 5 notebook is invalid or not tied to the governed result set")

    deliverable = _read_csv(root / "reports/stage5/deliverable_manifest.csv")
    if {row.get("deliverable") for row in deliverable} != {"D5.1", "D5.2", "D5.3", "D5.4", "G5", "software"}:
        errors.append("Stage 5 deliverable manifest has incomplete groups")
    for row in deliverable:
        path = root / row.get("path", "")
        if not path.is_file():
            errors.append(f"Stage 5 deliverable is missing: {row.get('path')}")
        elif row.get("sha256") != sha256_file(path) or row.get("size_bytes") != str(path.stat().st_size):
            errors.append(f"Stage 5 deliverable seal is stale: {row.get('path')}")


def validate_stage5(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Return Stage 5 contract violations; an empty list means G5 is reproducible."""

    repository = Path(root).resolve()
    errors = [
        f"missing required Stage 5 file: {path}"
        for path in REQUIRED_FILES
        if not (repository / path).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_config_registries(repository, errors)
    validate_backends_localization(repository, errors)
    validate_audits_selection(repository, errors)
    validate_manifest_gate_notebook(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1/2/3/4 regression: {error}"
            for error in validate_stage4(repository, require_prior_stages=True)
        )
    return errors

