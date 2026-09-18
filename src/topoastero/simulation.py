"""Deterministic signals used only for bootstrap and smoke validation."""

from __future__ import annotations

import math
import random


def deterministic_multimode_signal(
    *,
    samples: int,
    seed: int,
    fundamental_cycles: float,
    secondary_cycles: float,
    secondary_amplitude: float,
    noise_sigma: float,
) -> tuple[list[float], list[float]]:
    """Return a seeded two-mode signal on a normalized time interval."""

    if samples < 8:
        raise ValueError("The smoke signal requires at least eight samples")
    if noise_sigma < 0:
        raise ValueError("noise_sigma must be nonnegative")
    rng = random.Random(seed)
    time = [index / (samples - 1) for index in range(samples)]
    values = [
        math.sin(2.0 * math.pi * fundamental_cycles * value)
        + secondary_amplitude
        * math.sin(2.0 * math.pi * secondary_cycles * value + 0.37)
        + rng.gauss(0.0, noise_sigma)
        for value in time
    ]
    return time, values

