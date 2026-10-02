"""Physical-unit, sampling, multiplicity and uncertainty regression tests for S10."""

from __future__ import annotations

import numpy as np
import pytest

from topoastero.classical import one_sided_fft_psd
from topoastero.rudy_benchmark import (
    added_noise_sigma,
    gaussian_psd_realization,
    holm_adjust,
    integrate_cadences,
    linear_interpolation_response,
    monte_carlo_tail,
    rebin_spectrum,
    spectrum_diagnostics,
    weighted_segment_bootstrap,
)


def test_rebin_means_and_no_extrapolation() -> None:
    frequency = np.arange(1.0, 20.1, 0.1)
    centers = np.arange(2.0, 19.0, 1.0)
    power = 1 + frequency
    result = rebin_spectrum(frequency, power, centers)
    expected = np.histogram(frequency, bins=np.r_[centers - 0.5, centers[-1] + 0.5], weights=power)[0] / np.histogram(frequency, bins=np.r_[centers - 0.5, centers[-1] + 0.5])[0]
    np.testing.assert_allclose(result, expected)
    fine = np.arange(2.0, 3.0, 0.02)
    np.testing.assert_allclose(rebin_spectrum(frequency, power, fine), 1 + fine, atol=0.04)
    with pytest.raises(ValueError, match="extrapolate"):
        rebin_spectrum(frequency, power, np.arange(0.0, 5.0))
    with pytest.raises(ValueError, match="uniform"):
        rebin_spectrum(frequency, power, np.array([2.0, 4.0, 9.0]))
    with pytest.raises(ValueError, match="positive"):
        rebin_spectrum(frequency, -power, centers)
    with pytest.raises(ValueError, match="increasing"):
        rebin_spectrum(frequency[::-1], power, centers)
    with pytest.raises(ValueError, match="finite vector"):
        rebin_spectrum(np.array([1.0, np.nan, 3.0]), np.ones(3), np.arange(3.0))


def test_boxcar_integration_and_gap_rejection() -> None:
    time = np.arange(0.0, 1000.1, 1.0)
    centers = np.arange(30.0, 970.0, 30.0)
    integrated, valid = integrate_cadences(time, 3 * time + 5, centers, exposure_seconds=20, maximum_gap_seconds=3)
    assert np.all(valid)
    np.testing.assert_allclose(integrated, 3 * centers + 5)
    frequency = 0.007
    integrated, valid = integrate_cadences(time, np.cos(2 * np.pi * frequency * time), centers, exposure_seconds=20, maximum_gap_seconds=3)
    np.testing.assert_allclose(integrated, np.cos(2 * np.pi * frequency * centers) * np.sinc(frequency * 20), atol=0.0002)
    kept = (time < 400) | (time > 500)
    integrated, valid = integrate_cadences(time[kept], time[kept], np.array([10.0, 450.0, 600.0, 999.0]), exposure_seconds=20, maximum_gap_seconds=3)
    assert valid.tolist() == [True, False, True, False]
    assert np.isnan(integrated[1]) and np.isnan(integrated[3])


@pytest.mark.parametrize("time,flux,centers,exposure,gap", [
    (np.array([0., 0., 3.]), np.ones(3), np.arange(3.), 1., 2.),
    (np.arange(4.), np.ones(3), np.arange(3.), 1., 2.),
    (np.arange(4.), np.ones(4), np.array([1., 1., 2.]), 1., 2.),
    (np.arange(4.), np.ones(4), np.arange(3.), 0., 2.),
    (np.arange(4.), np.ones(4), np.arange(3.), 1., np.nan),
])
def test_boxcar_invalid_inputs(time: np.ndarray, flux: np.ndarray, centers: np.ndarray, exposure: float, gap: float) -> None:
    with pytest.raises(ValueError):
        integrate_cadences(time, flux, centers, exposure_seconds=exposure, maximum_gap_seconds=gap)


@pytest.mark.parametrize("count", [4095, 4096])
def test_gaussian_density_units_parseval_and_endpoints(count: int) -> None:
    cadence = 60.0
    density = np.full(count // 2 + 1, 2.0)
    flux = gaussian_psd_realization(density, sample_count=count, cadence_seconds=cadence, seed=721)
    frequency, measured = one_sided_fft_psd(np.arange(count) * cadence / 86400, flux / 1e6)
    df = frequency[1] - frequency[0]
    np.testing.assert_allclose(np.sum(measured) * df, np.var(flux), rtol=1e-10)
    assert np.isclose(np.mean(measured[1:-1]), 2, rtol=0.07)
    np.testing.assert_array_equal(flux, gaussian_psd_realization(density, sample_count=count, cadence_seconds=cadence, seed=721))
    assert abs(float(np.mean(flux))) < 1e-12
    with pytest.raises(ValueError, match="match"):
        gaussian_psd_realization(-density, sample_count=count, cadence_seconds=cadence, seed=0)
    with pytest.raises(ValueError, match="cadence"):
        gaussian_psd_realization(density, sample_count=count, cadence_seconds=0, seed=0)


def test_bootstrap_matches_weighted_estimator_not_full_span() -> None:
    matrix = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
    draws = weighted_segment_bootstrap(matrix, [1, 2, 3], replicates=32, seed=12)
    np.testing.assert_array_equal(draws, weighted_segment_bootstrap(matrix, [1, 2, 3], replicates=32, seed=12))
    assert draws.shape == (32, 3)
    assert np.all((draws >= matrix.min(axis=0)) & (draws <= matrix.max(axis=0)))
    # Preserve each frequency's unit offset under resampling and exposure weighting.
    np.testing.assert_allclose(np.diff(draws, axis=1), 1.0)
    for bad, counts, repetitions in ((matrix, [1, 2], 32), (-matrix, [1, 2, 3], 32), (matrix, [0, 2, 3], 32), (matrix, [1, 2, 3], 2)):
        with pytest.raises(ValueError):
            weighted_segment_bootstrap(bad, counts, replicates=repetitions, seed=0)


def test_conditional_tails_ties_precision_and_holm() -> None:
    null = np.arange(64, dtype=float)
    extreme = monte_carlo_tail(65, null)
    assert extreme.pvalue == 1 / 65
    assert extreme.exceedances == 0
    assert extreme.wilson95_upper > 0.05  # 64 draws cannot justify a tiny false-alarm rate.
    assert monte_carlo_tail(62, null).pvalue == 3 / 65
    assert monte_carlo_tail(-1, null).pvalue == 1
    np.testing.assert_allclose(holm_adjust([0.01, 0.03, 0.9]), [0.03, 0.06, 0.9])
    assert np.min(holm_adjust([1 / 65] * 7)) > 0.05
    with pytest.raises(ValueError):
        holm_adjust([0.01, 0.2, 1.2])
    with pytest.raises(ValueError):
        monte_carlo_tail(float("inf"), null)


def test_noise_matching_and_no_subtraction() -> None:
    sigma = added_noise_sigma(5.0, 1.0, 120.0, 0.8)
    assert np.isclose(2 * sigma**2 * 120 / (1e6 * 0.8) + 1, 5)
    assert added_noise_sigma(1, 5, 120, 0.8) == 0
    for values in ((-1, 1, 120, 1), (1, 1, 0, 1), (1, 1, 120, 1.1), (1, 1, 120, np.nan)):
        with pytest.raises(ValueError):
            added_noise_sigma(*values)


def test_interpolation_attenuation_is_corrected_before_null_tests() -> None:
    cadence = 60.0
    frequency = np.array([0.0, 1000.0, 3000.0])
    coordinates = np.r_[0.0, np.arange(1, 1000) + 0.25]
    time = coordinates * cadence / 86400
    expected = 1 - 2 * np.mean((coordinates % 1) * (1 - coordinates % 1)) * (1 - np.cos(2 * np.pi * frequency * 1e-6 * cadence))
    np.testing.assert_allclose(linear_interpolation_response(frequency, time, cadence), expected)
    np.testing.assert_allclose(linear_interpolation_response(frequency, np.arange(1000) * cadence / 86400, cadence), 1, atol=1e-12)
    assert expected[-1] < 1
    for axis, times, step in ((-frequency, time, cadence), (frequency, time[::-1], cadence), (frequency, time, 0.0)):
        with pytest.raises(ValueError):
            linear_interpolation_response(axis, times, step)


def test_diagnostics_and_registered_normalizations() -> None:
    frequency = np.linspace(1500, 2800, 1301)
    background = np.ones_like(frequency)
    power = np.ones_like(frequency)
    for center in np.arange(1680, 2700, 103):
        power += 8 * np.exp(-0.5 * ((frequency - center) / 2)**2) * np.exp(-0.5 * ((center - 2200) / 220)**2)
    for normalization in ("log_ratio", "ratio", "whitened_residual", "uncertainty_zscore"):
        result = spectrum_diagnostics(frequency, power, background, normalization=normalization)
        assert 1700 < result["persistence_numax_uHz"] < 2500
        assert abs(result["classical_dnu_uHz"] - 103) < 1
        assert result["finite_peak_count"] > 5
        assert result["peak_max_lifetime"] > 0
    for x, y, bg, smoothing in ((frequency, -power, background, 1), (frequency, power, background[:-1], 1), (frequency, power, background, 0), (frequency**1.01, power, background, 1)):
        with pytest.raises(ValueError):
            spectrum_diagnostics(x, y, bg, peak_smoothing_uHz=smoothing)
