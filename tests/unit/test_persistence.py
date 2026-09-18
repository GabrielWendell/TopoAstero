from __future__ import annotations

import math

import pytest

from topoastero.persistence import superlevel_h0
from topoastero.smoke import finite_pairs


def test_known_two_peak_signal() -> None:
    pairs = superlevel_h0([0.0, 2.0, 0.0, 1.0, 0.0])
    finite = finite_pairs(pairs)
    essential = [pair for pair in pairs if pair.essential]
    assert len(finite) == 1
    assert finite[0].birth == 1.0
    assert finite[0].death == 0.0
    assert finite[0].persistence == 1.0
    assert len(essential) == 1
    assert essential[0].birth == 2.0
    assert essential[0].persistence is None


def test_vertical_translation_and_reversal_preserve_finite_lifetimes() -> None:
    signal = [0.0, 2.0, -0.2, 1.0, 0.1]
    shifted = [value + 7.25 for value in signal]
    original_lifetimes = sorted(pair.persistence for pair in finite_pairs(superlevel_h0(signal)))
    shifted_lifetimes = sorted(pair.persistence for pair in finite_pairs(superlevel_h0(shifted)))
    reversed_lifetimes = sorted(
        pair.persistence for pair in finite_pairs(superlevel_h0(list(reversed(signal))))
    )
    assert shifted_lifetimes == pytest.approx(original_lifetimes)
    assert reversed_lifetimes == pytest.approx(original_lifetimes)


def test_zero_bars_are_optional_and_ties_are_deterministic() -> None:
    assert len(superlevel_h0([1.0, 1.0])) == 1
    with_zero = superlevel_h0([1.0, 1.0], include_zero=True)
    assert len(with_zero) == 2
    assert sum(pair.essential for pair in with_zero) == 1
    assert [pair.birth_index for pair in with_zero if pair.essential] == [0]


@pytest.mark.parametrize("values", [[], [0.0, math.nan], [math.inf]])
def test_invalid_signal_is_rejected(values: list[float]) -> None:
    with pytest.raises(ValueError):
        superlevel_h0(values)

