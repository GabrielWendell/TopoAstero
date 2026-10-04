"""Grouped development inference, frozen-model application and transfer evidence."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.config import content_hash
from topoastero.hybrid.features import CLASSICAL, TOPOLOGY, fingerprint, load_dataset, matrix
from topoastero.hybrid.models import domain_flags, nested_predict, predict
from topoastero.hybrid.statistics import (
    paired_increment,
    paired_quality,
    probability_report,
    transfer_contributions,
    transfer_summary,
)
from topoastero.hybrid.transfer import (
    LEVELS,
    RUDY,
    analyze_curve,
    degrade,
    read_mission_inputs,
    white_floor,
)
from topoastero.population_store import (
    contained,
    read_json,
    read_table,
    seal,
    seal_issues,
    write_json,
    write_table,
)
from topoastero.provenance import sha256_file


def run_development(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    output = contained(root, cfg["output"])
    if contained(root, cfg["release"]).exists():
        raise ValueError("Stage 12 signed models cannot be refitted")
    rows, ledger, inputs = load_dataset(root, cfg)
    identity = content_hash({"config": cfg, "code": fingerprint(root), "inputs": inputs})
    marker = output / "development_run.json"
    if marker.exists():
        old = read_json(marker)
        if old["input_id"] != identity or seal_issues(root, old["files"]):
            raise ValueError("changed Stage 12 checkpoint; use a new configured output directory")
        return old
    predictions: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    models: dict[str, Any] = {}
    task_status: list[dict[str, Any]] = []
    if len(rows) >= cfg["minimum_fit_stars"]:
        groups = [r["stable_star_id"] for r in rows]
        by_method: dict[str, Any] = {}
        for method in ("baseline", "hybrid"):
            names = list(CLASSICAL) + (list(TOPOLOGY) if method == "hybrid" else [])
            x = matrix(rows, names)
            for quantity in ("numax", "dnu"):
                # Predict a small log correction to the conventional seismic estimate.
                y = np.array([math.log(r["targets"][quantity] / r["classical"][quantity]) for r in rows])
                oof, model, audit = nested_predict(x, y, groups, cfg)
                model.update({"features": names, "quantity": quantity, "target": "log_reference_over_classical", "training_role": "development"})
                models[method + "_" + quantity] = model
                by_method[method + "_" + quantity] = oof
                audits.extend({"method": method, "quantity": quantity, **a} for a in audit)
        for i, row in enumerate(rows):
            for quantity in ("numax", "dnu"):
                record = {"stable_star_id": row["stable_star_id"], "role": "development", "quantity": quantity,
                          "reference": row["targets"][quantity], "classical_uncorrected": row["classical"][quantity]}
                for method in ("baseline", "hybrid"):
                    p = by_method[method + "_" + quantity][i]
                    record[method] = row["classical"][quantity] * math.exp(p["prediction"])
                    for suffix in ("lower", "upper"):
                        record[method + "_" + suffix] = row["classical"][quantity] * math.exp(p[suffix]) if p[suffix] is not None else None
                    record[method + "_fold"] = p["fold"]
                predictions.append(record)
        for task in ("catastrophic_failure", "nominal_alias_unreliable"):
            labels = np.array([int(max(abs(r["classical"][q] / r["targets"][q] - 1) for q in (("dnu",) if task == "nominal_alias_unreliable" else ("numax", "dnu"))) > cfg["catastrophic_fraction"]) for r in rows], dtype=np.float64)
            supported = min(int(sum(labels == 0)), int(sum(labels == 1))) >= cfg["minimum_classifier_class"]
            for method in ("baseline", "hybrid"):
                report: dict[str, Any] = {"status": "withheld_insufficient_classes", "Brier": None, "calibration": [], "decision_curve": []}
                if supported:
                    try:
                        names = list(CLASSICAL) + (list(TOPOLOGY) if method == "hybrid" else [])
                        oof, model, audit = nested_predict(matrix(rows, names), labels, groups, cfg, binary=True)
                        report = probability_report(labels.astype(int).tolist(), [p["prediction"] for p in oof])
                        report["predictions"] = [{"stable_star_id": groups[p["index"]], "outcome": int(labels[p["index"]]), **p} for p in oof]
                        model["features"] = names
                        models[method + "_" + task] = model
                        audits.extend({"method": method, "task": task, **a} for a in audit)
                    except ValueError as exc:
                        report["status"], report["reason"] = "withheld_fold_class_support", str(exc)
                task_status.append({"task": task, "method": method, "negative_stars": int(sum(labels == 0)), "positive_stars": int(sum(labels == 1)), **report})
    task_status.append({"task": "astrophysical_detectability", "status": "withheld_positive_only_cohort", "reason": "known-positive LEGACY stars do not supply absent-signal labels"})
    model_pack = {"schema_version": 1, "configuration_sha256": content_hash(cfg), "code_sha256": fingerprint(root),
                  "input_id": identity, "models": models, "unique_training_stars": len(rows),
                  "training_stars": [r["stable_star_id"] for r in rows], "holdout_used": False,
                  "interval_scope": "inner_OOF_residual_intervals_no_exact_conformal_or_stellar_posterior_guarantee"}
    write_json(output / "models.json", model_pack)
    write_json(output / "feature_dataset.json", {"schema_version": 1, "rows": rows, "ledger": ledger, "files": inputs})
    write_table(output / "cohort_ledger.csv", ledger)
    write_table(output / "oof_predictions.csv", predictions)
    write_json(output / "fold_audit.json", {"folds": audits, "star_grouped": True, "Rudy_used_for_training": False})
    quality = paired_quality(task_status, cfg)
    family_cfg = {**cfg, "_risk_superiority_p": quality["p_superior_raw"]}
    write_json(output / "increment.json", {"rows": paired_increment(predictions, family_cfg), "quality": quality})
    write_json(output / "probability_calibration.json", {"tasks": task_status})
    files = [seal(root, output / name) for name in ("models.json", "feature_dataset.json", "cohort_ledger.csv", "oof_predictions.csv", "fold_audit.json", "increment.json", "probability_calibration.json")]
    run = {"schema_version": 1, "input_id": identity, "configuration_sha256": content_hash(cfg), "code_sha256": fingerprint(root),
           "usable_stars": len(rows), "registered_development_stars": len(ledger), "raw_holdout_opened": False,
           "files": files, "inputs": inputs, "status": "fit" if models else "insufficient_training_stars"}
    write_json(marker, run, exclusive=True)
    return run


def apply_models(analysis: dict[str, Any], pack: dict[str, Any], cfg: dict[str, Any], *, mission: str) -> list[dict[str, Any]]:
    rows = []
    for method in ("baseline", "hybrid"):
        for quantity in ("numax", "dnu"):
            model = pack["models"].get(method + "_" + quantity)
            flags = []
            if analysis["envelope_ratio"] < cfg["quality"]["minimum_envelope_ratio"]:
                flags.append("missing_or_weak_envelope")
            if analysis["maximum_alias_score"] >= cfg["quality"]["alias_score_ratio"] * max(analysis["nominal_score"], 1e-12) or analysis["nominal_winner_at_boundary"]:
                flags.append("alias_ambiguity")
            value, lower, upper, probability, alias_probability = None, None, None, None, None
            if model:
                x = matrix([{"features": analysis["features"]}], model["features"])
                flags.extend(domain_flags(model, x, cfg["quality"]["domain_standard_deviations"]))
                correction = float(predict(model, x)[0])
                if mission != "Kepler":
                    correction += pack.get("calibration_layer", {}).get("offsets", {}).get(method + "_" + quantity, 0.0)
                if abs(correction) <= math.log(2):
                    value = float(analysis["classical_" + quantity] * math.exp(correction))
                else:
                    flags.append("unreliable_parameter")
                radius = model["residual_radius"]
                if radius is not None and value is not None:
                    lower, upper = value * math.exp(-radius), value * math.exp(radius)
                risk_model = pack["models"].get(method + "_catastrophic_failure")
                if risk_model:
                    p = predict(risk_model, x)[0]
                    logit = np.array([[math.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))]])
                    probability = float(predict(risk_model["calibrator"], logit)[0])
                alias_model = pack["models"].get(method + "_nominal_alias_unreliable")
                if alias_model:
                    p = predict(alias_model, x)[0]
                    logit = np.array([[math.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))]])
                    alias_probability = float(predict(alias_model["calibrator"], logit)[0])
            else:
                flags.append("model_unavailable")
            if mission != "Kepler":
                flags.append("mission_shift")
                # A Kepler risk calibration does not automatically transfer to TESS.
                probability, alias_probability, lower, upper = None, None, None, None
            if probability is None:
                flags.append("failure_probability_uncalibrated")
            elif probability >= cfg["quality"]["probability_threshold"]:
                flags.append("unreliable_parameter")
            blocked = {"missing_or_weak_envelope", "domain_shift", "missing_predictor", "unreliable_parameter"}
            if quantity == "dnu":
                blocked.add("alias_ambiguity")
                if alias_probability is not None and alias_probability >= cfg["quality"]["probability_threshold"]:
                    flags.append("unreliable_parameter")
            accepted = value is not None and not blocked.intersection(flags)
            rows.append({"method": method, "quantity": quantity, "candidate_estimate": value,
                         "estimate": value if accepted else None, "candidate_lower": lower, "candidate_upper": upper,
                         "failure_probability": probability, "alias_unreliable_probability": alias_probability,
                         "accepted": accepted, "flags": sorted(set(flags)),
                         "detection_claim": "none_quality_screen_only"})
    return rows


def run_transfer(root: Path, cache: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    output = contained(root, cfg["output"])
    pack = read_json(output / "models.json")
    development = read_json(output / "development_run.json")
    if seal_issues(root, development["files"] + development["inputs"]) or pack["code_sha256"] != fingerprint(root) or pack["configuration_sha256"] != content_hash(cfg):
        raise ValueError("models/source/configuration changed before transfer")
    source_time, source_flux, sectors, input_files = read_mission_inputs(root, cache)
    layer_path = output / "authorized_calibration_layer.json"
    if layer_path.exists():
        pack["calibration_layer"] = read_json(layer_path)
        input_files.append(seal(root, layer_path))
    nuisance_inputs = [seal(root, root / name) for name in ("results/stage10/benchmark_capsule.json", "results/stage10/tess_sectors.csv", "data/reference/stellar_references.csv")]
    if layer_path.exists():
        nuisance_inputs.append(seal(root, layer_path))
    identity = content_hash({"code": fingerprint(root), "config": cfg, "models": seal(root, output / "models.json"), "products": input_files, "nuisance_inputs": nuisance_inputs})
    marker = output / "transfer_run.json"
    if marker.exists():
        run = read_json(marker)
        if run["input_id"] != identity or seal_issues(root, run["files"]):
            raise ValueError("changed completed transfer checkpoint")
        return run
    frozen_models_hash = sha256_file(output / "models.json")
    layer_hash = sha256_file(layer_path) if layer_path.exists() else None
    target = output / "degraded"
    target.mkdir(parents=True, exist_ok=True)
    reference = {r["quantity"]: float(r["value"]) for r in read_table(root / "data/reference/stellar_references.csv") if r["stable_star_id"] == RUDY and r["quantity"] in {"numax", "dnu"}}
    tess_white = {int(r["sector"]): float(r["white_psd"]) for r in read_table(root / "results/stage10/tess_sectors.csv")}
    # Source white floor is a frozen nuisance estimate outside Rudy's envelope.
    cfg_transfer = cfg["transfer"]
    exposure_time, exposure_flux, _ = degrade(source_time, source_flux, (sectors[0]["time"] - sectors[0]["time"][0]) * 86400,
                                             cfg_transfer, level="exposure", offset_days=0, seed=cfg["seed"], source_white=0, target_white=0)
    source_white = white_floor(exposure_time, exposure_flux)
    selected = sectors if cfg_transfer["profile"] == "full" else [r for r in sectors if r["sector"] in cfg_transfer["pilot_sectors"]]
    repetitions = cfg_transfer["full_replicates"] if cfg_transfer["profile"] == "full" else cfg_transfer["pilot_replicates"]
    cells: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    actual: list[dict[str, Any]] = []

    def process(cell: dict[str, Any], time: np.ndarray[Any, Any], flux: np.ndarray[Any, Any], cadence: float, destination: list[dict[str, Any]]) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]] | None:
        if sha256_file(output / "models.json") != frozen_models_hash or fingerprint(root) != pack["code_sha256"]:
            raise ValueError("frozen model or source changed during transfer")
        if (sha256_file(layer_path) if layer_path.exists() else None) != layer_hash:
            raise ValueError("calibration layer changed during transfer")
        if seal_issues(root, nuisance_inputs):
            raise ValueError("transfer noise/reference inputs changed during transfer")
        try:
            analysis, grid, power = analyze_curve(time, flux, root, cfg, cadence)
            results = apply_models(analysis, pack, cfg, mission="TESS" if cell["origin"] != "native" else "Kepler")
            cell.update({"analysis_status": "measured", "envelope_ratio": analysis["envelope_ratio"]})
            for result in results:
                candidate = result["candidate_estimate"]
                destination.append({**cell, **result, "reference": reference[result["quantity"]],
                                    "recoverable": bool(result["accepted"] and candidate is not None and abs(candidate / reference[result["quantity"]] - 1) <= cfg["catastrophic_fraction"])})
            return grid, power
        except (ValueError, RuntimeError, FloatingPointError) as exc:
            cell.update({"analysis_status": "pipeline_failure", "reason": str(exc)})
            for method in ("baseline", "hybrid"):
                for quantity in ("numax", "dnu"):
                    destination.append({**cell, "method": method, "quantity": quantity, "estimate": None, "candidate_estimate": None,
                                        "reference": reference[quantity], "recoverable": False, "accepted": False,
                                        "flags": ["pipeline_failure"], "failure_probability": None})
            return None

    # Masks and high-frequency noise are declared nuisance inputs, not tuned on labels.
    actual_spectra = {}
    for sector in sectors:
        cell = {"stable_star_id": RUDY, "role": "descriptive_benchmark", "sector": sector["sector"], "level": "actual_single_sector",
                "origin": "actual_TESS", "duration_days": float(sector["time"][-1] - sector["time"][0]), "cadence_seconds": sector["cadence_seconds"]}
        spectrum = process(cell, sector["time"], sector["flux"], sector["cadence_seconds"], actual)
        if spectrum is not None:
            actual_spectra[sector["sector"]] = (spectrum[0], spectrum[1], len(sector["time"]))
    # Combine PSDs incoherently by retained exposure, never phase-stitch across years.
    combinations = []
    for group in cfg_transfer["adjacent_sector_groups"]:
        if not all(s in actual_spectra for s in group):
            continue
        grid = actual_spectra[group[0]][0]
        powers = np.array([actual_spectra[s][1] for s in group])
        mean = np.average(powers, axis=0, weights=[actual_spectra[s][2] for s in group])
        from topoastero.population import estimate_points, fit_population_background
        from topoastero.population_acquisition import load_config as population_config
        config = population_config(root)
        config["classical"]["envelope_search_uHz"] = [500.0, 3500.0]
        try:
            background = fit_population_background(grid, mean, config)[0]
            estimate = estimate_points(grid, mean, background, config)
            combinations.append({"sectors": group, "classical_numax": estimate["classical_numax"], "classical_dnu": estimate["classical_dnu"],
                                 "envelope_ratio": estimate["envelope_ratio"], "status": "candidate_only_no_calibrated_detection",
                                 "estimator": "exposure_weighted_incoherent_sector_mean_PSD", "combination_preregistered": True})
        except (ValueError, RuntimeError) as exc:
            combinations.append({"sectors": group, "status": "pipeline_failure", "reason": str(exc)})
    for sector in selected:
        sector_window = (sector["time"] - sector["time"][0]) * 86400
        for offset in cfg_transfer["offsets_days"]:
            for draw in range(repetitions):
                seed = int(content_hash([cfg["seed"], RUDY, sector["sector"], offset, draw])[:8], 16)
                for level in LEVELS:
                    cell_id = f"S{sector['sector']}_O{int(offset)}_R{draw}_{level}"
                    checkpoint = target / (cell_id + ".json")
                    cell = {"cell_id": cell_id, "stable_star_id": RUDY, "role": "descriptive_benchmark", "sector": sector["sector"],
                            "offset_days": offset, "draw": draw, "level": level, "origin": "native" if level == "native" else "degradation_simulation"}
                    if checkpoint.exists():
                        old = read_json(checkpoint)
                        if old["input_id"] != identity or seal_issues(root, old["files"]):
                            raise ValueError("changed degradation checkpoint")
                        cells.append(old["cell"])
                        predictions.extend(old["predictions"])
                        continue
                    before = len(predictions)
                    files = []
                    try:
                        time, flux, metadata = degrade(source_time, source_flux, sector_window, cfg_transfer, level=level,
                                                       offset_days=offset, seed=seed, source_white=source_white, target_white=tess_white[sector["sector"]])
                        cell.update(metadata)
                        npz = target / (cell_id + ".npz")
                        np.savez_compressed(npz, time_days=time, flux_ppm=flux)
                        files.append(seal(root, npz))
                        process(cell, time, flux, metadata["cadence_seconds"], predictions)
                    except ValueError as exc:
                        cell.update({"analysis_status": "unsupported_window", "reason": str(exc)})
                        for method in ("baseline", "hybrid"):
                            for quantity in ("numax", "dnu"):
                                predictions.append({**cell, "method": method, "quantity": quantity, "estimate": None,
                                                    "candidate_estimate": None, "accepted": False, "flags": ["unsupported_window"],
                                                    "reference": reference[quantity], "recoverable": False})
                    cells.append(cell)
                    write_json(checkpoint, {"input_id": identity, "cell": cell, "predictions": predictions[before:], "files": files}, exclusive=True)
            print(f"Stage 12 window S{sector['sector']} offset {offset:g}: {repetitions * len(LEVELS)} cells archived", flush=True)
    write_table(output / "degradation_cells.csv", cells, fields=sorted({key for cell in cells for key in cell}))
    write_json(output / "transfer_predictions.json", {"rows": predictions})
    write_table(output / "transfer_curves.csv", transfer_summary(predictions))
    write_table(output / "transfer_contributions.csv", transfer_contributions(predictions, LEVELS))
    write_json(output / "actual_tess.json", {"rows": actual, "combinations": combinations, "unique_stars": 1,
                                             "model_sha256_frozen_before_actual": frozen_models_hash, "actual_sectors_used_for_training": False})
    comparisons = []
    summary = transfer_summary(predictions)
    for row in actual:
        candidates = [r for r in summary if (r["sector"], r["level"], r["method"], r["quantity"]) == (row["sector"], "window", row["method"], row["quantity"])]
        prediction = candidates[0] if candidates else None
        agreement = "withheld_pilot_draws_or_nondetection"
        if prediction and prediction["valid"] >= 32 and row["accepted"]:
            agreement = "conditional_candidate_agreement" if prediction["conditional_draw05"] <= row["estimate"] <= prediction["conditional_draw95"] else "conditional_disagreement"
        comparisons.append({"sector": row["sector"], "method": row["method"], "quantity": row["quantity"],
                            "actual_accepted": row["accepted"], "actual_estimate": row["estimate"], "simulation": prediction,
                            "agreement": agreement, "population_transfer_claim": False})
    write_json(output / "actual_vs_degraded.json", {"rows": comparisons, "scope": "conditional_Rudy_case_study"})
    all_files = [seal(root, p) for p in sorted(target.glob("*"))]
    all_files += [seal(root, output / n) for n in ("degradation_cells.csv", "transfer_predictions.json", "transfer_curves.csv", "transfer_contributions.csv", "actual_tess.json", "actual_vs_degraded.json")]
    run = {"schema_version": 1, "input_id": identity, "configuration_sha256": content_hash(cfg), "code_sha256": fingerprint(root),
           "profile": cfg_transfer["profile"], "parent_stars": 1, "cells": len(cells), "actual_sectors": len(sectors), "products": input_files,
           "files": all_files, "inputs": nuisance_inputs, "source_noise_floor_ppm2_per_uHz": source_white, "source_noise_scope": "integrated_Q5_native_high_frequency_median_log2_approximation_not_exact_noise_decomposition",
           "model_frozen_before_actual": True, "actual_test_sectors_tuned": False, "recalibration_applied": layer_path.exists()}
    write_json(marker, run, exclusive=True)
    return run
