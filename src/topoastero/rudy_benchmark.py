"""Stage 10 numerical observation operators and auditable uncertainty summaries.

This module needs only the base dependencies. Mission FITS/Lightkurve integration
lives in the workflow. All random functions require a seed; invalid or unsupported
observations are rejected, rather than silently filled across long gaps.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d  # type: ignore[import-untyped]

from topoastero.classical import estimate_envelope, estimate_large_separation
from topoastero.spectral_topology import (
    NormalizationMethod,
    autocorrelation_spacing_scores,
    comb_score_scan,
    localized_peak_persistence,
    normalize_spectrum,
    persistence_weighted_location,
    psps_spacing_scores,
)

FloatArray = NDArray[np.float64]


def _vector(values: Sequence[float] | NDArray[np.floating], name: str) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size < 3 or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite vector with at least three elements")
    return array


def rebin_spectrum(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    centers_uHz: NDArray[np.floating],
) -> FloatArray:
    """Average native ordinates in uniform bins; reject any unsupported output bin.

    A finer grid than the native spacing is interpolated *inside* the source range
    for the registered resolution diagnostic only. It adds no independent data.
    """
    frequency = _vector(frequency_uHz, "frequency")
    values = _vector(power, "power")
    centers = _vector(centers_uHz, "centers")
    if values.shape != frequency.shape or np.any(values <= 0):
        raise ValueError("power must be positive and match frequency")
    if np.any(np.diff(frequency) <= 0) or np.any(np.diff(centers) <= 0):
        raise ValueError("frequency axes must be strictly increasing")
    step = float(np.median(np.diff(centers)))
    if not np.allclose(np.diff(centers), step, rtol=1e-6):
        raise ValueError("output centers must be uniform")
    edges = np.r_[centers - step / 2, centers[-1] + step / 2]
    count = np.histogram(frequency, bins=edges)[0]
    total = np.histogram(frequency, bins=edges, weights=values)[0]
    if centers[0] < frequency[0] or centers[-1] > frequency[-1]:
        raise ValueError("rebinning may not extrapolate")
    result = np.interp(centers, frequency, values)
    filled = count > 0
    result[filled] = total[filled] / count[filled]
    return np.asarray(result, dtype=np.float64)


def integrate_cadences(
    source_time_seconds: NDArray[np.floating],
    source_flux_ppm: NDArray[np.floating],
    target_centers_seconds: NDArray[np.floating],
    *,
    exposure_seconds: float,
    maximum_gap_seconds: float,
) -> tuple[FloatArray, NDArray[np.bool_]]:
    """Integrate a piecewise-linear light curve over each target exposure.

    Long source gaps invalidate every overlapping target exposure. The returned
    mask must be applied to time and flux together. No extrapolation is permitted.
    """
    time = _vector(source_time_seconds, "source time")
    flux = _vector(source_flux_ppm, "source flux")
    centers = _vector(target_centers_seconds, "target centers")
    if flux.shape != time.shape or np.any(np.diff(time) <= 0) or np.any(np.diff(centers) <= 0):
        raise ValueError("matching flux and strictly increasing source/target times are required")
    if not math.isfinite(exposure_seconds) or not math.isfinite(maximum_gap_seconds) or exposure_seconds <= 0 or maximum_gap_seconds <= 0:
        raise ValueError("exposure and maximum gap must be positive finite seconds")
    widths = np.diff(time)
    slopes = np.diff(flux) / widths
    integral = np.r_[0.0, np.cumsum(0.5 * (flux[:-1] + flux[1:]) * widths)]

    def primitive(at: FloatArray) -> FloatArray:
        indices = np.clip(np.searchsorted(time, at, side="right") - 1, 0, time.size - 2)
        delta = at - time[indices]
        return np.asarray(integral[indices] + flux[indices] * delta + 0.5 * slopes[indices] * delta**2, dtype=np.float64)

    lower = centers - exposure_seconds / 2
    upper = centers + exposure_seconds / 2
    valid = (lower >= time[0]) & (upper <= time[-1])
    gaps = widths > maximum_gap_seconds
    # Prefix counts make long-gap overlap checks linear in the number of samples.
    prefix = np.r_[0, np.cumsum(gaps)]
    first = np.clip(np.searchsorted(time, lower, side="right") - 1, 0, widths.size - 1)
    last = np.clip(np.searchsorted(time, upper, side="left"), 1, widths.size)
    valid &= (prefix[last] - prefix[first]) == 0
    values = (primitive(upper) - primitive(lower)) / exposure_seconds
    values[~valid] = np.nan
    return values, np.asarray(valid, dtype=np.bool_)


def gaussian_psd_realization(
    expected_psd_ppm2_per_uHz: NDArray[np.floating],
    *,
    sample_count: int,
    cadence_seconds: float,
    seed: int,
) -> FloatArray:
    """Draw a real stationary Gaussian signal from a one-sided density in ppm²/µHz.

    The input must match ``rfftfreq(sample_count, cadence_seconds)``. DC is removed;
    the real Nyquist coefficient uses the correct undoubled endpoint convention.
    """
    density = _vector(expected_psd_ppm2_per_uHz, "expected PSD")
    if sample_count < 4 or sample_count // 2 + 1 != density.size or np.any(density < 0):
        raise ValueError("nonnegative PSD must match the real FFT grid")
    if not math.isfinite(cadence_seconds) or cadence_seconds <= 0:
        raise ValueError("cadence must be positive finite seconds")
    rng = np.random.default_rng(seed)
    scale = np.sqrt(density * 1e6 * sample_count / (4 * cadence_seconds))
    transform = scale * (rng.normal(size=density.size) + 1j * rng.normal(size=density.size))
    transform[0] = 0.0
    if sample_count % 2 == 0:
        transform[-1] = math.sqrt(density[-1] * 1e6 * sample_count / cadence_seconds) * rng.normal()
    return np.asarray(np.fft.irfft(transform, n=sample_count), dtype=np.float64)


def linear_interpolation_response(
    frequency_uHz: NDArray[np.floating], time_days: NDArray[np.floating], cadence_seconds: float
) -> FloatArray:
    """Mean power response of interpolation from a uniform cadence grid.

    For fractional grid coordinate s, the two-tap response is
    1 - 2*s*(1-s)*(1-cos(2*pi*f*dt)). Averaging over observed coordinates
    gives the registered surrogate nuisance correction; cross-frequency/window
    covariance is still handled by sampling and LS, not by this scalar formula.
    """
    frequency = _vector(frequency_uHz, "frequency")
    time = _vector(time_days, "time")
    if np.any(frequency < 0) or np.any(np.diff(time) <= 0) or not math.isfinite(cadence_seconds) or cadence_seconds <= 0:
        raise ValueError("nonnegative frequencies, ordered times and positive cadence required")
    coordinates = (time - time[0]) * 86400 / cadence_seconds
    fractional = coordinates - np.floor(coordinates)
    mean_product = float(np.mean(fractional * (1 - fractional)))
    response = 1 - 2 * mean_product * (1 - np.cos(2 * np.pi * frequency * 1e-6 * cadence_seconds))
    if np.any(response <= 0):
        raise ValueError("interpolation response is singular at the requested frequencies")
    return np.asarray(response, dtype=np.float64)


def weighted_segment_bootstrap(
    spectra: NDArray[np.floating],
    cadence_counts: Sequence[int],
    *,
    replicates: int,
    seed: int,
) -> FloatArray:
    """Resample nonoverlapping months, then average their PSDs by retained exposure.

    These intervals describe the monthly averaged-spectrum estimator, not a
    confidence interval for the coherent absolute-time full-span periodogram.
    """
    matrix = np.asarray(spectra, dtype=np.float64)
    weights = np.asarray(cadence_counts, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 3 or matrix.shape[1] < 3 or weights.shape != (matrix.shape[0],):
        raise ValueError("at least three matching segment spectra and weights are required")
    if not np.all(np.isfinite(matrix)) or np.any(matrix <= 0) or not np.all(np.isfinite(weights)) or np.any(weights <= 0):
        raise ValueError("spectra and exposure weights must be positive finite values")
    if replicates < 8:
        raise ValueError("at least eight bootstrap replicates are required")
    rng = np.random.default_rng(seed)
    indices = rng.integers(matrix.shape[0], size=(replicates, matrix.shape[0]))
    selected_weights = weights[indices]
    return np.asarray(np.sum(matrix[indices] * selected_weights[:, :, None], axis=1) / selected_weights.sum(axis=1)[:, None], dtype=np.float64)


@dataclass(frozen=True, slots=True)
class MonteCarloTail:
    """Conditional plus-one tail estimate and finite simulation precision."""

    pvalue: float
    exceedances: int
    realizations: int
    standard_error: float
    wilson95_lower: float
    wilson95_upper: float


def monte_carlo_tail(observed: float, null_maxima: NDArray[np.floating]) -> MonteCarloTail:
    """Count upper-tail ties conservatively; uncertainty is for the exceedance rate."""
    draws = _vector(null_maxima, "null maxima")
    if not math.isfinite(observed):
        raise ValueError("observed statistic must be finite")
    count = int(np.count_nonzero(draws >= observed))
    total = draws.size
    pvalue = (count + 1) / (total + 1)
    rate = count / total
    z = 1.959963984540054
    center = (rate + z**2 / (2 * total)) / (1 + z**2 / total)
    half = z * math.sqrt(rate * (1 - rate) / total + z**2 / (4 * total**2)) / (1 + z**2 / total)
    return MonteCarloTail(pvalue, count, total, math.sqrt(pvalue * (1 - pvalue) / (total + 1)), max(0.0, center - half), min(1.0, center + half))


def added_noise_sigma(
    target_white_psd: float, source_white_psd: float, cadence_seconds: float, duty_cycle: float
) -> float:
    """Additional white-noise sigma in ppm under the LS full-span PSD convention.

    A smaller target noise floor adds zero noise. Existing Kepler noise is never
    subtracted from the light curve. Duty corrects the full-span LS density scale.
    """
    if not all(math.isfinite(x) for x in (target_white_psd, source_white_psd, cadence_seconds, duty_cycle)) or min(target_white_psd, source_white_psd) < 0 or cadence_seconds <= 0 or not 0 < duty_cycle <= 1:
        raise ValueError("noise floors, cadence, and duty must be in their physical domains")
    return math.sqrt(max(0.0, target_white_psd - source_white_psd) * 1e6 * duty_cycle / (2 * cadence_seconds))


def holm_adjust(pvalues: Sequence[float]) -> FloatArray:
    """Familywise correction across the reported maximum-statistic families."""
    values = _vector(pvalues, "p-values")
    if np.any(values < 0) or np.any(values > 1):
        raise ValueError("p-values must lie in [0,1]")
    order = np.argsort(values, kind="stable")
    sorted_adjusted = np.minimum(1.0, np.maximum.accumulate(values[order] * np.arange(values.size, 0, -1)))
    result = np.empty_like(values)
    result[order] = sorted_adjusted
    return result


def spectrum_diagnostics(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    background: NDArray[np.floating],
    *,
    normalization: NormalizationMethod = "log_ratio",
    peak_smoothing_uHz: float = 1.0,
    background_sigma_fraction: float = 0.10,
    comb_trials_uHz: NDArray[np.floating] | None = None,
    search_uHz: tuple[float, float] = (1700.0, 2500.0),
) -> dict[str, float]:
    """Classical, peak-persistence, ACF and PSPS diagnostics on one uniform PSD.

    The largest finite peak lifetime and maximum comb score each search the
    entire registered frequency/trial family. They require matching null maxima.
    """
    frequency = _vector(frequency_uHz, "frequency")
    values = _vector(power, "power")
    continuum = _vector(background, "background")
    if values.shape != frequency.shape or continuum.shape != values.shape or np.any(values <= 0) or np.any(continuum <= 0):
        raise ValueError("positive spectrum and background must match frequency")
    step = float(np.median(np.diff(frequency)))
    if step <= 0 or not np.allclose(np.diff(frequency), step, rtol=1e-6) or peak_smoothing_uHz <= 0 or background_sigma_fraction < 0:
        raise ValueError("uniform frequencies and valid smoothing/background sigma are required")
    trials = np.linspace(20, 300, 57) if comb_trials_uHz is None else np.asarray(comb_trials_uHz, dtype=np.float64)
    smoothed = np.asarray(gaussian_filter1d(values, peak_smoothing_uHz / step, mode="nearest"), dtype=np.float64)
    normalized = normalize_spectrum(frequency, smoothed, continuum, method=normalization, background_sigma=background_sigma_fraction * continuum)
    _, peaks = localized_peak_persistence(normalized)
    point = persistence_weighted_location(peaks, search_uHz=search_uHz, method="centroid")
    comb = comb_score_scan(peaks, trials)
    acf = autocorrelation_spacing_scores(frequency, smoothed / continuum, trials)
    psps = psps_spacing_scores(frequency, smoothed / continuum, trials)
    envelope = estimate_envelope(frequency, values, continuum, search_uHz=search_uHz)
    separation = estimate_large_separation(frequency, values, continuum, envelope.numax_uHz)
    ranked = np.sort(comb)
    return {
        "classical_numax_uHz": envelope.numax_uHz,
        "classical_dnu_uHz": separation.dnu_uHz,
        "classical_envelope_snr": envelope.peak_snr,
        "classical_acf_peak": separation.autocorrelation_peak,
        "persistence_numax_uHz": point,
        "peak_max_lifetime": max(float(peak.persistence or 0) for peak in peaks if not peak.essential),
        "comb_max_score": float(np.max(comb)),
        "comb_winner_uHz": float(trials[np.argmax(comb)]),
        "comb_top_two_ratio": float(ranked[-1] / max(ranked[-2], np.finfo(float).eps)),
        "acf_winner_uHz": float(trials[np.argmax(acf)]),
        "psps_winner_uHz": float(trials[np.argmax(psps)]),
        "finite_peak_count": float(sum(not peak.essential for peak in peaks)),
    }
