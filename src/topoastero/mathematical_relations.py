"""Stage 9 conditional identities and bounds; no estimator-utility claim.

Angles are in cycles, frequencies in microhertz, and logarithmic budgets are
dimensionless. These functions never infer a stochastic bound from a smoothed
or background-fitted spectrum without an externally supplied nuisance budget.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def _positive(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _nonnegative(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def path_peak_prominences(values: Sequence[float]) -> dict[int, float | None]:
    """Independent O(n^2) elder prominence of strict local maxima of a path.

    Endpoints have one neighbor. The unique global maximum is essential (None).
    Distinct finite vertex heights are required; tied/flat peaks need an explicit
    elder and plateau policy and are deliberately excluded from this identity.
    """

    heights = np.asarray(values, dtype=float)
    if heights.ndim != 1 or not heights.size or not np.all(np.isfinite(heights)):
        raise ValueError("a nonempty finite one-dimensional path is required")
    if np.unique(heights).size != heights.size:
        raise ValueError("distinct vertex heights are required")
    peaks = [
        i for i, height in enumerate(heights)
        if (i == 0 or height > heights[i - 1])
        and (i == heights.size - 1 or height > heights[i + 1])
    ]
    result: dict[int, float | None] = {}
    for peak in peaks:
        higher = [other for other in peaks if heights[other] > heights[peak]]
        if not higher:
            result[peak] = None
            continue
        saddle = max(float(np.min(heights[min(peak, other): max(peak, other) + 1])) for other in higher)
        result[peak] = float(heights[peak] - saddle)
    return result


def delay_ellipse_semiaxes(amplitude: float, frequency_hz: float, delay_seconds: float) -> tuple[float, float]:
    """Continuous sinusoid's two-coordinate delay ellipse, largest axis first."""

    amplitude = _positive(amplitude, "amplitude")
    frequency_hz = _positive(frequency_hz, "frequency_hz")
    delay_seconds = _nonnegative(delay_seconds, "delay_seconds")
    cosine = abs(math.cos(2 * math.pi * frequency_hz * delay_seconds))
    return amplitude * math.sqrt(1 + cosine), amplitude * math.sqrt(max(0.0, 1 - cosine))


def circle_distance(left: float, right: float) -> float:
    """Geodesic distance on R/Z, expressed in cycles."""

    if not (math.isfinite(left) and math.isfinite(right)):
        raise ValueError("phases must be finite")
    delta = (left - right) % 1.0
    return min(delta, 1 - delta)


@dataclass(frozen=True)
class RidgeDriftBound:
    """Bounds conditional on peaks occupying consecutive *trial* rows.

    ``candidate_edges_guaranteed`` certifies only the phase threshold, not
    retention by the graph's local-maximum/top-five candidate pruning.
    """

    mismatch_cycles: float
    lower_jump_cycles: float
    upper_jump_cycles: float
    candidate_edges_guaranteed: bool
    candidate_edges_excluded: bool

    def coherence_ceiling(self, track_length: int, valid_orders: int, jump_limit: float) -> float:
        """Stage 8 target-track coherence ceiling, assuming its contrast factor <= 1."""

        if not (2 <= track_length <= valid_orders):
            raise ValueError("a candidate track needs 2 <= length <= valid_orders")
        limit = _positive(jump_limit, "jump_limit")
        if self.candidate_edges_excluded:
            return 0.0
        return (track_length / valid_orders) * math.exp(-self.lower_jump_cycles / limit)


def ridge_drift_bound(
    true_spacing_uHz: float,
    trial_spacing_uHz: float,
    curvature_step_uHz: float,
    phase_error_cycles: float,
    *, jump_limit: float = 0.17,
) -> RidgeDriftBound:
    """Adjacent target-phase bounds on the finite cylinder.

    nu_q = nu_0 + q Delta_* + kappa_q, |kappa_(q+1)-kappa_q| <= C. Each retained target
    candidate is within ε circular cycles of the physical phase, and successive
    peaks occupy consecutive trial rows q=floor(nu/Delta). Missing orders, row skips
    at half aliases, row collisions at double aliases, candidate pruning, and
    competing/rerouted tracks are outside this conditional result.
    """

    true_spacing_uHz = _positive(true_spacing_uHz, "true_spacing_uHz")
    trial_spacing_uHz = _positive(trial_spacing_uHz, "trial_spacing_uHz")
    curvature_step_uHz = _nonnegative(curvature_step_uHz, "curvature_step_uHz")
    phase_error_cycles = _nonnegative(phase_error_cycles, "phase_error_cycles")
    limit = _positive(jump_limit, "jump_limit")
    if limit > 0.5:
        raise ValueError("jump_limit must not exceed a half cycle")
    mismatch = circle_distance(true_spacing_uHz / trial_spacing_uHz, 0.0)
    tolerance = curvature_step_uHz / trial_spacing_uHz + 2 * phase_error_cycles
    lower = max(0.0, mismatch - tolerance)
    upper = min(0.5, mismatch + tolerance)
    return RidgeDriftBound(mismatch, lower, upper, upper <= limit, lower > limit)


def log_ratio_perturbation_bound(
    power_relative_log: float, background_relative_log: float
) -> float:
    """Fixed-mask sup bound for log(P/B), with positive P and B."""

    return _nonnegative(power_relative_log, "power_relative_log") + _nonnegative(
        background_relative_log, "background_relative_log"
    )


def gamma_log_tail_bound(epsilon: float, shape: float, bins: int = 1) -> float:
    """Union bound for max |log X_i|, X_i ~ Gamma(k, scale=1/k).

    No independence between bins is needed for the union bound; each marginal
    must have this shape. Clip probability to one. Applies before smoothing.
    """

    epsilon = _nonnegative(epsilon, "epsilon")
    shape = _positive(shape, "shape")
    if bins < 1:
        raise ValueError("bins must be positive")
    upper = math.exp(-shape * math.expm1(epsilon) + shape * epsilon) if epsilon < 700 else 0.0
    lower = math.exp(-shape * (epsilon + math.expm1(-epsilon)))
    return min(1.0, bins * (upper + lower))


def gamma_log_uniform_radius(shape: float, bins: int, alpha: float) -> float:
    """Smallest nonnegative epsilon certified by Chernoff and union bounds."""

    _positive(shape, "shape")
    if bins < 1 or not (math.isfinite(alpha) and 0 < alpha < 1):
        raise ValueError("bins must be positive and 0 < alpha < 1")
    upper = 1.0
    while gamma_log_tail_bound(upper, shape, bins) > alpha:
        upper *= 2
    lower = 0.0
    for _ in range(64):
        middle = (lower + upper) / 2
        if gamma_log_tail_bound(middle, shape, bins) <= alpha:
            upper = middle
        else:
            lower = middle
    return upper


def r02_angle_discrepancy(numerator_uHz: float, dipole_spacing_uHz: float, trial_spacing_uHz: float) -> float:
    """Exact |r02 - unwrapped angular proxy| for correctly identified modes.

    The numerator is nu_(n,0)-nu_(n-1,2). The phase difference must have the
    same lift as the signed numerator; modulo-only angles can be ambiguous.
    """

    numerator = float(numerator_uHz)
    if not math.isfinite(numerator):
        raise ValueError("numerator must be finite")
    return abs(numerator) * abs(
        1 / _positive(dipole_spacing_uHz, "dipole_spacing_uHz")
        - 1 / _positive(trial_spacing_uHz, "trial_spacing_uHz")
    )


@dataclass(frozen=True)
class ScalingLogBounds:
    """Exact conditional log-radius for uncorrected seismic scaling monomials."""

    density: float
    radius: float
    mass: float
    gravity: float

    def relative_interval(self, quantity: str) -> tuple[float, float]:
        """Relative error interval [exp(-L)-1, exp(L)-1]."""

        if quantity not in {"density", "radius", "mass", "gravity"}:
            raise ValueError("unknown quantity")
        bound = getattr(self, quantity)
        return math.expm1(-bound), math.expm1(bound)


def scaling_log_bounds(
    dnu_log_error: float, numax_log_error: float, teff_log_error: float,
    *, dnu_systematic_log: float, numax_systematic_log: float,
) -> ScalingLogBounds:
    """Propagate separate estimator and astrophysical corrections in log space.

    Requires independent externally assessed systematic allowances. This is
    algebra for scaling monomials, not a theorem that they hold for all stars.
    """

    dnu = _nonnegative(dnu_log_error, "dnu_log_error") + _nonnegative(dnu_systematic_log, "dnu_systematic_log")
    numax = _nonnegative(numax_log_error, "numax_log_error") + _nonnegative(numax_systematic_log, "numax_systematic_log")
    teff = _nonnegative(teff_log_error, "teff_log_error")
    return ScalingLogBounds(2 * dnu, numax + 2 * dnu + 0.5 * teff,
                            3 * numax + 4 * dnu + 1.5 * teff, numax + 0.5 * teff)
