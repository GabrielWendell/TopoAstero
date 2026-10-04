"""Offline Stage 11 artifact, grouping, evidence-seal and honest-gate validation."""

from __future__ import annotations

from pathlib import Path

from topoastero.config import content_hash
from topoastero.population_acquisition import load_config
from topoastero.population_freeze import release_issues
from topoastero.population_pipeline import cohort, source_fingerprint
from topoastero.population_store import contained, read_json, read_table, seal_issues
from topoastero.provenance import sha256_file
from topoastero.stage10_validation import validate_stage10

REQUIRED = (
    "configs/stage11_legacy.yaml", "docs/protocols/STAGE11_POPULATION_PROTOCOL.md",
    "docs/reproducibility/STAGE11_REPRODUCTION.md", "environment/stage11.Dockerfile",
    "registries/stage11_exclusions.csv", "registries/stage11_qa.jsonl",
    "data/manifests/stage11/acquisition.json", "data/reference/stage11/reference_manifest.json",
    "reports/stage11/G11_ACCEPTANCE.json", "reports/stage11/cohort_ledger.csv",
    "reports/stage11/leakage_multiplicity_audit.json", "reports/stage11/failure_atlas.csv",
    "reports/stage11/task_traceability.csv", "reports/stage11/evidence_manifest.json",
    "reports/stage11/STAGE11_REPORT.md", "reports/stage11/TRACEABILITY_MATRIX.md",
    "paper2/main.tex", "paper2/results_status.tex", "paper2/results_tables.tex", "paper2/references.bib",
    "schemas/stage11_gate.schema.json", "schemas/stage11_catalog.schema.json", "schemas/stage11_release.schema.json",
)


def validate_stage11(root: str | Path, *, require_prior_stages: bool = True, require_confirmation: bool = False) -> list[str]:
    repository = Path(root).resolve()
    missing = [f"missing Stage 11 artifact: {name}" for name in REQUIRED if not (repository / name).is_file()]
    if missing:
        return missing
    issues = []
    try:
        cfg = load_config(repository)
        members = cohort(repository, cfg)
        gate = read_json(contained(repository, cfg["reports"]) / "G11_ACCEPTANCE.json")
        refs = read_json(contained(repository, cfg["reference_manifest"]))
        issues.extend(seal_issues(repository, refs["files"]))
        if refs["edition"] != cfg["references"]["edition"] or refs["stars"] != 66 or refs["covariance_available"]:
            issues.append("corrected reference edition/scope invalid")
        if gate["cohort_stars"] != len(members) or gate["configuration_sha256"] != content_hash(cfg) or gate["implementation_status"] != "pass":
            issues.append("Stage 11 gate does not match cohort/configuration")
        evidence = read_json(repository / "reports/stage11/evidence_manifest.json")
        issues.extend(seal_issues(repository, evidence["files"] + evidence["report_files"]))
        for name in ("development", "internal_validation", "descriptive_benchmark", "confirmation"):
            directory = contained(repository, evidence["role_directories"][name])
            if not (directory / "run_manifest.json").exists():
                continue
            manifest = read_json(directory / "run_manifest.json")
            issues.extend(seal_issues(repository, manifest["files"]))
            summary = read_json(directory / "summary.json")
            if summary["configuration_sha256"] != content_hash(cfg) or summary["code_sha256"] != source_fingerprint(repository):
                issues.append(f"stale batch code/configuration: {name}")
            rows = read_json(directory / "catalog.json")["rows"]
            expected_role = "final_holdout" if name == "confirmation" else name
            expected = {r["stable_star_id"] for r in members if r["role"] == expected_role}
            if {r["stable_star_id"] for r in rows} != expected or len(rows) != 4 * len(expected) or any(r["role"] != expected_role for r in rows):
                issues.append(f"role leakage/missing star rows: {name}")
            if len({(r["stable_star_id"], r["method"], r["quantity"]) for r in rows}) != len(rows):
                issues.append(f"repeated segments counted as stars: {name}")
            for path in directory.glob("stars/*/analysis.json"):
                result = read_json(path)
                if result["reference_values_used_in_estimation"]:
                    issues.append("published references leaked into estimation")
                if "cylinder_inference" in result and (result["cylinder_inference"] != "geometry_only" or result["blind_ridge_ratios"] != "withheld_without_degree_anchors"):
                    issues.append("unsupported blind cylindrical inference")
                if result.get("prominence_max_absolute_difference", 0) > 1e-8:
                    issues.append("path H0/prominence identity broken")
        statepath = contained(repository, cfg["confirmation_state"])
        state = read_json(statepath) if statepath.exists() else {"status": "unopened", "opening_count": 0}
        if (contained(repository, evidence["role_directories"]["confirmation"]) / "catalog.json").exists() and not statepath.exists():
            issues.append("confirmation evidence exists without a reserved one-time opening")
        releasepath = contained(repository, cfg["release"])
        if releasepath.exists():
            issues.extend(release_issues(repository, cfg, read_json(releasepath)))
        if state["status"] == "completed":
            if not releasepath.exists() or state["opening_count"] != 1 or not state["first_valid_run_preserved"]:
                issues.append("invalid confirmation opening/archive state")
            manifest_path = contained(repository, cfg["output"]) / "confirmation/run_manifest.json"
            if not manifest_path.exists() or sha256_file(manifest_path) != state["archive_manifest_sha256"]:
                issues.append("first confirmation archive changed")
        elif gate["scientific_population_gate_passed"] or gate["status"] != "population_pending":
            issues.append("G11 falsely claims unopened/incomplete population confirmation")
        if gate["publication_ready"]:
            issues.append("publication readiness requires independent scientific review")
        tasks = read_table(repository / "reports/stage11/task_traceability.csv")
        if {r["task_id"] for r in tasks} != {f"T11.{i}" for i in range(1, 12)}:
            issues.append("task traceability incomplete")
        if require_confirmation and (state["status"] != "completed" or not gate["scientific_population_gate_passed"]):
            issues.append("scientific G11 confirmation is pending")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        issues.append(f"invalid Stage 11 evidence: {exc}")
    if require_prior_stages:
        issues.extend(validate_stage10(repository))
    return issues
