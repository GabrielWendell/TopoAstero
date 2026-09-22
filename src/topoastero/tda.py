"""Tested topological primitives for TopoAstero Stage 5.

The public API deliberately stays small.  It covers the three complexes required by the
representation audit (an exact scalar filtration on a path, Vietoris--Rips complexes, and
triangulated rectangular/periodic grids), diagram distances, compact summaries, and reversible
localization.  All reductions use deterministic simplex ordering and coefficients in ``F_2``.

The implementation is a transparent reference backend intended for analytic examples and the
bounded Stage 5 pilot.  Later large-population stages may add an accelerated backend, but it must
remain cross-checked against these routines.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment  # type: ignore[import-untyped]

from topoastero.persistence import superlevel_h0

FloatArray: TypeAlias = NDArray[np.float64]
Direction = Literal["superlevel", "sublevel", "distance"]
Scalar: TypeAlias = str | int | float | bool | None
Location: TypeAlias = dict[str, Scalar]


@dataclass(frozen=True, slots=True)
class TopologicalPair:
    """One persistence pair with the simplices and physical locations that generated it."""

    dimension: int
    birth: float
    death: float | None
    birth_vertices: tuple[int, ...]
    death_vertices: tuple[int, ...] | None
    birth_location: tuple[Location, ...]
    death_location: tuple[Location, ...] | None
    direction: Direction
    essential: bool = False

    @property
    def persistence(self) -> float | None:
        """Return a nonnegative finite lifetime, or ``None`` for an essential class."""

        if self.death is None:
            return None
        if self.direction == "superlevel":
            return self.birth - self.death
        return self.death - self.birth

    def to_record(self, *, representation_id: str, pair_index: int) -> dict[str, object]:
        """Return a JSON/CSV-friendly localized record."""

        return {
            "representation_id": representation_id,
            "pair_id": f"{representation_id}-D{self.dimension}-{pair_index:04d}",
            "dimension": self.dimension,
            "birth": self.birth,
            "death": self.death,
            "persistence": self.persistence,
            "essential": self.essential,
            "birth_vertices": list(self.birth_vertices),
            "death_vertices": None
            if self.death_vertices is None
            else list(self.death_vertices),
            "birth_location": list(self.birth_location),
            "death_location": None
            if self.death_location is None
            else list(self.death_location),
        }


@dataclass(frozen=True, slots=True)
class PersistenceDiagram:
    """A deterministically ordered collection of persistence pairs."""

    pairs: tuple[TopologicalPair, ...]
    backend: str
    direction: Direction
    coefficient_field: str = "F2"
    essential_policy: str = "retain_localization_exclude_numeric_summaries"

    def finite(self, dimension: int | None = None) -> tuple[TopologicalPair, ...]:
        """Return finite positive-length pairs, optionally in one homology dimension."""

        return tuple(
            pair
            for pair in self.pairs
            if not pair.essential
            and pair.persistence is not None
            and pair.persistence > 0.0
            and (dimension is None or pair.dimension == dimension)
        )

    def essential(self, dimension: int | None = None) -> tuple[TopologicalPair, ...]:
        """Return essential classes, optionally in one homology dimension."""

        return tuple(
            pair
            for pair in self.pairs
            if pair.essential and (dimension is None or pair.dimension == dimension)
        )


@dataclass(frozen=True, slots=True)
class _Simplex:
    vertices: tuple[int, ...]
    dimension: int
    filtration: float


def _finite_vector(
    values: Sequence[float] | NDArray[np.floating], *, name: str
) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a nonempty finite vector")
    return array


def _metadata(
    count: int, vertex_metadata: Sequence[Mapping[str, Scalar]] | None
) -> tuple[Location, ...]:
    if vertex_metadata is None:
        return tuple({"vertex_index": index} for index in range(count))
    if len(vertex_metadata) != count:
        raise ValueError("vertex_metadata length must equal the number of vertices")
    return tuple(dict(record) for record in vertex_metadata)


def _external_value(value: float, direction: Direction) -> float:
    return -value if direction == "superlevel" else value


def _ordered_pairs(pairs: Sequence[TopologicalPair]) -> tuple[TopologicalPair, ...]:
    return tuple(
        sorted(
            pairs,
            key=lambda pair: (
                pair.dimension,
                pair.essential,
                -(pair.persistence if pair.persistence is not None else math.inf),
                pair.birth_vertices,
                pair.death_vertices or (),
            ),
        )
    )


def exact_path_persistence(
    values: Sequence[float] | NDArray[np.floating],
    *,
    direction: Literal["superlevel", "sublevel"] = "superlevel",
    vertex_metadata: Sequence[Mapping[str, Scalar]] | None = None,
    include_zero: bool = False,
) -> PersistenceDiagram:
    """Compute exact ``H_0`` persistence of a scalar function on a path.

    The legacy Stage 0 elder-rule kernel is retained as the independent exact implementation.
    Birth and merge vertices are mapped back to caller-supplied physical metadata.
    """

    array = _finite_vector(values, name="values")
    metadata = _metadata(array.size, vertex_metadata)
    transformed = array if direction == "superlevel" else -array
    legacy = superlevel_h0(transformed.tolist(), include_zero=include_zero)
    pairs: list[TopologicalPair] = []
    for pair in legacy:
        birth = float(array[pair.birth_index])
        death = None if pair.death_index is None else float(array[pair.death_index])
        death_vertices = None if pair.death_index is None else (pair.death_index,)
        death_location = None if pair.death_index is None else (metadata[pair.death_index],)
        pairs.append(
            TopologicalPair(
                dimension=0,
                birth=birth,
                death=death,
                birth_vertices=(pair.birth_index,),
                death_vertices=death_vertices,
                birth_location=(metadata[pair.birth_index],),
                death_location=death_location,
                direction=direction,
                essential=pair.essential,
            )
        )
    return PersistenceDiagram(_ordered_pairs(pairs), "exact_path", direction)


def pairwise_distances(points: NDArray[np.floating]) -> FloatArray:
    """Return a validated Euclidean pairwise-distance matrix."""

    coordinates = np.asarray(points, dtype=np.float64)
    if (
        coordinates.ndim != 2
        or coordinates.shape[0] == 0
        or coordinates.shape[1] == 0
        or not np.all(np.isfinite(coordinates))
    ):
        raise ValueError("points must be a nonempty finite matrix")
    delta = coordinates[:, None, :] - coordinates[None, :, :]
    return np.asarray(np.sqrt(np.sum(delta * delta, axis=2)), dtype=np.float64)


def farthest_point_landmarks(
    points: NDArray[np.floating], count: int
) -> tuple[FloatArray, NDArray[np.int64]]:
    """Select deterministic farthest-point landmarks and return points plus source indices."""

    coordinates = np.asarray(points, dtype=np.float64)
    distances = pairwise_distances(coordinates)
    if not 1 <= count <= coordinates.shape[0]:
        raise ValueError("count must lie between one and the number of points")
    centroid = np.mean(coordinates, axis=0)
    start = int(np.argmax(np.linalg.norm(coordinates - centroid, axis=1)))
    chosen = [start]
    minimum = distances[start].copy()
    while len(chosen) < count:
        minimum[np.asarray(chosen, dtype=int)] = -1.0
        next_index = int(np.argmax(minimum))
        chosen.append(next_index)
        minimum = np.minimum(minimum, distances[next_index])
    indices = np.asarray(chosen, dtype=np.int64)
    return np.asarray(coordinates[indices], dtype=np.float64), indices


def _reduce_simplices(
    simplices: Sequence[_Simplex],
    *,
    metadata: Sequence[Location],
    direction: Direction,
    max_output_dimension: int,
    include_zero: bool,
    backend: str,
) -> PersistenceDiagram:
    ordered = sorted(
        simplices, key=lambda simplex: (simplex.filtration, simplex.dimension, simplex.vertices)
    )
    index = {simplex.vertices: position for position, simplex in enumerate(ordered)}
    reduced: dict[int, set[int]] = {}
    pivot_owner: dict[int, int] = {}
    creators: set[int] = set()
    paired_births: set[int] = set()
    pairs: list[TopologicalPair] = []

    for column_index, simplex in enumerate(ordered):
        boundary: set[int] = set()
        if simplex.dimension > 0:
            for omitted in range(len(simplex.vertices)):
                face = simplex.vertices[:omitted] + simplex.vertices[omitted + 1 :]
                if face not in index:
                    raise RuntimeError(f"complex is missing face {face}")
                boundary.add(index[face])
        while boundary:
            low = max(boundary)
            owner = pivot_owner.get(low)
            if owner is None:
                break
            boundary.symmetric_difference_update(reduced[owner])
        reduced[column_index] = boundary
        if not boundary:
            creators.add(column_index)
            continue
        low = max(boundary)
        pivot_owner[low] = column_index
        paired_births.add(low)
        birth_simplex = ordered[low]
        if birth_simplex.dimension > max_output_dimension:
            continue
        birth = _external_value(birth_simplex.filtration, direction)
        death = _external_value(simplex.filtration, direction)
        lifetime = birth - death if direction == "superlevel" else death - birth
        if include_zero or lifetime > 1e-14:
            pairs.append(
                TopologicalPair(
                    dimension=birth_simplex.dimension,
                    birth=birth,
                    death=death,
                    birth_vertices=birth_simplex.vertices,
                    death_vertices=simplex.vertices,
                    birth_location=tuple(metadata[item] for item in birth_simplex.vertices),
                    death_location=tuple(metadata[item] for item in simplex.vertices),
                    direction=direction,
                )
            )

    for creator in sorted(creators - paired_births):
        simplex = ordered[creator]
        if simplex.dimension <= max_output_dimension:
            pairs.append(
                TopologicalPair(
                    dimension=simplex.dimension,
                    birth=_external_value(simplex.filtration, direction),
                    death=None,
                    birth_vertices=simplex.vertices,
                    death_vertices=None,
                    birth_location=tuple(metadata[item] for item in simplex.vertices),
                    death_location=None,
                    direction=direction,
                    essential=True,
                )
            )
    return PersistenceDiagram(_ordered_pairs(pairs), backend, direction)


def vietoris_rips_persistence(
    points: NDArray[np.floating],
    *,
    max_dimension: int = 1,
    max_edge: float | None = None,
    vertex_metadata: Sequence[Mapping[str, Scalar]] | None = None,
    include_zero: bool = False,
) -> PersistenceDiagram:
    """Compute a finite Vietoris--Rips filtration with exact ``F_2`` reduction.

    Simplices through dimension ``max_dimension + 1`` are generated so that classes in the
    requested maximum dimension can die.  The reference backend intentionally caps the requested
    homology dimension at two and is meant for small, audited landmark clouds.
    """

    if max_dimension not in {0, 1, 2}:
        raise ValueError("max_dimension must be 0, 1, or 2 in the reference backend")
    coordinates = np.asarray(points, dtype=np.float64)
    distances = pairwise_distances(coordinates)
    if max_edge is None:
        threshold = float(np.max(distances))
    elif not math.isfinite(max_edge) or max_edge <= 0:
        raise ValueError("max_edge must be finite and positive")
    else:
        threshold = float(max_edge)
    metadata = _metadata(coordinates.shape[0], vertex_metadata)
    simplices: list[_Simplex] = [
        _Simplex((index,), 0, 0.0) for index in range(coordinates.shape[0])
    ]
    for size in range(2, max_dimension + 3):
        for vertices in combinations(range(coordinates.shape[0]), size):
            diameter = max(distances[left, right] for left, right in combinations(vertices, 2))
            if diameter <= threshold + 1e-14:
                simplices.append(_Simplex(vertices, size - 1, float(diameter)))
    return _reduce_simplices(
        simplices,
        metadata=metadata,
        direction="distance",
        max_output_dimension=max_dimension,
        include_zero=include_zero,
        backend="vietoris_rips_reference",
    )


def grid_persistence(
    field: NDArray[np.floating],
    *,
    direction: Literal["superlevel", "sublevel"] = "superlevel",
    periodic_axes: tuple[bool, bool] = (False, False),
    max_dimension: int = 1,
    vertex_metadata: Sequence[Mapping[str, Scalar]] | None = None,
    include_zero: bool = False,
) -> PersistenceDiagram:
    """Compute lower/upper-star persistence on a triangulated 2-D grid.

    Setting ``periodic_axes=(False, True)`` gives the cylindrical echelle domain ``I x S1``.
    The fixed southwest-to-northeast diagonal makes the construction deterministic.  The public
    name says ``grid`` rather than ``cubical`` because this dependency-light reference backend
    realizes each square as two simplices while preserving the same vertices and boundary gluing.
    """

    values = np.asarray(field, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 2 or not np.all(np.isfinite(values)):
        raise ValueError("field must be a finite 2-D array with both dimensions at least two")
    if max_dimension not in {0, 1}:
        raise ValueError("grid max_dimension must be 0 or 1")
    if periodic_axes[0] and values.shape[0] < 3:
        raise ValueError("a periodic row axis requires at least three rows")
    if periodic_axes[1] and values.shape[1] < 3:
        raise ValueError("a periodic column axis requires at least three columns")
    rows, columns = values.shape
    flat = values.ravel()
    internal = -flat if direction == "superlevel" else flat
    metadata = _metadata(flat.size, vertex_metadata)

    def vertex(row: int, column: int) -> int:
        return row * columns + column

    edges: set[tuple[int, ...]] = set()
    triangles: set[tuple[int, ...]] = set()
    row_cells = rows if periodic_axes[0] else rows - 1
    column_cells = columns if periodic_axes[1] else columns - 1
    for row in range(row_cells):
        next_row = (row + 1) % rows
        for column in range(column_cells):
            next_column = (column + 1) % columns
            a = vertex(row, column)
            b = vertex(next_row, column)
            c = vertex(row, next_column)
            d = vertex(next_row, next_column)
            edges.update(
                {
                    tuple(sorted((a, b))),
                    tuple(sorted((a, c))),
                    tuple(sorted((b, d))),
                    tuple(sorted((c, d))),
                    tuple(sorted((a, d))),
                }
            )
            triangles.update({tuple(sorted((a, b, d))), tuple(sorted((a, c, d)))})

    simplices: list[_Simplex] = [
        _Simplex((index,), 0, float(internal[index])) for index in range(flat.size)
    ]
    simplices.extend(
        _Simplex(item, 1, float(max(internal[index] for index in item)))
        for item in sorted(edges)
    )
    if max_dimension == 1:
        simplices.extend(
            _Simplex(item, 2, float(max(internal[index] for index in item)))
            for item in sorted(triangles)
        )
    return _reduce_simplices(
        simplices,
        metadata=metadata,
        direction=direction,
        max_output_dimension=max_dimension,
        include_zero=include_zero,
        backend="periodic_grid_reference" if any(periodic_axes) else "grid_reference",
    )


def diagram_points(diagram: PersistenceDiagram, *, dimension: int) -> FloatArray:
    """Return finite pairs in the conventional ``birth <= death`` orientation."""

    points = []
    for pair in diagram.finite(dimension):
        if pair.death is None:
            continue
        points.append((min(pair.birth, pair.death), max(pair.birth, pair.death)))
    if not points:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(points, dtype=np.float64)


def _validate_diagram(points: NDArray[np.floating], name: str) -> FloatArray:
    diagram = np.asarray(points, dtype=np.float64)
    if diagram.ndim != 2 or diagram.shape[1] != 2 or not np.all(np.isfinite(diagram)):
        raise ValueError(f"{name} must be a finite (n, 2) array")
    if np.any(diagram[:, 1] < diagram[:, 0]):
        raise ValueError(f"{name} must use birth <= death orientation")
    return diagram


def _augmented_cost(left: FloatArray, right: FloatArray, *, metric: str) -> FloatArray:
    n_left, n_right = left.shape[0], right.shape[0]
    size = n_left + n_right
    if size == 0:
        return np.empty((0, 0), dtype=np.float64)
    cost = np.full((size, size), np.inf, dtype=np.float64)
    if n_left and n_right:
        differences = np.abs(left[:, None, :] - right[None, :, :])
        cost[:n_left, :n_right] = (
            np.max(differences, axis=2)
            if metric == "linf"
            else np.sqrt(np.sum(differences**2, axis=2))
        )
    left_diagonal = 0.5 * (left[:, 1] - left[:, 0])
    right_diagonal = 0.5 * (right[:, 1] - right[:, 0])
    for index, value in enumerate(left_diagonal):
        cost[index, n_right + index] = value if metric == "linf" else math.sqrt(2.0) * value
    for index, value in enumerate(right_diagonal):
        cost[n_left + index, index] = value if metric == "linf" else math.sqrt(2.0) * value
    cost[n_left:, n_right:] = 0.0
    return cost


def wasserstein_distance(
    left: NDArray[np.floating], right: NDArray[np.floating], *, order: float = 2.0
) -> float:
    """Return the finite-diagram Wasserstein distance with Euclidean ground metric."""

    first = _validate_diagram(left, "left")
    second = _validate_diagram(right, "right")
    if not math.isfinite(order) or order < 1:
        raise ValueError("order must be finite and at least one")
    cost = _augmented_cost(first, second, metric="l2")
    if cost.size == 0:
        return 0.0
    rows, columns = linear_sum_assignment(cost**order)
    return float(np.sum(cost[rows, columns] ** order) ** (1.0 / order))


def _has_perfect_matching(adjacency: NDArray[np.bool_]) -> bool:
    matched = np.full(adjacency.shape[1], -1, dtype=int)

    def augment(row: int, seen: NDArray[np.bool_]) -> bool:
        for column in np.flatnonzero(adjacency[row]):
            if seen[column]:
                continue
            seen[column] = True
            if matched[column] < 0 or augment(int(matched[column]), seen):
                matched[column] = row
                return True
        return False

    for row in range(adjacency.shape[0]):
        if not augment(row, np.zeros(adjacency.shape[1], dtype=bool)):
            return False
    return True


def bottleneck_distance(left: NDArray[np.floating], right: NDArray[np.floating]) -> float:
    """Return the exact bottleneck distance for two finite diagrams."""

    first = _validate_diagram(left, "left")
    second = _validate_diagram(right, "right")
    cost = _augmented_cost(first, second, metric="linf")
    if cost.size == 0:
        return 0.0
    candidates = np.unique(cost[np.isfinite(cost)])
    if candidates.size == 0:
        return 0.0
    low, high = 0, candidates.size - 1
    while low < high:
        middle = (low + high) // 2
        if _has_perfect_matching(cost <= candidates[middle] + 1e-14):
            high = middle
        else:
            low = middle + 1
    return float(candidates[low])


def diagram_summary(
    diagram: PersistenceDiagram, *, dimension: int, location_key: str | None = None
) -> dict[str, float | int | None]:
    """Return the compact, preregistered summary family for one homology dimension."""

    pairs = diagram.finite(dimension)
    lifetime_values: list[float] = []
    for pair in pairs:
        persistence = pair.persistence
        if persistence is None:
            raise RuntimeError("finite diagram unexpectedly contains an essential pair")
        lifetime_values.append(persistence)
    lifetimes = np.asarray(lifetime_values, dtype=np.float64)
    if lifetimes.size == 0:
        return {
            "finite_count": 0,
            "total_persistence": 0.0,
            "maximum_persistence": 0.0,
            "persistence_centroid": None,
        }
    if location_key is None:
        location_values: list[float] = []
        for pair in pairs:
            if pair.death is None:
                raise RuntimeError("finite diagram unexpectedly contains an essential pair")
            location_values.append(0.5 * (pair.birth + pair.death))
        locations = np.asarray(location_values, dtype=np.float64)
    else:
        raw_locations: list[float] = []
        for pair in pairs:
            value = pair.birth_location[0].get(location_key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"birth localization lacks numeric key {location_key!r}")
            raw_locations.append(float(value))
        locations = np.asarray(raw_locations, dtype=np.float64)
    total = float(np.sum(lifetimes))
    return {
        "finite_count": int(lifetimes.size),
        "total_persistence": total,
        "maximum_persistence": float(np.max(lifetimes)),
        "persistence_centroid": float(np.sum(locations * lifetimes) / total),
    }


def empirical_pvalue(observed: float, null_statistics: Sequence[float]) -> float:
    """Compute a conservative plus-one upper-tail empirical p-value."""

    null = _finite_vector(null_statistics, name="null_statistics")
    if not math.isfinite(observed):
        raise ValueError("observed must be finite")
    return float((1 + np.count_nonzero(null >= observed)) / (null.size + 1))


def localized_records(
    diagram: PersistenceDiagram, *, representation_id: str
) -> list[dict[str, object]]:
    """Expose all finite and essential pairs as deterministic localization records."""

    return [
        pair.to_record(representation_id=representation_id, pair_index=index)
        for index, pair in enumerate(diagram.pairs, start=1)
    ]
