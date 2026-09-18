from __future__ import annotations

import pytest

from topoastero.simulation import deterministic_multimode_signal


def test_seeded_signal_is_repeatable_and_changes_with_seed() -> None:
    kwargs = {
        "samples": 32,
        "fundamental_cycles": 2.0,
        "secondary_cycles": 5.0,
        "secondary_amplitude": 0.3,
        "noise_sigma": 0.01,
    }
    first = deterministic_multimode_signal(seed=7, **kwargs)
    second = deterministic_multimode_signal(seed=7, **kwargs)
    third = deterministic_multimode_signal(seed=8, **kwargs)
    assert first == second
    assert first[0] == third[0]
    assert first[1] != third[1]
    assert first[0][0] == 0.0
    assert first[0][-1] == 1.0


def test_signal_validation() -> None:
    base = {
        "seed": 1,
        "fundamental_cycles": 2.0,
        "secondary_cycles": 5.0,
        "secondary_amplitude": 0.3,
    }
    with pytest.raises(ValueError, match="eight"):
        deterministic_multimode_signal(samples=7, noise_sigma=0.0, **base)
    with pytest.raises(ValueError, match="nonnegative"):
        deterministic_multimode_signal(samples=8, noise_sigma=-0.1, **base)

