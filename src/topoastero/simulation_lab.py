"""Analytic and stochastic reference laboratory for TopoAstero Stage 4.

The module contains small, inspectable kernels rather than a mission-specific pipeline.  It
supports exact regression cases, stochastic damped oscillators, cadence integration and gaps,
surrogate nulls, multiplicity control, and Monte-Carlo precision planning.  Frequencies are in
microhertz, times are in days, and power spectral densities are in ``ppm^2 / uHz``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, NamedTuple

import numpy as np
from numpy.typing import NDArray
from scipy.signal import peak_prominences  # type: ignore[import-untyped]

from topoastero.classical import HarveyComponent, harvey_background
from topoastero.persistence import superlevel_h0

FloatArray = NDArray[np.float64]
NullKind = Literal[
    "background_only",
    "randomized_comb",
    "white_noise",
    "red_noise",
    "phase_randomized",
    "iaaft",
    "real_window",
]


@dataclass(frozen=True, slots=True)
class ModeSpec:
    """One Lorentzian oscillator component."""

    frequency_uHz: float
    height_ppm2_per_uHz: float
    linewidth_uHz: float
    degree: int = 0
    azimuthal_order: int = 0

    def __post_init__(self) -> None:
        positive = (self.frequency_uHz, self.height_ppm2_per_uHz, self.linewidth_uHz)
        if not all(math.isfinite(value) and value > 0 for value in positive):
            raise ValueError("mode frequency, height, and linewidth must be finite and positive")
        if self.degree < 0 or abs(self.azimuthal_order) > self.degree:
            raise ValueError("mode degree and azimuthal order are inconsistent")


@dataclass(frozen=True, slots=True)
class ObservationSpec:
    """Finite-duration observing operator applied to a stochastic spectrum."""

    duration_days: float
    cadence_seconds: float
    duty_cycle: float = 1.0
    gap_pattern: Literal["none", "random", "mission"] = "none"
    contamination_fraction: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.duration_days) or self.duration_days <= 0:
            raise ValueError("duration_days must be finite and positive")
        if not math.isfinite(self.cadence_seconds) or self.cadence_seconds <= 0:
            raise ValueError("cadence_seconds must be finite and positive")
        if not 0 < self.duty_cycle <= 1:
            raise ValueError("duty_cycle must lie in (0, 1]")
        if not 0 <= self.contamination_fraction < 1:
            raise ValueError("contamination_fraction must lie in [0, 1)")
        if self.gap_pattern == "none" and self.duty_cycle != 1.0:
            raise ValueError("gap_pattern='none' requires duty_cycle=1")


class SpectrumSimulation(NamedTuple):
    """A target mean PSD and one exponentially distributed periodogram realization."""

    frequency_uHz: FloatArray
    target_psd: FloatArray
    periodogram: FloatArray


class LightCurveSimulation(NamedTuple):
    """A simulated relative-flux light curve and its complete sampling mask."""

    time_days: FloatArray
    relative_flux: FloatArray
    observed: NDArray[np.bool_]


def linewidth_from_lifetime(lifetime_days: float) -> float:
    """Convert an exponentially damped mode lifetime to FWHM linewidth in microhertz."""

    if not math.isfinite(lifetime_days) or lifetime_days <= 0:
        raise ValueError("lifetime_days must be finite and positive")
    return 1e6 / (math.pi * lifetime_days * 86400.0)


def lifetime_from_linewidth(linewidth_uHz: float) -> float:
    """Invert :func:`linewidth_from_lifetime`."""

    if not math.isfinite(linewidth_uHz) or linewidth_uHz <= 0:
        raise ValueError("linewidth_uHz must be finite and positive")
    return 1e6 / (math.pi * linewidth_uHz * 86400.0)


def lorentzian_profile(frequency_uHz: NDArray[np.floating], mode: ModeSpec) -> FloatArray:
    """Evaluate a mode-height Lorentzian with the registered FWHM convention."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    if frequency.ndim != 1 or not np.all(np.isfinite(frequency)):
        raise ValueError("frequency_uHz must be a finite one-dimensional array")
    offset = 2.0 * (frequency - mode.frequency_uHz) / mode.linewidth_uHz
    return np.asarray(mode.height_ppm2_per_uHz / (1.0 + offset**2), dtype=np.float64)


def cadence_integration_response(
    frequency_uHz: NDArray[np.floating], integration_seconds: float
) -> FloatArray:
    """Return the boxcar-integration attenuation in power, ``sinc^2(pi f dt)``."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    if frequency.ndim != 1 or np.any(frequency < 0) or not np.all(np.isfinite(frequency)):
        raise ValueError("frequencies must be finite and nonnegative")
    if not math.isfinite(integration_seconds) or integration_seconds <= 0:
        raise ValueError("integration_seconds must be finite and positive")
    return np.asarray(np.sinc(frequency * 1e-6 * integration_seconds) ** 2, dtype=np.float64)


def target_oscillator_psd(
    frequency_uHz: NDArray[np.floating],
    *,
    modes: tuple[ModeSpec, ...],
    white_noise_ppm2_per_uHz: float,
    background: tuple[HarveyComponent, ...] = (),
    integration_seconds: float | None = None,
    contamination_fraction: float = 0.0,
) -> FloatArray:
    """Build the expected PSD for damped modes plus Harvey-like and white backgrounds.

    Contamination dilutes stellar variability by ``(1-c)^2``; instrumental white noise is not
    diluted.  Cadence integration is applied to all variable stellar components.
    """

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    if not 0 <= contamination_fraction < 1:
        raise ValueError("contamination_fraction must lie in [0, 1)")
    baseline = harvey_background(frequency, white_noise_ppm2_per_uHz, background)
    stellar = baseline - white_noise_ppm2_per_uHz
    for mode in modes:
        stellar += lorentzian_profile(frequency, mode)
    if integration_seconds is not None:
        stellar *= cadence_integration_response(frequency, integration_seconds)
    dilution = (1.0 - contamination_fraction) ** 2
    return np.asarray(white_noise_ppm2_per_uHz + dilution * stellar, dtype=np.float64)


def asymptotic_mode_comb(
    *,
    numax_uHz: float,
    dnu_uHz: float,
    radial_orders: int,
    radial_height_ppm2_per_uHz: float,
    lifetime_days: float,
    envelope_sigma_uHz: float | None = None,
    degree_visibilities: tuple[float, ...] = (1.0, 1.5, 0.5),
    rotational_splitting_uHz: float = 0.0,
) -> tuple[ModeSpec, ...]:
    """Construct a compact asymptotic p-mode pattern around ``numax``.

    Degree offsets are 0, 1/2, and -0.12 large separations for l=0, 1, and 2.  When rotation is
    non-zero each non-radial mode is split into equal-height azimuthal components.
    """

    if radial_orders < 1 or radial_orders % 2 == 0:
        raise ValueError("radial_orders must be a positive odd integer")
    if dnu_uHz <= 0 or radial_height_ppm2_per_uHz <= 0:
        raise ValueError("dnu and radial height must be positive")
    if rotational_splitting_uHz < 0:
        raise ValueError("rotational splitting cannot be negative")
    sigma = envelope_sigma_uHz or 2.5 * dnu_uHz
    linewidth = linewidth_from_lifetime(lifetime_days)
    offsets = (0.0, 0.5, -0.12)
    half = radial_orders // 2
    modes: list[ModeSpec] = []
    for order in range(-half, half + 1):
        radial_frequency = numax_uHz + order * dnu_uHz
        for degree, visibility in enumerate(degree_visibilities):
            center = radial_frequency + offsets[degree] * dnu_uHz
            envelope = math.exp(-0.5 * ((center - numax_uHz) / sigma) ** 2)
            azimuthal = range(-degree, degree + 1) if rotational_splitting_uHz > 0 else (0,)
            components = 2 * degree + 1 if rotational_splitting_uHz > 0 else 1
            for m_value in azimuthal:
                modes.append(
                    ModeSpec(
                        center + m_value * rotational_splitting_uHz,
                        radial_height_ppm2_per_uHz * visibility * envelope / components,
                        linewidth,
                        degree,
                        m_value,
                    )
                )
    return tuple(sorted(modes, key=lambda item: item.frequency_uHz))


def simulate_periodogram(
    observation: ObservationSpec,
    *,
    modes: tuple[ModeSpec, ...],
    white_noise_ppm2_per_uHz: float,
    background: tuple[HarveyComponent, ...] = (),
    seed: int,
) -> SpectrumSimulation:
    """Draw an independent exponential periodogram about the exact target PSD."""

    sample_count = max(
        8, math.floor(observation.duration_days * 86400 / observation.cadence_seconds)
    )
    frequency = np.asarray(
        np.fft.rfftfreq(sample_count, observation.cadence_seconds) * 1e6,
        dtype=np.float64,
    )
    target = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=white_noise_ppm2_per_uHz,
        background=background,
        integration_seconds=observation.cadence_seconds,
        contamination_fraction=observation.contamination_fraction,
    )
    periodogram = np.random.default_rng(seed).exponential(target)
    return SpectrumSimulation(frequency, target, np.asarray(periodogram, dtype=np.float64))


def _random_mask(
    sample_count: int, duty_cycle: float, rng: np.random.Generator
) -> NDArray[np.bool_]:
    target = max(4, min(sample_count, round(sample_count * duty_cycle)))
    order = rng.permutation(sample_count)
    mask = np.zeros(sample_count, dtype=bool)
    mask[order[:target]] = True
    return mask


def mission_interval_mask(
    time_days: NDArray[np.floating], intervals_days: NDArray[np.floating]
) -> NDArray[np.bool_]:
    """Evaluate a compact mission-window interval table on a time grid."""

    time = np.asarray(time_days, dtype=np.float64)
    intervals = np.asarray(intervals_days, dtype=np.float64)
    if time.ndim != 1 or intervals.ndim != 2 or intervals.shape[1] != 2:
        raise ValueError("time must be 1-D and intervals must have shape (n, 2)")
    if np.any(intervals[:, 1] < intervals[:, 0]):
        raise ValueError("window interval ends must not precede starts")
    mask = np.zeros(time.size, dtype=bool)
    for start, stop in intervals:
        mask |= (time >= start) & (time <= stop)
    return mask


def simulate_light_curve(
    observation: ObservationSpec,
    *,
    modes: tuple[ModeSpec, ...],
    white_noise_ppm2_per_uHz: float,
    background: tuple[HarveyComponent, ...] = (),
    seed: int,
    mission_intervals_days: NDArray[np.floating] | None = None,
) -> LightCurveSimulation:
    """Synthesize a Gaussian time series whose expected FFT PSD matches the target spectrum."""

    count = max(8, math.floor(observation.duration_days * 86400 / observation.cadence_seconds))
    time = np.arange(count, dtype=np.float64) * observation.cadence_seconds / 86400.0
    frequency = np.fft.rfftfreq(count, observation.cadence_seconds) * 1e6
    target = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=white_noise_ppm2_per_uHz,
        background=background,
        integration_seconds=observation.cadence_seconds,
        contamination_fraction=observation.contamination_fraction,
    )
    rng = np.random.default_rng(seed)
    expected_squared_modulus = target * count / (2.0 * observation.cadence_seconds * 1e6)
    coefficients = (
        rng.normal(size=frequency.size) + 1j * rng.normal(size=frequency.size)
    ) * np.sqrt(expected_squared_modulus / 2.0)
    coefficients[0] = 0.0
    if count % 2 == 0:
        coefficients[-1] = complex(rng.normal() * math.sqrt(expected_squared_modulus[-1]), 0.0)
    flux = np.asarray(np.fft.irfft(coefficients, n=count), dtype=np.float64)
    if observation.gap_pattern == "none":
        observed: NDArray[np.bool_] = np.ones(count, dtype=np.bool_)
    elif observation.gap_pattern == "random":
        observed = _random_mask(count, observation.duty_cycle, rng)
    else:
        if mission_intervals_days is None:
            raise ValueError("mission gaps require mission_intervals_days")
        observed = mission_interval_mask(time, mission_intervals_days)
    return LightCurveSimulation(time, flux, observed)


def delay_embedding(signal: NDArray[np.floating], lag: int) -> tuple[FloatArray, FloatArray]:
    """Return a two-dimensional delay embedding ``(x_t, x_{t+lag})``."""

    values = np.asarray(signal, dtype=np.float64)
    if values.ndim != 1 or values.size < 4 or not np.all(np.isfinite(values)):
        raise ValueError("signal must contain at least four finite samples")
    if not 0 < lag < values.size:
        raise ValueError("lag must be between one and len(signal)-1")
    return values[:-lag], values[lag:]


def sinusoid_delay_axes(amplitude: float, phase_lag_radians: float) -> tuple[float, float]:
    """Return the semimajor and semiminor axes of an ideal sinusoidal delay ellipse."""

    if amplitude <= 0 or not math.isfinite(amplitude) or not math.isfinite(phase_lag_radians):
        raise ValueError("amplitude must be positive and phase lag finite")
    cosine = math.cos(phase_lag_radians)
    axes = sorted(
        (
            amplitude * math.sqrt(max(0.0, 1.0 + cosine)),
            amplitude * math.sqrt(max(0.0, 1.0 - cosine)),
        ),
        reverse=True,
    )
    return float(axes[0]), float(axes[1])


def sinusoid_ellipse_residual(
    x: NDArray[np.floating],
    y: NDArray[np.floating],
    *,
    amplitude: float,
    phase_lag_radians: float,
) -> FloatArray:
    """Evaluate ``x²+y²-2 cos(phi)xy-A² sin²(phi)`` for delay points."""

    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    if left.shape != right.shape:
        raise ValueError("x and y must have the same shape")
    cosine = math.cos(phase_lag_radians)
    return np.asarray(
        left**2
        + right**2
        - 2.0 * cosine * left * right
        - amplitude**2 * math.sin(phase_lag_radians) ** 2,
        dtype=np.float64,
    )


def fold_frequencies(frequency_uHz: NDArray[np.floating], trial_dnu_uHz: float) -> FloatArray:
    """Fold frequencies modulo a trial large separation."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    if frequency.ndim != 1 or not np.all(np.isfinite(frequency)) or trial_dnu_uHz <= 0:
        raise ValueError("finite one-dimensional frequencies and positive trial_dnu are required")
    return np.asarray(np.mod(frequency, trial_dnu_uHz), dtype=np.float64)


def ridge_mismatch_rms(order_count: int, slope_error_uHz: float) -> float:
    """Exact unwrapped RMS ridge displacement for centered consecutive orders."""

    if order_count < 1:
        raise ValueError("order_count must be positive")
    if not math.isfinite(slope_error_uHz):
        raise ValueError("slope_error_uHz must be finite")
    return abs(slope_error_uHz) * math.sqrt((order_count**2 - 1.0) / 12.0)


def persistence_prominence_pairs(values: NDArray[np.floating]) -> tuple[FloatArray, FloatArray]:
    """Return matched finite H0 persistence and classical prominence for interior peaks.

    Equality holds for a path graph when prominence uses the same elder-rule merge saddle and
    boundary-reaching/global peaks are excluded.  The function enforces that explicit domain.
    """

    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 3 or not np.all(np.isfinite(signal)):
        raise ValueError("values must be a finite one-dimensional signal of length at least three")
    pairs = [pair for pair in superlevel_h0(signal.tolist()) if not pair.essential]
    peaks = np.asarray([pair.birth_index for pair in pairs], dtype=int)
    if peaks.size == 0:
        return np.asarray([], dtype=np.float64), np.asarray([], dtype=np.float64)
    persistence = np.asarray(
        [pair.birth - float(pair.death) for pair in pairs if pair.death is not None],
        dtype=np.float64,
    )
    prominence = np.asarray(peak_prominences(signal, peaks)[0], dtype=np.float64)
    return persistence, prominence


def phase_randomized_surrogate(values: NDArray[np.floating], *, seed: int) -> FloatArray:
    """Preserve the Fourier amplitudes of a series while randomizing nonterminal phases."""

    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.all(np.isfinite(signal)):
        raise ValueError("values must contain at least four finite samples")
    centered = signal - np.mean(signal)
    transform = np.fft.rfft(centered)
    rng = np.random.default_rng(seed)
    stop = transform.size - 1 if signal.size % 2 == 0 else transform.size
    phases = rng.uniform(0.0, 2.0 * math.pi, max(0, stop - 1))
    transform[1:stop] = np.abs(transform[1:stop]) * np.exp(1j * phases)
    return np.asarray(np.fft.irfft(transform, n=signal.size) + np.mean(signal), dtype=np.float64)


def iaaft_surrogate(
    values: NDArray[np.floating], *, seed: int, iterations: int = 100
) -> FloatArray:
    """Generate an iterative amplitude-adjusted Fourier-transform surrogate."""

    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.all(np.isfinite(signal)):
        raise ValueError("values must contain at least four finite samples")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = np.random.default_rng(seed)
    target_sorted = np.sort(signal)
    target_amplitude = np.abs(np.fft.rfft(signal - np.mean(signal)))
    surrogate = rng.permutation(signal)
    for _ in range(iterations):
        transform = np.fft.rfft(surrogate - np.mean(surrogate))
        phases = np.exp(1j * np.angle(transform))
        spectrum_matched = np.fft.irfft(target_amplitude * phases, n=signal.size)
        ranks = np.argsort(np.argsort(spectrum_matched, kind="mergesort"), kind="mergesort")
        surrogate = target_sorted[ranks]
    return np.asarray(surrogate, dtype=np.float64)


def generate_null(
    kind: NullKind,
    *,
    samples: int,
    seed: int,
    reference: NDArray[np.floating] | None = None,
    duty_cycle: float = 1.0,
    mission_mask: NDArray[np.bool_] | None = None,
) -> FloatArray:
    """Generate one registered null-family realization on a normalized index grid."""

    if samples < 8:
        raise ValueError("samples must be at least eight")
    rng = np.random.default_rng(seed)
    if kind == "white_noise":
        values = rng.normal(size=samples)
    elif kind in {"red_noise", "background_only"}:
        innovations = rng.normal(size=samples)
        alpha = 0.85 if kind == "red_noise" else 0.65
        values = np.empty(samples, dtype=np.float64)
        values[0] = innovations[0]
        for index in range(1, samples):
            values[index] = alpha * values[index - 1] + innovations[index]
    elif kind == "randomized_comb":
        x = np.arange(samples, dtype=np.float64)
        values = rng.normal(scale=0.7, size=samples)
        for center in rng.uniform(0, samples, 8):
            values += np.exp(-0.5 * ((x - center) / 1.5) ** 2)
    elif kind in {"phase_randomized", "iaaft"}:
        if reference is None or np.asarray(reference).size != samples:
            raise ValueError(f"{kind} requires a reference with exactly samples values")
        values = (
            phase_randomized_surrogate(np.asarray(reference), seed=seed)
            if kind == "phase_randomized"
            else iaaft_surrogate(np.asarray(reference), seed=seed, iterations=40)
        )
    elif kind == "real_window":
        values = rng.normal(size=samples)
        if mission_mask is None or np.asarray(mission_mask).shape != (samples,):
            raise ValueError("real_window requires a Boolean mission_mask")
        values = values * np.asarray(mission_mask, dtype=bool)
    else:
        raise ValueError(f"unsupported null kind: {kind}")
    if duty_cycle < 1.0 and kind != "real_window":
        values = values * _random_mask(samples, duty_cycle, rng)
    return np.asarray(values, dtype=np.float64)


def folded_contrast(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    *,
    trial_dnu_uHz: float,
    bins: int = 24,
) -> float:
    """Compute a robust folded-spectrum ridge contrast."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    values = np.asarray(power, dtype=np.float64)
    if frequency.shape != values.shape or frequency.ndim != 1 or bins < 4:
        raise ValueError("frequency/power shapes and bin count are invalid")
    phase = fold_frequencies(frequency, trial_dnu_uHz) / trial_dnu_uHz
    index = np.minimum((phase * bins).astype(int), bins - 1)
    sums = np.bincount(index, weights=values, minlength=bins)
    counts = np.bincount(index, minlength=bins)
    profile = sums / np.maximum(counts, 1)
    median = float(np.median(profile))
    mad = float(np.median(np.abs(profile - median)))
    scale = max(1.4826 * mad, np.finfo(float).eps)
    return float((np.max(profile) - median) / scale)


def max_statistic_threshold(statistics: NDArray[np.floating], *, alpha: float) -> float:
    """Calibrate a family-wise threshold from row-wise maxima of a null statistic matrix."""

    matrix = np.asarray(statistics, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or not np.all(np.isfinite(matrix)):
        raise ValueError("statistics must be a finite matrix with at least two realizations")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1)")
    maxima = np.max(matrix, axis=1)
    rank = min(maxima.size - 1, math.ceil((1.0 - alpha) * (maxima.size + 1)) - 1)
    return float(np.sort(maxima)[rank])


def empirical_pvalues(
    null_maxima: NDArray[np.floating], observed: NDArray[np.floating]
) -> FloatArray:
    """Compute conservative plus-one empirical p-values against a maximum null."""

    null = np.asarray(null_maxima, dtype=np.float64)
    values = np.asarray(observed, dtype=np.float64)
    if null.ndim != 1 or values.ndim != 1 or null.size < 1:
        raise ValueError("null_maxima and observed must be nonempty vectors")
    return np.asarray(
        [(1 + np.count_nonzero(null >= value)) / (null.size + 1) for value in values],
        dtype=np.float64,
    )


def benjamini_hochberg(pvalues: NDArray[np.floating], *, q: float) -> NDArray[np.bool_]:
    """Return Benjamini-Hochberg rejections under the standard independent/PRDS rule."""

    values = np.asarray(pvalues, dtype=np.float64)
    if values.ndim != 1 or not np.all((values >= 0) & (values <= 1)):
        raise ValueError("pvalues must be a vector in [0, 1]")
    if not 0 < q < 1:
        raise ValueError("q must lie in (0, 1)")
    order = np.argsort(values)
    ordered = values[order]
    passing = np.flatnonzero(ordered <= q * np.arange(1, values.size + 1) / values.size)
    rejected = np.zeros(values.size, dtype=bool)
    if passing.size:
        rejected[order[: passing[-1] + 1]] = True
    return rejected


def monte_carlo_repetitions(probability: float, target_standard_error: float) -> int:
    """Return ``ceil(p(1-p)/SE^2)`` repetitions for a binomial operating characteristic."""

    if not 0 < probability < 1 or not 0 < target_standard_error < 0.5:
        raise ValueError("probability and target_standard_error are outside their valid ranges")
    return math.ceil(probability * (1.0 - probability) / target_standard_error**2)


def percentile_interval(
    values: NDArray[np.floating], *, level: float = 0.95
) -> tuple[float, float]:
    """Return an equal-tailed empirical interval."""

    samples = np.asarray(values, dtype=np.float64)
    if samples.ndim != 1 or samples.size < 2 or not np.all(np.isfinite(samples)):
        raise ValueError("values must be a finite vector with at least two samples")
    if not 0 < level < 1:
        raise ValueError("level must lie in (0, 1)")
    tail = 0.5 * (1.0 - level)
    lower, upper = np.quantile(samples, [tail, 1.0 - tail])
    return float(lower), float(upper)
