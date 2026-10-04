"""Inference tests stress star leakage, train-only preprocessing and class support."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from topoastero.hybrid.models import (
    domain_flags,
    fit_model,
    group_weights,
    grouped_folds,
    nested_predict,
    predict,
    residual_radius,
    star_residuals,
    tune_model,
)


def test_grouped_folds_keep_all_draws_of_star_together() -> None:
    groups = [f"S{i}" for i in range(12) for _ in range(3)]
    first = grouped_folds(groups, 3, 42)
    seen = []
    for train, test in first:
        assert not {groups[i] for i in train} & {groups[i] for i in test}
        seen.extend(test.tolist())
    assert sorted(seen) == list(range(36))
    assert all(np.array_equal(a[1], b[1]) for a, b in zip(first, grouped_folds(groups, 3, 42), strict=True))
    assert sum(group_weights(groups)[np.array(groups) == "S0"]) == pytest.approx(1)
    with pytest.raises(ValueError):
        grouped_folds(["same"]*12, 2, 0)


def test_ridge_preprocessing_is_training_only_and_star_weighted() -> None:
    x = np.array([[0., np.nan], [2., 4.], [4., 4.], [4., 4.]])
    model = fit_model(x, np.array([0., 2., 4., 4.]), ["A", "B", "C", "C"], 1)
    assert model["preprocessing"]["mean"][0] == pytest.approx(2)
    prep = copy.deepcopy(model["preprocessing"])
    values = predict(model, np.array([[1e9, np.nan]]))
    assert np.isfinite(values).all() and model["preprocessing"] == prep
    assert set(domain_flags(model, np.array([[1e9, np.nan]]), 4)) == {"domain_shift", "outside_training_range", "missing_predictor"}
    assert domain_flags(model, np.array([[2., 4.]]), 4) == []
    with pytest.raises(ValueError):
        domain_flags(model, np.zeros((2, 2)), 4)
    with pytest.raises(ValueError):
        predict(model, np.zeros((1, 3)))
    for y, penalty in [(np.array([0., 2.]), 1), (np.array([0., np.nan, 4., 4.]), 1), (np.ones(4), 0)]:
        with pytest.raises(ValueError):
            fit_model(x, y, ["A", "B", "C", "C"], penalty)
    empty = fit_model(np.full((3, 1), np.nan), np.ones(3), ["A", "B", "C"], 1)
    assert empty["preprocessing"]["median"] == [0.0]


def test_nested_predictions_do_not_see_outer_outcomes(hybrid_repository: tuple) -> None:
    _, cfg, _, _ = hybrid_repository
    groups = [f"S{i}" for i in range(30)]
    x = np.arange(60.).reshape(30, 2)
    y = np.sin(x[:, 0]/20)
    predictions, model, audit = nested_predict(x, y, groups, cfg)
    changed_y = y.copy()
    held = set(audit[0]["test_stars"])
    indices = [i for i, g in enumerate(groups) if g in held]
    changed_y[indices] = 1000
    altered, _, altered_audit = nested_predict(x, changed_y, groups, cfg)
    assert [predictions[i]["prediction"] for i in indices] == [altered[i]["prediction"] for i in indices]
    assert audit[0]["preprocessing"] == altered_audit[0]["preprocessing"]
    assert len(model["training_stars"]) == 30 and all(p["lower"] is not None for p in predictions)
    for fold in audit:
        assert not set(fold["train_stars"]) & set(fold["test_stars"])
    with pytest.raises(ValueError):
        nested_predict(x[:3], y[:3], groups[:3], cfg)


def test_binary_calibration_is_inner_oof_and_rejects_missing_classes(hybrid_repository: tuple) -> None:
    _, cfg, _, _ = hybrid_repository
    groups = [f"S{i}" for i in range(30)]
    x = np.linspace(-2, 2, 30)[:, None]
    y = np.array([i % 2 for i in range(30)], dtype=float)
    rows, model, audit = nested_predict(x, y, groups, cfg, binary=True)
    assert all(0 < p["prediction"] < 1 and p["lower"] is None for p in rows)
    assert model["kind"] == "logistic" and "calibrator" in model
    assert all(a["calibration_training"] == "inner_out_of_fold" for a in audit)
    with pytest.raises(ValueError, match="both outcome"):
        fit_model(x, np.zeros(30), groups, 1, binary=True)
    with pytest.raises(ValueError, match="support"):
        tune_model(x, np.zeros(30), groups, cfg, binary=True)


def test_logistic_nonconvergence_is_an_explicit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import topoastero.hybrid.models as module
    monkeypatch.setattr(module, "minimize", lambda *a, **k: SimpleNamespace(success=False))
    with pytest.raises(ValueError, match="converge"):
        fit_model(np.ones((4, 1)), np.array([0., 1., 0., 1.]), ["A", "B", "C", "D"], 1, binary=True)


def test_residual_interval_rank_counts_stars_not_segments() -> None:
    assert residual_radius(np.ones(6), .9) is None
    assert residual_radius(np.arange(10.), .9) == 9
    assert np.array_equal(star_residuals(np.array([1., 3., 2., 4.]), ["A", "A", "B", "B"]), [3., 4.])
    assert residual_radius(star_residuals(np.arange(30.), ["A"]*15+["B"]*15), .9) is None
    for sample, level in [(np.array([np.nan]), .9), (np.ones((2, 2)), .9), (np.ones(4), 1.)]:
        with pytest.raises(ValueError):
            residual_radius(sample, level)
