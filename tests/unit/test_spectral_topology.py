from __future__ import annotations

import math

import numpy as np
import pytest

from topoastero.spectral_topology import (
    QualityFlag,
    adapt_pysyd_numax,
    assess_spectrum_quality,
    autocorrelation_spacing_scores,
    calibrate_maximum_statistic,
    comb_score_scan,
    empirical_max_pvalue,
    estimate_comb_candidates,
    estimate_numax,
    evaluate_maximum_calibration,
    independent_path_prominence,
    localized_peak_persistence,
    normalize_spectrum,
    persistence_autocorrelation_score,
    persistence_difference_score,
    persistence_weighted_location,
    prominence_matches,
    psps_spacing_scores,
    smoothed_envelope_numax,
)


def _spectrum() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequency = np.arange(9, dtype=float) * 10.0 + 100.0
    background = np.full(9, 2.0)
    ratio = np.asarray([1.0, 2.0, 1.0, 4.0, 1.0, 3.0, 1.0, 2.0, 1.0])
    return frequency, background * ratio, background


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("ratio", np.asarray([1.0, 2.0, 1.0, 4.0, 1.0, 3.0, 1.0, 2.0, 1.0])),
        ("log_ratio", np.log([1.0, 2.0, 1.0, 4.0, 1.0, 3.0, 1.0, 2.0, 1.0])),
        ("whitened_residual", np.asarray([0.0, 1.0, 0.0, 3.0, 0.0, 2.0, 0.0, 1.0, 0.0])),
    ],
)
def test_normalizations(method: str, expected: np.ndarray) -> None:
    frequency, power, background = _spectrum()
    result = normalize_spectrum(frequency, power, background, method=method)  # type: ignore[arg-type]
    assert result.values == pytest.approx(expected)
    assert result.primary is (method == "log_ratio")


def test_uncertainty_aware_normalization() -> None:
    frequency, power, background = _spectrum()
    sigma = np.ones_like(background)
    result = normalize_spectrum(
        frequency,
        power,
        background,
        method="uncertainty_zscore",
        background_sigma=sigma,
    )
    assert result.values[3] == pytest.approx(6.0 / math.sqrt(5.0))
    with pytest.raises(ValueError, match="requires"):
        normalize_spectrum(frequency, power, background, method="uncertainty_zscore")


@pytest.mark.parametrize(
    ("frequency", "power", "background"),
    [
        ([1, 2, 3, 4], [1, 1, 1, 1], [1, 1, 1, 1]),
        ([1, 2, 2, 4, 5], [1, 1, 1, 1, 1], [1, 1, 1, 1, 1]),
        ([1, 2, 3, 4, 5], [1, 0, 1, 1, 1], [1, 1, 1, 1, 1]),
    ],
)
def test_invalid_spectrum_rejected(
    frequency: list[float], power: list[float], background: list[float]
) -> None:
    with pytest.raises(ValueError):
        normalize_spectrum(frequency, power, background)


def test_exact_peak_localization_and_essential_rule() -> None:
    frequency, power, background = _spectrum()
    spectrum = normalize_spectrum(frequency, power, background, method="ratio")
    diagram, peaks = localized_peak_persistence(spectrum)
    assert len(diagram.essential(0)) == 1
    essential = next(peak for peak in peaks if peak.essential)
    assert essential.peak_index == 3
    assert essential.saddle_index is None
    assert essential.persistence is None
    finite = {peak.peak_index: peak for peak in peaks if not peak.essential}
    assert finite[5].saddle_frequency_uHz == 140.0
    assert finite[5].persistence == pytest.approx(2.0)
    assert all(peak.to_record()["dimension"] == 0 for peak in peaks)


def test_boundary_peak_is_retained_and_matches_independent_prominence() -> None:
    frequency = np.arange(7, dtype=float)
    power = np.asarray([3.0, 0.5, 1.0, 0.0, 4.0, 0.5, 2.0])
    spectrum = normalize_spectrum(frequency, power + 1.0, np.ones(7), method="whitened_residual")
    matches = prominence_matches(spectrum)
    assert matches
    assert max(match.absolute_error for match in matches) < 1e-12
    assert any(match.boundary_peak for match in matches)
    prominence, saddle = independent_path_prominence(spectrum.values, 0)
    assert prominence == pytest.approx(3.0)
    assert saddle == 3


def test_global_peak_has_no_finite_independent_prominence() -> None:
    with pytest.raises(ValueError, match="essential"):
        independent_path_prominence([0.0, 2.0, 0.0], 1)
    with pytest.raises(ValueError, match="outside"):
        independent_path_prominence([0.0, 2.0, 0.0], 4)


@pytest.mark.parametrize("method", ["centroid", "weighted_median", "huber"])
def test_numax_locations_and_intervals(method: str) -> None:
    frequency, power, background = _spectrum()
    spectrum = normalize_spectrum(frequency, power, background, method="ratio")
    _, peaks = localized_peak_persistence(spectrum)
    location = persistence_weighted_location(
        peaks,
        search_uHz=(100.0, 180.0),
        method=method,  # type: ignore[arg-type]
    )
    assert 125.0 <= location <= 165.0
    result = estimate_numax(
        spectrum,
        search_uHz=(100.0, 180.0),
        method=method,  # type: ignore[arg-type]
        bootstrap_replicates=32,
        minimum_half_width_uHz=5.0,
        seed=4,
    )
    assert result.lower_uHz <= result.numax_uHz - 5.0
    assert result.upper_uHz >= result.numax_uHz + 5.0
    assert result.finite_peak_count == 3
    assert result.to_record()["method"] == method


def test_numax_accepts_predictive_draws_and_rejects_bad_draws() -> None:
    frequency, power, background = _spectrum()
    spectrum = normalize_spectrum(frequency, power, background, method="ratio")
    draws = np.tile(spectrum.values, (10, 1))
    result = estimate_numax(
        spectrum,
        search_uHz=(100.0, 180.0),
        bootstrap_values=draws,
        bootstrap_replicates=10,
    )
    assert result.bootstrap_replicates == 10
    with pytest.raises(ValueError, match="matching"):
        estimate_numax(
            spectrum,
            search_uHz=(100.0, 180.0),
            bootstrap_values=np.ones((10, 8)),
        )


def test_topology_free_numax_control_and_pysyd_adapter() -> None:
    frequency = np.linspace(0.0, 200.0, 201)
    ratio = 1.0 + 4.0 * np.exp(-0.5 * ((frequency - 120.0) / 8.0) ** 2)
    estimate = smoothed_envelope_numax(
        frequency, ratio, search_uHz=(80.0, 160.0), smoothing_uHz=5.0
    )
    assert estimate == pytest.approx(120.0, abs=1.0)
    assert adapt_pysyd_numax({"numax": 120.0, "numax_err": 3.0}) == (120.0, 3.0)
    assert adapt_pysyd_numax({"numax_uHz": 120.0}) == (120.0, None)
    with pytest.raises(ValueError):
        adapt_pysyd_numax({"numax": -1.0})


def test_comb_scores_prefer_registered_spacing_for_simple_comb() -> None:
    frequency = np.arange(0.0, 501.0, 1.0)
    values = np.ones_like(frequency)
    for center in (100.0, 200.0, 300.0, 400.0):
        values += 8.0 * np.exp(-0.5 * ((frequency - center) / 2.0) ** 2)
    spectrum = normalize_spectrum(frequency, values, np.ones_like(values), method="log_ratio")
    _, peaks = localized_peak_persistence(spectrum)
    scan = comb_score_scan(peaks, [80.0, 100.0, 120.0], fractional_bandwidth=0.08)
    assert int(np.argmax(scan)) == 1
    estimate = estimate_comb_candidates(
        peaks, nominal_spacing_uHz=100.0, fractional_bandwidth=0.08
    )
    assert {candidate.alias for candidate in estimate.candidates} == {"half", "nominal", "double"}
    assert sorted(candidate.rank for candidate in estimate.candidates) == [1, 2, 3]
    assert estimate.winner == "nominal"
    assert all(candidate.to_record()["spacing_uHz"] > 0 for candidate in estimate.candidates)


def test_low_level_comb_scores_validate_and_are_bounded() -> None:
    frequency = np.asarray([0.0, 10.0, 20.0, 30.0])
    weights = np.asarray([1.0, 2.0, 1.0, 2.0])
    difference = persistence_difference_score(
        frequency, weights, 10.0, bandwidth_uHz=1.0, harmonics=3
    )
    correlation = persistence_autocorrelation_score(
        frequency, weights, 10.0, bandwidth_uHz=1.0
    )
    assert 0 < difference <= 1
    assert 0 < correlation <= 1
    with pytest.raises(ValueError):
        persistence_difference_score(frequency, [-1.0, 1.0, 1.0, 1.0], 10.0, bandwidth_uHz=1.0)


def test_acf_and_psps_controls_find_periodicity() -> None:
    frequency = np.arange(256, dtype=float)
    values = np.cos(2.0 * np.pi * frequency / 32.0)
    trials = np.asarray([24.0, 32.0, 40.0])
    acf = autocorrelation_spacing_scores(frequency, values, trials)
    psps = psps_spacing_scores(frequency, values, trials)
    assert int(np.argmax(acf)) == 1
    assert int(np.argmax(psps)) == 1


def test_maximum_statistic_calibration_and_plus_one_pvalue() -> None:
    calibration_values = np.asarray(
        [[0.1, 0.2], [0.3, 0.1], [0.2, 0.4], [0.1, 0.15], [0.25, 0.2]]
    )
    calibration = calibrate_maximum_statistic(calibration_values, alpha=0.2)
    assert calibration.threshold == 0.4
    assert empirical_max_pvalue([0.5, 0.1], calibration) == pytest.approx(1.0 / 6.0)
    evaluation = evaluate_maximum_calibration(
        np.asarray([[0.1, 0.2], [0.5, 0.1]]),
        calibration,
        confidence_mask=[False, True],
    )
    assert evaluation.detections == 1
    assert evaluation.false_positive_rate == 0.5
    assert evaluation.false_confidence_rate == 0.5


def test_calibration_shape_errors() -> None:
    with pytest.raises(ValueError):
        calibrate_maximum_statistic(np.asarray([1.0, 2.0]))
    calibration = calibrate_maximum_statistic(np.ones((8, 2)))
    with pytest.raises(ValueError, match="match"):
        empirical_max_pvalue([1.0], calibration)
    with pytest.raises(ValueError, match="confidence"):
        evaluate_maximum_calibration(np.ones((2, 2)), calibration, confidence_mask=[True])


def test_quality_flags_are_reason_coded() -> None:
    assessment = assess_spectrum_quality(
        envelope_pvalue=0.2,
        alias_score_ratio=1.02,
        visible_orders=3,
        window_alias_power=0.4,
        background_relative_spread=0.3,
    )
    assert assessment.status == "not_detected"
    assert set(assessment.flags) == set(QualityFlag)
    assert assessment.to_record()["reliable"] is False
    reliable = assess_spectrum_quality(
        envelope_pvalue=0.01,
        alias_score_ratio=1.5,
        visible_orders=8,
        window_alias_power=0.1,
        background_relative_spread=0.1,
    )
    assert reliable.reliable
    limited = assess_spectrum_quality(
        envelope_pvalue=0.01,
        alias_score_ratio=1.0,
        visible_orders=8,
        window_alias_power=0.1,
        background_relative_spread=0.1,
    )
    assert limited.status == "limited"
