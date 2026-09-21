from __future__ import annotations

import math

import numpy as np
import pytest

from topoastero.classical import HarveyComponent, one_sided_fft_psd
from topoastero.simulation_lab import (
    ModeSpec,
    ObservationSpec,
    asymptotic_mode_comb,
    benjamini_hochberg,
    cadence_integration_response,
    delay_embedding,
    empirical_pvalues,
    fold_frequencies,
    folded_contrast,
    generate_null,
    iaaft_surrogate,
    lifetime_from_linewidth,
    linewidth_from_lifetime,
    lorentzian_profile,
    max_statistic_threshold,
    mission_interval_mask,
    monte_carlo_repetitions,
    percentile_interval,
    persistence_prominence_pairs,
    phase_randomized_surrogate,
    ridge_mismatch_rms,
    simulate_light_curve,
    simulate_periodogram,
    sinusoid_delay_axes,
    sinusoid_ellipse_residual,
    target_oscillator_psd,
)


def test_linewidth_lifetime_and_lorentzian_conventions() -> None:
    linewidth = linewidth_from_lifetime(10.0)
    assert lifetime_from_linewidth(linewidth) == pytest.approx(10.0)
    frequency = np.array([99.0, 100.0, 101.0])
    profile = lorentzian_profile(frequency, ModeSpec(100.0, 8.0, 2.0))
    assert profile.tolist() == pytest.approx([4.0, 8.0, 4.0])
    with pytest.raises(ValueError):
        linewidth_from_lifetime(0.0)
    with pytest.raises(ValueError):
        lifetime_from_linewidth(-1.0)
    with pytest.raises(ValueError):
        ModeSpec(100.0, 1.0, 1.0, degree=1, azimuthal_order=2)
    with pytest.raises(ValueError):
        lorentzian_profile(np.array([[1.0]]), ModeSpec(100.0, 1.0, 1.0))


def test_cadence_response_and_target_psd() -> None:
    frequency = np.array([0.0, 1000.0, 2000.0])
    response = cadence_integration_response(frequency, 120.0)
    assert response[0] == pytest.approx(1.0)
    assert np.all(np.diff(response) < 0)
    modes = (ModeSpec(1000.0, 10.0, 2.0),)
    background = (HarveyComponent(4.0, 500.0),)
    clean = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=2.0,
        background=background,
    )
    diluted = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=2.0,
        background=background,
        contamination_fraction=0.5,
        integration_seconds=120.0,
    )
    assert clean[1] > diluted[1] > 2.0
    with pytest.raises(ValueError):
        cadence_integration_response(np.array([-1.0]), 1.0)
    with pytest.raises(ValueError):
        target_oscillator_psd(
            frequency,
            modes=modes,
            white_noise_ppm2_per_uHz=2.0,
            contamination_fraction=1.0,
        )


def test_asymptotic_comb_rotation_and_validation() -> None:
    modes = asymptotic_mode_comb(
        numax_uHz=2000.0,
        dnu_uHz=100.0,
        radial_orders=3,
        radial_height_ppm2_per_uHz=20.0,
        lifetime_days=10.0,
        rotational_splitting_uHz=0.5,
    )
    assert len(modes) == 27
    assert {mode.degree for mode in modes} == {0, 1, 2}
    assert all(mode.height_ppm2_per_uHz > 0 for mode in modes)
    with pytest.raises(ValueError):
        asymptotic_mode_comb(
            numax_uHz=2000.0,
            dnu_uHz=100.0,
            radial_orders=4,
            radial_height_ppm2_per_uHz=20.0,
            lifetime_days=10.0,
        )


def test_periodogram_has_expected_exponential_statistics() -> None:
    observation = ObservationSpec(2.0, 120.0)
    modes = (ModeSpec(2000.0, 20.0, 2.0),)
    ratios: list[float] = []
    for seed in range(64):
        simulation = simulate_periodogram(
            observation,
            modes=modes,
            white_noise_ppm2_per_uHz=3.0,
            seed=seed,
        )
        ratios.extend((simulation.periodogram[1:50] / simulation.target_psd[1:50]).tolist())
    assert np.mean(ratios) == pytest.approx(1.0, abs=0.05)
    assert np.var(ratios) == pytest.approx(1.0, abs=0.12)


def test_time_domain_synthesis_observation_masks_and_parseval() -> None:
    mode = (ModeSpec(800.0, 25.0, 4.0),)
    complete = simulate_light_curve(
        ObservationSpec(2.0, 120.0),
        modes=mode,
        white_noise_ppm2_per_uHz=2.0,
        seed=9,
    )
    assert np.all(complete.observed)
    frequency, power = one_sided_fft_psd(complete.time_days, complete.relative_flux)
    assert frequency.shape == power.shape
    assert np.trapezoid(power, frequency) == pytest.approx(
        np.var(complete.relative_flux) * 1e12, rel=2e-3
    )

    random_gaps = simulate_light_curve(
        ObservationSpec(1.0, 300.0, duty_cycle=0.5, gap_pattern="random"),
        modes=(),
        white_noise_ppm2_per_uHz=1.0,
        seed=4,
    )
    assert np.mean(random_gaps.observed) == pytest.approx(0.5, abs=0.01)
    intervals = np.array([[0.0, 0.2], [0.7, 0.9]])
    mission = simulate_light_curve(
        ObservationSpec(1.0, 300.0, duty_cycle=0.4, gap_pattern="mission"),
        modes=(),
        white_noise_ppm2_per_uHz=1.0,
        seed=4,
        mission_intervals_days=intervals,
    )
    assert mission.observed.tolist() == mission_interval_mask(mission.time_days, intervals).tolist()
    with pytest.raises(ValueError):
        simulate_light_curve(
            ObservationSpec(1.0, 300.0, duty_cycle=0.5, gap_pattern="mission"),
            modes=(),
            white_noise_ppm2_per_uHz=1.0,
            seed=4,
        )


def test_observation_contract_rejects_incoherent_inputs() -> None:
    with pytest.raises(ValueError):
        ObservationSpec(0.0, 120.0)
    with pytest.raises(ValueError):
        ObservationSpec(1.0, 0.0)
    with pytest.raises(ValueError):
        ObservationSpec(1.0, 120.0, duty_cycle=0.5)
    with pytest.raises(ValueError):
        ObservationSpec(1.0, 120.0, contamination_fraction=1.0)
    with pytest.raises(ValueError):
        mission_interval_mask(np.arange(3.0), np.array([[2.0, 1.0]]))


def test_sinusoid_delay_ellipse_identity_and_degeneracy() -> None:
    phase = 0.71
    theta = np.linspace(0.0, 8.0 * math.pi, 2048, endpoint=False)
    signal = 2.5 * np.cos(theta)
    lag = 41
    x, y = delay_embedding(signal, lag)
    actual_phase = theta[lag] - theta[0]
    residual = sinusoid_ellipse_residual(x, y, amplitude=2.5, phase_lag_radians=actual_phase)
    assert np.max(np.abs(residual)) < 1e-12
    major, minor = sinusoid_delay_axes(2.5, actual_phase)
    assert major >= minor > 0
    assert sinusoid_delay_axes(2.5, 0.0)[1] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        delay_embedding(signal, 0)
    with pytest.raises(ValueError):
        sinusoid_delay_axes(-1.0, phase)


def test_comb_aliases_and_ridge_mismatch_formula() -> None:
    comb = np.arange(10.0) * 100.0 + 13.0
    assert np.ptp(fold_frequencies(comb, 100.0)) < 1e-12
    assert np.ptp(fold_frequencies(comb, 50.0)) < 1e-12
    assert len(np.unique(np.round(fold_frequencies(comb, 200.0), 6))) == 2
    orders = np.arange(9.0) - 4.0
    assert ridge_mismatch_rms(9, 1.5) == pytest.approx(np.sqrt(np.mean((orders * 1.5) ** 2)))
    with pytest.raises(ValueError):
        fold_frequencies(comb, 0.0)
    with pytest.raises(ValueError):
        ridge_mismatch_rms(0, 1.0)


def test_peak_persistence_equals_prominence_under_registered_assumptions() -> None:
    signal = np.array([0.0, 1.0, 4.0, 1.0, 2.5, 1.2, 3.0, 0.5])
    persistence, prominence = persistence_prominence_pairs(signal)
    assert persistence.size == 2
    assert sorted(persistence) == pytest.approx(sorted(prominence))
    empty, empty_prominence = persistence_prominence_pairs(np.arange(5.0))
    assert empty.size == empty_prominence.size == 0


def test_surrogates_preserve_registered_invariants() -> None:
    rng = np.random.default_rng(12)
    reference = rng.normal(size=128) ** 3
    phase = phase_randomized_surrogate(reference, seed=8)
    assert np.abs(np.fft.rfft(phase - phase.mean())) == pytest.approx(
        np.abs(np.fft.rfft(reference - reference.mean())), abs=1e-10
    )
    iaaft = iaaft_surrogate(reference, seed=8, iterations=50)
    assert np.sort(iaaft) == pytest.approx(np.sort(reference))
    assert iaaft_surrogate(reference, seed=8, iterations=50) == pytest.approx(iaaft)
    with pytest.raises(ValueError):
        iaaft_surrogate(reference, seed=8, iterations=0)


@pytest.mark.parametrize(
    "kind",
    ["background_only", "randomized_comb", "white_noise", "red_noise"],
)
def test_direct_null_families_are_seeded(kind: str) -> None:
    first = generate_null(kind, samples=128, seed=15, duty_cycle=0.8)  # type: ignore[arg-type]
    second = generate_null(kind, samples=128, seed=15, duty_cycle=0.8)  # type: ignore[arg-type]
    assert first == pytest.approx(second)
    assert np.count_nonzero(first) == round(128 * 0.8)


def test_reference_and_real_window_null_families() -> None:
    reference = np.sin(np.linspace(0, 4 * math.pi, 64)) + np.linspace(0, 0.2, 64)
    for kind in ("phase_randomized", "iaaft"):
        assert generate_null(kind, samples=64, seed=2, reference=reference).shape == (64,)  # type: ignore[arg-type]
    mask = np.arange(64) % 3 != 0
    windowed = generate_null("real_window", samples=64, seed=2, mission_mask=mask)
    assert np.all(windowed[~mask] == 0)
    with pytest.raises(ValueError):
        generate_null("phase_randomized", samples=64, seed=2)
    with pytest.raises(ValueError):
        generate_null("real_window", samples=64, seed=2)
    with pytest.raises(ValueError):
        generate_null("not-a-null", samples=64, seed=2)  # type: ignore[arg-type]


def test_folded_contrast_prefers_true_comb() -> None:
    frequency = np.linspace(1000.0, 3000.0, 4001)
    power = np.ones_like(frequency)
    for center in np.arange(1100.0, 3000.0, 100.0):
        power += 10.0 * np.exp(-0.5 * ((frequency - center) / 1.5) ** 2)
    assert folded_contrast(frequency, power, trial_dnu_uHz=100.0) > folded_contrast(
        frequency, power, trial_dnu_uHz=83.0
    )


def test_multiplicity_and_precision_utilities() -> None:
    matrix = np.array([[1.0, 2.0], [2.0, 1.0], [1.5, 3.0], [0.5, 1.0]])
    threshold = max_statistic_threshold(matrix, alpha=0.25)
    assert threshold == pytest.approx(3.0)
    pvalues = empirical_pvalues(np.max(matrix, axis=1), np.array([0.0, 2.5, 4.0]))
    assert pvalues.tolist() == pytest.approx([1.0, 0.4, 0.2])
    assert benjamini_hochberg(np.array([0.001, 0.02, 0.3, 0.8]), q=0.1).tolist() == [
        True,
        True,
        False,
        False,
    ]
    assert monte_carlo_repetitions(0.05, 0.015) == 212
    assert percentile_interval(np.arange(101.0), level=0.8) == pytest.approx((10.0, 90.0))
    with pytest.raises(ValueError):
        max_statistic_threshold(np.array([1.0]), alpha=0.05)
    with pytest.raises(ValueError):
        benjamini_hochberg(np.array([1.2]), q=0.1)
    with pytest.raises(ValueError):
        monte_carlo_repetitions(0.0, 0.1)
