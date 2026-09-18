"""Validation of the frozen Stage 0 governance contract."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from topoastero.config import load_yaml

REQUIRED_HYPOTHESES = {f"H{index}" for index in range(1, 7)}
REQUIRED_OBJECTIVES = {f"O{index}" for index in range(1, 11)}
REQUIRED_QUESTIONS = {f"RQ{index}" for index in range(10)}
REQUIRED_TERMS = {
    "persistence",
    "ridge",
    "coherence",
    "topological_echelle",
    "detection",
    "calibration",
    "robustness",
    "complementarity",
    "failure",
}
REQUIRED_DATASETS = {
    "DS-ANALYTIC",
    "DS-SIMULATION",
    "DS-MESA-GYRE",
    "DS-RUDY-KEPLER",
    "DS-RUDY-TESS",
    "DS-LEGACY",
    "DS-CONTROLS",
    "DS-KEPLER-TESS-DEGRADED",
}


def _ids(entries: Any) -> set[str]:
    if not isinstance(entries, list):
        return set()
    return {str(entry.get("id")) for entry in entries if isinstance(entry, dict)}


def _require_fields(
    entries: Iterable[dict[str, Any]], fields: set[str], label: str, errors: list[str]
) -> None:
    for entry in entries:
        missing = sorted(fields - set(entry))
        if missing:
            errors.append(f"{label} {entry.get('id', '<unknown>')} missing: {', '.join(missing)}")


def validate_hypotheses(root: Path, errors: list[str]) -> None:
    registry = load_yaml(root / "registries/hypotheses.yaml")
    hypotheses = registry.get("hypotheses", [])
    found = _ids(hypotheses)
    if found != REQUIRED_HYPOTHESES:
        errors.append(f"Hypothesis IDs must be H1-H6; found {sorted(found)}")
    _require_fields(
        [entry for entry in hypotheses if isinstance(entry, dict)],
        {
            "id",
            "hypothesis",
            "null_hypothesis",
            "estimand",
            "unit_of_analysis",
            "primary_metric",
            "baseline",
            "minimum_publishable_conclusion",
            "falsification_rule",
            "decision_stage",
        },
        "Hypothesis",
        errors,
    )
    crosswalk = load_yaml(root / "registries/objective_crosswalk.yaml")
    objectives = crosswalk.get("objectives", [])
    questions = crosswalk.get("research_questions", [])
    if _ids(objectives) != REQUIRED_OBJECTIVES:
        errors.append("Objective crosswalk must contain O1-O10 exactly")
    if _ids(questions) != REQUIRED_QUESTIONS:
        errors.append("Research-question crosswalk must contain RQ0-RQ9 exactly")


def validate_terminology(root: Path, errors: list[str]) -> None:
    registry = load_yaml(root / "registries/terminology.yaml")
    entries = registry.get("terms", [])
    found = _ids(entries)
    missing = REQUIRED_TERMS - found
    if missing:
        errors.append(f"Terminology registry missing: {sorted(missing)}")
    _require_fields(
        [entry for entry in entries if isinstance(entry, dict)],
        {"id", "preferred_label", "operational_definition", "measurement_rule"},
        "Term",
        errors,
    )


def validate_datasets(root: Path, errors: list[str]) -> None:
    inventory = load_yaml(root / "data/manifests/planned_datasets.yaml")
    datasets = inventory.get("datasets", [])
    found = _ids(datasets)
    missing = REQUIRED_DATASETS - found
    if missing:
        errors.append(f"Dataset inventory missing: {sorted(missing)}")
    _require_fields(
        [entry for entry in datasets if isinstance(entry, dict)],
        {
            "id",
            "tier",
            "role",
            "source",
            "identity_status",
            "resolution_stage",
            "license_or_terms",
            "retention_class",
        },
        "Dataset",
        errors,
    )


def validate_risks(root: Path, errors: list[str]) -> None:
    register = load_yaml(root / "registries/risk_register.yaml")
    risks = register.get("risks", [])
    if len(risks) < 10:
        errors.append("Risk register must retain at least the ten principal project risks")
    _require_fields(
        [entry for entry in risks if isinstance(entry, dict)],
        {
            "id",
            "category",
            "risk",
            "probability",
            "impact",
            "early_warning",
            "mitigation",
            "owner_role",
            "fallback",
            "review_date",
        },
        "Risk",
        errors,
    )


def validate_decisions(root: Path, errors: list[str]) -> None:
    schedule = load_yaml(root / "registries/pilot_decisions.yaml")
    decisions = schedule.get("decisions", [])
    _require_fields(
        [entry for entry in decisions if isinstance(entry, dict)],
        {"id", "choice", "status", "decision_stage", "owner_role", "evidence_required"},
        "Decision",
        errors,
    )


def validate_holdout_log(root: Path, errors: list[str]) -> None:
    path = root / "registries/holdout_access_log.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows:
        errors.append("Stage 0 holdout access log must be empty")


def validate_smoke(root: Path, errors: list[str]) -> None:
    required = {
        "signal.csv",
        "persistence_pairs.csv",
        "summary.json",
        "smoke_figure.svg",
        "run_manifest.json",
    }
    missing = sorted(name for name in required if not (root / "results/smoke" / name).is_file())
    if missing:
        errors.append(f"Smoke outputs missing: {missing}")
        return
    summary = json.loads((root / "results/smoke/summary.json").read_text(encoding="utf-8"))
    if summary.get("workflow") != "stage0-smoke-v1":
        errors.append("Smoke summary has an unexpected workflow ID")
    if summary.get("essential_pair_count") != 1:
        errors.append("Smoke persistence output must contain one essential H0 class")


def validate_stage0(root: str | Path, *, require_smoke: bool = True) -> list[str]:
    repository = Path(root).resolve()
    required_files = [
        "README.md",
        "pyproject.toml",
        "uv.lock",
        ".github/workflows/ci.yml",
        "docs/governance/PROJECT_CHARTER.md",
        "docs/governance/GOVERNANCE.md",
        "docs/governance/RISK_REGISTER.md",
        "docs/protocols/PREREGISTERED_ANALYSIS_PROTOCOL.md",
        "docs/protocols/SPLIT_AND_HOLDOUT_POLICY.md",
        "docs/reproducibility/DATA_MANAGEMENT_PLAN.md",
        "docs/reproducibility/REPRODUCIBILITY_SPECIFICATION.md",
        "docs/resources/RESOURCE_INVENTORY.md",
        "docs/science/TERMINOLOGY_AND_DATA_DICTIONARY.md",
        "registries/experiment_ledger.csv",
        "registries/pilot_decisions.yaml",
        "registries/risk_register.yaml",
        "reports/stage0/G0_ACCEPTANCE.json",
        "reports/stage0/STAGE0_REPORT.md",
        "reports/stage0/TRACEABILITY_MATRIX.md",
        "schemas/data_manifest.schema.json",
    ]
    errors = [name for name in required_files if not (repository / name).is_file()]
    errors = [f"Required file missing: {name}" for name in errors]
    validate_hypotheses(repository, errors)
    validate_terminology(repository, errors)
    validate_datasets(repository, errors)
    validate_risks(repository, errors)
    validate_decisions(repository, errors)
    validate_holdout_log(repository, errors)
    if require_smoke:
        validate_smoke(repository, errors)
    return errors
