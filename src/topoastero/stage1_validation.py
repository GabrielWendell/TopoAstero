"""Validation for the Stage 1 literature and benchmark contract."""

from __future__ import annotations

import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from topoastero.config import load_yaml
from topoastero.evidence import bibtex_keys, normalized_doi, read_csv_rows, split_source_keys
from topoastero.provenance import sha256_file
from topoastero.validation import REQUIRED_HYPOTHESES, validate_stage0

REQUIRED_TASKS = {f"T1.{index}" for index in range(1, 9)}
REQUIRED_CONCEPTS = {f"NQ-{index:02d}" for index in range(1, 7)}
REQUIRED_BASELINES = {f"CB-{index:02d}" for index in range(1, 9)}
REQUIRED_TDA_TOPICS = {f"TDA-{index:02d}" for index in range(1, 10)}
REQUIRED_TARGET_QUANTITIES = {"numax", "dnu", "teff", "feh"}

REQUIRED_FILES = [
    "evidence/README.md",
    "evidence/literature/literature_matrix.csv",
    "evidence/literature/physics_matrix.csv",
    "evidence/literature/classical_baseline_matrix.csv",
    "evidence/literature/theorem_matrix.csv",
    "evidence/literature/astronomy_tda_gap_map.csv",
    "evidence/literature/hypothesis_baseline_crosswalk.csv",
    "evidence/benchmarks/rudy_identity.yaml",
    "evidence/benchmarks/legacy_population.csv",
    "evidence/benchmarks/benchmark_targets.csv",
    "evidence/benchmarks/rudy_mode_frequencies.csv",
    "evidence/benchmarks/source_provenance.csv",
    "evidence/search/novelty_search_log.csv",
    "evidence/references/reference_audit.csv",
    "evidence/references/topoastero_stage1.bib",
    "docs/literature/SOLAR_LIKE_PHYSICS_MAP.md",
    "docs/literature/CLASSICAL_PIPELINE_MAP.md",
    "docs/literature/MATHEMATICAL_TDA_MAP.md",
    "docs/literature/ASTRONOMY_TDA_GAP_MAP.md",
    "docs/literature/RESEARCH_GAP_MEMORANDUM.md",
    "docs/literature/NOVELTY_AUDIT.md",
    "docs/literature/REFERENCE_UPDATE_PROTOCOL.md",
    "docs/benchmarks/RUDY_BENCHMARK_SPECIFICATION.md",
    "docs/benchmarks/LEGACY_POPULATION_SPECIFICATION.md",
    "schemas/literature_evidence.schema.json",
    "schemas/benchmark_target.schema.json",
    "schemas/reference_audit.schema.json",
    "schemas/novelty_search.schema.json",
    "reports/stage1/G1_ACCEPTANCE.json",
    "reports/stage1/STAGE1_REPORT.md",
    "reports/stage1/TRACEABILITY_MATRIX.md",
    "reports/stage1/deliverable_manifest.csv",
]

MATRIX_FIELDS = {
    "literature_matrix.csv": {
        "record_id",
        "task",
        "domain",
        "question",
        "method",
        "dataset_or_setting",
        "sample_size",
        "key_result",
        "limitation",
        "project_relevance",
        "evidence_class",
        "source_keys",
    },
    "physics_matrix.csv": {
        "physics_id",
        "topic",
        "physical_quantity",
        "observable_signature",
        "nuisance_or_limit",
        "benchmark_implication",
        "source_keys",
    },
    "classical_baseline_matrix.csv": {
        "baseline_id",
        "method",
        "implementation",
        "inputs",
        "outputs",
        "uncertainty_or_failure_mode",
        "hypotheses",
        "source_keys",
    },
    "theorem_matrix.csv": {
        "theorem_id",
        "topic",
        "result",
        "assumptions",
        "project_use",
        "non_claim",
        "source_keys",
    },
    "astronomy_tda_gap_map.csv": {
        "gap_id",
        "astronomy_area",
        "directness",
        "representation_or_task",
        "transferable_idea",
        "non_transferable_limit",
        "stage1_conclusion",
        "source_keys",
    },
    "hypothesis_baseline_crosswalk.csv": {
        "hypothesis_id",
        "topological_claim",
        "classical_baseline_ids",
        "primary_metric",
        "comparison_rule",
        "source_keys",
    },
}


def _require_fields(
    rows: list[dict[str, str]], required: set[str], label: str, errors: list[str]
) -> None:
    if not rows:
        errors.append(f"{label} must contain at least one row")
        return
    fields = set(rows[0])
    if fields != required:
        errors.append(f"{label} fields differ: expected {sorted(required)}; found {sorted(fields)}")
    for number, row in enumerate(rows, start=2):
        missing_values = sorted(field for field in required if not row.get(field, "").strip())
        if missing_values:
            errors.append(f"{label} row {number} has blank required fields: {missing_values}")


def _decimal(value: str, label: str, errors: list[str]) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        errors.append(f"{label} is not numeric: {value!r}")
        return None


def _unique(rows: list[dict[str, str]], field: str, label: str, errors: list[str]) -> None:
    values = [row.get(field, "") for row in rows]
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        errors.append(f"{label} has duplicate {field}: {duplicates}")


def validate_literature(root: Path, errors: list[str]) -> set[str]:
    source_keys_used: set[str] = set()
    matrices: dict[str, list[dict[str, str]]] = {}
    for name, fields in MATRIX_FIELDS.items():
        rows = read_csv_rows(root / "evidence/literature" / name)
        matrices[name] = rows
        _require_fields(rows, fields, name, errors)
        for row in rows:
            source_keys_used.update(split_source_keys(row.get("source_keys", "")))

    literature = matrices["literature_matrix.csv"]
    _unique(literature, "record_id", "literature matrix", errors)
    tasks = {row["task"] for row in literature}
    if tasks != REQUIRED_TASKS:
        errors.append(f"literature matrix must cover T1.1-T1.8 exactly; found {sorted(tasks)}")

    baselines = matrices["classical_baseline_matrix.csv"]
    baseline_ids = {row["baseline_id"] for row in baselines}
    if baseline_ids != REQUIRED_BASELINES:
        errors.append(f"classical baselines must be CB-01..CB-08; found {sorted(baseline_ids)}")

    theorems = matrices["theorem_matrix.csv"]
    theorem_ids = {row["theorem_id"] for row in theorems}
    if theorem_ids != REQUIRED_TDA_TOPICS:
        errors.append(f"theorem matrix must be TDA-01..TDA-09; found {sorted(theorem_ids)}")

    crosswalk = matrices["hypothesis_baseline_crosswalk.csv"]
    hypothesis_ids = {row["hypothesis_id"] for row in crosswalk}
    if hypothesis_ids != REQUIRED_HYPOTHESES:
        errors.append("Stage 1 crosswalk must contain H1-H6 exactly")
    for row in crosswalk:
        referenced = split_source_keys(row["classical_baseline_ids"])
        if not referenced or not referenced <= baseline_ids:
            errors.append(f"{row['hypothesis_id']} references unknown classical baselines")

    return source_keys_used


def validate_benchmarks(root: Path, errors: list[str]) -> set[str]:
    directory = root / "evidence/benchmarks"
    source_keys_used: set[str] = set()
    population = read_csv_rows(directory / "legacy_population.csv")
    if len(population) != 66:
        errors.append(f"LEGACY population must contain 66 stars; found {len(population)}")
    _unique(population, "kic", "LEGACY population", errors)
    population_ids = {row["object_id"] for row in population}
    if "KIC 10963065" not in population_ids:
        errors.append("Rudy (KIC 10963065) is absent from the LEGACY population")
    for number, row in enumerate(population, start=2):
        source_keys_used.update(split_source_keys(row.get("source_key", "")))
        for field in ("numax_uHz", "dnu_uHz", "teff_K", "feh_dex"):
            _decimal(row.get(field, ""), f"legacy_population.csv row {number} {field}", errors)

    targets = read_csv_rows(directory / "benchmark_targets.csv")
    required_target_fields = {
        "benchmark_id",
        "object_id",
        "object_label",
        "sample",
        "quantity",
        "value",
        "unit",
        "uncertainty_minus",
        "uncertainty_plus",
        "uncertainty_type",
        "method",
        "source_key",
        "source_location",
        "reconciliation",
        "status",
    }
    # object_label and uncertainty bounds may intentionally be blank.
    if not targets or set(targets[0]) != required_target_fields:
        errors.append("benchmark target fields differ from the Stage 1 schema")
    _unique(targets, "benchmark_id", "benchmark targets", errors)
    authoritative: dict[str, set[str]] = {object_id: set() for object_id in population_ids}
    for number, row in enumerate(targets, start=2):
        source_keys_used.add(row.get("source_key", ""))
        _decimal(row.get("value", ""), f"benchmark_targets.csv row {number} value", errors)
        for field in ("uncertainty_minus", "uncertainty_plus"):
            value = row.get(field, "")
            if value:
                bound = _decimal(value, f"benchmark_targets.csv row {number} {field}", errors)
                if bound is not None and bound < 0:
                    errors.append(f"benchmark_targets.csv row {number} has a negative bound")
        required_text = ("unit", "uncertainty_type", "method", "source_location", "reconciliation")
        if any(not row.get(field, "").strip() for field in required_text):
            errors.append(f"benchmark_targets.csv row {number} lacks traceability text")
        if row.get("status") == "benchmark" and row.get("object_id") in authoritative:
            authoritative[row["object_id"]].add(row.get("quantity", ""))
    incomplete = sorted(
        object_id
        for object_id, quantities in authoritative.items()
        if quantities != REQUIRED_TARGET_QUANTITIES
    )
    if incomplete:
        errors.append(f"LEGACY stars with incomplete authoritative targets: {incomplete}")

    rudy_global = {
        row["quantity"]: row
        for row in targets
        if row["object_id"] == "KIC 10963065" and row["status"] == "benchmark"
    }
    expected = {"numax": Decimal("2203.7"), "dnu": Decimal("103.179")}
    for quantity, expected_value in expected.items():
        rudy_row = rudy_global.get(quantity)
        if rudy_row is None or Decimal(rudy_row["value"]) != expected_value:
            errors.append(f"Rudy authoritative {quantity} target is missing or altered")

    modes = read_csv_rows(directory / "rudy_mode_frequencies.csv")
    if len(modes) != 42:
        errors.append(f"Rudy mode table must contain 42 rows; found {len(modes)}")
    mode_ids = {(row.get("radial_order_n", ""), row.get("angular_degree_l", "")) for row in modes}
    if len(mode_ids) != len(modes):
        errors.append("Rudy mode (n,l) labels must be unique")
    for number, row in enumerate(modes, start=2):
        source_keys_used.add(row.get("source_key", ""))
        if row.get("object_id") != "KIC 10963065":
            errors.append(f"rudy_mode_frequencies.csv row {number} has a wrong object ID")
        for field in (
            "frequency_uHz",
            "frequency_error_minus_uHz",
            "frequency_error_plus_uHz",
        ):
            numeric_value = _decimal(row.get(field, ""), f"rudy modes row {number} {field}", errors)
            if numeric_value is not None and numeric_value <= 0:
                errors.append(f"rudy modes row {number} {field} must be positive")

    identity = load_yaml(directory / "rudy_identity.yaml")
    aliases = set(identity.get("aliases", []))
    required_aliases = {"KIC 10963065", "HD 176693", "Kepler-408", "TIC 48450369"}
    if not required_aliases <= aliases:
        errors.append("Rudy identity record is missing a required alias")
    if identity.get("canonical_object_id") != "KIC 10963065":
        errors.append("Rudy identity has an unexpected canonical object ID")

    provenance = read_csv_rows(directory / "source_provenance.csv")
    _unique(provenance, "source_id", "benchmark provenance", errors)
    for row in provenance:
        source_keys_used.add(row.get("source_key", ""))
        if re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) is None:
            errors.append(f"invalid source checksum for {row.get('source_id', '<unknown>')}")
    return {key for key in source_keys_used if key}


def validate_search(root: Path, errors: list[str]) -> None:
    rows = read_csv_rows(root / "evidence/search/novelty_search_log.csv")
    concepts = {row.get("concept_id", "") for row in rows}
    if concepts != REQUIRED_CONCEPTS:
        errors.append(f"novelty audit must contain NQ-01..NQ-06; found {sorted(concepts)}")
    completed_services = {row["service"] for row in rows if row.get("status") == "completed"}
    if len(completed_services) < 2:
        errors.append("novelty audit needs at least two successfully queried services")
    for service in completed_services:
        service_concepts = {
            row["concept_id"]
            for row in rows
            if row.get("service") == service and row.get("status") == "completed"
        }
        if service_concepts != REQUIRED_CONCEPTS:
            errors.append(f"completed novelty service {service} lacks one or more concept queries")
    for number, row in enumerate(rows, start=2):
        if row.get("status") == "completed":
            for field in ("total_results", "screened_results", "direct_precedents"):
                if not row.get(field, "").isdigit():
                    errors.append(f"novelty row {number} completed without numeric {field}")
        else:
            if any(row.get(field, "") for field in ("total_results", "direct_precedents")):
                errors.append(f"novelty row {number} turns a failed/limited query into evidence")
    if any(int(row["direct_precedents"]) > 0 for row in rows if row.get("status") == "completed"):
        errors.append("G1 cannot pass while a direct precedent remains unreconciled")


def validate_references(root: Path, used_keys: set[str], errors: list[str]) -> None:
    audit = read_csv_rows(root / "evidence/references/reference_audit.csv")
    _unique(audit, "source_key", "reference audit", errors)
    audit_keys = {row["source_key"] for row in audit}
    bibliography_keys = bibtex_keys(root / "evidence/references/topoastero_stage1.bib")
    if audit_keys != bibliography_keys:
        errors.append("reference-audit keys and clean BibTeX keys must match exactly")
    unresolved = sorted(used_keys - audit_keys)
    if unresolved:
        errors.append(f"evidence has unresolved source keys: {unresolved}")
    if any(row.get("metadata_status") != "verified" for row in audit):
        errors.append("all admitted Stage 1 references must be verified")
    dois = [normalized_doi(row["doi"]) for row in audit if row.get("doi")]
    duplicates = sorted(doi for doi, count in Counter(dois).items() if count > 1)
    if duplicates:
        errors.append(f"reference audit has duplicate DOI values: {duplicates}")


def validate_gate_and_manifest(root: Path, errors: list[str]) -> None:
    gate = json.loads((root / "reports/stage1/G1_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G1" or gate.get("decision") != "PASS":
        errors.append("G1 acceptance record must declare gate G1 with decision PASS")
    clauses = gate.get("clauses", [])
    if not isinstance(clauses, list) or len(clauses) < 3:
        errors.append("G1 acceptance record must contain the three agenda clauses")
    elif any(not isinstance(clause, dict) or clause.get("status") != "pass" for clause in clauses):
        errors.append("every G1 clause must pass")

    manifest = read_csv_rows(root / "reports/stage1/deliverable_manifest.csv")
    _unique(manifest, "path", "Stage 1 manifest", errors)
    for row in manifest:
        path = root / row.get("path", "")
        if not path.is_file():
            errors.append(f"Stage 1 manifest path missing: {row.get('path', '')}")
            continue
        if row.get("sha256") != sha256_file(path):
            errors.append(f"Stage 1 manifest checksum mismatch: {row.get('path', '')}")


def validate_stage1(root: str | Path, *, require_stage0: bool = True) -> list[str]:
    """Validate every T1.1-T1.8 deliverable and the G1 decision."""
    repository = Path(root).resolve()
    errors = [
        f"Required Stage 1 file missing: {relative}"
        for relative in REQUIRED_FILES
        if not (repository / relative).is_file()
    ]
    if errors:
        return errors
    for schema_name in (
        "literature_evidence.schema.json",
        "benchmark_target.schema.json",
        "reference_audit.schema.json",
        "novelty_search.schema.json",
    ):
        try:
            json.loads((repository / "schemas" / schema_name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON schema {schema_name}: {exc}")
    used_keys = validate_literature(repository, errors)
    used_keys.update(validate_benchmarks(repository, errors))
    validate_search(repository, errors)
    validate_references(repository, used_keys, errors)
    validate_gate_and_manifest(repository, errors)
    if require_stage0:
        errors.extend(f"Stage 0 regression: {error}" for error in validate_stage0(repository))
    return errors
