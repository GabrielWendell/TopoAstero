"""Small, dependency-light reference algorithms for analytic and smoke tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PersistencePair:
    """A zero-dimensional superlevel-set persistence pair on a path graph."""

    birth_index: int
    death_index: int | None
    birth: float
    death: float | None
    essential: bool = False

    @property
    def persistence(self) -> float | None:
        if self.death is None:
            return None
        return self.birth - self.death

    def to_dict(self) -> dict[str, int | float | bool | None]:
        result = asdict(self)
        result["persistence"] = self.persistence
        return result


def _validate_values(values: Sequence[float]) -> list[float]:
    if len(values) == 0:
        raise ValueError("At least one scalar value is required")
    normalized = [float(value) for value in values]
    if not all(isfinite(value) for value in normalized):
        raise ValueError("Persistence input must contain only finite values")
    return normalized


def superlevel_h0(
    values: Sequence[float], *, include_zero: bool = False
) -> list[PersistencePair]:
    """Compute exact H0 persistence for superlevel sets on a one-dimensional path.

    Vertices enter in descending scalar order. When two components merge, the component
    with the lower birth level dies (elder rule). Equal births are resolved by the lower peak
    index. This deterministic tie policy can create zero-length bars; they are omitted unless
    ``include_zero`` is requested. The final surviving component is returned as essential.
    """

    signal = _validate_values(values)
    size = len(signal)
    parent = list(range(size))
    active = [False] * size
    component_birth = signal.copy()
    component_peak = list(range(size))
    pairs: list[PersistencePair] = []

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def older(left: int, right: int) -> tuple[int, int]:
        left_key = (component_birth[left], -component_peak[left])
        right_key = (component_birth[right], -component_peak[right])
        return (left, right) if left_key >= right_key else (right, left)

    for index in sorted(range(size), key=lambda item: (-signal[item], item)):
        active[index] = True
        for neighbor in (index - 1, index + 1):
            if not (0 <= neighbor < size and active[neighbor]):
                continue
            root = find(index)
            neighbor_root = find(neighbor)
            if root == neighbor_root:
                continue
            survivor, dying = older(root, neighbor_root)
            death = signal[index]
            persistence = component_birth[dying] - death
            if include_zero or persistence > 0.0:
                pairs.append(
                    PersistencePair(
                        birth_index=component_peak[dying],
                        death_index=index,
                        birth=component_birth[dying],
                        death=death,
                    )
                )
            parent[dying] = survivor
            parent[root] = survivor
            parent[neighbor_root] = survivor

    roots = {find(index) for index in range(size) if active[index]}
    if len(roots) != 1:
        raise RuntimeError("The path graph should contain exactly one final component")
    root = roots.pop()
    pairs.append(
        PersistencePair(
            birth_index=component_peak[root],
            death_index=None,
            birth=component_birth[root],
            death=None,
            essential=True,
        )
    )
    return sorted(
        pairs,
        key=lambda pair: (
            pair.essential,
            -(pair.persistence if pair.persistence is not None else float("inf")),
            pair.birth_index,
        ),
    )

