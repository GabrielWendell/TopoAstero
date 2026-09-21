from __future__ import annotations

import math

import numpy as np
import pytest

from topoastero.classical import (
    HarveyComponent,
    ModeReference,
    ScalingEstimate,
    audit_mode_peaks,
    classify_tess_sector,
    echelle_grid,
    estimate_envelope,
    estimate_large_separation,
    fit_harvey_models,
    harvey_background,
    one_sided_fft_psd,
    quadrature_uncertainty,
    scaling_relations,
    scaling_uncertainty,
    spectral_window,
    strongest_window_aliases,
)


def test_fft_psd_obeys_parseval_and_recovers_sinusoid() -> None:
    cadence_seconds = 60.0
    count = 16384
    time_days = np.arange(count) * cadence_seconds / 86400.0
    frequency_uHz = 2000.0
    amplitude_ppm = 12.0
    flux = 1.0 + amplitude_ppm * 1e-6 * np.sin(
        2 * np.pi * frequency_uHz * 1e-6 * np.arange(count) * cadence_seconds
    )
    frequency, power = one_sided_fft_psd(time_days, flux)
    recovered = frequency[1:][np.argmax(power[1:])]
    spacing = frequency[1] - frequency[0]
    assert abs(recovered - frequency_uHz) <= spacing
    assert np.trapezoid(power, frequency) == pytest.approx(
        np.var((flux - np.mean(flux)) * 1e6), rel=1e-9
    )


@pytest.mark.parametrize(
    ("time", "flux", "message"),
    [
        (np.arange(3.0), np.arange(3.0), "at least four"),
        (np.arange(4.0), np.arange(5.0), "equally sized"),
        (np.array([0.0, 1.0, 1.0, 2.0]), np.ones(4), "strictly increasing"),
        (np.array([0.0, 1.0, 2.1, 3.0]), np.ones(4), "uniformly sampled"),
    ],
)
def test_fft_psd_rejects_invalid_axes(
    time: np.ndarray, flux: np.ndarray, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        one_sided_fft_psd(time, flux)


def test_harvey_background_is_positive_and_component_validation_is_strict() -> None:
    frequency = np.linspace(0, 5000, 50)
    components = (HarveyComponent(20.0, 300.0), HarveyComponent(3.0, 1500.0, 2.0))
    background = harvey_background(frequency, 1.5, components)
    assert np.all(background >= 1.5)
    assert background[0] == pytest.approx(24.5)
    assert background[-1] < background[0]
    with pytest.raises(ValueError, match="finite and positive"):
        HarveyComponent(-1.0, 100.0)
    with pytest.raises(ValueError, match="white-noise"):
        harvey_background(frequency, 0.0, ())
    with pytest.raises(ValueError, match="frequencies"):
        harvey_background(np.array([-1.0, 0.0]), 1.0, ())


def test_background_injection_prefers_two_harvey_components() -> None:
    random = np.random.default_rng(42)
    frequency = np.linspace(50.0, 6000.0, 12000)
    truth = harvey_background(
        frequency,
        1.2,
        (HarveyComponent(30.0, 180.0), HarveyComponent(6.0, 1200.0)),
    )
    power = truth * random.exponential(size=frequency.size)
    fits = fit_harvey_models(
        frequency, power, exclusion_uHz=(1800.0, 2600.0), bins=120
    )
    assert [fit.component_count for fit in fits] == [0, 1, 2]
    assert min(fits, key=lambda fit: fit.bic).component_count == 2
    assert fits[2].white_noise_ppm2_per_uHz > 0
    assert len(fits[2].parameter_sigma_log) == 5
    assert fits[2].covariance_condition > 0


def test_background_fit_rejects_invalid_requests() -> None:
    frequency = np.linspace(100.0, 500.0, 100)
    power = np.ones_like(frequency)
    with pytest.raises(ValueError, match="max_components"):
        fit_harvey_models(frequency, power, max_components=3)
    with pytest.raises(ValueError, match="positive power"):
        fit_harvey_models(frequency, np.zeros_like(power))
    with pytest.raises(ValueError, match="too few bins"):
        fit_harvey_models(frequency, power, exclusion_uHz=(0.0, 1000.0))
    with pytest.raises(ValueError, match="populated bins"):
        fit_harvey_models(frequency, power, bins=10000)


def _comb_spectrum() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequency = np.arange(1500.0, 2700.0, 0.1)
    background = 1.0 + 5e-5 * (2700.0 - frequency)
    power = background.copy()
    for mode in np.arange(1580.0, 2670.0, 103.2):
        envelope = math.exp(-0.5 * ((mode - 2150.0) / 250.0) ** 2)
        power += background * 12.0 * envelope * np.exp(-0.5 * ((frequency - mode) / 0.6) ** 2)
    return frequency, power, background


def test_envelope_and_comb_autocorrelation_recover_injection() -> None:
    frequency, power, background = _comb_spectrum()
    envelope = estimate_envelope(
        frequency, power, background, search_uHz=(1800.0, 2400.0), smoothing_uHz=20.0
    )
    assert envelope.numax_uHz == pytest.approx(2150.0, abs=55.0)
    assert envelope.peak_snr > 1.0
    assert envelope.fwhm_uHz > 20.0
    spacing = estimate_large_separation(
        frequency, power, background, envelope.numax_uHz, smoothing_uHz=0.3
    )
    assert spacing.dnu_uHz == pytest.approx(103.2, abs=0.3)
    assert spacing.autocorrelation_peak > 0.5
    assert 100 < spacing.scaling_prediction_uHz < 120


def test_envelope_and_spacing_validate_background_and_grid() -> None:
    frequency, power, background = _comb_spectrum()
    with pytest.raises(ValueError, match="background"):
        estimate_envelope(frequency, power, -background)
    irregular = frequency.copy()
    irregular[len(irregular) // 2] += 0.03
    with pytest.raises(ValueError, match="uniform grid"):
        estimate_envelope(irregular, power, background)
    with pytest.raises(ValueError, match="too few bins"):
        estimate_envelope(frequency, power, background, search_uHz=(10.0, 20.0))
    with pytest.raises(ValueError, match="window is too small"):
        estimate_large_separation(
            frequency, power, background, 2150.0, half_width_uHz=0.5
        )
    with pytest.raises(ValueError, match="background"):
        estimate_large_separation(frequency, power, np.zeros_like(background), 2150.0)


def test_spectral_window_reports_duty_resolution_and_aliases() -> None:
    cadence = 60.0
    full = np.arange(4096) * cadence / 86400.0
    times = np.delete(full, np.arange(100, 4096, 300))
    window = spectral_window(times, cadence, maximum_frequency_uHz=200.0)
    assert 0.99 < window.duty_cycle < 1.0
    assert window.power[0] == pytest.approx(1.0)
    assert window.resolution_uHz == pytest.approx(1e6 / ((times[-1] - times[0]) * 86400))
    aliases = strongest_window_aliases(window, 3)
    assert 1 <= len(aliases) <= 3
    assert all(frequency > 0 and power >= 0 for frequency, power in aliases)
    with pytest.raises(ValueError, match="positive"):
        spectral_window(times, 0.0)
    with pytest.raises(ValueError, match="at least four"):
        spectral_window(np.arange(3.0), cadence)
    with pytest.raises(ValueError, match="alias count"):
        strongest_window_aliases(window, 0)


def test_echelle_uses_circular_phase_and_standard_orientation() -> None:
    frequency = np.arange(1000.0, 1800.0, 0.05)
    dnu = 100.0
    phase = np.mod(frequency, dnu) / dnu
    power = 1.0 + 8.0 * np.exp(-0.5 * (np.minimum(phase, 1.0 - phase) / 0.02) ** 2)
    grid = echelle_grid(
        frequency,
        power,
        dnu,
        frequency_range_uHz=(1050.0, 1750.0),
        phase_bins=64,
        phase_smoothing_bins=1.5,
    )
    assert grid.power.shape == (8, 64)
    assert "bottom_to_top" in grid.orientation
    assert grid.phase_boundary == "circular_wrap"
    center = grid.power[2:-2].mean(axis=0)
    assert center[0] > center[16]
    assert center[-1] > center[16]
    with pytest.raises(ValueError, match="invalid echelle"):
        echelle_grid(frequency, power, -1.0, frequency_range_uHz=(1000.0, 1800.0))
    with pytest.raises(ValueError, match="too few bins"):
        echelle_grid(
            frequency, power, dnu, frequency_range_uHz=(1000.0, 1000.1), phase_bins=64
        )


def test_mode_audit_matches_peaks_and_reconciles_orders() -> None:
    frequency = np.arange(1400.0, 1800.0, 0.01)
    power = np.ones_like(frequency)
    references = (
        ModeReference("M1", 13, 0, 1478.93, 0.25),
        ModeReference("M2", 13, 1, 1526.43, 0.3),
    )
    for target in (1479.13, 1526.03):
        power += 10 * np.exp(-0.5 * ((frequency - target) / 0.03) ** 2)
    matches = audit_mode_peaks(frequency, power, references, 103.2, search_half_width_uHz=1.0)
    assert [match.residual_uHz for match in matches] == pytest.approx([0.2, -0.4], abs=0.01)
    assert matches[0].order_offset == 1
    assert matches[0].normalized_residual == pytest.approx(0.8, abs=0.05)
    with pytest.raises(ValueError, match="references"):
        audit_mode_peaks(frequency, power, (), 103.2)
    with pytest.raises(ValueError, match="no spectrum bins"):
        audit_mode_peaks(
            frequency,
            power,
            (ModeReference("outside", 30, 0, 5000.0, 1.0),),
            103.2,
        )


def test_scaling_relations_and_uncertainties_match_tutorial() -> None:
    estimate = scaling_relations(2145.0, 103.1121022818, 6140.0)
    expected = ScalingEstimate(1.0801044, 1.2285299, 4.2926943)
    assert estimate.mass_solar == pytest.approx(expected.mass_solar, rel=1e-6)
    assert estimate.radius_solar == pytest.approx(expected.radius_solar, rel=1e-6)
    assert estimate.logg_cgs == pytest.approx(expected.logg_cgs, rel=1e-6)
    uncertainty = scaling_uncertainty(2145.0, 103.1121, 6140.0, 90.0, 0.2, 77.0)
    assert uncertainty.mass_solar > uncertainty.radius_solar > uncertainty.logg_dex > 0
    assert quadrature_uncertainty(3.0, 4.0) == 5.0
    with pytest.raises(ValueError, match="finite and positive"):
        scaling_relations(0.0, 100.0, 6000.0)
    with pytest.raises(ValueError, match="nonnegative"):
        scaling_uncertainty(2000, 100, 6000, -1, 1, 1)
    with pytest.raises(ValueError, match="nonempty"):
        quadrature_uncertainty()


def test_tess_classification_is_conservative() -> None:
    assert (
        classify_tess_sector(1.25, 2140.0, 104.0, 0.1, reference_numax_uHz=2145, reference_dnu_uHz=103.1)
        == "marginal_candidate_not_confirmation"
    )
    assert (
        classify_tess_sector(1.3, 2500.0, 104.0, 0.1, reference_numax_uHz=2145, reference_dnu_uHz=103.1)
        == "not_detected_individually"
    )
    assert (
        classify_tess_sector(1.1, 2140.0, 104.0, 0.1, reference_numax_uHz=2145, reference_dnu_uHz=103.1)
        == "not_detected_individually"
    )
    with pytest.raises(ValueError, match="nonnegative"):
        classify_tess_sector(-1.0, 2140, 103, 0.1, reference_numax_uHz=2145, reference_dnu_uHz=103)
