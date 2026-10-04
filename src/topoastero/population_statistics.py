"""Star-paired performance, conditional calibration, equivalence and failure domains."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.stats import t  # type: ignore[import-untyped]


def wilson_interval(successes: int, total: int) -> tuple[float | None, float | None]:
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("invalid binomial counts")
    if total == 0:
        return None, None
    z = 1.959963984540054
    p = successes / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, center - half), min(1.0, center + half)


def holm(pvalues: list[float]) -> list[float]:
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in pvalues):
        raise ValueError("invalid p-values")
    order = np.argsort(pvalues, kind="stable")
    adjusted = [0.0] * len(order)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(order) - rank) * pvalues[int(index)])
        adjusted[int(index)] = min(1.0, running)
    return adjusted


def paired_equivalence(differences: list[float], margin: float, alpha: float) -> dict[str, Any]:
    """Two one-sided paired t tests on fractional absolute-loss differences.

    Normality of the star-level difference is an explicit approximation. A small
    sample yields no test; a zero-variance sample is handled without division by 0.
    A non-significant superiority test never establishes equivalence.
    """
    x = np.asarray(differences, dtype=float)
    if margin <= 0 or not 0 < alpha < 0.5 or not np.all(np.isfinite(x)):
        raise ValueError("invalid equivalence inputs")
    if x.size < 3:
        return {"status": "insufficient_stars", "n": int(x.size), "p_tost": None, "equivalent_unadjusted": None}
    mean = float(np.mean(x))
    se = float(np.std(x, ddof=1) / np.sqrt(x.size))
    if se == 0:
        p = 0.0 if -margin < mean < margin else 1.0
        lower = upper = mean
    else:
        p = max(float(t.sf((mean + margin) / se, df=x.size - 1)), float(t.cdf((mean - margin) / se, df=x.size - 1)))
        delta = float(t.ppf(1 - alpha, df=x.size - 1)) * se
        lower, upper = mean - delta, mean + delta
    return {"status": "evaluated", "n": int(x.size), "mean_loss_difference": mean,
            "margin": margin, "p_tost": p, "lower": lower, "upper": upper,
            "equivalent_unadjusted": p < alpha, "assumption": "paired_star_difference_t_approximation"}


def build_performance(catalog: list[dict[str, Any]], cfg: dict[str, Any], *, role: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use one row per star/method/quantity; retain every unsuccessful star denominator."""
    if any(r["role"] != role for r in catalog):
        raise ValueError("role pooling would leak development into confirmation estimates")
    keys = [(r["stable_star_id"], r["method"], r["quantity"]) for r in catalog]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate star-level estimate; segments are not independent stars")
    stats = cfg["statistics"]
    performance = []
    comparisons = []
    rng = np.random.default_rng(cfg["master_seed"] + 1107)
    for quantity in stats["primary_quantities"]:
        by_method = {method: {r["stable_star_id"]: r for r in catalog if r["quantity"] == quantity and r["method"] == method} for method in ("classical", "topology")}
        universe = set(by_method["classical"]) | set(by_method["topology"])
        paired = sorted(s for s in universe if all(s in by_method[m] and by_method[m][s].get("estimate") is not None and by_method[m][s].get("reference") is not None for m in by_method))
        indices = rng.integers(0, len(paired), size=(stats["star_bootstrap_replicates"], len(paired))) if len(paired) >= stats["minimum_stars_for_interval"] else None
        losses = {}
        for method in ("classical", "topology"):
            rows = list(by_method[method].values())
            valid = [r for r in rows if r.get("estimate") is not None and r.get("reference") is not None]
            pairrows = [by_method[method][s] for s in paired]
            error = np.asarray([r["estimate"] - r["reference"] for r in pairrows], dtype=float)
            fractional = np.asarray([e / r["reference"] for e, r in zip(error, pairrows, strict=True)], dtype=float)
            losses[method] = np.abs(fractional)
            covered_rows = [r for r in valid if r.get("lower") is not None and r.get("upper") is not None]
            covered = sum(r["lower"] <= r["reference"] <= r["upper"] for r in covered_rows)
            compatibility = sum(r["lower"] <= r["reference"] + r["reference_plus"] and r["upper"] >= r["reference"] - r["reference_minus"] for r in covered_rows)
            wlo, whi = wilson_interval(covered, len(covered_rows))
            failures = sum(r["estimate"] is None for r in rows)
            low, high = wilson_interval(failures, len(universe))
            metrics: dict[str, Any] = {"bias": float(np.mean(error)) if len(error) else None,
                                       "mae": float(np.mean(np.abs(error))) if len(error) else None,
                                       "rmse": float(np.sqrt(np.mean(error**2))) if len(error) else None,
                                       "median_fractional_error": float(np.median(fractional)) if len(error) else None,
                                       "mean_absolute_fractional_error": float(np.mean(np.abs(fractional))) if len(error) else None}
            for name in ("bias", "mae", "rmse", "median_fractional_error", "mean_absolute_fractional_error"):
                lo = hi = None
                if indices is not None:
                    sampled = error[indices]
                    fdraw = fractional[indices]
                    draw = {"bias": sampled.mean(axis=1), "mae": np.abs(sampled).mean(axis=1),
                            "rmse": np.sqrt((sampled**2).mean(axis=1)), "median_fractional_error": np.median(fdraw, axis=1),
                            "mean_absolute_fractional_error": np.abs(fdraw).mean(axis=1)}[name]
                    lo, hi = (float(x) for x in np.quantile(draw, [0.025, 0.975]))
                metrics[name + "_lower95"] = lo
                metrics[name + "_upper95"] = hi
            performance.append({"role": role, "quantity": quantity, "method": method, "expected_stars": len(universe),
                                "valid_stars": len(valid), "paired_stars": len(paired), "failure_count": failures,
                                "failure_rate": failures / len(universe) if universe else None,
                                "failure_lower95": low, "failure_upper95": high,
                                "limited_count": sum(r["status"] == "limited" for r in rows),
                                "not_detected_count": sum(r["status"] == "not_detected" for r in rows),
                                "interval_stars": len(covered_rows), "reference_center_coverage": covered / len(covered_rows) if covered_rows else None,
                                "coverage_lower95": wlo, "coverage_upper95": whi,
                                "reference_interval_overlap": compatibility / len(covered_rows) if covered_rows else None,
                                "false_confidence_reference_center": (len(covered_rows) - covered) / len(covered_rows) if covered_rows else None,
                                "catastrophic_count_on_paired": int(np.sum(np.abs(fractional) > stats["catastrophic_fractional_error"][quantity])),
                                "specificity": None, "false_alarm_rate": None, "probability_calibration": "not_identifiable_positive_only_cohort",
                                "coverage_semantics": "conditional_interval_reference_center_not_truth_posterior", **metrics})
        difference = losses["topology"] - losses["classical"]
        test = paired_equivalence(difference.tolist(), stats["equivalence_fractional_margin"][quantity], stats["alpha"])
        lo = hi = None
        if indices is not None:
            lo, hi = (float(x) for x in np.quantile(difference[indices].mean(axis=1), [0.025, 0.975]))
        comparisons.append({"role": role, "quantity": quantity, "comparison": "topology_minus_classical_absolute_fractional_loss",
                            "difference_lower95": lo, "difference_upper95": hi, **test})
    eligible = [r for r in comparisons if r["p_tost"] is not None]
    # Unavailable endpoints count as p=1 in the PRESPECIFIED family, never shrink it.
    adjusted = holm([float(r["p_tost"]) if r["p_tost"] is not None else 1.0 for r in comparisons])
    for row, p in zip(comparisons, adjusted, strict=True):
        row["p_tost_holm"] = p if row in eligible else None
        row["equivalent_familywise"] = p < stats["alpha"] if row in eligible else None
    return performance, comparisons


def operating_domain(catalog: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Fixed bins, explicit missingness, descriptive Wilson intervals; no tiny-cell claims."""
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in catalog:
        for variable, edges in cfg["operating_domain"].items():
            value = row.get(variable)
            index = int(np.searchsorted(edges, value, side="right")) if value is not None else -1
            label = "missing" if index < 0 else (f"bin{index}:" + (str(edges[index - 1]) if index else "-inf") + ":" + (str(edges[index]) if index < len(edges) else "inf"))
            key = (row["role"], row["method"], row["quantity"], variable, label)
            groups.setdefault(key, []).append(row)
        for variable in ("evolutionary_state", "mode_category"):
            key = (row["role"], row["method"], row["quantity"], variable, row.get(variable) or "missing")
            groups.setdefault(key, []).append(row)
    result = []
    for (role, method, quantity, variable, label), rows in sorted(groups.items()):
        valid = [r for r in rows if r.get("estimate") is not None and r.get("reference") is not None]
        failed = len(rows) - len(valid)
        lo, hi = wilson_interval(failed, len(rows))
        result.append({"role": role, "method": method, "quantity": quantity, "variable": variable, "bin": label,
                       "stars": len(rows), "valid": len(valid), "failure_count": failed,
                       "failure_rate": failed / len(rows), "failure_lower95": lo, "failure_upper95": hi,
                       "mean_absolute_fractional_error": float(np.mean([abs(r["estimate"] / r["reference"] - 1) for r in valid])) if len(valid) >= cfg["statistics"]["minimum_stars_for_interval"] else None,
                       "interpretation": "descriptive" if len(valid) >= cfg["statistics"]["minimum_stars_for_interval"] else "sparse_cell_no_performance_claim"})
    return result
