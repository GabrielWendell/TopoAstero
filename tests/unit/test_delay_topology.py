from __future__ import annotations

import math

import numpy as np
import pytest

from topoastero.delay_topology import (
    autocorrelation_curve,
    classical_coherence_features,
    delay_persistence,
    diagram_features,
    first_local_minimum,
    maximum_statistic_phase_test,
    metric_cloud,
    mutual_information_curve,
    normalized_diagram_points,
    persistence_entropy,
    physics_delay_samples,
    project_for_visualization,
    relative_fourier_amplitude_error,
    rolling_window_bounds,
    select_delay_parameters,
    sliding_delay_embedding,
)
from topoastero.simulation_lab import phase_randomized_surrogate


def _sinusoid(samples: int = 256, period: float = 16.0) -> np.ndarray:
    index = np.arange(samples, dtype=float)
    return np.sin(2.0 * np.pi * index / period)


def test_autocorrelation_and_local_minimum() -> None:
    signal = _sinusoid()
    observed = np.ones(signal.size, dtype=bool)
    observed[20:24] = False
    curve = autocorrelation_curve(signal, maximum_lag=12, observed=observed)
    assert curve[0] == pytest.approx(1.0)
    assert first_local_minimum(curve) == pytest.approx(8, abs=1)
    assert first_local_minimum(np.asarray([1.0, 0.8, 0.6, 0.4])) == 3


@pytest.mark.parametrize(
    ("values", "maximum_lag"),
    [(np.ones(16), 3), (np.arange(7, dtype=float), 2), (np.arange(16, dtype=float), 16)],
)
def test_autocorrelation_rejects_invalid_inputs(values: np.ndarray, maximum_lag: int) -> None:
    with pytest.raises(ValueError):
        autocorrelation_curve(values, maximum_lag=maximum_lag)


def test_mutual_information_and_delay_selection() -> None:
    signal = _sinusoid(384, 24.0) + 0.05 * np.cos(np.arange(384, dtype=float))
    information = mutual_information_curve(signal, maximum_lag=24, bins=10)
    assert information.shape == (25,)
    assert np.nanmin(information[1:]) >= 0.0
    selection = select_delay_parameters(
        signal,
        cadence_seconds=100.0,
        physics_frequency_uHz=1e6 / (24.0 * 100.0),
        maximum_lag=32,
    )
    assert selection.selected_method == "multiscale_consensus"
    assert {candidate.method for candidate in selection.candidates} == {
        "physics_quarter_period",
        "acf_first_minimum",
        "mutual_information_first_minimum",
        "multiscale_consensus",
    }
    assert 1 <= selection.selected_lag <= 32
    assert selection.to_record()["selected_lag"] == selection.selected_lag


def test_mutual_information_validation() -> None:
    with pytest.raises(ValueError):
        mutual_information_curve(np.ones(32), maximum_lag=4)
    with pytest.raises(ValueError):
        mutual_information_curve(np.arange(32, dtype=float), maximum_lag=4, bins=2)
    with pytest.raises(ValueError):
        select_delay_parameters(
            np.arange(64, dtype=float),
            cadence_seconds=1.0,
            physics_frequency_uHz=1.0,
            multiscale_fractions=(1.2,),
        )


def test_physics_delay_clips_aliases() -> None:
    assert physics_delay_samples(1000.0, 100.0, maximum_lag=20) == 2
    assert physics_delay_samples(5000.0, 1800.0, maximum_lag=20) == 1
    with pytest.raises(ValueError):
        physics_delay_samples(-1.0, 100.0, maximum_lag=20)
    with pytest.raises(ValueError):
        physics_delay_samples(1000.0, 0.0, maximum_lag=20)


@pytest.mark.parametrize("sampling", ["uniform", "farthest"])
def test_missing_aware_embedding_and_density_control(sampling: str) -> None:
    signal = _sinusoid(160, 20.0)
    observed = np.ones(signal.size, dtype=bool)
    observed[25:32] = False
    embedding = sliding_delay_embedding(
        signal,
        delay=5,
        dimension=3,
        observed=observed,
        maximum_points=20,
        sampling=sampling,  # type: ignore[arg-type]
    )
    assert embedding.points.shape == (20, 3)
    assert np.all(np.diff(embedding.source_indices) >= 0)
    assert embedding.rejected_windows > 0
    assert 0 < embedding.valid_fraction < 1
    assert embedding.to_record()["retained_points"] == 20


def test_embedding_normalizations_and_failures() -> None:
    signal = np.arange(64, dtype=float)
    assert sliding_delay_embedding(
        signal, delay=2, dimension=3, normalization="none", sampling="uniform"
    ).points[0, 0] == 0.0
    zscore = sliding_delay_embedding(
        signal, delay=2, dimension=3, normalization="zscore_global", sampling="uniform"
    )
    assert abs(float(np.mean(zscore.points))) < 0.1
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=0, dimension=3)
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=20, dimension=5)
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=2, dimension=3, maximum_points=3)
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=2, dimension=3, sampling="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sliding_delay_embedding(np.ones(64), delay=2, dimension=3)


def test_embedding_rejects_sparse_mask_and_bad_shape() -> None:
    signal = _sinusoid(64)
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=2, dimension=3, observed=np.ones(63, dtype=bool))
    observed = np.zeros(64, dtype=bool)
    observed[:8] = True
    with pytest.raises(ValueError):
        sliding_delay_embedding(signal, delay=4, dimension=3, observed=observed)


def test_visual_projection_is_explicit_and_finite() -> None:
    embedding = sliding_delay_embedding(
        _sinusoid(), delay=4, dimension=4, maximum_points=24
    )
    projected, explained = project_for_visualization(embedding.points)
    assert projected.shape == (24, 2)
    assert explained.shape == (2,)
    assert 0 < np.sum(explained) <= 1.0
    with pytest.raises(ValueError):
        project_for_visualization(np.ones((4, 1)))


@pytest.mark.parametrize(
    "metric", ["euclidean", "standardized_euclidean", "cosine_chord"]
)
def test_metric_clouds(metric: str) -> None:
    cloud = np.asarray([[1.0, 0.0], [0.0, 2.0], [-1.0, 0.0]])
    transformed = metric_cloud(cloud, metric)  # type: ignore[arg-type]
    assert transformed.shape == cloud.shape
    assert np.all(np.isfinite(transformed))
    if metric == "cosine_chord":
        assert np.linalg.norm(transformed[0]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        metric_cloud(cloud, "bad")  # type: ignore[arg-type]


def test_delay_persistence_detects_sinusoid_loop() -> None:
    embedding = sliding_delay_embedding(
        _sinusoid(320, 20.0),
        delay=5,
        dimension=3,
        maximum_points=18,
        sampling="farthest",
    )
    diagram = delay_persistence(embedding, maximum_dimension=1)
    features = diagram_features(diagram)
    assert features["h1_count"] >= 1
    assert features["h1_maximum_persistence"] > 0
    assert 0 <= persistence_entropy(diagram, dimension=1) <= 1
    points = normalized_diagram_points(diagram, dimension=1)
    assert points.ndim == 2 and points.shape[1] == 2


def test_limited_h2_path_and_empty_summary() -> None:
    embedding = sliding_delay_embedding(
        _sinusoid(128, 16.0), delay=4, dimension=4, maximum_points=9
    )
    diagram = delay_persistence(
        embedding,
        maximum_dimension=2,
        metric="standardized_euclidean",
    )
    features = diagram_features(diagram)
    assert features["h2_count"] >= 0
    assert persistence_entropy(diagram, dimension=2) >= 0


def test_maximum_statistic_phase_test() -> None:
    result = maximum_statistic_phase_test(
        np.asarray([2.0, 1.0]),
        np.asarray([[0.2, 0.3], [0.5, 0.4], [0.1, 0.2], [0.7, 0.6]]),
        alpha=0.25,
    )
    assert result.pvalue == pytest.approx(0.2)
    assert result.rejected
    assert result.to_record()["trials"] == 2
    with pytest.raises(ValueError):
        maximum_statistic_phase_test(np.asarray([]), np.ones((4, 1)))
    with pytest.raises(ValueError):
        maximum_statistic_phase_test(np.ones(2), np.ones((4, 3)))


def test_classical_controls_are_bounded_and_physical() -> None:
    signal = _sinusoid(256, 16.0)
    observed = np.ones(256, dtype=bool)
    observed[40:50] = False
    features = classical_coherence_features(
        signal, cadence_seconds=120.0, observed=observed
    )
    assert features["coherence_time_seconds"] > 0
    assert 0 <= features["spectral_entropy"] <= 1
    assert 0 <= features["wavelet_concentration"] <= 1
    assert 0 <= features["dominant_fourier_fraction"] <= 1
    assert 0 <= features["fourier_phase_coupling"] <= 1
    with pytest.raises(ValueError):
        classical_coherence_features(signal, cadence_seconds=0.0)


def test_psd_preservation_audit() -> None:
    signal = _sinusoid(128) + 0.1 * np.arange(128, dtype=float) / 128
    surrogate = phase_randomized_surrogate(signal, seed=9)
    assert relative_fourier_amplitude_error(signal, surrogate) < 1e-12
    assert relative_fourier_amplitude_error(signal, signal) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        relative_fourier_amplitude_error(signal, signal[:-1])


def test_rolling_window_bounds_include_endpoint() -> None:
    assert rolling_window_bounds(20, width=8, step=5) == ((0, 8), (5, 13), (10, 18), (12, 20))
    assert rolling_window_bounds(16, width=8, step=8) == ((0, 8), (8, 16))
    with pytest.raises(ValueError):
        rolling_window_bounds(10, width=11, step=1)


def test_first_minimum_validation() -> None:
    with pytest.raises(ValueError):
        first_local_minimum(np.asarray([1.0, 0.0]), start=1)
    with pytest.raises(ValueError):
        first_local_minimum(np.asarray([1.0, math.nan, math.nan]))
