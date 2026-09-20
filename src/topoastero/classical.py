"""Classical asteroseismic estimators and observation-model utilities.

The functions in this module are deliberately independent of Lightkurve.  Lightkurve is used
by the Stage 3 acquisition/reproduction workflow, while this module provides a second numerical
path whose conventions can be tested with analytic signals and deterministic injections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter, gaussian_filter1d  # type: ignore[import-untyped]
from scipy.optimize import least_squares  # type: ignore[import-untyped]
from scipy.signal import find_peaks  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]

SOLAR_NUMAX_UHZ = 3090.0
SOLAR_DNU_UHZ = 135.1
SOLAR_TEFF_K = 5777.2
SOLAR_LOGG_CGS = 4.438


def _arrays(x: NDArray[np.floating], y: NDArray[np.floating]) -> tuple[FloatArray, FloatArray]:
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1 or left.size != right.size:
        raise ValueError("inputs must be equally sized one-dimensional arrays")
    if left.size < 4 or not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("inputs must contain at least four finite samples")
    if np.any(np.diff(left) <= 0):
        raise ValueError("coordinate values must be strictly increasing")
    return left, right


def one_sided_fft_psd(
    time_days: NDArray[np.floating], relative_flux: NDArray[np.floating]
) -> tuple[FloatArray, FloatArray]:
    """Return a one-sided PSD in ``ppm^2/uHz`` for a uniform relative-flux series.

    The normalization obeys Parseval's theorem: integrating the returned density over positive
    frequency equals the variance of the mean-subtracted input expressed in ppm squared.
    """

    time, flux = _arrays(time_days, relative_flux)
    deltas = np.diff(time) * 86400.0
    cadence = float(np.median(deltas))
    if cadence <= 0 or not np.allclose(deltas, cadence, rtol=1e-5, atol=1e-6):
        raise ValueError("FFT PSD requires a uniformly sampled time axis")
    centered = flux - np.mean(flux)
    transform = np.fft.rfft(centered)
    # Density per Hz for relative flux is 2*dt/N*|FFT|^2.  Converting relative-flux^2 to
    # ppm^2 contributes 1e12 and converting per-Hz to per-uHz contributes 1e-6.
    power = (2.0 * cadence / centered.size) * np.abs(transform) ** 2 * 1e6
    power[0] *= 0.5
    if centered.size % 2 == 0:
        power[-1] *= 0.5
    frequency = np.fft.rfftfreq(centered.size, cadence) * 1e6
    return np.asarray(frequency, dtype=np.float64), np.asarray(power, dtype=np.float64)


@dataclass(frozen=True, slots=True)
class HarveyComponent:
    """One rational Harvey-like granulation component."""

    amplitude_ppm2_per_uHz: float
    characteristic_uHz: float
    exponent: float = 4.0

    def __post_init__(self) -> None:
        values = (self.amplitude_ppm2_per_uHz, self.characteristic_uHz, self.exponent)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("Harvey component parameters must be finite and positive")


@dataclass(frozen=True, slots=True)
class BackgroundFit:
    """Summary of a white-noise plus Harvey-component fit."""

    component_count: int
    white_noise_ppm2_per_uHz: float
    components: tuple[HarveyComponent, ...]
    log_residual_rms: float
    negative_log_likelihood: float
    aic: float
    bic: float
    covariance_condition: float
    parameter_sigma_log: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.component_count != len(self.components):
            raise ValueError("component_count does not match components")
        if not math.isfinite(self.white_noise_ppm2_per_uHz) or self.white_noise_ppm2_per_uHz <= 0:
            raise ValueError("white-noise level must be finite and positive")


def harvey_background(
    frequency_uHz: NDArray[np.floating],
    white_noise_ppm2_per_uHz: float,
    components: tuple[HarveyComponent, ...],
) -> FloatArray:
    """Evaluate a white-noise plus Harvey-like background model."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    if frequency.ndim != 1 or not np.all(np.isfinite(frequency)) or np.any(frequency < 0):
        raise ValueError("frequencies must be a finite nonnegative one-dimensional array")
    if not math.isfinite(white_noise_ppm2_per_uHz) or white_noise_ppm2_per_uHz <= 0:
        raise ValueError("white-noise level must be finite and positive")
    model = np.full(frequency.shape, white_noise_ppm2_per_uHz, dtype=np.float64)
    for component in components:
        ratio = frequency / component.characteristic_uHz
        model += component.amplitude_ppm2_per_uHz / (1.0 + ratio**component.exponent)
    return model


def _log_bin_medians(
    frequency: FloatArray, power: FloatArray, bins: int
) -> tuple[FloatArray, FloatArray]:
    positive = (frequency > 0) & (power > 0)
    x = frequency[positive]
    y = power[positive]
    edges = np.geomspace(float(x.min()), float(x.max()), bins + 1)
    centers: list[float] = []
    medians: list[float] = []
    for lower, upper in pairwise(edges):
        selected = (x >= lower) & (x < upper)
        if np.count_nonzero(selected) >= 4:
            centers.append(math.sqrt(lower * upper))
            # A raw periodogram ordinate is exponential; median/ln(2) estimates its mean.
            medians.append(float(np.median(y[selected]) / math.log(2.0)))
    if len(centers) < 12:
        raise ValueError("too few populated bins for background fitting")
    return np.asarray(centers), np.asarray(medians)


def fit_harvey_models(
    frequency_uHz: NDArray[np.floating],
    power_ppm2_per_uHz: NDArray[np.floating],
    *,
    exclusion_uHz: tuple[float, float] = (1500.0, 2800.0),
    max_components: int = 2,
    bins: int = 180,
) -> tuple[BackgroundFit, ...]:
    """Fit zero-, one-, and two-component Harvey-like backgrounds in log space.

    The oscillation envelope is excluded from fitting.  Model comparison uses the exponential
    periodogram likelihood evaluated on all retained raw ordinates.
    """

    frequency, power = _arrays(frequency_uHz, power_ppm2_per_uHz)
    if np.any(frequency < 0) or np.any(power <= 0):
        raise ValueError("background fitting requires nonnegative frequencies and positive power")
    if max_components not in {0, 1, 2}:
        raise ValueError("max_components must be 0, 1, or 2")
    lower, upper = exclusion_uHz
    retained = (frequency < lower) | (frequency > upper)
    if np.count_nonzero(retained) < 50:
        raise ValueError("background exclusion leaves too few bins")
    raw_frequency = frequency[retained]
    raw_power = power[retained]
    x, y = _log_bin_medians(raw_frequency, raw_power, bins)
    low_level = max(float(np.median(y[: max(3, len(y) // 10)])), np.finfo(float).tiny)
    high_level = max(float(np.median(y[-max(3, len(y) // 10) :])), np.finfo(float).tiny)
    fits: list[BackgroundFit] = []
    for count in range(max_components + 1):
        initial = [math.log(high_level)]
        if count == 1:
            initial.extend((math.log(max(low_level - high_level, high_level)), math.log(650.0)))
        elif count == 2:
            excess = max(low_level - high_level, high_level)
            initial.extend(
                (
                    math.log(0.75 * excess),
                    math.log(300.0),
                    math.log(0.25 * excess),
                    math.log(1500.0),
                )
            )

        def model(
            theta: FloatArray, at: FloatArray, component_count: int = count
        ) -> FloatArray:
            result = np.full(at.shape, math.exp(float(theta[0])), dtype=np.float64)
            for index in range(component_count):
                amplitude = math.exp(float(theta[1 + 2 * index]))
                characteristic = math.exp(float(theta[2 + 2 * index]))
                result += amplitude / (1.0 + (at / characteristic) ** 4)
            return result

        minimum_power = max(float(np.min(power)) * 1e-3, np.finfo(float).tiny)
        maximum_power = float(np.max(power)) * 100.0
        lower_bounds = [math.log(minimum_power)]
        upper_bounds = [math.log(maximum_power)]
        for _ in range(count):
            lower_bounds.extend((math.log(minimum_power), math.log(10.0)))
            upper_bounds.extend((math.log(maximum_power), math.log(10000.0)))
        result = least_squares(
            lambda theta: np.log(model(theta, x)) - np.log(y),
            np.asarray(initial),
            bounds=(np.asarray(lower_bounds), np.asarray(upper_bounds)),
            max_nfev=5000,
        )
        if not result.success:
            raise RuntimeError(f"background optimization failed for {count} components")
        values = np.asarray(result.x, dtype=np.float64)
        component_values = [
            HarveyComponent(
                math.exp(float(values[1 + 2 * index])),
                math.exp(float(values[2 + 2 * index])),
            )
            for index in range(count)
        ]
        component_values.sort(key=lambda item: item.characteristic_uHz)
        raw_model = model(values, raw_frequency)
        negative_log_likelihood = float(np.sum(np.log(raw_model) + raw_power / raw_model))
        parameter_count = len(values)
        residual = np.asarray(result.fun, dtype=np.float64)
        dof = max(len(residual) - parameter_count, 1)
        information = np.asarray(result.jac.T @ result.jac, dtype=np.float64)
        condition = float(np.linalg.cond(information))
        covariance = np.linalg.pinv(information) * float(np.sum(residual**2) / dof)
        sigma = tuple(float(value) for value in np.sqrt(np.maximum(np.diag(covariance), 0.0)))
        fits.append(
            BackgroundFit(
                component_count=count,
                white_noise_ppm2_per_uHz=math.exp(float(values[0])),
                components=tuple(component_values),
                log_residual_rms=float(np.sqrt(np.mean(residual**2))),
                negative_log_likelihood=negative_log_likelihood,
                aic=2.0 * parameter_count + 2.0 * negative_log_likelihood,
                bic=math.log(raw_power.size) * parameter_count + 2.0 * negative_log_likelihood,
                covariance_condition=condition,
                parameter_sigma_log=sigma,
            )
        )
    return tuple(fits)


class EnvelopeEstimate(NamedTuple):
    numax_uHz: float
    peak_snr: float
    fwhm_uHz: float


def estimate_envelope(
    frequency_uHz: NDArray[np.floating],
    power_ppm2_per_uHz: NDArray[np.floating],
    background_ppm2_per_uHz: NDArray[np.floating],
    *,
    search_uHz: tuple[float, float] = (1700.0, 2500.0),
    smoothing_uHz: float = 35.0,
) -> EnvelopeEstimate:
    """Estimate ``nu_max`` from a smoothed background-normalized spectrum."""

    frequency, power = _arrays(frequency_uHz, power_ppm2_per_uHz)
    background = np.asarray(background_ppm2_per_uHz, dtype=np.float64)
    if background.shape != power.shape or np.any(background <= 0):
        raise ValueError("background must be positive and match the spectrum")
    spacing = float(np.median(np.diff(frequency)))
    if smoothing_uHz <= 0 or not np.allclose(np.diff(frequency), spacing, rtol=1e-3):
        raise ValueError("envelope estimation requires a uniform grid and positive smoothing")
    smoothed = gaussian_filter1d(power / background, smoothing_uHz / spacing, mode="nearest")
    selected = (frequency >= search_uHz[0]) & (frequency <= search_uHz[1])
    if np.count_nonzero(selected) < 3:
        raise ValueError("envelope search interval contains too few bins")
    indices = np.flatnonzero(selected)
    peak_index = int(indices[np.argmax(smoothed[selected])])
    peak = float(smoothed[peak_index])
    half_level = 1.0 + 0.5 * (peak - 1.0)
    left = peak_index
    right = peak_index
    while left > 0 and smoothed[left] >= half_level:
        left -= 1
    while right < len(smoothed) - 1 and smoothed[right] >= half_level:
        right += 1
    return EnvelopeEstimate(
        numax_uHz=float(frequency[peak_index]),
        peak_snr=peak,
        fwhm_uHz=float(frequency[right] - frequency[left]),
    )


class SeparationEstimate(NamedTuple):
    dnu_uHz: float
    autocorrelation_peak: float
    scaling_prediction_uHz: float


def estimate_large_separation(
    frequency_uHz: NDArray[np.floating],
    power_ppm2_per_uHz: NDArray[np.floating],
    background_ppm2_per_uHz: NDArray[np.floating],
    numax_uHz: float,
    *,
    half_width_uHz: float = 275.0,
    smoothing_uHz: float = 0.5,
) -> SeparationEstimate:
    """Estimate ``Delta nu`` from the FFT autocorrelation of a whitened mode envelope."""

    frequency, power = _arrays(frequency_uHz, power_ppm2_per_uHz)
    background = np.asarray(background_ppm2_per_uHz, dtype=np.float64)
    if background.shape != power.shape or np.any(background <= 0):
        raise ValueError("background must be positive and match the spectrum")
    spacing = float(np.median(np.diff(frequency)))
    selected = np.abs(frequency - numax_uHz) <= half_width_uHz
    whitened = power[selected] / background[selected] - 1.0
    if whitened.size < 32 or smoothing_uHz <= 0:
        raise ValueError("large-separation window is too small or smoothing is invalid")
    whitened = gaussian_filter1d(whitened, smoothing_uHz / spacing)
    whitened -= np.mean(whitened)
    padded = 2 * whitened.size
    transform = np.fft.rfft(whitened, n=padded)
    autocorrelation = np.fft.irfft(np.abs(transform) ** 2, n=padded)[: whitened.size]
    if autocorrelation[0] <= 0:
        raise ValueError("spectrum has zero autocorrelation energy")
    autocorrelation /= autocorrelation[0]
    lag = np.arange(whitened.size, dtype=np.float64) * spacing
    prediction = 0.294 * numax_uHz**0.772
    search = (lag >= 0.75 * prediction) & (lag <= 1.25 * prediction)
    local_indices = np.flatnonzero(search)
    index = int(local_indices[np.argmax(autocorrelation[search])])
    # Three-point parabolic interpolation removes dependence on the arbitrary frequency bin edge.
    offset = 0.0
    if 0 < index < len(autocorrelation) - 1:
        before, center, after = autocorrelation[index - 1 : index + 2]
        denominator = before - 2.0 * center + after
        if denominator != 0:
            offset = 0.5 * float(before - after) / float(denominator)
            offset = max(-1.0, min(1.0, offset))
    return SeparationEstimate(
        dnu_uHz=float((index + offset) * spacing),
        autocorrelation_peak=float(autocorrelation[index]),
        scaling_prediction_uHz=float(prediction),
    )


@dataclass(frozen=True, slots=True)
class SpectralWindow:
    frequency_uHz: FloatArray
    power: FloatArray
    duty_cycle: float
    resolution_uHz: float


def spectral_window(
    time_days: NDArray[np.floating],
    cadence_seconds: float,
    *,
    maximum_frequency_uHz: float = 50.0,
) -> SpectralWindow:
    """Compute the FFT spectral window of an observed cadence mask."""

    time = np.asarray(time_days, dtype=np.float64)
    if time.ndim != 1 or time.size < 4 or not np.all(np.isfinite(time)):
        raise ValueError("time must contain at least four finite samples")
    if cadence_seconds <= 0 or maximum_frequency_uHz <= 0:
        raise ValueError("cadence and maximum frequency must be positive")
    time = np.unique(np.sort(time))
    indices = np.rint((time - time[0]) * 86400.0 / cadence_seconds).astype(np.int64)
    mask = np.zeros(int(indices[-1]) + 1, dtype=np.float64)
    mask[indices] = 1.0
    transform = np.fft.rfft(mask)
    frequency = np.fft.rfftfreq(mask.size, cadence_seconds) * 1e6
    power = np.abs(transform) ** 2 / float(np.count_nonzero(mask)) ** 2
    selected = frequency <= maximum_frequency_uHz
    duration_seconds = max(float((time[-1] - time[0]) * 86400.0), cadence_seconds)
    return SpectralWindow(
        frequency_uHz=np.asarray(frequency[selected], dtype=np.float64),
        power=np.asarray(power[selected], dtype=np.float64),
        duty_cycle=float(np.mean(mask)),
        resolution_uHz=1e6 / duration_seconds,
    )


def strongest_window_aliases(window: SpectralWindow, count: int = 3) -> tuple[tuple[float, float], ...]:
    """Return the strongest resolved non-zero local maxima in a spectral window."""

    if count < 1:
        raise ValueError("alias count must be positive")
    frequency = window.frequency_uHz
    power = window.power
    peaks, _ = find_peaks(power)
    peaks = peaks[frequency[peaks] >= 3.0 * window.resolution_uHz]
    if peaks.size == 0:
        return ()
    order = peaks[np.argsort(power[peaks])[::-1][:count]]
    return tuple((float(frequency[index]), float(power[index])) for index in order)


@dataclass(frozen=True, slots=True)
class EchelleGrid:
    phase: FloatArray
    radial_orders: FloatArray
    power: FloatArray
    orientation: str = "frequency_increases_bottom_to_top; phase_increases_left_to_right"
    phase_boundary: str = "circular_wrap"


def echelle_grid(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    dnu_uHz: float,
    *,
    frequency_range_uHz: tuple[float, float],
    phase_bins: int = 128,
    phase_smoothing_bins: float = 1.5,
) -> EchelleGrid:
    """Build a conventional échelle grid with a circular phase boundary."""

    frequency, values = _arrays(frequency_uHz, power)
    if dnu_uHz <= 0 or phase_bins < 8 or phase_smoothing_bins < 0:
        raise ValueError("invalid echelle spacing or bin/smoothing parameter")
    selected = (frequency >= frequency_range_uHz[0]) & (frequency <= frequency_range_uHz[1])
    frequency = frequency[selected]
    values = values[selected]
    if frequency.size < phase_bins:
        raise ValueError("echelle frequency range contains too few bins")
    order = np.floor(frequency / dnu_uHz).astype(np.int64)
    order_min = int(order.min())
    order_max = int(order.max())
    order_edges = np.arange(order_min, order_max + 2, dtype=np.float64) - 0.5
    phase = np.mod(frequency, dnu_uHz) / dnu_uHz
    phase_edges = np.linspace(0.0, 1.0, phase_bins + 1)
    weighted, _, _ = np.histogram2d(order, phase, bins=(order_edges, phase_edges), weights=values)
    counts, _, _ = np.histogram2d(order, phase, bins=(order_edges, phase_edges))
    matrix = np.divide(weighted, counts, out=np.zeros_like(weighted), where=counts > 0)
    if phase_smoothing_bins > 0:
        matrix = gaussian_filter(
            matrix,
            sigma=(0.5, phase_smoothing_bins),
            mode=("nearest", "wrap"),
        )
    phase_centers = 0.5 * (phase_edges[:-1] + phase_edges[1:])
    radial_orders = np.arange(order_min, order_max + 1, dtype=np.float64)
    return EchelleGrid(phase_centers, radial_orders, np.asarray(matrix, dtype=np.float64))


@dataclass(frozen=True, slots=True)
class ModeReference:
    row_id: str
    radial_order_n: int
    angular_degree_l: int
    frequency_uHz: float
    uncertainty_uHz: float


@dataclass(frozen=True, slots=True)
class ModeMatch:
    row_id: str
    radial_order_n: int
    angular_degree_l: int
    reference_frequency_uHz: float
    measured_peak_uHz: float
    residual_uHz: float
    normalized_residual: float
    echelle_order: int
    order_offset: int


def audit_mode_peaks(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    references: tuple[ModeReference, ...],
    dnu_uHz: float,
    *,
    search_half_width_uHz: float = 2.5,
) -> tuple[ModeMatch, ...]:
    """Match each published mode to the highest local spectral ordinate."""

    frequency, values = _arrays(frequency_uHz, power)
    if not references or dnu_uHz <= 0 or search_half_width_uHz <= 0:
        raise ValueError("mode references, dnu, and search width must be positive/nonempty")
    matches: list[ModeMatch] = []
    for reference in references:
        selected = np.abs(frequency - reference.frequency_uHz) <= search_half_width_uHz
        if not np.any(selected):
            raise ValueError(f"no spectrum bins near {reference.row_id}")
        candidates = np.flatnonzero(selected)
        index = int(candidates[np.argmax(values[selected])])
        measured = float(frequency[index])
        residual = measured - reference.frequency_uHz
        uncertainty = max(reference.uncertainty_uHz, np.finfo(float).eps)
        echelle_order = math.floor(reference.frequency_uHz / dnu_uHz)
        matches.append(
            ModeMatch(
                row_id=reference.row_id,
                radial_order_n=reference.radial_order_n,
                angular_degree_l=reference.angular_degree_l,
                reference_frequency_uHz=reference.frequency_uHz,
                measured_peak_uHz=measured,
                residual_uHz=residual,
                normalized_residual=residual / uncertainty,
                echelle_order=echelle_order,
                order_offset=echelle_order - reference.radial_order_n,
            )
        )
    return tuple(matches)


class ScalingEstimate(NamedTuple):
    mass_solar: float
    radius_solar: float
    logg_cgs: float


class ScalingUncertainty(NamedTuple):
    mass_solar: float
    radius_solar: float
    logg_dex: float


def scaling_relations(numax_uHz: float, dnu_uHz: float, teff_K: float) -> ScalingEstimate:
    """Evaluate the uncorrected solar scaling relations used by the tutorial."""

    if not all(math.isfinite(value) and value > 0 for value in (numax_uHz, dnu_uHz, teff_K)):
        raise ValueError("scaling-relation inputs must be finite and positive")
    n = numax_uHz / SOLAR_NUMAX_UHZ
    d = dnu_uHz / SOLAR_DNU_UHZ
    t = teff_K / SOLAR_TEFF_K
    return ScalingEstimate(
        mass_solar=n**3 * d**-4 * t**1.5,
        radius_solar=n * d**-2 * t**0.5,
        logg_cgs=SOLAR_LOGG_CGS + math.log10(n * t**0.5),
    )


def scaling_uncertainty(
    numax_uHz: float,
    dnu_uHz: float,
    teff_K: float,
    sigma_numax_uHz: float,
    sigma_dnu_uHz: float,
    sigma_teff_K: float,
) -> ScalingUncertainty:
    """Propagate independent random errors through the uncorrected scaling relations."""

    estimate = scaling_relations(numax_uHz, dnu_uHz, teff_K)
    errors = (sigma_numax_uHz, sigma_dnu_uHz, sigma_teff_K)
    if not all(math.isfinite(value) and value >= 0 for value in errors):
        raise ValueError("input uncertainties must be finite and nonnegative")
    n = sigma_numax_uHz / numax_uHz
    d = sigma_dnu_uHz / dnu_uHz
    t = sigma_teff_K / teff_K
    return ScalingUncertainty(
        mass_solar=estimate.mass_solar * math.sqrt((3.0 * n) ** 2 + (4.0 * d) ** 2 + (1.5 * t) ** 2),
        radius_solar=estimate.radius_solar * math.sqrt(n**2 + (2.0 * d) ** 2 + (0.5 * t) ** 2),
        logg_dex=math.sqrt(n**2 + (0.5 * t) ** 2) / math.log(10.0),
    )


def quadrature_uncertainty(*components: float) -> float:
    """Combine independent, finite, nonnegative uncertainty components."""

    if not components or not all(math.isfinite(value) and value >= 0 for value in components):
        raise ValueError("uncertainty components must be finite, nonnegative, and nonempty")
    return math.sqrt(sum(value * value for value in components))


def classify_tess_sector(
    envelope_peak_snr: float,
    candidate_numax_uHz: float,
    dnu_uHz: float,
    dnu_autocorrelation: float,
    *,
    reference_numax_uHz: float,
    reference_dnu_uHz: float,
) -> str:
    """Apply the frozen conservative TESS single-sector detection rule."""

    values = (
        envelope_peak_snr,
        candidate_numax_uHz,
        dnu_uHz,
        dnu_autocorrelation,
        reference_numax_uHz,
        reference_dnu_uHz,
    )
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("TESS detection inputs must be finite and nonnegative")
    envelope_ok = envelope_peak_snr >= 1.20 and abs(candidate_numax_uHz - reference_numax_uHz) <= 150.0
    spacing_ok = abs(dnu_uHz - reference_dnu_uHz) <= 10.0 and dnu_autocorrelation >= 0.08
    if envelope_ok and spacing_ok:
        return "marginal_candidate_not_confirmation"
    return "not_detected_individually"
