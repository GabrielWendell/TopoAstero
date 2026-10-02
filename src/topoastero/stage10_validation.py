"""Offline scientific integrity and honest review-gate checks for the Paper I freeze."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.config import configuration_hash, load_yaml
from topoastero.provenance import sha256_file
from topoastero.rudy_benchmark import holm_adjust, monte_carlo_tail
from topoastero.stage9_validation import validate_stage9

RUN_ID = "TA-S10-RUDY-R001"
FIGURES = (
    "01_observation_window", "02_psd_background", "03_ordinary_echelle",
    "04_localized_persistence", "05_spacing_aliases", "06_cylinder_ridges",
    "07_simulation_placement", "08_sensitivity_uncertainty", "09_quarter_stability",
    "10_kepler_tess_transfer",
)
RESULTS = (
    "benchmark_capsule.json", "classical_branches.csv", "background_models.json",
    "sampling_audit.csv", "branch_spectra.csv", "broad_spectrum.csv", "robustness.csv",
    "observation_preview.csv", "spectral_windows.csv", "quarter_stability.csv",
    "monthly_bootstrap.csv", "monthly_spectra.csv", "stochastic_draws.csv",
    "localized_peaks.json", "spectral_score_scan.csv", "echelle_score_scan.csv",
    "cylinder.json", "echelle_branch_controls.csv", "echelle_bootstrap.csv",
    "published_mode_overlay.csv", "published_frequency_ratios.csv", "ratio_reference_audit.csv",
    "null_draws.csv", "conditional_null_tests.csv", "uncertainty_budget.csv",
    "scaling_draws.csv", "scaling_uncertainty.csv", "quality_flags.csv",
    "tess_sectors.csv", "kepler_to_tess.csv", "simulation_placement.csv", "summary.json",
    "environment.json", "run_manifest.json",
)
REQUIRED = (
    "configs/stage10_rudy.yaml", "registries/stage10_independent_review.yaml",
    "docs/protocols/STAGE10_RUDY_FREEZE_PROTOCOL.md", "docs/reproducibility/STAGE10_REPRODUCTION.md",
    "reports/stage10/claim_evidence.csv", "reports/stage10/claim_audit.json",
    "reports/stage10/freeze_manifest.json", "reports/stage10/clean_reproduction.json",
    "reports/stage10/G10_ACCEPTANCE.json", "reports/stage10/deliverable_manifest.csv",
    "reports/stage10/STAGE10_REPORT.md", "reports/stage10/TRACEABILITY_MATRIX.md",
    "reports/stage10/LIMITATIONS_AND_NEGATIVE_RESULTS.md", "reports/stage10/figure_manifest.json",
    "paper1/main.tex", "paper1/main.pdf", "paper1/results_macros.tex", "paper1/results_tables.tex",
    "paper1/references.bib", "paper1/build_status.json", "paper1/README.md",
    "schemas/stage10_gate.schema.json", "schemas/stage10_freeze.schema.json",
    "schemas/stage10_capsule.schema.json",
)


def _json(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def file_seal_issues(root: Path, records: object, label: str) -> list[str]:
    """Reject unsafe paths before checking exact file identity."""
    issues = []
    if not isinstance(records, list) or not records:
        return [f"{label}: missing file seals"]
    for record in records:
        if not isinstance(record, dict):
            issues.append(f"{label}: invalid seal record")
            continue
        relative = record.get("path")
        if not isinstance(relative, str) or not relative or relative.startswith("/") or "\\" in relative or ":" in relative or ".." in Path(relative).parts:
            issues.append(f"{label}: unsafe path {relative}")
            continue
        target = root / relative
        if not target.is_file() or sha256_file(target) != record.get("sha256") or target.stat().st_size != record.get("size_bytes"):
            issues.append(f"{label}: stale seal {relative}")
    return issues


def independent_review_accepted(root: Path, review: dict[str, Any]) -> tuple[bool, list[str]]:
    """Accept a signed exact-snapshot review, never a machine-generated attestation."""
    if review.get("review_id") != "TA-S10-INDEPENDENT-REVIEW-001" or review.get("reviewed_snapshot") != "reports/stage10/freeze_manifest.json":
        return False, ["independent review targets the wrong snapshot"]
    fields = ("reviewer_name", "reviewer_affiliation", "reviewer_independent_of_authors", "review_date", "document_sha256", "decision")
    if review.get("status") == "pending_external_review":
        if any(review.get(key) is not None for key in fields) or review.get("reproduced_claim_ids") != []:
            return False, ["pending independent review contains a fabricated attestation"]
        return False, []
    if review.get("status") != "accepted":
        return False, ["unknown independent review status"]
    try:
        reviewed_on = date.fromisoformat(review["review_date"])
    except (TypeError, ValueError, KeyError):
        return False, ["accepted review lacks a valid review date"]
    expected = {f"P1-C{index:02d}" for index in range(1, 9)}
    if (reviewed_on > date.today() or not review.get("reviewer_name") or not review.get("reviewer_affiliation")
            or review.get("reviewer_independent_of_authors") is not True or review.get("decision") != "accepted"
            or set(review.get("reproduced_claim_ids", [])) != expected
            or review.get("document_sha256") != sha256_file(root / review["reviewed_snapshot"])):
        return False, ["accepted independent review is incomplete, nonindependent or stale"]
    return True, []


def validate_stage10(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Validate completion while keeping the final G10 human-review hold explicit."""
    repository = Path(root).resolve()
    required = (*REQUIRED, *(f"results/stage10/{name}" for name in RESULTS),
                *(f"reports/stage10/figures/{name}.{suffix}" for name in FIGURES for suffix in ("svg", "pdf", "png")))
    errors = [f"missing Stage 10 file: {relative}" for relative in required if not (repository / relative).is_file()]
    if errors:
        return errors
    cfg = load_yaml(repository / "configs/stage10_rudy.yaml")
    summary = _json(repository / "results/stage10/summary.json")
    capsule = _json(repository / "results/stage10/benchmark_capsule.json")
    freeze = _json(repository / "reports/stage10/freeze_manifest.json")
    gate = _json(repository / "reports/stage10/G10_ACCEPTANCE.json")
    audit = _json(repository / "reports/stage10/claim_audit.json")
    reproduction = _json(repository / "reports/stage10/clean_reproduction.json")
    manifest = _json(repository / "results/stage10/run_manifest.json")
    build = _json(repository / "paper1/build_status.json")
    review = load_yaml(repository / "registries/stage10_independent_review.yaml")
    accepted, review_errors = independent_review_accepted(repository, review)
    errors.extend(review_errors)
    if cfg.get("run_id") != RUN_ID or cfg.get("software_version") != "TopoAstero-0.11.0" or summary.get("run_id") != RUN_ID:
        errors.append("Stage 10 protocol/run/software identity drift")
    if capsule.get("config_sha256") != configuration_hash(repository / "configs/stage10_rudy.yaml"):
        errors.append("Stage 10 config seal drift")
    if summary.get("population_spectra_used") is not False or summary.get("final_holdout_used") is not False or cfg["scope"]["role"] != "descriptive_single_star_benchmark":
        errors.append("Stage 10 scope leaks population or final holdout")
    if capsule.get("preprocessing_selection_used_topology") is not False or capsule.get("raw_payloads_redistributed") is not False:
        errors.append("benchmark capsule violates acquisition/selection policy")
    if summary.get("delay_status") != "not_run_G7_preregistered_drop" or summary.get("echelle_claim") != "geometry_only_no_estimator_utility":
        errors.append("Stage 10 overrules prior negative/geometry-only decisions")
    products = _csv(repository / cfg["inputs"]["kepler_manifest"])
    products += [row for row in _csv(repository / cfg["inputs"]["tess_manifest"]) if row["author"] == "SPOC"]
    expected_products = {(row["product_key"], row["sha256"], row["data_uri"]) for row in products}
    actual_products = {(row["product_key"], row["sha256"], row["data_uri"]) for row in capsule.get("products", [])}
    if capsule.get("product_count") != 21 or expected_products != actual_products:
        errors.append("capsule does not contain the 21 frozen public products")
    errors.extend(file_seal_issues(repository, capsule.get("inputs"), "capsule input"))
    errors.extend(file_seal_issues(repository, freeze.get("files"), "Paper I freeze"))
    errors.extend(file_seal_issues(repository, manifest.get("outputs"), "Stage 10 output"))
    if freeze.get("status") != "internal_review_snapshot" or freeze.get("external_publication_or_DOI_created") is not False:
        errors.append("freeze falsely implies publication or final approval")
    branches = _csv(repository / "results/stage10/classical_branches.csv")
    audit_rows = _csv(repository / "results/stage10/robustness.csv")
    factorial = {(row["branch_id"], row["background_id"], row["normalization"]) for row in audit_rows if row["factor"] == "factorial"}
    expected_factorial = {(branch, f"H{model}", method) for branch in cfg["preprocessing"]["kepler_branches"] for model in (0, 1, 2) for method in cfg["topology"]["normalizations"]}
    if len(audit_rows) != 72 or factorial != expected_factorial or {row["branch_id"] for row in branches} != {"PP-01", "PP-02", "PP-03", "PP-04"}:
        errors.append("mandatory preprocessing/background/normalization branches omitted")
    expected_rows = {"monthly_bootstrap.csv": 256, "null_draws.csv": 256, "stochastic_draws.csv": 64,
                     "echelle_bootstrap.csv": 64, "echelle_branch_controls.csv": 180, "quarter_stability.csv": 8,
                     "tess_sectors.csv": 11, "kepler_to_tess.csv": 396}
    for name, count in expected_rows.items():
        if len(_csv(repository / "results/stage10" / name)) != count:
            errors.append(f"incomplete Stage 10 experiment: {name}")
    nulls = _csv(repository / "results/stage10/null_draws.csv")
    tests = _csv(repository / "results/stage10/conditional_null_tests.csv")
    if len(tests) != 7:
        errors.append("seven-family multiplicity policy omitted")
    else:
        adjusted = holm_adjust([float(row["pvalue"]) for row in tests])
        for row, holm in zip(tests, adjusted, strict=True):
            tail = monte_carlo_tail(float(row["observed"]), np.array([float(draw[row["statistic"]]) for draw in nulls]))
            if not np.isclose(float(row["pvalue"]), tail.pvalue, atol=1e-12) or int(row["exceedances"]) != tail.exceedances or not np.isclose(float(row["holm_pvalue"]), holm, atol=1e-12):
                errors.append(f"incorrect conditional null/multiplicity calculation: {row['statistic']}")
    if summary.get("maximum_prominence_equivalence_error", 1) > 1e-10:
        errors.append("path-persistence/prominence identity failed")
    cylinder = _json(repository / "results/stage10/cylinder.json")
    if any(cylinder.get(key) is not None for key in ("inferred_r02", "inferred_r01", "inferred_r10")):
        errors.append("unsupported blind topological frequency ratios")
    budgets = _csv(repository / "results/stage10/uncertainty_budget.csv")
    if any(row["interval_target"] != "cadence_weighted_monthly_averaged_spectrum_not_full_span_LS" for row in budgets):
        errors.append("bootstrap estimand was mislabeled")
    claims = _csv(repository / "reports/stage10/claim_evidence.csv")
    if {row["claim_id"] for row in claims} != {f"P1-C{index:02d}" for index in range(1, 9)} or any(row["population_claim"] != "False" for row in claims):
        errors.append("claim registry contains missing or population claims")
    for row in claims:
        if not row["controls"] or not row["limit"] or row["frozen_before_manuscript"] != "True":
            errors.append(f"uncontrolled/unbounded claim: {row['claim_id']}")
        for relative in row["evidence"].split(";"):
            if not (repository / relative).is_file():
                errors.append(f"claim evidence missing: {relative}")
    if audit.get("status") != "pass" or audit.get("unsupported_claims") != [] or audit.get("new_G9_proposition_headline_claims") != [] or audit.get("claim_evidence_sha256") != sha256_file(repository / "reports/stage10/claim_evidence.csv"):
        errors.append("claim audit is unsupported or stale")
    expected_status = "pass" if accepted else "review_pending"
    if gate.get("status") != expected_status or gate.get("implementation_status") != "pass" or gate.get("independent_human_review") != ("accepted" if accepted else "pending"):
        errors.append("G10 falsely reports independent approval")
    if reproduction.get("status") != "pass" or reproduction.get("independent_human_reviewer") is not None or reproduction.get("fresh_source_copy") is not True or reproduction.get("new_process") is not True:
        errors.append("clean reproduction is incomplete or masquerades as human review")
    errors.extend(file_seal_issues(repository, reproduction.get("source_inputs"), "clean reproduction source"))
    errors.extend(file_seal_issues(repository, reproduction.get("result_files"), "clean reproduction result"))
    if build.get("status") != "compiled" or build.get("claims_frozen_before_manuscript") is not True:
        errors.append("Paper I draft was not compiled after claim freeze")
    figure_manifest = _json(repository / "reports/stage10/figure_manifest.json")
    if {row["figure_id"] for row in figure_manifest.get("figures", [])} != set(FIGURES):
        errors.append("journal figure suite is incomplete")
    for name in FIGURES:
        source = (repository / f"reports/stage10/figures/{name}.svg").read_text(encoding="utf-8")
        if "TA-PLOT-1.0" not in source or "Machine-readable source:" not in source:
            errors.append(f"figure violates style/provenance contract: {name}")
    if require_prior_stages:
        errors.extend(f"Stage 9: {issue}" for issue in validate_stage9(repository))
    return errors
