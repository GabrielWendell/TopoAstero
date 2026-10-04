"""Sign Stage 12 models BEFORE the Stage 11 holdout opening; apply them once."""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.config import canonical_json, content_hash
from topoastero.hybrid.features import fingerprint, load_dataset, matrix
from topoastero.hybrid.models import predict
from topoastero.hybrid.statistics import paired_increment, paired_quality, probability_report
from topoastero.population_acquisition import load_config as population_config
from topoastero.population_store import (
    contained,
    read_json,
    seal,
    seal_issues,
    utc_now,
    write_json,
    write_table,
)
from topoastero.provenance import sha256_file
from topoastero.stage11_validation import validate_stage11


def signature_valid(release: dict[str, Any]) -> bool:
    try:
        with tempfile.TemporaryDirectory(prefix="topoastero-s12-") as folder:
            root = Path(folder)
            (root / "public.pem").write_text(release["public_key_pem"], encoding="utf-8")
            (root / "signature.bin").write_bytes(bytes.fromhex(release["signature_hex"]))
            (root / "payload.json").write_text(canonical_json(release["payload"]), encoding="utf-8")
            return subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(root / "public.pem"), "-signature", str(root / "signature.bin"), str(root / "payload.json")], capture_output=True, check=False).returncode == 0
    except (KeyError, ValueError, OSError, TypeError):
        return False


def release_issues(root: Path, cfg: dict[str, Any]) -> list[str]:
    try:
        release = read_json(contained(root, cfg["release"]))
        payload = release["payload"]
        required = {"files", "supervisor", "data_steward", "holdout_opened", "configuration_sha256", "code_sha256"}
        if not isinstance(payload, dict) or not required.issubset(payload) or "payload_sha256" not in release:
            return ["malformed Stage 12 release"]
    except (KeyError, ValueError, OSError, TypeError):
        return ["missing or malformed Stage 12 release"]
    issues = []
    if content_hash(release["payload"]) != release["payload_sha256"] or not signature_valid(release):
        issues.append("Stage 12 release signature/hash invalid")
    if payload["configuration_sha256"] != content_hash(cfg) or payload["code_sha256"] != fingerprint(root):
        issues.append("Stage 12 code/configuration changed after signing")
    issues.extend(seal_issues(root, payload["files"]))
    if not payload["supervisor"] or not payload["data_steward"] or payload["holdout_opened"]:
        issues.append("Stage 12 release approval/scope invalid")
    return issues


def freeze(root: Path, cfg: dict[str, Any], *, signing_key: Path, supervisor: str, data_steward: str, container_digest: str) -> dict[str, Any]:
    target = contained(root, cfg["release"])
    if target.exists() or contained(root, cfg["confirmation_state"]).exists() or (root / "registries/stage11_confirmation.json").exists():
        raise ValueError("freeze Stage 12 BEFORE Stage 11 holdout opening; cannot refreeze")
    if not supervisor.strip() or not data_steward.strip() or re.fullmatch(r"sha256:[0-9a-f]{64}", container_digest) is None:
        raise ValueError("actual supervisor/steward approval identities and container digest required")
    if not signing_key.is_file() or signing_key.resolve().is_relative_to(root.resolve()):
        raise ValueError("private signing key must be outside repository")
    output = contained(root, cfg["output"])
    run = read_json(output / "development_run.json")
    if run["usable_stars"] < cfg["minimum_claim_stars"] or seal_issues(root, run["files"] + run["inputs"]) or run["code_sha256"] != fingerprint(root) or run["configuration_sha256"] != content_hash(cfg):
        raise ValueError("complete adequately supported current development evidence before freeze")
    files = [contained(root, r["path"]) for r in run["files"] + run["inputs"]]
    files += list((root / "src/topoastero/hybrid").glob("*.py")) + list((root / "src/topoastero").glob("*.py"))
    files += list((root / "workflows").glob("*stage12*.py"))
    files += [root / "configs/stage12_hybrid.yaml", root / "pyproject.toml", root / "uv.lock", root / "environment/stage12.Dockerfile",
              root / "registries/population_partitions.csv", root / "registries/split_attestation.json", root / "registries/stage12_tasks.csv",
              root / "registries/stage12_features.csv", root / "docs/protocols/STAGE12_HYBRID_PROTOCOL.md"]
    layer_path = output / "authorized_calibration_layer.json"
    if layer_path.exists():
        files.append(layer_path)
    payload = {"schema_version": 1, "locked_at_utc": utc_now(), "holdout_opened": False,
               "supervisor": supervisor.strip(), "data_steward": data_steward.strip(), "container_digest": container_digest,
               "configuration_sha256": content_hash(cfg), "code_sha256": fingerprint(root), "files": [seal(root, p) for p in sorted(set(files))]}
    signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(signing_key)], input=canonical_json(payload).encode(), capture_output=True, check=True).stdout
    public = subprocess.run(["openssl", "pkey", "-in", str(signing_key), "-pubout"], capture_output=True, check=True).stdout.decode()
    release = {"payload": payload, "payload_sha256": content_hash(payload), "signature_hex": signature.hex(), "public_key_pem": public}
    if not signature_valid(release):
        raise ValueError("release signature verification failed")
    write_json(target, release, exclusive=True)
    return release


def evaluate_confirmation(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    issues = release_issues(root, cfg)
    if issues:
        raise ValueError("; ".join(issues))
    population = population_config(root)
    state11 = read_json(contained(root, population["confirmation_state"]))
    if state11["status"] != "completed" or state11["opening_count"] != 1 or not state11["first_valid_run_preserved"]:
        raise ValueError("Stage 11 exact first confirmation archive required")
    if validate_stage11(root, require_prior_stages=False, require_confirmation=True):
        raise ValueError("Stage 11 confirmation archive failed validation")
    state_path = contained(root, cfg["confirmation_state"])
    if state_path.exists():
        raise ValueError("Stage 12 confirmation archive already reserved; never rerun")
    output = contained(root, cfg["output"])
    # Reserve before observing any predictions; failed attempts stay auditable.
    state = {"schema_version": 1, "status": "running", "opening_count": 1, "reserved_at_utc": utc_now(),
             "release_sha256": sha256_file(contained(root, cfg["release"])), "source_archive_sha256": state11["archive_manifest_sha256"]}
    write_json(state_path, state, exclusive=True)
    rows, ledger, files = load_dataset(root, cfg, role="final_holdout", permit_confirmation=True)
    models = read_json(output / "models.json")["models"]
    predictions = []
    quality_tasks = []
    for row in rows:
        for quantity in ("numax", "dnu"):
            record = {"stable_star_id": row["stable_star_id"], "quantity": quantity, "role": "final_holdout", "reference": row["targets"][quantity]}
            for method in ("baseline", "hybrid"):
                model = models[method + "_" + quantity]
                correction = float(predict(model, matrix([row], model["features"]))[0])
                record[method] = float(row["classical"][quantity] * math.exp(correction))
                radius = model["residual_radius"]
                record[method + "_lower"] = record[method] * math.exp(-radius) if radius is not None else None
                record[method + "_upper"] = record[method] * math.exp(radius) if radius is not None else None
            predictions.append(record)
    labels = [int(max(abs(r["classical"][q] / r["targets"][q] - 1) for q in ("numax", "dnu")) > cfg["catastrophic_fraction"]) for r in rows]
    for method in ("baseline", "hybrid"):
        risk = models.get(method + "_catastrophic_failure")
        if risk is None:
            continue
        raw = predict(risk, matrix(rows, risk["features"]))
        logits = np.log(np.clip(raw, 1e-9, 1 - 1e-9) / np.clip(1 - raw, 1e-9, 1))[:, None]
        probabilities = predict(risk["calibrator"], logits).tolist()
        report = probability_report(labels, probabilities)
        report.update({"task": "catastrophic_failure", "method": method, "predictions": [{"stable_star_id": r["stable_star_id"], "outcome": label, "prediction": p} for r, label, p in zip(rows, labels, probabilities, strict=True)]})
        quality_tasks.append(report)
    write_table(output / "confirmation_predictions.csv", predictions)
    confirmation_cfg = {**cfg, "minimum_claim_stars": 10}
    quality = paired_quality(quality_tasks, confirmation_cfg)
    confirmation_cfg["_risk_superiority_p"] = quality["p_superior_raw"]
    write_json(output / "confirmation_increment.json", {"rows": paired_increment(predictions, confirmation_cfg), "quality": quality, "quality_tasks": quality_tasks, "ledger": ledger,
                                                        "scope": "13_star_confirmation_after_at_least_20_development_stars"})
    manifest = {"schema_version": 1, "files": files + [seal(root, output / n) for n in ("confirmation_predictions.csv", "confirmation_increment.json")]}
    write_json(output / "confirmation_archive.json", manifest, exclusive=True)
    state.update({"status": "completed", "first_valid_run_preserved": True, "archive_sha256": sha256_file(output / "confirmation_archive.json")})
    write_json(state_path, state)
    return state
