"""Signed confirmation release, checksum preflight and one-time holdout execution.

Protection is procedural and content-addressed within this repository. Public KIC
identities/references are visible. Copying/deleting a repository cannot be prevented
by local software; the supervisor/steward maintain the signed release and access log.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from topoastero.config import canonical_json, content_hash
from topoastero.population_acquisition import verified_star_products
from topoastero.population_pipeline import cohort, run_role, source_fingerprint
from topoastero.population_store import (
    append_event,
    contained,
    read_json,
    seal,
    seal_issues,
    utc_now,
    write_json,
)
from topoastero.provenance import sha256_file


def _verify_signature(release: dict[str, Any]) -> bool:
    with tempfile.TemporaryDirectory(prefix="topoastero-release-") as folder:
        directory = Path(folder)
        (directory / "public.pem").write_text(release["public_key_pem"], encoding="utf-8")
        (directory / "signature.bin").write_bytes(bytes.fromhex(release["signature_hex"]))
        (directory / "payload.json").write_text(canonical_json(release["payload"]), encoding="utf-8")
        result = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(directory / "public.pem"),
                                 "-signature", str(directory / "signature.bin"), str(directory / "payload.json")],
                                capture_output=True, check=False)
        return result.returncode == 0


def release_issues(root: Path, cfg: dict[str, Any], release: dict[str, Any]) -> list[str]:
    try:
        payload = release["payload"]
        issues = []
        if release.get("payload_sha256") != content_hash(payload) or not _verify_signature(release):
            issues.append("confirmation release signature/hash invalid")
        if payload["configuration_sha256"] != content_hash(cfg) or payload["code_sha256"] != source_fingerprint(root):
            issues.append("code/configuration changed after release")
        issues.extend(seal_issues(root, payload["files"]))
        if not payload["supervisor"] or not payload["data_steward"] or payload["approval"] != "operator_recorded_supervisor_and_steward_approval":
            issues.append("confirmation authorization missing")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", payload["container_digest"]) is None:
            issues.append("container image digest is missing")
        if payload["models"] != "none_fixed_estimators" or payload["holdout_opened"] is not False:
            issues.append("release scope invalid")
        return issues
    except (KeyError, TypeError, ValueError, OSError):
        return ["invalid confirmation release or unavailable OpenSSL verifier"]


def freeze_release(root: Path, cache: Path, cfg: dict[str, Any], *, supervisor: str, data_steward: str,
                   container_digest: str, signing_key: Path, development_dir: Path | None = None) -> dict[str, Any]:
    """Freeze only after complete development/internal results and input acquisition.

    Names and image digest are supplied by the operator, never fabricated. RSA or
    ECDSA PEM keys supported by OpenSSL work; store the private key OUTSIDE the
    research repository. The release carries the public key and detached signature.
    """
    target = contained(root, cfg["release"])
    if target.exists() or contained(root, cfg["confirmation_state"]).exists():
        raise ValueError("confirmation release/opening already exists; cannot refreeze")
    if not supervisor.strip() or not data_steward.strip():
        raise ValueError("record supervisor and data steward approval identities")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", container_digest) is None:
        raise ValueError("supply the built container image's actual sha256 digest")
    if not signing_key.is_file() or signing_key.resolve().is_relative_to(root.resolve()):
        raise ValueError("keep the release signing private key outside the repository")
    development = development_dir or contained(root, cfg["output"])
    members = cohort(root, cfg)
    mandatory = [contained(root, cfg[k]) for k in ("partitions", "split_attestation", "population", "stellar_references",
                                                  "products", "acquisition", "reference_manifest", "mode_references", "ratio_references", "covariates", "exclusions", "qa_log")]
    mandatory += [root / "configs/stage11_legacy.yaml", root / "pyproject.toml", root / "uv.lock",
                  root / "environment/stage11.Dockerfile", root / "reports/stage10/freeze_manifest.json",
                  root / "docs/protocols/STAGE11_POPULATION_PROTOCOL.md"]
    mandatory += sorted((root / "src/topoastero").glob("*.py"))
    mandatory += sorted((root / "workflows").glob("*stage11*.py"))
    for role in ("development", "internal_validation"):
        directory = development / role
        summary = read_json(directory / "summary.json")
        if summary["role"] != role or summary["holdout_used"] or summary["configuration_sha256"] != content_hash(cfg) or summary["code_sha256"] != source_fingerprint(root):
            raise ValueError("development/internal validation must match this exact release")
        expected_stars = {m["stable_star_id"] for m in members if m["role"] == role}
        if summary["stars"] != len(expected_stars) or len(summary["statuses"]) != len(expected_stars) or {s["stable_star_id"] for s in summary["statuses"]} != expected_stars:
            raise ValueError("development/internal cohort coverage incomplete")
        catalog = read_json(directory / "catalog.json")["rows"]
        expected_keys = {(s, m, q) for s in expected_stars for m in ("classical", "topology") for q in ("numax", "dnu")}
        actual_keys = {(r["stable_star_id"], r["method"], r["quantity"]) for r in catalog}
        if len(catalog) != 4 * len(expected_stars) or actual_keys != expected_keys or any(r["role"] != role for r in catalog):
            raise ValueError("development catalog has missing stars or role leakage")
        if any(s["status"] in ("missing_input", "pipeline_failure") or "incomplete_products" in s["flags"] for s in summary["statuses"]):
            raise ValueError("finish acquisition/development QA before confirmation freeze")
        manifest = read_json(directory / "run_manifest.json")
        if seal_issues(root, manifest["files"]):
            raise ValueError("development evidence is stale")
        mandatory.extend(contained(root, r["path"]) for r in manifest["files"])
        mandatory.append(directory / "run_manifest.json")
    for member in members:
        if member["exclusion"]:
            continue
        paths, expected = verified_star_products(root, cache, cfg, member["stable_star_id"])
        if len(paths) != expected or len(paths) < cfg["observation"]["minimum_months"]:
            raise ValueError(f"complete checksum-verified input acquisition required: {member['stable_star_id']}")
    payload = {"schema_version": 1, "release_id": "TA-S11-CONFIRMATION-v1", "locked_at_utc": utc_now(),
               "supervisor": supervisor.strip(), "data_steward": data_steward.strip(),
               "approval": "operator_recorded_supervisor_and_steward_approval", "holdout_opened": False,
               "container_digest": container_digest, "configuration": cfg, "configuration_sha256": content_hash(cfg),
               "development_directory": development.resolve().relative_to(root.resolve()).as_posix(),
               "code_sha256": source_fingerprint(root), "models": "none_fixed_estimators",
               "prior_scope": "G8_geometry_only_G7_delay_dropped_G9_G10_external_review_pending",
               "files": [seal(root, p) for p in sorted(set(mandatory))]}
    serialized = canonical_json(payload).encode("utf-8")
    signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(signing_key)], input=serialized,
                               capture_output=True, check=True).stdout
    public = subprocess.run(["openssl", "pkey", "-in", str(signing_key), "-pubout"], capture_output=True, check=True).stdout.decode("utf-8")
    release = {"payload": payload, "payload_sha256": content_hash(payload), "signature_algorithm": "OpenSSL-SHA256-PEM",
               "signature_hex": signature.hex(), "public_key_pem": public}
    if not _verify_signature(release):
        raise ValueError("new release signature verification failed")
    write_json(target, release, exclusive=True)
    return release


def _preflight(root: Path, cache: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    release = read_json(contained(root, cfg["release"]))
    issues = release_issues(root, cfg, release)
    if issues:
        raise ValueError("; ".join(issues))
    for member in cohort(root, cfg):
        if member["role"] == "final_holdout" and not member["exclusion"]:
            paths, expected = verified_star_products(root, cache, cfg, member["stable_star_id"])
            if len(paths) != expected:
                raise ValueError("holdout input preflight failed before opening")
    return release


def open_confirmation(root: Path, cache: Path, cfg: dict[str, Any], *, resume: bool = False) -> dict[str, Any]:
    """Reserve an opening atomically; resume only uncompleted, identical checkpoints.

    A completed run can NEVER execute again. Scientific star failures are completed
    records and cannot be selectively retried. If the process dies, --resume uses
    intact checkpoints and the original input/code/configuration snapshot.
    """
    release = _preflight(root, cache, cfg)
    state_path = contained(root, cfg["confirmation_state"])
    directory = contained(root, cfg["output"]) / "confirmation"
    if resume:
        state = read_json(state_path)
        if state["status"] != "running" or state["release_sha256"] != sha256_file(contained(root, cfg["release"])):
            raise ValueError("only an interrupted identical confirmation can resume")
    else:
        if directory.exists():
            raise ValueError("confirmation output directory already exists")
        state = {"schema_version": 1, "status": "running", "opening_count": 1, "opened_at_utc": utc_now(),
                 "release_sha256": sha256_file(contained(root, cfg["release"])),
                 "configuration_sha256": content_hash(cfg), "code_sha256": source_fingerprint(root),
                 "supervisor": release["payload"]["supervisor"], "data_steward": release["payload"]["data_steward"]}
        write_json(state_path, state, exclusive=True)
    # Exclusive process lease prevents simultaneous resume workers; a stale lease
    # from an OS crash must be removed manually with a documented QA event.
    lease = state_path.with_suffix(".lease")
    with lease.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps({"release_sha256": state["release_sha256"], "started": utc_now()}))
    try:
        append_event(root / "registries/stage11_access.jsonl", {"event": "resume" if resume else "open",
                                                               "release_sha256": state["release_sha256"], "opening_count": 1})
        summary = run_role(root, cache, cfg, "final_holdout", directory, confirmation=True)
        state.update(status="completed", completed_at_utc=utc_now(),
                     archive_manifest_sha256=sha256_file(directory / "run_manifest.json"),
                     first_valid_run_preserved=True, scientific_failures_retained=True)
        write_json(state_path, state)
        return summary
    finally:
        lease.unlink(missing_ok=True)
