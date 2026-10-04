"""Paired star statistics, multiplicity, calibration, and operational utility."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import t  # type: ignore[import-untyped]


def paired_increment(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for quantity in ("numax", "dnu"):
        selected = [r for r in rows if r["quantity"] == quantity]
        if any(r["reference"] <= 0 or not np.all(np.isfinite([r["reference"], r["baseline"], r["hybrid"]])) for r in selected):
            raise ValueError("paired metrics need positive references and finite predictions")
        if len({r["stable_star_id"] for r in selected}) != len(selected):
            raise ValueError("paired population metrics require one row per star/quantity")
        difference = np.array([abs(r["baseline"] / r["reference"] - 1) - abs(r["hybrid"] / r["reference"] - 1) for r in selected])
        n = len(difference)
        margin = cfg["primary_margin"][quantity]
        mean = float(np.mean(difference)) if n else None
        interval, p_superior, p_equivalent = [None, None], 1.0, 1.0
        if n >= 3:
            assert mean is not None
            rng = np.random.default_rng(cfg["seed"])
            draws = difference[rng.integers(n, size=(cfg["bootstrap_replicates"], n))].mean(axis=1)
            interval = np.quantile(draws, [0.025, 0.975]).tolist()
            se = float(np.std(difference, ddof=1) / np.sqrt(n))
            if se > 0:
                p_superior = float(t.sf((mean - margin) / se, n - 1))
                p_equivalent = max(float(t.sf((mean + margin) / se, n - 1)), float(t.cdf((mean - margin) / se, n - 1)))
            else:
                p_superior = 0.0 if mean > margin else 1.0
                p_equivalent = 0.0 if abs(mean) < margin else 1.0
        metrics: dict[str, Any] = {}
        for method in ("baseline", "hybrid"):
            errors = np.array([r[method] / r["reference"] - 1 for r in selected])
            covered = [r for r in selected if r.get(method + "_lower") is not None]
            metrics[method] = {"fractional_bias": float(np.mean(errors)) if n else None,
                               "fractional_MAE": float(np.mean(abs(errors))) if n else None,
                               "fractional_RMSE": float(np.sqrt(np.mean(errors**2))) if n else None,
                               "catastrophic_failures": int(np.sum(abs(errors) > cfg["catastrophic_fraction"])),
                               "interval_available": len(covered),
                               "reference_center_coverage": float(np.mean([r[method + "_lower"] <= r["reference"] <= r[method + "_upper"] for r in covered])) if covered else None}
        results.append({"quantity": quantity, "paired_stars": n, "mean_fractional_loss_improvement": mean,
                        "bootstrap95_lower": interval[0], "bootstrap95_upper": interval[1], "practical_margin": margin,
                        "p_superior_raw": p_superior, "p_equivalent_raw": p_equivalent, "metrics": metrics,
                        "interval_scope": "paired_star_bootstrap_conditional_on_fitted_OOF_models",
                        "claim_power_supported": n >= cfg["minimum_claim_stars"]})
    # Superiority includes two regressions plus failure Brier (missing support -> p=1).
    # Equivalence is a separate two-regression family.
    for key in ("p_superior", "p_equivalent"):
        pvalues = [r[key + "_raw"] for r in results]
        if key == "p_superior":
            pvalues.append(cfg.get("_risk_superiority_p", 1.0))
        order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
        running = 0.0
        for rank, index in enumerate(order):
            running = min(1.0, max(running, (len(pvalues) - rank) * pvalues[index]))
            if index < 2:
                results[index][key + "_holm"] = running
    for result in results:
        result["positive_increment"] = bool(result["claim_power_supported"] and result["p_superior_holm"] < 0.05 and result["bootstrap95_lower"] > result["practical_margin"])
        result["quantified_equivalence"] = bool(result["claim_power_supported"] and result["p_equivalent_holm"] < 0.05)
    return results


def paired_quality(tasks: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    selected = [r for r in tasks if r.get("task") == "catastrophic_failure"]
    if any(len({p["stable_star_id"] for p in r.get("predictions", [])}) != len(r.get("predictions", [])) for r in selected):
        raise ValueError("quality metrics require one prediction per parent star")
    methods = {r["method"]: {p["stable_star_id"]: p for p in r.get("predictions", [])} for r in selected}
    groups = sorted(set(methods.get("baseline", {})) & set(methods.get("hybrid", {})))
    result: dict[str, Any] = {"status": "withheld", "paired_stars": len(groups), "p_superior_raw": 1.0,
                              "positive_quality_increment": False, "Brier_margin": cfg["failure_Brier_margin"]}
    if len(groups) < 3:
        return result
    y = np.array([methods["baseline"][g]["outcome"] for g in groups])
    if len(set(y)) < 2:
        result["status"] = "withheld_single_class"
        return result
    if any(methods["baseline"][g]["outcome"] != methods["hybrid"][g]["outcome"] for g in groups):
        raise ValueError("quality methods do not share paired outcomes")
    baseline = np.array([methods["baseline"][g]["prediction"] for g in groups])
    hybrid = np.array([methods["hybrid"][g]["prediction"] for g in groups])
    difference = (baseline - y)**2 - (hybrid - y)**2
    rng = np.random.default_rng(cfg["seed"])
    index = rng.integers(len(groups), size=(cfg["bootstrap_replicates"], len(groups)))
    lower, upper = np.quantile(difference[index].mean(axis=1), [.025, .975])
    threshold = cfg["quality"]["probability_threshold"]
    weight = threshold / (1 - threshold)
    benefits = (hybrid >= threshold) * (y - (1 - y) * weight) - (baseline >= threshold) * (y - (1 - y) * weight)
    nb_lower = float(np.quantile(benefits[index].mean(axis=1), .025))
    se = float(np.std(difference, ddof=1) / np.sqrt(len(groups)))
    mean = float(np.mean(difference))
    pvalue = float(t.sf((mean - cfg["failure_Brier_margin"]) / se, len(groups) - 1)) if se > 0 else (0.0 if mean > cfg["failure_Brier_margin"] else 1.0)
    result.update({"status": "paired_OOF", "Brier_improvement": mean, "bootstrap95_lower": float(lower), "bootstrap95_upper": float(upper),
                   "net_benefit_improvement": float(np.mean(benefits)), "net_benefit_bootstrap95_lower": nb_lower, "p_superior_raw": pvalue,
                   "positive_quality_increment": bool(len(groups) >= cfg["minimum_claim_stars"] and lower > cfg["failure_Brier_margin"] and nb_lower > 0 and min(1, 3 * pvalue) < .05),
                   "multiplicity": "conservative_three_primary_tests_Bonferroni_for_quality_Holm_for_regressions"})
    return result


def probability_report(outcomes: list[int], probabilities: list[float], *, thresholds: tuple[float, ...] = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9)) -> dict[str, Any]:
    y, p = np.asarray(outcomes), np.asarray(probabilities)
    if y.shape != p.shape or y.ndim != 1 or len(y) == 0 or not np.all(np.isfinite(p)) or not set(y).issubset({0, 1}) or np.any((p < 0) | (p > 1)):
        raise ValueError("binary labels and finite probabilities in [0,1] required")
    if len(set(y)) < 2:
        return {"status": "withheld_single_class", "Brier": None, "calibration": [], "decision_curve": []}
    calibration = []
    for lo, hi in zip((0, .2, .4, .6, .8), (.2, .4, .6, .8, 1), strict=True):
        mask = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        calibration.append({"lower": lo, "upper": hi, "n": int(sum(mask)),
                            "mean_predicted": float(np.mean(p[mask])) if np.any(mask) else None,
                            "observed_fraction": float(np.mean(y[mask])) if np.any(mask) else None})
    curves = []
    for threshold in thresholds:
        if not 0 < threshold < 1:
            raise ValueError("decision thresholds must be inside (0,1)")
        flagged = p >= threshold
        weight = threshold / (1 - threshold)
        net = float(np.mean(flagged & (y == 1)) - weight * np.mean(flagged & (y == 0)))
        curves.append({"threshold": threshold, "net_benefit": net,
                       "flag_all": float(np.mean(y) - weight * np.mean(1 - y)), "flag_none": 0.0,
                       "false_confidence": int(np.sum((~flagged) & (y == 1)))})
    return {"status": "out_of_sample", "n": len(y), "Brier": float(np.mean((p - y) ** 2)), "calibration": calibration, "decision_curve": curves}


def transfer_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    keys = sorted({(r["sector"], r["level"], r["method"], r["quantity"]) for r in rows})
    for sector, level, method, quantity in keys:
        subset = [r for r in rows if (r["sector"], r["level"], r["method"], r["quantity"]) == (sector, level, method, quantity)]
        valid = [r for r in subset if r.get("estimate") is not None]
        values = [r["estimate"] for r in valid]
        candidates = [r for r in subset if r.get("candidate_estimate") is not None]
        candidate_values = [r["candidate_estimate"] for r in candidates]
        results.append({"sector": sector, "level": level, "method": method, "quantity": quantity,
                        "parent_stars": len({r["stable_star_id"] for r in subset}), "cells": len(subset), "valid": len(valid),
                        "recoverable_fraction": float(np.mean([r["recoverable"] for r in subset])),
                        "median": float(np.median(values)) if values else None,
                        "conditional_draw05": float(np.quantile(values, .05)) if values else None,
                        "conditional_draw95": float(np.quantile(values, .95)) if values else None,
                        "candidate_cells": len(candidates),
                        "candidate_median": float(np.median(candidate_values)) if candidates else None,
                        "candidate_fractional_MAE": float(np.mean([abs(r["candidate_estimate"] / r["reference"] - 1) for r in candidates])) if candidates else None,
                        "scope": "same_star_offsets_and_random_draws_not_independent_stars"})
    return results


def transfer_contributions(rows: list[dict[str, Any]], levels: tuple[str, ...]) -> list[dict[str, Any]]:
    """Matched cumulative-step differences; conditional diagnostics, not causal effects."""
    lookup = {(r["stable_star_id"], r["sector"], r["offset_days"], r["draw"], r["method"], r["quantity"], r["level"]): r for r in rows}
    result = []
    for key, row in lookup.items():
        level = row["level"]
        index = levels.index(level)
        if index == 0:
            continue
        previous = lookup.get((*key[:-1], levels[index - 1]))
        candidate, prior = row.get("candidate_estimate"), previous.get("candidate_estimate") if previous else None
        change = None
        if candidate is not None and prior is not None:
            change = abs(candidate / row["reference"] - 1) - abs(prior / row["reference"] - 1)
        result.append({"stable_star_id": key[0], "sector": key[1], "offset_days": key[2], "draw": key[3],
                       "method": key[4], "quantity": key[5], "from_level": levels[index - 1], "to_level": level,
                       "candidate_fractional_loss_change": change,
                       "accepted_before": bool(previous and previous.get("accepted")), "accepted_after": bool(row.get("accepted")),
                       "scope": "matched_cumulative_operator_difference_one_star_not_isolated_causal_effect"})
    return result
