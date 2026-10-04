"""Compact ridge/logistic models with preprocessing and tuning inside star folds."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize  # type: ignore[import-untyped]
from scipy.special import expit  # type: ignore[import-untyped]

from topoastero.config import content_hash

Array = NDArray[np.float64]


def grouped_folds(groups: list[str], count: int, seed: int) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
    unique = sorted(set(groups), key=lambda s: content_hash([seed, s]))
    if count < 2 or len(unique) < count:
        raise ValueError("at least two folds and enough unique stars are required")
    assignment = {g: i % count for i, g in enumerate(unique)}
    return [(np.array([i for i, g in enumerate(groups) if assignment[g] != k], dtype=np.int64),
             np.array([i for i, g in enumerate(groups) if assignment[g] == k], dtype=np.int64)) for k in range(count)]


def group_weights(groups: list[str]) -> Array:
    """Every parent star has total weight one, irrespective of segment/draw count."""
    return np.array([1.0 / groups.count(g) for g in groups], dtype=np.float64)


def _transform(x: Array, prep: dict[str, Any]) -> Array:
    if x.ndim != 2 or x.shape[1] != len(prep["median"]):
        raise ValueError("prediction features differ from fitted feature contract")
    clean = np.where(np.isfinite(x), x, np.asarray(prep["median"]))
    return np.asarray((clean - prep["mean"]) / prep["scale"], dtype=np.float64)


def fit_model(x: Array, y: Array, groups: list[str], penalty: float, *, binary: bool = False) -> dict[str, Any]:
    if x.ndim != 2 or y.shape != (len(x),) or len(groups) != len(x) or len(set(groups)) < 2 or not np.all(np.isfinite(y)) or penalty <= 0:
        raise ValueError("invalid model data or regularization")
    if binary and (not set(y).issubset({0, 1}) or len(set(y)) < 2):
        raise ValueError("binary model needs both outcome classes")
    w = group_weights(groups)
    median = np.array([np.median(v[np.isfinite(v)]) if np.any(np.isfinite(v)) else 0.0 for v in x.T])
    clean = np.where(np.isfinite(x), x, median)
    mean = np.average(clean, axis=0, weights=w)
    scale = np.sqrt(np.average((clean - mean) ** 2, axis=0, weights=w))
    scale[scale < 1e-12] = 1.0
    prep = {"median": median.tolist(), "mean": mean.tolist(), "scale": scale.tolist()}
    design = np.column_stack([np.ones(len(x)), _transform(x, prep)])
    regularizer = np.diag([0.0] + [float(penalty)] * x.shape[1])
    if binary:
        def objective(beta: Array) -> tuple[float, Array]:
            eta = design @ beta
            loss = float(np.sum(w * (np.logaddexp(0.0, eta) - y * eta)) + beta @ regularizer @ beta / 2)
            gradient = design.T @ (w * (expit(eta) - y)) + regularizer @ beta
            return loss, np.asarray(gradient, dtype=np.float64)
        result = minimize(objective, np.zeros(design.shape[1]), jac=True, method="L-BFGS-B")
        if not result.success:
            raise ValueError("logistic fit did not converge")
        beta = result.x
    else:
        beta = np.linalg.solve(design.T @ (w[:, None] * design) + regularizer, design.T @ (w * y))
    return {"kind": "logistic" if binary else "ridge", "penalty": float(penalty), "preprocessing": prep,
            "coefficients": beta.tolist(), "training_stars": sorted(set(groups)),
            "feature_min": np.min(clean, axis=0).tolist(), "feature_max": np.max(clean, axis=0).tolist()}


def predict(model: dict[str, Any], x: Array) -> Array:
    design = np.column_stack([np.ones(len(x)), _transform(x, model["preprocessing"])])
    eta = design @ np.asarray(model["coefficients"])
    return np.asarray(expit(eta) if model["kind"] == "logistic" else eta, dtype=np.float64)


def tune_model(x: Array, y: Array, groups: list[str], cfg: dict[str, Any], *, binary: bool = False) -> tuple[dict[str, Any], Array, list[dict[str, Any]]]:
    folds = grouped_folds(groups, min(cfg["inner_folds"], len(set(groups))), cfg["seed"] + 100)
    trials, candidates = [], []
    for penalty in cfg["ridge_penalties"]:
        oof = np.full(len(y), np.nan)
        for train, test in folds:
            training_groups = [groups[i] for i in train]
            if binary and len(set(y[train])) < 2:
                continue
            model = fit_model(x[train], y[train], training_groups, penalty, binary=binary)
            oof[test] = predict(model, x[test])
        valid = np.isfinite(oof)
        if not np.all(valid):
            score = math.inf
        elif binary:
            p = np.clip(oof, 1e-12, 1 - 1e-12)
            score = float(np.average(-y * np.log(p) - (1 - y) * np.log(1 - p), weights=group_weights(groups)))
        else:
            score = float(np.average((oof - y) ** 2, weights=group_weights(groups)))
        trials.append({"penalty": penalty, "inner_loss": score if math.isfinite(score) else None})
        candidates.append((score, penalty, oof))
    score, penalty, oof = min(candidates, key=lambda a: (a[0], a[1]))
    if not math.isfinite(score):
        raise ValueError("inner star folds lack support for this outcome")
    return fit_model(x, y, groups, penalty, binary=binary), oof, trials


def residual_radius(residual: Array, level: float) -> float | None:
    """Finite-rank OOF residual interval; explicitly not an exact conformal guarantee."""
    if not 0 < level < 1 or residual.ndim != 1 or not np.all(np.isfinite(residual)):
        raise ValueError("invalid residual sample or interval level")
    rank = math.ceil((len(residual) + 1) * level)
    return float(np.sort(np.abs(residual))[rank - 1]) if 0 < rank <= len(residual) else None


def star_residuals(residual: Array, groups: list[str]) -> Array:
    return np.array([np.max(np.abs(residual[[i for i, g in enumerate(groups) if g == group]])) for group in sorted(set(groups))], dtype=np.float64)


def nested_predict(x: Array, y: Array, groups: list[str], cfg: dict[str, Any], *, binary: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if len(set(groups)) < cfg["minimum_fit_stars"]:
        raise ValueError("insufficient unique development stars")
    predictions, audit = [], []
    for fold, (train, test) in enumerate(grouped_folds(groups, cfg["outer_folds"], cfg["seed"])):
        train_groups = [groups[i] for i in train]
        model, inner, trials = tune_model(x[train], y[train], train_groups, cfg, binary=binary)
        point = predict(model, x[test])
        radius = residual_radius(star_residuals(inner - y[train], train_groups), cfg["interval_level"]) if not binary else None
        calibrator = None
        if binary:
            # Calibration uses INNER OOF logits; never outer test outcomes.
            logits = np.log(np.clip(inner, 1e-9, 1 - 1e-9) / np.clip(1 - inner, 1e-9, 1))[:, None]
            calibrator = fit_model(logits, y[train], train_groups, 10.0, binary=True)
            point = predict(calibrator, np.log(np.clip(point, 1e-9, 1 - 1e-9) / np.clip(1 - point, 1e-9, 1))[:, None])
        for i, value in zip(test, point, strict=True):
            predictions.append({"index": int(i), "group": groups[i], "fold": fold, "prediction": float(value),
                                "lower": float(value - radius) if radius is not None else None,
                                "upper": float(value + radius) if radius is not None else None})
        audit.append({"fold": fold, "train_stars": sorted(set(train_groups)), "test_stars": sorted({groups[i] for i in test}),
                      "penalty": model["penalty"], "inner_trials": trials, "preprocessing": model["preprocessing"],
                      "interval_radius": radius, "calibration_training": "inner_out_of_fold" if binary else "inner_OOF_residuals",
                      "calibrator": calibrator})
    final, oof, trials = tune_model(x, y, groups, cfg, binary=binary)
    final["residual_radius"] = residual_radius(star_residuals(oof - y, groups), cfg["interval_level"]) if not binary else None
    if binary:
        logits = np.log(np.clip(oof, 1e-9, 1 - 1e-9) / np.clip(1 - oof, 1e-9, 1))[:, None]
        final["calibrator"] = fit_model(logits, y, groups, 10.0, binary=True)
    final["inner_trials"] = trials
    return sorted(predictions, key=lambda r: r["index"]), final, audit


def domain_flags(model: dict[str, Any], x: Array, threshold: float) -> list[str]:
    if x.shape != (1, len(model["preprocessing"]["median"])):
        raise ValueError("QC expects one matching feature row")
    flags = []
    if not np.all(np.isfinite(x)):
        flags.append("missing_predictor")
    if np.any(np.abs(_transform(x, model["preprocessing"])) > threshold):
        flags.append("domain_shift")
    if np.any((x[0] < np.array(model["feature_min"])) | (x[0] > np.array(model["feature_max"]))):
        flags.append("outside_training_range")
    return flags
