"""Exact cylindrical boundary and frozen-score regressions for Stage 8."""

from __future__ import annotations

import numpy as np
import pytest

from topoastero.echelle_topology import (
    EchelleField,
    circular_center,
    circular_distance,
    circular_interval,
    cubical_superlevel_persistence,
    fast_superlevel_h0,
    five_point_frequency_ratios,
    make_echelle_field,
    maximum_statistic_pvalue,
    percentile_interval,
    ridge_angle_ratios,
    ridge_graph,
    score_echelle,
    trial_spacing_grid,
)


def _field(values: np.ndarray, valid: np.ndarray | None = None) -> EchelleField:
    rows, columns = values.shape
    mask = np.ones_like(values, dtype=bool) if valid is None else valid
    return EchelleField(
        np.where(mask, values, np.nan), mask,
        np.arange(10, 10 + rows, dtype=np.int64),
        (np.arange(columns, dtype=float) + 0.5) / columns,
        100.0 * (np.arange(10, 10 + rows)[:, None]
                 + (np.arange(columns)[None, :] + 0.5) / columns),
        100.0,
    )


def test_complete_cylinder_has_one_essential_loop_not_rectangle() -> None:
    field = _field(np.ones((3, 6)))
    cylindrical = cubical_superlevel_persistence(field)
    rectangular = cubical_superlevel_persistence(field, periodic=False)
    assert len(cylindrical.essential(0)) == 1
    assert len(cylindrical.essential(1)) == 1
    assert len(rectangular.essential(0)) == 1
    assert len(rectangular.essential(1)) == 0
    assert cylindrical.essential(1)[0].death is None


def test_seam_vertices_connect_at_high_threshold() -> None:
    field = _field(np.array([[3., 0., 0., 0., 0., 2.],
                             [3., 0., 0., 0., 0., 2.]]))
    cylinder = fast_superlevel_h0(field)
    rectangle = fast_superlevel_h0(field, periodic=False)
    assert not any(pair.birth == 2 and pair.death == 0 for pair in cylinder.finite(0))
    assert any(pair.birth == 2 and pair.death == 0 for pair in rectangle.finite(0))


@pytest.mark.parametrize("periodic", [False, True])
def test_fast_h0_matches_full_cubical_filtration(periodic: bool) -> None:
    values = np.random.default_rng(341).normal(size=(3, 7))
    mask = np.ones_like(values, dtype=bool)
    mask[1, 3] = False
    field = _field(values, mask)
    full = cubical_superlevel_persistence(field, periodic=periodic)
    fast = fast_superlevel_h0(field, periodic=periodic)
    assert sorted(round(pair.persistence or 0, 12) for pair in full.finite(0)) == sorted(
        round(pair.persistence or 0, 12) for pair in fast.finite(0)
    )
    assert len(full.essential(0)) == len(fast.essential(0))


def test_incomplete_order_omits_incident_cells_and_breaks_loop() -> None:
    mask = np.ones((3, 6), dtype=bool)
    mask[:, 0] = False
    field = _field(np.ones((3, 6)), mask)
    diagram = cubical_superlevel_persistence(field)
    assert len(diagram.essential(1)) == 0
    assert all(0 not in pair.birth_vertices for pair in diagram.pairs)


def test_field_is_inside_spectrum_and_masks_partial_orders() -> None:
    frequency = np.linspace(1040, 1460, 85)
    power = 2 + 0.1 * np.sin(frequency)
    field = make_echelle_field(frequency, power, np.full(85, 2.), spacing_uHz=100.)
    assert field.orders.tolist() == [10, 11, 12, 13, 14]
    assert field.complete_orders == 3
    assert not field.valid[0].any() and not field.valid[-1].any()
    assert np.all(np.isnan(field.values[~field.valid]))
    with pytest.raises(ValueError):
        make_echelle_field(frequency[::-1], power, np.ones(85), spacing_uHz=100.)


def test_graph_continues_through_seam_and_keeps_competing_tracks() -> None:
    values = np.full((5, 8), -2.)
    for row in range(5):
        values[row, 7 if row % 2 else 0] = 3.
        values[row, 4] = 2.
    graph = ridge_graph(_field(values))
    assert len(graph.hypotheses) >= 2
    assert any(edge.phase_distance == pytest.approx(0.125) for edge in graph.edges)
    assert any(len(track.node_indices) == 5 for track in graph.hypotheses)
    assert circular_distance(0.98, 0.02) == pytest.approx(0.04)
    assert circular_center(np.array([0.98, 0.02])) == pytest.approx(0.)
    with pytest.raises(ValueError):
        circular_center(np.array([0., 0.5]))


def test_frozen_score_and_orderwise_control() -> None:
    values = np.random.default_rng(700).normal(size=(5, 8))
    score, graph, diagram = score_echelle(_field(values), full_diagram=True)
    assert score.combined == pytest.approx(0.55 * score.topology + 0.45 * score.graph_only)
    assert score.finite_h0_count == len(diagram.finite(0))
    assert score.finite_h1_count == len(diagram.finite(1))
    assert score.orderwise >= 0 and score.valid_orders == 5
    assert graph.hypotheses


def test_grid_maximum_null_and_intervals() -> None:
    trials = trial_spacing_grid(100.)
    assert len(trials) == 15
    assert {alias for alias, _ in trials} == {"half", "nominal", "double"}
    assert trials[2] == ("half", 50.)
    assert maximum_statistic_pvalue(2., np.array([0., 1., 2., 3.])) == pytest.approx(3 / 5)
    assert percentile_interval(np.array([1., 2., 3., 4.]))[0] < 2
    low, high, wrapped = circular_interval(np.array([0.96, 0.98, 0.01, 0.03]))
    assert wrapped and low > high
    with pytest.raises(ValueError):
        maximum_statistic_pvalue(1., np.array([1., 2.]))


def test_ratios_need_degree_identification_and_neighboring_modes() -> None:
    assert all(value is None for value in ridge_angle_ratios({0: 0.2, 2: 0.1}).values())
    anchored = ridge_angle_ratios({0: 0.98, 2: 0.02}, anchor_phase=0.98)
    assert anchored["r02_proxy"] == pytest.approx(0.96)
    assert ridge_angle_ratios({0: 0.2, 2: 0.2}, anchor_phase=0.2)["r02_proxy"] is None
    modes = {(n, degree): 100 * (n + 0.5 * degree) for n in range(3) for degree in (0, 1, 2)}
    ratios = five_point_frequency_ratios(modes)
    assert ratios[0]["r02"] is None
    assert ratios[1]["r02"] == pytest.approx(0.)
    assert ratios[1]["r01"] == pytest.approx(0.)
    assert ratios[1]["r10"] == pytest.approx(0.)


@pytest.mark.parametrize("bad_spacing", [0., -1., float("nan")])
def test_invalid_trial_spacings_are_rejected(bad_spacing: float) -> None:
    with pytest.raises(ValueError):
        trial_spacing_grid(bad_spacing)


def test_reject_invalid_cylindrical_fields_and_graph_policy() -> None:
    empty = _field(np.ones((2, 6)), np.zeros((2, 6), dtype=bool))
    with pytest.raises(ValueError):
        fast_superlevel_h0(empty)
    with pytest.raises(ValueError):
        cubical_superlevel_persistence(_field(np.ones((1, 6))))
    with pytest.raises(ValueError):
        ridge_graph(_field(np.ones((2, 6))), jump_limit=0.)


def test_reject_invalid_statistical_inputs() -> None:
    with pytest.raises(ValueError):
        percentile_interval(np.array([1., 2., 3.]))
    with pytest.raises(ValueError):
        circular_interval(np.array([0., 1., 2., 3.]), level=1.)
    with pytest.raises(ValueError):
        circular_distance(0., float("inf"))
    with pytest.raises(ValueError):
        circular_center(np.array([0., 0.2]), weights=np.array([-1., 2.]))
