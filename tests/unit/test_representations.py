from __future__ import annotations

import numpy as np
import pytest

from topoastero.representations import (
    cylindrical_echelle_field,
    cylindrical_echelle_filtration,
    delay_coordinates,
    delay_embedding_filtration,
    light_curve_filtration,
    mode_frequency_cloud_filtration,
    psd_superlevel_filtration,
    robust_standardize,
)


def test_robust_standardization_is_shift_and_scale_invariant() -> None:
    values = np.asarray([-1.0, 0.0, 1.0, 4.0])
    assert robust_standardize(values * 7.0 + 3.0) == pytest.approx(robust_standardize(values))
    assert np.all(robust_standardize(np.ones(5)) == 0.0)


def test_constant_light_curve_has_no_peak_controls() -> None:
    result = light_curve_filtration(np.arange(6.0), np.ones(6))
    assert result.controls == {
        "peak_count": 0.0,
        "maximum_prominence": 0.0,
        "total_prominence": 0.0,
    }


def test_light_curve_and_psd_representations_localize_births() -> None:
    time = np.arange(9, dtype=float) / 48.0
    flux = np.asarray([0.0, 2.0, 0.0, 1.0, 0.0, 3.0, 0.0, 0.5, 0.0])
    light_curve = light_curve_filtration(time, flux)
    assert light_curve.representation_id == "light_curve_filtration"
    assert light_curve.summaries["finite_count"] == 3
    assert light_curve.controls["peak_count"] == 4.0
    assert "time_days" in light_curve.diagram.finite(0)[0].birth_location[0]

    frequency = np.linspace(900.0, 1100.0, 65)
    background = np.full(65, 2.0)
    power = background * (1.0 + 8.0 * np.exp(-0.5 * ((frequency - 1000.0) / 15.0) ** 2))
    spectrum = psd_superlevel_filtration(frequency, power, background=background)
    assert spectrum.controls["envelope_centroid_uHz"] == pytest.approx(1000.0, abs=2.0)
    assert "frequency_uHz" in spectrum.diagram.essential(0)[0].birth_location[0]


def test_delay_embedding_extracts_loop_and_controls() -> None:
    phase = np.linspace(0.0, 6.0 * np.pi, 180, endpoint=False)
    signal = np.sin(phase)
    coordinates, source = delay_coordinates(signal, lag=15, dimension=3)
    assert coordinates.shape == (150, 3)
    assert source[-1] == 149
    result = delay_embedding_filtration(signal, lag=15, dimension=2, landmark_count=20)
    assert result.summaries["h1_maximum_persistence"] is not None
    assert float(result.summaries["h1_maximum_persistence"] or 0.0) > 0.0
    assert -1.0 <= result.controls["lag_autocorrelation"] <= 1.0


def test_mode_cloud_has_nearest_neighbor_control_and_mode_localization() -> None:
    order = np.repeat(np.arange(5), 3)
    degree = np.tile(np.arange(3), 5)
    frequency = 1000.0 + 100.0 * order + np.asarray([0.0, 50.0, -12.0])[degree]
    result = mode_frequency_cloud_filtration(frequency, degree, dnu_uHz=100.0)
    assert result.controls["nearest_neighbor_mean"] > 0.0
    assert any("degree" in pair.birth_location[0] for pair in result.diagram.pairs)


def test_cylindrical_echelle_wraps_phase_and_exposes_pixels() -> None:
    frequency = np.linspace(0.1, 799.9, 2048)
    phase = np.mod(frequency, 100.0) / 100.0
    circular_distance = np.minimum(abs(phase - 0.98), 1.0 - abs(phase - 0.98))
    power = 1.0 + 12.0 * np.exp(-0.5 * (circular_distance / 0.035) ** 2)
    field, orders, phases = cylindrical_echelle_field(
        frequency, power, trial_dnu_uHz=100.0, order_bins=8, phase_bins=16
    )
    assert field.shape == (8, 16)
    assert orders.size == 8 and phases.size == 16
    periodic = cylindrical_echelle_filtration(
        frequency,
        power,
        trial_dnu_uHz=100.0,
        order_bins=8,
        phase_bins=16,
        max_dimension=0,
    )
    assert periodic.controls["ridge_circular_resultant"] > 0.9
    assert "phase" in periodic.diagram.pairs[0].birth_location[0]


@pytest.mark.parametrize(
    "call",
    [
        lambda: robust_standardize(np.asarray([])),
        lambda: delay_coordinates(np.arange(5.0), lag=4, dimension=3),
        lambda: delay_embedding_filtration(np.ones(20), lag=2),
        lambda: delay_embedding_filtration(np.arange(6.0), lag=1, landmark_count=3),
        lambda: mode_frequency_cloud_filtration(np.arange(3.0), np.arange(3), dnu_uHz=1.0),
        lambda: mode_frequency_cloud_filtration(np.arange(4.0), np.arange(4), dnu_uHz=0.0),
        lambda: cylindrical_echelle_field(np.arange(5.0), np.ones(5), trial_dnu_uHz=1.0),
        lambda: cylindrical_echelle_field(np.arange(16.0), np.ones(16), trial_dnu_uHz=-1.0),
        lambda: psd_superlevel_filtration(np.arange(4.0), np.asarray([1.0, 0.0, 1.0, 1.0])),
        lambda: psd_superlevel_filtration(
            np.arange(4.0), np.ones(4), background=np.ones(3)
        ),
        lambda: psd_superlevel_filtration(np.arange(4.0), np.ones(4), smoothing_bins=-1.0),
        lambda: light_curve_filtration(np.asarray([0.0, 2.0, 1.0]), np.ones(3)),
    ],
)
def test_invalid_representation_inputs_are_rejected(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]
