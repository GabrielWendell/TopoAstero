"""Locked, label-free feature extraction and archival Stage 11 reconciliation."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.config import content_hash, load_yaml
from topoastero.population_acquisition import load_config as stage11_config
from topoastero.population_pipeline import cohort
from topoastero.population_store import contained, read_json, seal, seal_issues, star_slug
from topoastero.provenance import sha256_file

CLASSICAL = ("log_numax", "log_dnu", "log_envelope", "duty_cycle", "log_duration", "log_resolution", "prominence_delta", "graph_score")
TOPOLOGY = ("comb_score", "alias_excess", "cylinder_score")


def load_config(root: Path) -> dict[str, Any]:
    cfg = load_yaml(root / "configs/stage12_hybrid.yaml")
    if cfg["schema_version"] != 1 or cfg["training_role"] != "development" or tuple(cfg["classical_features"]) != CLASSICAL or tuple(cfg["topology_features"]) != TOPOLOGY:
        raise ValueError("Stage 12 feature/task contract differs from locked registry")
    if min(cfg["outer_folds"], cfg["inner_folds"]) < 2 or min(cfg["ridge_penalties"]) <= 0 or not 0 < cfg["interval_level"] < 1:
        raise ValueError("invalid grouped validation configuration")
    if cfg["minimum_fit_stars"] < 6 or cfg["minimum_claim_stars"] < 20 or cfg["bootstrap_replicates"] < 100:
        raise ValueError("insufficient fit/claim/uncertainty support")
    if cfg["transfer"]["profile"] not in {"pilot", "full"} or cfg["transfer"]["recalibration_enabled"]:
        raise ValueError("recalibration is separately authorized; valid transfer profile required")
    transfer = cfg["transfer"]
    if transfer["source_quarter"] != 5 or not 0 < transfer["additional_duty"] <= 1 or transfer["contaminating_to_target_flux"] < 0:
        raise ValueError("locked Q5 source and physical duty/contamination required")
    if min(transfer["pilot_replicates"], transfer["full_replicates"], transfer["short_duration_days"], transfer["maximum_source_gap_seconds"]) <= 0 or transfer["cadence_seconds"] < transfer["exposure_seconds"] or transfer["exposure_seconds"] <= 0:
        raise ValueError("invalid physical exposure or transfer support")
    lo, hi, step = transfer["frequency_grid_uHz"]
    if not 0 < lo < hi < 1e6 / (2 * transfer["cadence_seconds"]) or step <= 0:
        raise ValueError("invalid transfer frequency grid")
    if not 0 < cfg["quality"]["probability_threshold"] < 1 or cfg["failure_Brier_margin"] <= 0:
        raise ValueError("invalid quality utility contract")
    return cfg


def fingerprint(root: Path) -> str:
    files = sorted((root / "src/topoastero/hybrid").glob("*.py")) + sorted((root / "src/topoastero").glob("*.py")) + sorted((root / "workflows").glob("*stage12*.py"))
    return content_hash([seal(root, p) for p in files])


def feature_row(analysis: dict[str, Any]) -> dict[str, float | None]:
    """Never read published values; include exact prominence and graph controls."""
    result: dict[str, float | None] = dict.fromkeys(CLASSICAL + TOPOLOGY)
    required = ("classical_numax", "classical_dnu", "envelope_ratio", "duration_days", "native_window_resolution_uHz")
    if any(not isinstance(analysis.get(k), (float, int)) or not math.isfinite(analysis[k]) or analysis[k] <= 0 for k in (*required, "topology_numax")):
        return result
    numax, dnu = analysis["classical_numax"], analysis["classical_dnu"]
    if analysis.get("prominence_max_absolute_difference", 0.0) > 1e-8:
        raise ValueError("unmatched path persistence/prominence control")
    result.update({"log_numax": math.log(numax), "log_dnu": math.log(dnu), "log_envelope": math.log(analysis["envelope_ratio"]),
                   "duty_cycle": analysis.get("duty_cycle"), "log_duration": math.log(analysis["duration_days"]),
                   "log_resolution": math.log(analysis["native_window_resolution_uHz"]),
                   "prominence_delta": math.log(analysis["topology_numax"] / numax),
                   "comb_score": analysis.get("nominal_score"),
                   "alias_excess": math.log(max(analysis.get("maximum_alias_score", 0), 1e-12) / max(analysis.get("nominal_score", 0), 1e-12))})
    nominal = [r for r in analysis.get("echelle_scan", []) if r["alias_family"] == "nominal"]
    if nominal:
        score = min(nominal, key=lambda r: abs(r["spacing_uHz"] - dnu))
        result["graph_score"], result["cylinder_score"] = score["graph_only"], score["topology"]
    return result


def matrix(rows: list[dict[str, Any]], names: list[str] | tuple[str, ...]) -> np.ndarray[Any, np.dtype[np.float64]]:
    return np.asarray([[r["features"].get(n) if r["features"].get(n) is not None else np.nan for n in names] for r in rows], dtype=np.float64)


def load_dataset(root: Path, cfg: dict[str, Any], *, role: str = "development", permit_confirmation: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if role not in {"development", "internal_validation", "final_holdout"} or (role == "final_holdout" and not permit_confirmation):
        raise ValueError("protected or unsupported Stage 12 dataset role")
    if role == "final_holdout":
        state_path, release_path = contained(root, cfg["confirmation_state"]), contained(root, cfg["release"])
        if not state_path.exists() or not release_path.exists():
            raise ValueError("confirmation needs a reserved signed Stage 12 attempt")
        state = read_json(state_path)
        if state["status"] != "running" or state["opening_count"] != 1 or state["release_sha256"] != sha256_file(release_path):
            raise ValueError("confirmation reservation does not match the signed release")
    evidence_path = contained(root, cfg["stage11_evidence"])
    evidence = read_json(evidence_path)
    name = "confirmation" if role == "final_holdout" else role
    directory = contained(root, evidence["role_directories"][name])
    manifest = read_json(directory / "run_manifest.json")
    issues = seal_issues(root, manifest["files"])
    if issues:
        raise ValueError("stale Stage 11 input: " + "; ".join(issues))
    previous = stage11_config(root)
    members = [m for m in cohort(root, previous) if m["role"] == role]
    rows, ledger = [], []
    files = [seal(root, evidence_path), seal(root, directory / "run_manifest.json")]
    files += [seal(root, contained(root, previous[key])) for key in ("partitions", "split_attestation", "stellar_references", "covariates", "exclusions", "reference_manifest")]
    for member in members:
        path = directory / "stars" / star_slug(member["stable_star_id"]) / "analysis.json"
        analysis = read_json(path)
        if analysis["stable_star_id"] != member["stable_star_id"] or analysis["role"] != role or analysis["reference_values_used_in_estimation"]:
            raise ValueError("identifier/role/reference leakage in feature input")
        features = feature_row(analysis)
        available = all(features[n] is not None for n in ("log_numax", "log_dnu", "log_envelope"))
        ledger.append({"stable_star_id": member["stable_star_id"], "role": role, "included": available,
                       "upstream_status": analysis["status"], "reason": analysis.get("reason", ";".join(analysis.get("quality_flags", []))),
                       "source": path.relative_to(root).as_posix()})
        files.append(seal(root, path))
        if available:
            rows.append({"stable_star_id": member["stable_star_id"], "role": role, "features": features,
                         "targets": {q: member[q + "_uHz"] for q in ("numax", "dnu")},
                         "classical": {q: analysis["classical_" + q] for q in ("numax", "dnu")},
                         "flags": analysis.get("quality_flags", [])})
    return rows, ledger, files
