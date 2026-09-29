"""Proof-linked property and adversarial regressions for Stage 9."""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from topoastero.echelle_topology import EchelleField, ridge_graph
from topoastero.mathematical_relations import (
    circle_distance,
    delay_ellipse_semiaxes,
    gamma_log_tail_bound,
    gamma_log_uniform_radius,
    log_ratio_perturbation_bound,
    path_peak_prominences,
    r02_angle_discrepancy,
    ridge_drift_bound,
    scaling_log_bounds,
)
from topoastero.persistence import superlevel_h0
from topoastero.tda import bottleneck_distance


def _points(values: np.ndarray) -> np.ndarray:
    return np.asarray([(pair.death, pair.birth) for pair in superlevel_h0(values)
                       if pair.death is not None], dtype=float).reshape((-1, 2))


def test_peak_prominence_matches_independent_elder_union_find_on_random_paths() -> None:
    rng = np.random.default_rng(901)
    for _ in range(120):
        values = rng.permutation(31).astype(float) + rng.uniform(-0.01, 0.01, 31)
        reference = path_peak_prominences(values)
        actual = {pair.birth_index: pair.persistence for pair in superlevel_h0(values)}
        assert reference.keys() == actual.keys()
        for index, value in reference.items():
            assert actual[index] == pytest.approx(value) if value is not None else actual[index] is None
    assert path_peak_prominences([4., 0., 2.]) == {0: None, 2: 2.}
    assert path_peak_prominences([1.]) == {0: None}
    with pytest.raises(ValueError, match="distinct"):
        path_peak_prominences([1, 1, 0])


def test_sinusoid_singular_values_and_finite_cloud_limitation() -> None:
    amplitude, frequency = 2.3, 0.25
    for delay in (0., 0.2, 0.7, 1., 2., 3.):
        delta = 2 * math.pi * frequency * delay
        mapping = amplitude * np.array([[1., 0.], [math.cos(delta), math.sin(delta)]])
        expected = delay_ellipse_semiaxes(amplitude, frequency, delay)
        assert np.linalg.svd(mapping, compute_uv=False) == pytest.approx(expected, abs=1e-12)
    assert delay_ellipse_semiaxes(2., 0.25, 1.) == pytest.approx((2., 2.))
    with pytest.raises(ValueError):
        delay_ellipse_semiaxes(0., 1., 1.)


def test_diagram_stability_with_essential_birth_tracked_separately() -> None:
    rng = np.random.default_rng(905)
    for _ in range(48):
        signal = rng.normal(size=21)
        perturb = rng.uniform(-0.23, 0.23, size=21)
        changed = signal + perturb
        eta = float(np.max(np.abs(perturb)))
        assert bottleneck_distance(_points(signal), _points(changed)) <= eta + 1e-10
        assert abs(max(signal) - max(changed)) <= eta + 1e-10
    assert log_ratio_perturbation_bound(.2, .1) == pytest.approx(.3)


def test_stage8_specific_ridge_threshold_and_half_alias() -> None:
    for trial in (50., 100., 200.):
        bound = ridge_drift_bound(100., trial, 0., 0.)
        assert bound.mismatch_cycles == pytest.approx(0. if trial != 200 else .5)
    half = ridge_drift_bound(100., 50., 0., 0.)
    double = ridge_drift_bound(100., 200., 0., 0.)
    assert half.candidate_edges_guaranteed
    assert double.candidate_edges_excluded
    assert double.coherence_ceiling(4, 8, .17) == 0
    rng = np.random.default_rng(906)
    for _ in range(160):
        truth = 100.
        trial = float(rng.uniform(55, 155))
        curvature = float(rng.uniform(0, 5))
        epsilon = float(rng.uniform(0, .02))
        steps = rng.uniform(-curvature, curvature, 8)
        errors = rng.uniform(-epsilon, epsilon, 9)
        phase = np.cumsum(np.r_[0., truth + steps]) / trial + errors
        bound = ridge_drift_bound(truth, trial, curvature, epsilon)
        for left, right in pairwise(phase):
            distance = circle_distance(float(left), float(right))
            assert bound.lower_jump_cycles - 1e-12 <= distance <= bound.upper_jump_cycles + 1e-12


def test_conditional_graph_bound_has_actual_finite_order_witness() -> None:
    orders = np.arange(10, 14, dtype=np.int64)
    phases = (np.arange(24, dtype=float) + .5) / 24
    mask = np.ones((4, 24), dtype=bool)

    def selected(columns: list[int]) -> EchelleField:
        values = np.full((4, 24), -2.)
        for row, column in enumerate(columns):
            values[row, column] = 3.
        return EchelleField(values, mask, orders, phases,
                            100 * (orders[:, None] + phases[None, :]), 100.)

    coherent = ridge_graph(selected([1, 3, 5, 6]))
    bound = ridge_drift_bound(108, 100, 0, 1 / 48)
    tracks = [track for track in coherent.hypotheses if len(track.node_indices) == 4]
    assert bound.candidate_edges_guaranteed and tracks
    assert tracks[0].coherence <= bound.coherence_ceiling(4, 4, .17) + 1e-12
    # Frequencies 1095,1173,1251,1329 occupy trial rows 10..13; even with
    # 24-bin localization, their .22-cycle physical jumps exceed the cutoff.
    incoherent = ridge_graph(selected([22, 17, 12, 6]))
    excluded = ridge_drift_bound(78, 100, 0, 1 / 48)
    assert excluded.candidate_edges_excluded
    assert not incoherent.edges and not incoherent.hypotheses


def test_gamma_union_bound_and_monte_carlo_coverage() -> None:
    alpha, n, shape = .1, 24, 8.
    radius = gamma_log_uniform_radius(shape, n, alpha)
    assert gamma_log_tail_bound(radius, shape, n) <= alpha + 1e-13
    assert gamma_log_tail_bound(radius - 1e-5, shape, n) > alpha
    rng = np.random.default_rng(907)
    draws = rng.gamma(shape=shape, scale=1 / shape, size=(4000, n))
    failures = int(np.count_nonzero(np.max(np.abs(np.log(draws)), axis=1) > radius))
    assert failures <= 4000 * alpha + 5 * math.sqrt(4000 * alpha * (1 - alpha))
    with pytest.raises(ValueError):
        gamma_log_uniform_radius(shape, n, 1.)


def test_angular_indexing_and_stellar_systematics_are_separate() -> None:
    assert r02_angle_discrepancy(8., 100., 100.) == pytest.approx(0.)
    assert r02_angle_discrepancy(8., 100., 90.) == pytest.approx(abs(8 / 100 - 8 / 90))
    bounds = scaling_log_bounds(.02, .03, .01, dnu_systematic_log=.04, numax_systematic_log=.05)
    assert bounds.density == pytest.approx(.12)
    assert bounds.radius == pytest.approx(.205)
    assert bounds.mass == pytest.approx(.495)
    assert bounds.gravity == pytest.approx(.085)
    for name in ("density", "radius", "mass", "gravity"):
        lower, upper = bounds.relative_interval(name)
        assert math.log1p(upper) == pytest.approx(getattr(bounds, name))
        assert math.log1p(lower) == pytest.approx(-getattr(bounds, name))
    with pytest.raises(TypeError):
        scaling_log_bounds(.1, .1, .1)  # type: ignore[call-arg]
