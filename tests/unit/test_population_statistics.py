from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest

from topoastero.population import analyze_spectra, validate_spectra
from topoastero.population_acquisition import load_config
from topoastero.population_statistics import (
    build_performance,
    holm,
    operating_domain,
    paired_equivalence,
    wilson_interval,
)

ROOT = Path(__file__).parents[2]


def sample_catalog() -> list[dict]:
    rows = []
    for index in range(6):
        for method in ("classical", "topology"):
            for quantity in ("numax", "dnu"):
                reference = 2000.0 if quantity == "numax" else 100.0
                error = (index - 2) * (2.0 if quantity == "numax" else .2)
                estimate = reference + error + (1.0 if method == "topology" else 0)
                rows.append({"stable_star_id": f"KIC {1000000 + index}", "role": "internal_validation",
                             "method": method, "quantity": quantity, "reference": reference,
                             "reference_minus": .4, "reference_plus": .6,
                             "estimate": None if index == 5 else estimate,
                             "lower": reference - 2 if index < 4 else None, "upper": reference + 2 if index < 4 else None,
                             "status": "missing_input" if index == 5 else "limited", "numax_uHz": reference if quantity == "numax" else 2000,
                             "kp_mag": 8.0 if index < 3 else None, "evolutionary_state": "not_individually_classified"})
    return rows


def test_paired_metrics_and_missing_denominators() -> None:
    cfg = load_config(ROOT)
    rows = sample_catalog()
    performance, comparison = build_performance(rows, cfg, role="internal_validation")
    assert len(performance) == 4 and len(comparison) == 2
    for row in performance:
        assert row["expected_stars"] == 6 and row["paired_stars"] == 5
        assert row["failure_count"] == 1 and row["reference_center_coverage"] == 1
        assert row["failure_rate"] == pytest.approx(1/6)
        assert row["mae_lower95"] <= row["mae"] <= row["mae_upper95"]
        assert row["specificity"] is None and row["false_alarm_rate"] is None
    assert comparison[0]["p_tost_holm"] >= comparison[0]["p_tost"]
    missing = copy.deepcopy(rows)
    for row in missing:
        if row["quantity"] == "dnu":
            row["estimate"] = None
    _, tests = build_performance(missing, cfg, role="internal_validation")
    assert tests[1]["p_tost"] is None and tests[1]["p_tost_holm"] is None
    assert tests[0]["p_tost_holm"] == min(1, 2 * tests[0]["p_tost"])


def test_no_role_pooling_or_segment_pseudoreplication() -> None:
    cfg = load_config(ROOT)
    rows = sample_catalog()
    with pytest.raises(ValueError, match="role pooling"):
        build_performance(rows, cfg, role="final_holdout")
    with pytest.raises(ValueError, match="duplicate star"):
        build_performance([*rows, rows[0]], cfg, role="internal_validation")


def test_sparse_operating_domains_keep_missing_covariates() -> None:
    rows = operating_domain(sample_catalog(), load_config(ROOT))
    assert any(r["variable"] == "kp_mag" and r["bin"] == "missing" for r in rows)
    tiny = operating_domain(sample_catalog()[:4], load_config(ROOT))
    assert all(r["mean_absolute_fractional_error"] is None for r in tiny)
    assert all(r["interpretation"] == "sparse_cell_no_performance_claim" for r in tiny)


def test_equivalence_is_margin_test_not_failure_to_find_difference() -> None:
    assert paired_equivalence([0.001, 0.001, 0.001], .01, .05)["equivalent_unadjusted"]
    assert not paired_equivalence([.01, .01, .01], .01, .05)["equivalent_unadjusted"]
    assert paired_equivalence([0, 0], .01, .05)["p_tost"] is None
    with pytest.raises(ValueError):
        paired_equivalence([np.nan], .01, .05)
    assert holm([.01, .05, .04]) == pytest.approx([.03, .08, .08])
    with pytest.raises(ValueError):
        holm([2])
    assert wilson_interval(0, 0) == (None, None)
    assert wilson_interval(0, 13)[1] > 0
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_same_estimator_bootstrap_and_prominence_control() -> None:
    cfg = copy.deepcopy(load_config(ROOT))
    cfg["uncertainty"]["segment_bootstrap_replicates"] = 8
    frequency = np.arange(100, 8001, 2, dtype=float)
    background = 2 + 20 / (1 + (frequency / 700)**4)
    power = background.copy()
    for at in np.arange(1600, 2600, 100):
        power += 40 * np.exp(-((frequency - at) / 2)**2) * np.exp(-((at - 2100) / 450)**2)
    rng = np.random.default_rng(1)
    spectra = np.asarray([power * rng.gamma(10, .1, frequency.size) for _ in range(3)])
    result, mean, fitted, draws = analyze_spectra(frequency, spectra, np.ones(3), cfg, seed=101, duty_cycle=.8)
    assert np.allclose(mean, spectra.mean(axis=0)) and np.all(fitted > 0)
    assert result["reference_values_used_in_estimation"] is False
    assert result["prominence_max_absolute_difference"] < 1e-8
    assert result["classical_dnu"] == pytest.approx(100, abs=2)
    assert result["bootstrap_valid"] == 8 and result["bootstrap_failed"] == 0
    assert len(draws) == 8 and result["cylinder_inference"] == "geometry_only"
    assert all(v["lower"] is not None for v in result["intervals"].values())
    low, *_ = analyze_spectra(frequency, spectra[:2], np.ones(2), cfg, seed=101, duty_cycle=.2)
    assert "uncertainty_unavailable" in low["quality_flags"] and "low_duty_cycle" in low["quality_flags"]
    assert all(v["lower"] is None for v in low["intervals"].values())


@pytest.mark.parametrize("kind", ["nonuniform", "nonpositive", "weights", "shape"])
def test_invalid_spectral_observation_rejected(kind: str) -> None:
    f = np.arange(100, 301, 2, dtype=float)
    p, w = np.ones((3, len(f))), np.ones(3)
    if kind == "nonuniform":
        f[10] += .1
    elif kind == "nonpositive":
        p[0, 0] = 0
    elif kind == "weights":
        w[0] = np.nan
    else:
        p = p[:, :-1]
    with pytest.raises(ValueError):
        validate_spectra(f, p, w)
