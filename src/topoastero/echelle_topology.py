"""Stage 8 cylindrical echelle geometry, cubical persistence, and ridge controls.

The angular coordinate is sampled once on [0, 1), without a duplicated endpoint.  The
last and first angular columns share an edge; radial orders never wrap.  Missing vertices
and their incident cells are *omitted*, not replaced by low-valued pixels.  Cubical cells
enter the superlevel filtration when all their vertices enter (minimum vertex value).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray

from topoastero.tda import Location, PersistenceDiagram, TopologicalPair

FloatArray: TypeAlias = NDArray[np.float64]
BoolArray: TypeAlias = NDArray[np.bool_]
CellKey: TypeAlias = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class EchelleField:
    """Log(P/B) at integer order and half-bin angular centers in cycles."""

    values: FloatArray
    valid: BoolArray
    orders: NDArray[np.int64]
    phases: FloatArray
    frequencies_uHz: FloatArray
    spacing_uHz: float

    @property
    def complete_orders(self) -> int:
        return int(np.count_nonzero(np.all(self.valid, axis=1)))


@dataclass(frozen=True, slots=True)
class RidgeNode:
    row: int
    order: int
    column: int
    phase: float
    contrast: float


@dataclass(frozen=True, slots=True)
class RidgeEdge:
    source: int
    target: int
    phase_distance: float
    cost: float


@dataclass(frozen=True, slots=True)
class RidgeTrack:
    node_indices: tuple[int, ...]
    center_phase: float
    mean_jump: float
    coherence: float


@dataclass(frozen=True, slots=True)
class RidgeGraph:
    nodes: tuple[RidgeNode, ...]
    edges: tuple[RidgeEdge, ...]
    hypotheses: tuple[RidgeTrack, ...]


@dataclass(frozen=True, slots=True)
class EchelleScore:
    spacing_uHz: float
    topology: float
    graph_only: float
    combined: float
    orderwise: float
    valid_orders: int
    finite_h0_count: int
    finite_h1_count: int | None = None


@dataclass(frozen=True, slots=True)
class _Cell:
    key: CellKey
    vertices: tuple[int, ...]
    boundary: tuple[CellKey, ...]
    filtration: float


def circular_distance(left: float, right: float) -> float:
    """Minimum circular separation in normalized phase cycles."""

    if not math.isfinite(left) or not math.isfinite(right):
        raise ValueError("circular phase must be finite")
    difference = abs((left - right) % 1.0)
    return min(difference, 1.0 - difference)


def circular_center(phases: NDArray[np.floating], weights: NDArray[np.floating] | None = None) -> float:
    """Weighted circular mean in [0,1); reject a directionless resultant."""

    angles = np.asarray(phases, dtype=np.float64)
    weights_array = np.ones(angles.size) if weights is None else np.asarray(weights, dtype=float)
    if angles.ndim != 1 or not angles.size or weights_array.shape != angles.shape:
        raise ValueError("phases and weights must be nonempty equal-length vectors")
    if not np.all(np.isfinite(angles)) or not np.all(np.isfinite(weights_array)) or np.any(weights_array < 0):
        raise ValueError("phases/weights must be finite, with nonnegative weights")
    vector = np.sum(weights_array * np.exp(2j * np.pi * angles))
    if abs(vector) <= 1e-12:
        raise ValueError("circular center is undefined for a directionless sample")
    center = float((np.angle(vector) / (2 * np.pi)) % 1.0)
    return 0.0 if center >= 1.0 - 1e-15 else center


def make_echelle_field(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    background: NDArray[np.floating],
    *,
    spacing_uHz: float,
    phase_bins: int = 24,
    minimum_order_coverage: float = 0.75,
) -> EchelleField:
    """Interpolate log(P/B) only *inside* the observed frequency domain.

    The order interval is the floor-indexed extent of the supplied spectrum; a row with too
    few observed phase bins is kept in the audit mask but contributes no cubical vertices.
    """

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    observed = np.asarray(power, dtype=np.float64)
    continuum = np.asarray(background, dtype=np.float64)
    if frequency.ndim != 1 or frequency.size < 16 or observed.shape != frequency.shape or continuum.shape != frequency.shape:
        raise ValueError("frequency, power, and background must be equal vectors of length >=16")
    if not np.all(np.isfinite(frequency)) or np.any(np.diff(frequency) <= 0):
        raise ValueError("frequencies must be finite and strictly increasing")
    if not np.all(np.isfinite(observed)) or not np.all(np.isfinite(continuum)) or np.any(observed <= 0) or np.any(continuum <= 0):
        raise ValueError("power and background must be positive finite vectors")
    if not math.isfinite(spacing_uHz) or spacing_uHz <= 0 or phase_bins < 4:
        raise ValueError("spacing must be positive and phase_bins >= 4")
    if not 0 < minimum_order_coverage <= 1:
        raise ValueError("minimum order coverage must be in (0,1]")
    first = math.floor(frequency[0] / spacing_uHz)
    last = math.floor(frequency[-1] / spacing_uHz)
    orders = np.arange(first, last + 1, dtype=np.int64)
    phases = (np.arange(phase_bins, dtype=np.float64) + 0.5) / phase_bins
    sampled = spacing_uHz * (orders[:, None] + phases[None, :])
    valid = (sampled >= frequency[0]) & (sampled <= frequency[-1])
    coverage = np.mean(valid, axis=1)
    valid &= (coverage >= minimum_order_coverage)[:, None]
    field = np.full(sampled.shape, np.nan, dtype=np.float64)
    field[valid] = np.interp(sampled[valid], frequency, np.log(observed / continuum))
    return EchelleField(field, valid, orders, phases, sampled, spacing_uHz)


def normalize_field_for_score(field: EchelleField) -> EchelleField:
    """Use a robust global log-ratio scale while retaining the physical field separately."""

    _check_field(field, full_complex=False)
    observed = field.values[field.valid]
    center = float(np.median(observed))
    scale = max(0.5, float(1.4826 * np.median(np.abs(observed - center))))
    normalized = np.full(field.values.shape, np.nan, dtype=np.float64)
    normalized[field.valid] = (observed - center) / scale
    return EchelleField(normalized, field.valid, field.orders, field.phases, field.frequencies_uHz, field.spacing_uHz)


def _check_field(field: EchelleField, *, full_complex: bool) -> tuple[int, int]:
    values = field.values
    valid = field.valid
    if values.ndim != 2 or valid.shape != values.shape or values.shape[1] < 3:
        raise ValueError("cylinder requires a 2-D field with at least three angular bins")
    if full_complex and values.shape[0] < 2:
        raise ValueError("full cubical complex requires at least two radial orders")
    if field.orders.shape != (values.shape[0],) or field.phases.shape != (values.shape[1],):
        raise ValueError("order and phase coordinate shapes do not match field")
    if np.any(~np.isfinite(values[valid])) or not np.any(valid):
        raise ValueError("all observed vertices must be finite, with at least one present")
    return values.shape[0], values.shape[1]


def _vertex_location(field: EchelleField, index: int) -> Location:
    bins = field.phases.size
    row, column = divmod(index, bins)
    return {
        "row": row,
        "order": int(field.orders[row]),
        "phase_cycles": float(field.phases[column]),
        "frequency_uHz": float(field.frequencies_uHz[row, column]),
    }


def _cubical_cells(field: EchelleField, *, periodic: bool) -> list[_Cell]:
    rows, columns = _check_field(field, full_complex=True)
    valid = field.valid
    values = field.values
    cells: list[_Cell] = []

    def idx(row: int, column: int) -> int:
        return row * columns + column

    for row in range(rows):
        for column in range(columns):
            if valid[row, column]:
                cells.append(_Cell((0, row, column, 0), (idx(row, column),), (), -float(values[row, column])))
    for row in range(rows):
        for column in range(columns if periodic else columns - 1):
            following = (column + 1) % columns
            if valid[row, column] and valid[row, following]:
                cells.append(
                    _Cell(
                        (1, row, column, 0),
                        (idx(row, column), idx(row, following)),
                        ((0, row, column, 0), (0, row, following, 0)),
                        -float(min(values[row, column], values[row, following])),
                    )
                )
    for row in range(rows - 1):
        for column in range(columns):
            if valid[row, column] and valid[row + 1, column]:
                cells.append(
                    _Cell(
                        (1, row, column, 1),
                        (idx(row, column), idx(row + 1, column)),
                        ((0, row, column, 0), (0, row + 1, column, 0)),
                        -float(min(values[row, column], values[row + 1, column])),
                    )
                )
    for row in range(rows - 1):
        for column in range(columns if periodic else columns - 1):
            following = (column + 1) % columns
            if np.all(valid[np.ix_((row, row + 1), (column, following))]):
                vertices = (
                    idx(row, column), idx(row, following), idx(row + 1, column), idx(row + 1, following)
                )
                cells.append(
                    _Cell(
                        (2, row, column, 0),
                        vertices,
                        (
                            (1, row, column, 0),
                            (1, row + 1, column, 0),
                            (1, row, column, 1),
                            (1, row, following, 1),
                        ),
                        -float(min(values[np.unravel_index(index, values.shape)] for index in vertices)),
                    )
                )
    return sorted(cells, key=lambda cell: (cell.filtration, cell.key[0], cell.key))


def cubical_superlevel_persistence(field: EchelleField, *, periodic: bool = True) -> PersistenceDiagram:
    """Exact F2 H0/H1 of the upper-star cubical cylinder, including essential classes."""

    cells = _cubical_cells(field, periodic=periodic)
    indices = {cell.key: index for index, cell in enumerate(cells)}
    reduced: dict[int, int] = {}
    owners: dict[int, int] = {}
    creators: set[int] = set()
    paired: set[int] = set()
    pairs: list[TopologicalPair] = []
    for index, cell in enumerate(cells):
        boundary = 0
        for face in cell.boundary:
            boundary ^= 1 << indices[face]
        while boundary:
            pivot = boundary.bit_length() - 1
            owner = owners.get(pivot)
            if owner is None:
                break
            boundary ^= reduced[owner]
        if not boundary:
            creators.add(index)
            continue
        pivot = boundary.bit_length() - 1
        reduced[index] = boundary
        owners[pivot] = index
        paired.add(pivot)
        birth_cell = cells[pivot]
        lifetime = cell.filtration - birth_cell.filtration
        if lifetime > 1e-14 and birth_cell.key[0] <= 1:
            pairs.append(
                TopologicalPair(
                    birth_cell.key[0], -birth_cell.filtration, -cell.filtration,
                    birth_cell.vertices, cell.vertices,
                    tuple(_vertex_location(field, item) for item in birth_cell.vertices),
                    tuple(_vertex_location(field, item) for item in cell.vertices),
                    "superlevel",
                )
            )
    for index in sorted(creators - paired):
        cell = cells[index]
        if cell.key[0] <= 1:
            pairs.append(
                TopologicalPair(
                    cell.key[0], -cell.filtration, None, cell.vertices, None,
                    tuple(_vertex_location(field, item) for item in cell.vertices),
                    None, "superlevel", essential=True,
                )
            )
    pairs.sort(key=lambda pair: (pair.dimension, pair.essential, -(pair.persistence or 0.0), pair.birth_vertices))
    return PersistenceDiagram(tuple(pairs), "periodic_cubical_F2" if periodic else "rectangular_cubical_F2", "superlevel")


def fast_superlevel_h0(field: EchelleField, *, periodic: bool = True) -> PersistenceDiagram:
    """Union-find H0 of the same cubical filtration, used for large trial scans."""

    rows, columns = _check_field(field, full_complex=False)
    flat = field.values.ravel()
    mask = field.valid.ravel()
    parent = np.arange(flat.size)
    active = np.zeros(flat.size, dtype=bool)
    birth = np.arange(flat.size)
    pairs: list[TopologicalPair] = []

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = int(parent[index])
        return index

    events: list[tuple[float, int, int, int]] = []
    for index in np.flatnonzero(mask):
        events.append((-float(flat[index]), 0, int(index), int(index)))
    for row in range(rows):
        for column in range(columns):
            a = row * columns + column
            if not mask[a]:
                continue
            neighbours: list[int] = []
            if column + 1 < columns:
                neighbours.append(a + 1)
            elif periodic:
                neighbours.append(row * columns)
            if row + 1 < rows:
                neighbours.append(a + columns)
            for b in neighbours:
                if mask[b]:
                    events.append((-float(min(flat[a], flat[b])), 1, a, b))
    events.sort()
    for filtration, dimension, a, b in events:
        if dimension == 0:
            active[a] = True
            continue
        if not active[a] or not active[b]:
            raise RuntimeError("cubical edge precedes a vertex")
        ra, rb = find(a), find(b)
        if ra == rb:
            continue
        old_a, old_b = int(birth[ra]), int(birth[rb])
        older, younger = (
            (ra, rb) if (-flat[old_a], old_a) <= (-flat[old_b], old_b) else (rb, ra)
        )
        dead = int(birth[younger])
        if float(flat[dead]) + filtration > 1e-14:
            pairs.append(
                TopologicalPair(
                    0, float(flat[dead]), -filtration, (dead,), (a, b),
                    (_vertex_location(field, dead),),
                    (_vertex_location(field, a), _vertex_location(field, b)), "superlevel",
                )
            )
        parent[younger] = older
    for root in {find(int(index)) for index in np.flatnonzero(mask)}:
        index = int(birth[root])
        pairs.append(
            TopologicalPair(
                0, float(flat[index]), None, (index,), None,
                (_vertex_location(field, index),), None, "superlevel", essential=True,
            )
        )
    pairs.sort(key=lambda pair: (pair.essential, -(pair.persistence or 0.0), pair.birth_vertices))
    return PersistenceDiagram(tuple(pairs), "periodic_cubical_fast_H0" if periodic else "rectangular_cubical_fast_H0", "superlevel")


def ridge_graph(field: EchelleField, *, maximum_candidates: int = 5, jump_limit: float = 0.17) -> RidgeGraph:
    """Circular local maxima and competing adjacent-order dynamic-programming paths."""

    rows, columns = _check_field(field, full_complex=False)
    if maximum_candidates < 1 or not 0 < jump_limit <= 0.5:
        raise ValueError("candidate count and jump limit must be positive")
    valid_orders = max(1, int(np.count_nonzero(np.any(field.valid, axis=1))))
    nodes: list[RidgeNode] = []
    for row in range(rows):
        if not np.any(field.valid[row]):
            continue
        values = field.values[row]
        mask = field.valid[row]
        candidate_columns = [
            column for column in range(columns)
            if mask[column] and mask[(column - 1) % columns] and mask[(column + 1) % columns]
            and values[column] >= values[(column - 1) % columns]
            and values[column] > values[(column + 1) % columns]
        ]
        candidate_columns.sort(key=lambda column: (-values[column], column))
        selected: list[int] = []
        for column in candidate_columns:
            if all(min(abs(column - other), columns - abs(column - other)) >= 2 for other in selected):
                selected.append(column)
            if len(selected) == maximum_candidates:
                break
        for column in selected:
            nodes.append(RidgeNode(row, int(field.orders[row]), column, float(field.phases[column]), float(values[column])))
    edges: list[RidgeEdge] = []
    predecessors: dict[int, list[tuple[int, float]]] = {index: [] for index in range(len(nodes))}
    for current, node in enumerate(nodes):
        for previous in range(current):
            earlier = nodes[previous]
            if node.order != earlier.order + 1:
                continue
            separation = circular_distance(node.phase, earlier.phase)
            if separation <= jump_limit:
                penalty = separation / jump_limit + 0.08 * abs(node.contrast - earlier.contrast)
                edges.append(RidgeEdge(previous, current, separation, penalty))
                predecessors[current].append((previous, separation))
    path_to: dict[int, tuple[int, ...]] = {}
    for index in range(len(nodes)):
        best: tuple[int, ...] = (index,)
        best_value = -math.inf
        for predecessor, separation in predecessors[index]:
            prior = path_to[predecessor]
            value = len(prior) - 0.7 * separation / jump_limit
            if value > best_value:
                best, best_value = (*prior, index), value
        path_to[index] = best
    hypotheses: list[RidgeTrack] = []
    for path in sorted(path_to.values(), key=lambda item: (-len(item), item)):
        if len(path) < 2:
            continue
        phases = np.asarray([nodes[index].phase for index in path])
        try:
            center = circular_center(phases)
        except ValueError:
            continue
        if any(circular_distance(center, previous.center_phase) < 0.08 for previous in hypotheses):
            continue
        jumps = [circular_distance(phases[index], phases[index - 1]) for index in range(1, len(path))]
        mean_jump = float(np.mean(jumps))
        strength = float(np.mean([max(0.0, min(4.0, nodes[index].contrast)) / 4 for index in path]))
        coherence = (len(path) / valid_orders) * math.exp(-mean_jump / jump_limit) * (0.5 + 0.5 * strength)
        hypotheses.append(RidgeTrack(path, center, mean_jump, coherence))
        if len(hypotheses) >= 3:
            break
    return RidgeGraph(tuple(nodes), tuple(edges), tuple(hypotheses))


def score_echelle(field: EchelleField, *, full_diagram: bool = False) -> tuple[EchelleScore, RidgeGraph, PersistenceDiagram]:
    """Frozen score: normalized finite H0 persistence + topology-free ridge coherence.

    Essential classes are retained for localization but excluded from numeric scores.  The
    per-order H0 diagnostic applies the same periodic graph rule independently by row.
    """

    normalized = normalize_field_for_score(field)
    diagram = cubical_superlevel_persistence(normalized) if full_diagram else fast_superlevel_h0(normalized)
    graph = ridge_graph(normalized)
    orders = max(1, int(np.count_nonzero(np.any(field.valid, axis=1))))
    lifetimes = sorted((float(pair.persistence or 0) for pair in diagram.finite(0)), reverse=True)
    topology = float(sum(min(value, 4.0) for value in lifetimes[: 3 * orders]) / (12 * orders))
    graph_only = max((track.coherence for track in graph.hypotheses), default=0.0)
    per_order: list[float] = []
    for row in range(field.values.shape[0]):
        if not np.any(field.valid[row]):
            continue
        subfield = EchelleField(
            normalized.values[row : row + 1], normalized.valid[row : row + 1],
            normalized.orders[row : row + 1], normalized.phases,
            normalized.frequencies_uHz[row : row + 1], normalized.spacing_uHz,
        )
        local = fast_superlevel_h0(subfield)
        per_order.append(max((float(pair.persistence or 0) for pair in local.finite(0)), default=0.0))
    score = EchelleScore(
        field.spacing_uHz, topology, graph_only,
        0.55 * topology + 0.45 * graph_only,
        float(np.mean(per_order)) if per_order else 0.0,
        orders, len(diagram.finite(0)), len(diagram.finite(1)) if full_diagram else None,
    )
    return score, graph, diagram


def trial_spacing_grid(anchor_uHz: float, *, fractions: tuple[float, ...] = (0.9, 0.95, 1.0, 1.05, 1.1)) -> tuple[tuple[str, float], ...]:
    """Registered half/nominal/double alias families around a non-truth anchor."""

    if not math.isfinite(anchor_uHz) or anchor_uHz <= 0 or not fractions:
        raise ValueError("anchor and fractional trial family must be positive")
    if any(not math.isfinite(value) or value <= 0 for value in fractions):
        raise ValueError("trial fractions must be finite and positive")
    return tuple((name, anchor_uHz * multiplier * fraction) for name, multiplier in (("half", 0.5), ("nominal", 1.0), ("double", 2.0)) for fraction in fractions)


def maximum_statistic_pvalue(observed: float, null_maxima: NDArray[np.floating]) -> float:
    """Plus-one family-wise p-value; each null already maximized over trial spacings."""

    values = np.asarray(null_maxima, dtype=np.float64)
    if not math.isfinite(observed) or values.ndim != 1 or values.size < 3 or not np.all(np.isfinite(values)):
        raise ValueError("observed and at least three null maxima must be finite")
    return float((1 + np.count_nonzero(values >= observed)) / (values.size + 1))


def percentile_interval(draws: NDArray[np.floating], *, level: float = 0.90) -> tuple[float, float]:
    """Percentile interval of independent stochastic/branch refits."""

    values = np.asarray(draws, dtype=np.float64)
    if values.ndim != 1 or values.size < 4 or not np.all(np.isfinite(values)) or not 0 < level < 1:
        raise ValueError("at least four finite draws and a level in (0,1) are required")
    tail = (1.0 - level) / 2.0
    lower, upper = np.quantile(values, (tail, 1.0 - tail))
    return float(lower), float(upper)


def circular_interval(draws: NDArray[np.floating], *, level: float = 0.90) -> tuple[float, float, bool]:
    """Shortest empirical phase arc; wrapped intervals have lower > upper."""

    values = np.asarray(draws, dtype=np.float64)
    if values.ndim != 1 or values.size < 4 or not np.all(np.isfinite(values)) or not 0 < level < 1:
        raise ValueError("at least four finite circular draws and a valid level are required")
    sorted_values = np.sort(values % 1.0)
    count = max(1, math.ceil(level * values.size))
    extended = np.concatenate((sorted_values, sorted_values + 1.0))
    widths = extended[count - 1 : count - 1 + values.size] - extended[: values.size]
    start = int(np.argmin(widths))
    lower = float(extended[start] % 1.0)
    upper = float(extended[start + count - 1] % 1.0)
    return lower, upper, lower > upper


def ridge_angle_ratios(centers: dict[int, float], *, anchor_phase: float | None = None) -> dict[str, float | None]:
    """Return seam-aware ridge geometry only when an external degree anchor is supplied.

    Angular offsets are *not* substituted for the five-point r01/r10 definitions.
    """

    result: dict[str, float | None] = {"theta_0": None, "theta_1": None, "theta_2": None, "delta_theta_02": None, "r02_proxy": None}
    if anchor_phase is None or 0 not in centers:
        return result
    if circular_distance(centers[0], anchor_phase) > 0.15:
        return result
    for degree in (0, 1, 2):
        if degree in centers:
            result[f"theta_{degree}"] = centers[degree] % 1.0
    if 2 in centers and circular_distance(centers[0], centers[2]) > 1e-9:
        difference = (centers[0] - centers[2]) % 1.0
        result["delta_theta_02"] = 2 * math.pi * difference
        result["r02_proxy"] = difference
    return result


def five_point_frequency_ratios(modes: dict[tuple[int, int], float]) -> list[dict[str, float | int | None]]:
    """Compute observed-mode r02, r01, r10 with explicit radial-order indexing.

    r02(n) uses nu(n,0)-nu(n-1,2), divided by nu(n,1)-nu(n-1,1).
    r01/r10 use the five-point small separations and the matching l=1/l=0 spacings.
    Missing degrees or neighbouring orders yield None rather than imputed values.
    """

    def get(order: int, degree: int) -> float | None:
        return modes.get((order, degree))

    def ratio(numerator: float, denominator: float) -> float | None:
        return numerator / denominator if denominator > 0 else None

    records: list[dict[str, float | int | None]] = []
    for order in sorted({key[0] for key in modes}):
        n0, n1 = get(order, 0), get(order, 1)
        previous0, previous1, previous2 = get(order - 1, 0), get(order - 1, 1), get(order - 1, 2)
        next0, next1 = get(order + 1, 0), get(order + 1, 1)
        r02 = ratio(n0 - previous2, n1 - previous1) if n0 is not None and previous2 is not None and n1 is not None and previous1 is not None else None
        r01 = (
            ratio((previous0 - 4 * previous1 + 6 * n0 - 4 * n1 + next0) / 8, n1 - previous1)
            if previous0 is not None and previous1 is not None and n0 is not None and n1 is not None and next0 is not None else None
        )
        r10 = (
            ratio((-previous1 + 4 * n0 - 6 * n1 + 4 * next0 - next1) / 8, next0 - n0)
            if previous1 is not None and n0 is not None and n1 is not None and next0 is not None and next1 is not None else None
        )
        records.append({"radial_order_n": order, "r02": r02, "r01": r01, "r10": r10})
    return records
