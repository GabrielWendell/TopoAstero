"""Offline integrity and science-gate validation for Stage 9 artifacts."""

from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from topoastero.config import configuration_hash, load_yaml
from topoastero.mathematical_relations import gamma_log_tail_bound
from topoastero.provenance import sha256_file
from topoastero.stage8_validation import validate_stage8

RUN_ID = "TA-S09-MATH-R001"
SCHEMAS = (
    "stage9_numerical_audit.schema.json", "stage9_counterexamples.schema.json",
    "stage9_gate.schema.json", "stage9_run_manifest.schema.json",
)
REQUIRED = (
    "configs/stage9_mathematics.yaml", "registries/stage9_proof_review.yaml",
    "docs/science/STAGE9_THEOREMS_AND_PROOFS.md", "docs/protocols/STAGE9_MATHEMATICAL_AUDIT.md",
    "src/topoastero/mathematical_relations.py", "notebooks/09_mathematical_relations.ipynb",
    "results/stage9/numerical_audit.json", "results/stage9/counterexamples.json",
    "results/stage9/environment.json", "results/stage9/run_manifest.json",
    "reports/stage9/STAGE9_REPORT.md", "reports/stage9/COUNTEREXAMPLE_CATALOG.md",
    "reports/stage9/UNCERTAINTY_PROPAGATION.md", "reports/stage9/PROOF_REVIEW_PACKET.md",
    "reports/stage9/TRACEABILITY_MATRIX.md", "reports/stage9/G9_ACCEPTANCE.json",
    "reports/stage9/deliverable_manifest.csv", "reports/stage9/figures/ridge_jump_bounds.svg",
    "reports/stage9/figures/gamma_calibration.svg",
)


def _json(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


def _seals(root: Path, records: object, label: str, errors: list[str]) -> None:
    if not isinstance(records, list) or not records:
        errors.append(f"{label} has no file seals")
        return
    for record in records:
        if not isinstance(record, dict):
            errors.append(f"invalid {label} record")
            continue
        relative = record.get("path")
        if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative or ".." in Path(relative).parts:
            errors.append(f"invalid {label} path: {relative}")
            continue
        target = root / relative
        if not target.is_file() or sha256_file(target) != record.get("sha256") or target.stat().st_size != record.get("size_bytes"):
            errors.append(f"stale {label} seal: {relative}")


def _accepted_review(root: Path, review: dict[str, Any], errors: list[str]) -> bool:
    if review.get("review_id") != "TA-S09-PROOF-REVIEW-001" or review.get("reviewed_document") != "docs/science/STAGE9_THEOREMS_AND_PROOFS.md":
        errors.append("independent review targets the wrong claim/document")
        return False
    if review.get("status") == "pending_external_review":
        if any(review.get(key) is not None for key in (
            "reviewer_name", "reviewer_affiliation", "reviewer_independent_of_authors",
            "review_date", "document_sha256", "decision",
        )) or review.get("reviewed_claim_ids") != []:
            errors.append("pending review contains an unsigned/fabricated attestation")
        return False
    if review.get("status") != "accepted":
        errors.append("unknown proof review state")
        return False
    try:
        review_date = date.fromisoformat(review["review_date"])
    except (TypeError, ValueError, KeyError):
        errors.append("accepted review lacks a valid ISO date")
        return False
    if (review_date > date.today() or not review.get("reviewer_name")
            or not review.get("reviewer_affiliation")
            or review.get("reviewer_independent_of_authors") is not True
            or review.get("decision") != "accepted"
            or "S9-T1" not in review.get("reviewed_claim_ids", [])
            or review.get("document_sha256") != sha256_file(root / review["reviewed_document"])):
        errors.append("independent proof attestation is incomplete or stale")
        return False
    return True


def validate_stage9(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Check implementation integrity while preserving an honest pending G9 gate."""

    repository = Path(root).resolve()
    errors = [f"missing Stage 9 file: {relative}" for relative in REQUIRED if not (repository / relative).is_file()]
    errors.extend(f"missing Stage 9 schema: {name}" for name in SCHEMAS if not (repository / "schemas" / name).is_file())
    if errors:
        return errors
    config = load_yaml(repository / "configs/stage9_mathematics.yaml")
    review = load_yaml(repository / "registries/stage9_proof_review.yaml")
    audit = _json(repository / "results/stage9/numerical_audit.json")
    counter = _json(repository / "results/stage9/counterexamples.json")
    gate = _json(repository / "reports/stage9/G9_ACCEPTANCE.json")
    manifest = _json(repository / "results/stage9/run_manifest.json")
    environment = _json(repository / "results/stage9/environment.json")
    if config.get("config_id") != "TA-STAGE9-MATHEMATICS-1.0" or config.get("run_id") != RUN_ID or config.get("software_version") != "TopoAstero-0.10.0":
        errors.append("Stage 9 protocol identity/version drifted")
    if config.get("prior_stage8_decision") != "geometry_only" or config.get("population_spectra_allowed") is not False or config.get("final_holdout_allowed") is not False:
        errors.append("Stage 8 negative decision or forbidden-data boundary drifted")
    if config.get("coefficients") != "F2" or config.get("stage8_ridge_jump_limit_cycles") != .17 or config.get("phase_bins") != 24:
        errors.append("fixed field/graph geometry drifted")
    for name in SCHEMAS:
        schema = _json(repository / "schemas" / name)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or schema.get("additionalProperties") is not False:
            errors.append(f"Stage 9 schema is not closed draft 2020-12: {name}")
    if audit.get("run_id") != RUN_ID or audit.get("seed") != config.get("seed") or audit.get("path_cases") != config.get("path_random_cases") or audit.get("cylinder_cases") != config.get("cylinder_random_cases") or audit.get("ridge_cases") != config.get("ridge_random_cases"):
        errors.append("numerical audit is detached from registered inputs")
    if set(audit.get("claim_ids", [])) != {"S9-P1", "S9-P2", "S9-P3", "S9-P4", "S9-T1", "S9-P5", "S9-P6"}:
        errors.append("proof-linked claim registry is incomplete")
    if any(not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or value > 1e-9 for key, value in audit.items() if key.startswith("max_")):
        errors.append("proof-linked numerical inequality failed")
    gamma = config["gamma"]
    if any(audit.get(key) != gamma[field] for key, field in (("gamma_shape", "shape"), ("gamma_bins", "bins"), ("gamma_alpha", "alpha"), ("gamma_replicates", "simulation_replicates"))):
        errors.append("Gamma calibration model or sampling count drifted")
    if not math.isclose(audit.get("gamma_tail_bound", -1), gamma_log_tail_bound(audit["gamma_radius"], audit["gamma_shape"], audit["gamma_bins"]), abs_tol=1e-12) or audit.get("gamma_tail_bound", 1) > gamma["alpha"] + 1e-12:
        errors.append("Gamma Chernoff bound no longer certifies registered alpha")
    if not 0 <= audit.get("gamma_exceedances", -1) <= audit.get("gamma_replicates", 0) or not math.isclose(audit.get("gamma_exceedance_rate", -1), audit["gamma_exceedances"] / audit["gamma_replicates"], abs_tol=1e-12):
        errors.append("Gamma empirical exceedance rate is inconsistent")
    if audit.get("stage8_decision") != "geometry_only" or audit.get("population_spectra_used") is not False or audit.get("final_holdout_used") is not False:
        errors.append("Stage 9 numerical audit overstates its evidence scope")
    cases = counter.get("cases", [])
    if counter.get("run_id") != RUN_ID or len(cases) != 9 or {case.get("id") for case in cases} != {f"CE{i:02d}" for i in range(1, 10)}:
        errors.append("nine distinct registered counterexample families are required")
    if any(not case.get("family") or not case.get("violated_assumption") for case in cases):
        errors.append("counterexample assumptions are missing")
    if cases and cases[0].get("values") != [4, 1, 3]:
        errors.append("merged-peak adversarial fixture drifted")
    accepted = _accepted_review(repository, review, errors)
    expected = "pass" if accepted else "review_pending"
    if gate.get("gate") != "G9" or gate.get("run_id") != RUN_ID or gate.get("status") != expected or gate.get("implementation_status") != "pass" or gate.get("new_claim") != "S9-T1" or gate.get("review_id") != review.get("review_id") or gate.get("review_status") != review.get("status") or gate.get("review_document_sha256") != review.get("document_sha256"):
        errors.append("G9 status does not reflect the independent review record")
    if gate.get("prior_stage8_decision") != "geometry_only" or gate.get("population_spectra_used") is not False or gate.get("final_holdout_used") is not False:
        errors.append("G9 scope contradicts the Stage 8 verdict")
    checks = {item.get("check"): item.get("status") for item in gate.get("checks", [])}
    if len(checks) != 5 or any(value != "pass" for key, value in checks.items() if key != "independent_human_proof_review") or checks.get("independent_human_proof_review") != ("pass" if accepted else "pending"):
        errors.append("G9 check list is inconsistent with review hold")
    if manifest.get("run_id") != RUN_ID or manifest.get("config_sha256") != configuration_hash(repository / "configs/stage9_mathematics.yaml") or manifest.get("software_version") != "TopoAstero-0.10.0" or manifest.get("style_id") != "TA-PLOT-1.0" or manifest.get("status") != "implementation_complete" or manifest.get("gate_status") != expected:
        errors.append("Stage 9 run provenance identity/config/review drifted")
    if manifest.get("population_spectra_used") is not False or manifest.get("final_holdout_used") is not False:
        errors.append("Stage 9 run manifest claims forbidden data")
    _seals(repository, manifest.get("inputs"), "run input", errors)
    _seals(repository, manifest.get("outputs"), "run output", errors)
    sealed_inputs = {item.get("path") for item in manifest.get("inputs", [])}
    sealed_outputs = {item.get("path") for item in manifest.get("outputs", [])}
    if sealed_inputs != {"configs/stage9_mathematics.yaml", "registries/stage9_proof_review.yaml", "reports/stage8/G8_ACCEPTANCE.json"}:
        errors.append("Stage 9 input provenance is incomplete")
    if not {"docs/science/STAGE9_THEOREMS_AND_PROOFS.md", "reports/stage9/G9_ACCEPTANCE.json", "results/stage9/numerical_audit.json", "tests/unit/test_mathematical_relations.py"} <= sealed_outputs:
        errors.append("Stage 9 claim evidence is not byte sealed")
    if environment.get("run_id") != RUN_ID or environment.get("plot_style") != "TA-PLOT-1.0":
        errors.append("numeric environment/style audit drifted")
    for relative in ("ridge_jump_bounds.svg", "gamma_calibration.svg"):
        source = (repository / "reports/stage9/figures" / relative).read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source or "TopoAstero-0.10.0" not in source:
            errors.append(f"Stage 9 figure lacks source/style metadata: {relative}")
    notebook = _json(repository / "notebooks/09_mathematical_relations.ipynb")
    code = [cell for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"]
    joined = " ".join("".join(cell.get("source", [])) for cell in code)
    if notebook.get("nbformat") != 4 or len(code) != 2 or (RUN_ID not in joined and "results/stage9" not in joined) or any(cell.get("execution_count") is None or not cell.get("outputs") for cell in code):
        errors.append("Stage 9 notebook is unexecuted or detached from governed evidence")
    chapter = (repository / "docs/science/STAGE9_THEOREMS_AND_PROOFS.md").read_text()
    if any(claim not in chapter for claim in ("S9-T1", "S9-P1", "S9-P6", "independent review", "geometry_only")):
        errors.append("formal claim chapter lacks scope/classification/review")
    with (repository / "reports/stage9/deliverable_manifest.csv").open(encoding="utf-8", newline="") as handle:
        deliverables = list(csv.DictReader(handle))
    if {row.get("deliverable") for row in deliverables} != {"D9.1", "D9.2", "D9.3", "D9.4", "G9", "software"}:
        errors.append("Stage 9 deliverable mapping is incomplete")
    _seals(repository, [{**row, "size_bytes": int(row["size_bytes"])} for row in deliverables], "deliverable", errors)
    if any(row.get("status") != (expected if row.get("deliverable") == "G9" else "implemented") for row in deliverables):
        errors.append("deliverable statuses contradict G9 hold")
    if require_prior_stages:
        errors.extend(f"Stage 8: {issue}" for issue in validate_stage8(repository))
    return errors
