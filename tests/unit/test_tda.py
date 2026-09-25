from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.sparse.csgraph import minimum_spanning_tree

from topoastero.tda import (
    bottleneck_distance,
    diagram_points,
    diagram_summary,
    empirical_pvalue,
    exact_path_persistence,
    farthest_point_landmarks,
    grid_persistence,
    localized_records,
    pairwise_distances,
    vietoris_rips_persistence,
    wasserstein_distance,
)


def test_exact_path_preserves_physical_localization() -> None:
    metadata = [{"time_days": float(index) / 2} for index in range(5)]
    diagram = exact_path_persistence(
        [0.0, 2.0, 0.0, 1.0, 0.0], vertex_metadata=metadata
    )
    finite = diagram.finite(0)
    assert len(finite) == 1
    assert finite[0].persistence == pytest.approx(1.0)
    assert finite[0].birth_location[0]["time_days"] == 1.5
    assert finite[0].death_location is not None
    records = localized_records(diagram, representation_id="LC")
    assert records[0]["pair_id"] == "LC-D0-0001"
    assert any(record["essential"] for record in records)


def test_path_sublevel_and_compact_summary() -> None:
    diagram = exact_path_persistence([0.0, 2.0, 0.0], direction="sublevel")
    finite = diagram.finite(0)
    assert [pair.persistence for pair in finite] == pytest.approx([2.0])
    summary = diagram_summary(diagram, dimension=0)
    assert summary == {
        "finite_count": 1,
        "total_persistence": 2.0,
        "maximum_persistence": 2.0,
        "persistence_centroid": 1.0,
    }
    assert diagram_summary(diagram, dimension=1)["finite_count"] == 0


def test_rips_h0_agrees_with_independent_mst() -> None:
    points = np.random.default_rng(5).normal(size=(8, 2))
    distances = pairwise_distances(points)
    diagram = vietoris_rips_persistence(points, max_dimension=0)
    observed = sorted(float(pair.persistence) for pair in diagram.finite(0))
    expected = sorted(minimum_spanning_tree(distances).data.tolist())
    assert observed == pytest.approx(expected)
    assert len(diagram.essential(0)) == 1


def test_rips_square_has_known_h1_bar_and_deterministic_order() -> None:
    square = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    first = vietoris_rips_persistence(square, max_dimension=1)
    second = vietoris_rips_persistence(square, max_dimension=1)
    h1 = first.finite(1)
    assert len(h1) == 1
    assert h1[0].birth == pytest.approx(1.0)
    assert h1[0].death == pytest.approx(math.sqrt(2.0))
    assert first == second


def test_periodic_grid_has_cylinder_class_but_rectangle_does_not() -> None:
    field = np.ones((3, 5))
    cylinder = grid_persistence(
        field, periodic_axes=(False, True), max_dimension=1, include_zero=True
    )
    rectangle = grid_persistence(field, max_dimension=1, include_zero=True)
    assert len(cylinder.essential(1)) == 1
    assert len(rectangle.essential(1)) == 0
    assert len(cylinder.essential(0)) == 1


def test_diagram_distances_handle_identity_translation_and_empty() -> None:
    empty = np.empty((0, 2))
    point = np.asarray([[0.0, 2.0]])
    shifted = np.asarray([[1.0, 3.0]])
    assert bottleneck_distance(point, point) == 0.0
    assert wasserstein_distance(point, point) == 0.0
    assert bottleneck_distance(empty, point) == pytest.approx(1.0)
    assert wasserstein_distance(empty, point) == pytest.approx(math.sqrt(2.0))
    assert bottleneck_distance(point, shifted) == pytest.approx(1.0)
    assert wasserstein_distance(point, shifted) == pytest.approx(math.sqrt(2.0))
    assert bottleneck_distance(empty, empty) == 0.0
    assert wasserstein_distance(empty, empty) == 0.0


def test_path_diagram_obeys_sup_norm_stability_example() -> None:
    left = exact_path_persistence([0.0, 3.0, 0.0, 2.0, 0.0])
    right = exact_path_persistence([0.2, 2.9, -0.1, 2.1, 0.1])
    distance = bottleneck_distance(diagram_points(left, dimension=0), diagram_points(right, dimension=0))
    assert distance <= 0.2 + 1e-12


def test_farthest_landmarks_are_deterministic_and_traceable() -> None:
    points = np.column_stack((np.arange(10.0), np.zeros(10)))
    selected, indices = farthest_point_landmarks(points, 4)
    assert indices.tolist() == [0, 9, 4, 2]
    assert np.array_equal(selected, points[indices])


def test_empirical_pvalue_is_plus_one_calibrated() -> None:
    assert empirical_pvalue(2.5, [1.0, 2.0, 3.0]) == 0.5


def test_summary_requires_requested_numeric_localization() -> None:
    diagram = exact_path_persistence([0.0, 2.0, 0.0, 1.0, 0.0])
    with pytest.raises(ValueError, match="localization"):
        diagram_summary(diagram, dimension=0, location_key="frequency_uHz")


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda: pairwise_distances(np.asarray([1.0, 2.0])), "matrix"),
        (lambda: vietoris_rips_persistence(np.ones((3, 2)), max_dimension=3), "max_dimension"),
        (lambda: grid_persistence(np.ones((1, 3))), "2-D"),
        (lambda: grid_persistence(np.ones((2, 3)), periodic_axes=(True, False)), "three rows"),
        (lambda: grid_persistence(np.ones((3, 2)), periodic_axes=(False, True)), "three columns"),
        (lambda: grid_persistence(np.ones((3, 3)), max_dimension=2), "max_dimension"),
        (lambda: vietoris_rips_persistence(np.ones((3, 2)), max_edge=0.0), "max_edge"),
        (lambda: farthest_point_landmarks(np.ones((3, 2)), 0), "count"),
        (
            lambda: exact_path_persistence([0.0, 1.0], vertex_metadata=[{"x": 0}]),
            "metadata length",
        ),
        (lambda: wasserstein_distance(np.asarray([[2.0, 1.0]]), np.empty((0, 2))), "birth"),
        (lambda: wasserstein_distance(np.empty((0, 2)), np.empty((0, 2)), order=0.5), "order"),
        (lambda: empirical_pvalue(1.0, []), "null_statistics"),
        (lambda: empirical_pvalue(math.nan, [1.0]), "observed"),
    ],
)
def test_invalid_tda_inputs_are_rejected(call: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        call()  # type: ignore[operator]
