"""Stage 12 evidence, feature grouping, calibrated scope and archive checks."""

from __future__ import annotations

from pathlib import Path

from topoastero.config import content_hash
from topoastero.hybrid.features import fingerprint, load_config
from topoastero.hybrid.release import release_issues
from topoastero.population_store import contained, read_json, read_table, seal_issues
from topoastero.provenance import sha256_file
from topoastero.stage11_validation import validate_stage11


def validate(root: Path, *, prior: bool = True) -> list[str]:
    issues = []
    try:
        cfg = load_config(root)
        output = contained(root, cfg["output"])
        reports = contained(root, cfg["reports"])
        gate = read_json(reports / "G12_ACCEPTANCE.json")
        if gate["configuration_sha256"] != content_hash(cfg) or gate["code_sha256"] != fingerprint(root):
            issues.append("Stage 12 source/configuration seal is stale")
        for path in (output / "development_run.json", output / "transfer_run.json", reports / "evidence_manifest.json"):
            if not path.exists():
                issues.append("missing Stage 12 run/evidence: " + path.name)
                continue
            record = read_json(path)
            if path.name != "evidence_manifest.json" and (record["code_sha256"] != fingerprint(root) or record["configuration_sha256"] != content_hash(cfg)):
                issues.append("Stage 12 run source/configuration stale: " + path.name)
            issues.extend(seal_issues(root, record["files"]))
            issues.extend(seal_issues(root, record.get("inputs", [])))
        pack = read_json(output / "models.json")
        if pack["code_sha256"] != fingerprint(root) or pack["configuration_sha256"] != content_hash(cfg):
            issues.append("Stage 12 fitted model source/configuration stale")
        data = read_json(output / "feature_dataset.json")
        groups = {r["stable_star_id"] for r in data["rows"]}
        if len(groups) != len(data["rows"]) or any(r["role"] != "development" or r["stable_star_id"] == "KIC 10963065" for r in data["rows"]):
            issues.append("training star grouping/Rudy/holdout leakage")
        if set(pack["training_stars"]) != groups or pack["holdout_used"]:
            issues.append("model training role differs from dataset")
        for fold in read_json(output / "fold_audit.json")["folds"]:
            if set(fold["train_stars"]) & set(fold["test_stars"]) or set(fold["train_stars"] + fold["test_stars"]) != groups:
                issues.append("outer train/test stars overlap or cohort incomplete")
        if {r["task_id"] for r in read_table(reports / "task_traceability.csv")} != {f"T12.{i}" for i in range(1, 12)}:
            issues.append("Stage 12 task traceability incomplete")
        if gate["publication_ready"] or gate["positive_population_transfer_claim"]:
            issues.append("unsupported Stage 12 publication/population transfer claim")
        if gate["usable_development_stars"] < cfg["minimum_claim_stars"] and gate["positive_complementarity_claim"]:
            issues.append("sparse development sample falsely supports complementarity")
        if read_json(reports / "TESS_SCOPE_DECISION.json")["broader_TESS_expansion"]:
            issues.append("broader TESS expansion lacks powered evidence")
        if contained(root, cfg["release"]).exists():
            issues.extend(release_issues(root, cfg))
        state_path = contained(root, cfg["confirmation_state"])
        if state_path.exists():
            state = read_json(state_path)
            if state["opening_count"] != 1:
                issues.append("invalid Stage 12 opening count")
            if state["status"] == "completed" and sha256_file(output / "confirmation_archive.json") != state["archive_sha256"]:
                issues.append("first Stage 12 confirmation archive changed")
    except (ValueError, KeyError, OSError, TypeError) as exc:
        issues.append("invalid Stage 12 evidence: " + str(exc))
    if prior:
        issues.extend(validate_stage11(root))
    return issues
