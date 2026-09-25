"""Persistent-topology estimators for background-normalized power spectra.

This module implements the Stage 6 inference surface.  Zero-dimensional superlevel
persistence is computed by the exact path backend from :mod:`topoastero.tda`; every class is
localized to a birth frequency and (for finite classes) a merge-saddle frequency.  The numerical
estimators deliberately expose ordinary peak-prominence, autocorrelation, and PSPS-style controls
because path ``H_0`` persistence and elder-rule prominence are mathematically equivalent on their
shared domain.

The functions are dependency-light, deterministic for a fixed seed, and contain no mission-data
I/O.  Workflows are responsible for provenance, split policy, and maximum-statistic null draws.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d  # type: ignore[import-untyped]

from topoastero.tda import PersistenceDiagram, exact_path_persistence

FloatArray: TypeAlias = NDArray[np.float64]
NormalizationMethod = Literal["ratio", "log_ratio", "whitened_residual", "uncertainty_zscore"]
LocationMethod = Literal["centroid", "weighted_median", "huber"]
AliasLabel = Literal["half", "nominal", "double"]


class QualityFlag(StrEnum):
    """Registered Stage 6 reason codes; values are stable serialization identifiers."""

    ABSENT_ENVELOPE = "absent_envelope"
    ALIAS_AMBIGUITY = "alias_ambiguity"
    INSUFFICIENT_ORDERS = "insufficient_orders"
    WINDOW_CONTAMINATION = "window_contamination"
    UNSTABLE_BACKGROUND = "unstable_background"


@dataclass(frozen=True, slots=True)
class NormalizedSpectrum:
    """One normalized spectrum with enough context to reconstruct its contract."""

    frequency_uHz: FloatArray
    power: FloatArray
    background: FloatArray
    values: FloatArray
    method: NormalizationMethod
    primary: bool
    background_sigma: FloatArray | None = None


@dataclass(frozen=True, slots=True)
class SpectralPeak:
    """A localized path-persistence class in a one-dimensional spectrum."""

    pair_id: str
    peak_index: int
    birth_frequency_uHz: float
    birth_value: float
    saddle_index: int | None
    saddle_frequency_uHz: float | None
    death_value: float | None
    persistence: float | None
    essential: bool
    boundary_peak: bool

    def to_record(self) -> dict[str, object]:
        """Return a JSON-friendly record governed by the Stage 6 pair schema."""

        return {
            "pair_id": self.pair_id,
            "dimension": 0,
            "peak_index": self.peak_index,
            "birth_frequency_uHz": self.birth_frequency_uHz,
            "birth_value": self.birth_value,
            "saddle_index": self.saddle_index,
            "saddle_frequency_uHz": self.saddle_frequency_uHz,
            "death_value": self.death_value,
            "persistence": self.persistence,
            "essential": self.essential,
            "boundary_peak": self.boundary_peak,
        }


@dataclass(frozen=True, slots=True)
class ProminenceMatch:
    """One independently matched persistence/prominence value."""

    peak_index: int
    persistence: float
    prominence: float
    persistence_saddle_index: int
    prominence_saddle_index: int
    boundary_peak: bool

    @property
    def absolute_error(self) -> float:
        return abs(self.persistence - self.prominence)


@dataclass(frozen=True, slots=True)
class NumaxEstimate:
    """Persistence-localized oscillation-envelope location with an uncertainty interval."""

    numax_uHz: float
    lower_uHz: float
    upper_uHz: float
    interval_level: float
    method: LocationMethod
    effective_peak_count: float
    finite_peak_count: int
    detection_statistic: float
    bootstrap_replicates: int

    def to_record(self) -> dict[str, object]:
        return {
            "numax_uHz": self.numax_uHz,
            "lower_uHz": self.lower_uHz,
            "upper_uHz": self.upper_uHz,
            "interval_level": self.interval_level,
            "method": self.method,
            "effective_peak_count": self.effective_peak_count,
            "finite_peak_count": self.finite_peak_count,
            "detection_statistic": self.detection_statistic,
            "bootstrap_replicates": self.bootstrap_replicates,
        }


@dataclass(frozen=True, slots=True)
class CombCandidate:
    """One explicit spacing alternative; candidates are never silently collapsed."""

    alias: AliasLabel
    spacing_uHz: float
    difference_score: float
    autocorrelation_score: float
    combined_score: float
    rank: int

    def to_record(self) -> dict[str, object]:
        return {
            "alias": self.alias,
            "spacing_uHz": self.spacing_uHz,
            "difference_score": self.difference_score,
            "autocorrelation_score": self.autocorrelation_score,
            "combined_score": self.combined_score,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class CombEstimate:
    """The registered half/nominal/double spacing candidate set."""

    candidates: tuple[CombCandidate, ...]
    winner: AliasLabel
    ambiguity_ratio: float
    ambiguous: bool


@dataclass(frozen=True, slots=True)
class MaxStatisticCalibration:
    """Finite-sample calibration based on maxima across every registered trial."""

    threshold: float
    alpha: float
    calibration_size: int
    trial_count: int
    maxima: FloatArray


@dataclass(frozen=True, slots=True)
class CalibrationEvaluation:
    """Independent evaluation of a maximum-statistic threshold."""

    false_positive_rate: float
    detections: int
    evaluation_size: int
    false_confidence_rate: float


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    """Reason-coded reliability result."""

    flags: tuple[QualityFlag, ...]
    status: Literal["reliable", "limited", "not_detected"]

    @property
    def reliable(self) -> bool:
        return self.status == "reliable"

    def to_record(self) -> dict[str, object]:
        return {
            "flags": [flag.value for flag in self.flags],
            "status": self.status,
            "reliable": self.reliable,
        }


def _spectrum_arrays(
    frequency_uHz: Sequence[float] | NDArray[np.floating],
    power: Sequence[float] | NDArray[np.floating],
    background: Sequence[float] | NDArray[np.floating],
) -> tuple[FloatArray, FloatArray, FloatArray]:
    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    observed = np.asarray(power, dtype=np.float64)
    continuum = np.asarray(background, dtype=np.float64)
    if frequency.ndim != 1 or observed.ndim != 1 or continuum.ndim != 1:
        raise ValueError("frequency, power, and background must be one-dimensional")
    if frequency.size < 5 or observed.shape != frequency.shape or continuum.shape != frequency.shape:
        raise ValueError("spectrum arrays must share a length of at least five")
    if not np.all(np.isfinite(frequency)) or np.any(np.diff(frequency) <= 0):
        raise ValueError("frequency must be finite and strictly increasing")
    if (
        not np.all(np.isfinite(observed))
        or not np.all(np.isfinite(continuum))
        or np.any(observed <= 0)
        or np.any(continuum <= 0)
    ):
        raise ValueError("power and background must be finite and strictly positive")
    return frequency, observed, continuum


def normalize_spectrum(
    frequency_uHz: Sequence[float] | NDArray[np.floating],
    power: Sequence[float] | NDArray[np.floating],
    background: Sequence[float] | NDArray[np.floating],
    *,
    method: NormalizationMethod = "log_ratio",
    background_sigma: Sequence[float] | NDArray[np.floating] | None = None,
) -> NormalizedSpectrum:
    """Normalize a positive PSD according to the frozen Stage 6 alternatives.

    ``log_ratio`` is primary.  ``uncertainty_zscore`` uses the exponential-periodogram standard
    deviation together with a supplied background-posterior standard deviation in quadrature.
    """

    frequency, observed, continuum = _spectrum_arrays(frequency_uHz, power, background)
    sigma: FloatArray | None = None
    if background_sigma is not None:
        sigma = np.asarray(background_sigma, dtype=np.float64)
        if sigma.shape != continuum.shape or not np.all(np.isfinite(sigma)) or np.any(sigma < 0):
            raise ValueError("background_sigma must be finite, nonnegative, and match the spectrum")
    ratio = observed / continuum
    if method == "ratio":
        values = ratio
    elif method == "log_ratio":
        values = np.log(ratio)
    elif method == "whitened_residual":
        values = ratio - 1.0
    elif method == "uncertainty_zscore":
        if sigma is None:
            raise ValueError("uncertainty_zscore requires background_sigma")
        values = (observed - continuum) / np.hypot(continuum, sigma)
    else:  # pragma: no cover - Literal protects typed callers
        raise ValueError(f"unknown normalization method: {method}")
    return NormalizedSpectrum(
        np.asarray(frequency, dtype=np.float64),
        np.asarray(observed, dtype=np.float64),
        np.asarray(continuum, dtype=np.float64),
        np.asarray(values, dtype=np.float64),
        method,
        method == "log_ratio",
        None if sigma is None else np.asarray(sigma, dtype=np.float64),
    )


def localized_peak_persistence(spectrum: NormalizedSpectrum) -> tuple[PersistenceDiagram, tuple[SpectralPeak, ...]]:
    """Compute exact superlevel ``H_0`` and localize births and merge saddles in frequency."""

    metadata: list[Mapping[str, str | int | float | bool | None]] = [
        {"bin_index": index, "frequency_uHz": float(value), "domain": "power_spectrum"}
        for index, value in enumerate(spectrum.frequency_uHz)
    ]
    diagram = exact_path_persistence(
        spectrum.values,
        direction="superlevel",
        vertex_metadata=metadata,
    )
    peaks: list[SpectralPeak] = []
    for index, pair in enumerate(diagram.pairs):
        peak_index = pair.birth_vertices[0]
        saddle_index = None if pair.death_vertices is None else pair.death_vertices[0]
        persistence = pair.persistence
        peaks.append(
            SpectralPeak(
                pair_id=f"PSD-H0-{index:05d}",
                peak_index=peak_index,
                birth_frequency_uHz=float(spectrum.frequency_uHz[peak_index]),
                birth_value=float(pair.birth),
                saddle_index=saddle_index,
                saddle_frequency_uHz=None
                if saddle_index is None
                else float(spectrum.frequency_uHz[saddle_index]),
                death_value=None if pair.death is None else float(pair.death),
                persistence=None if persistence is None else float(persistence),
                essential=pair.essential,
                boundary_peak=peak_index in {0, spectrum.values.size - 1},
            )
        )
    return diagram, tuple(peaks)


def independent_path_prominence(
    values: Sequence[float] | NDArray[np.floating], peak_index: int
) -> tuple[float, int]:
    """Compute elder-rule peak prominence without calling the persistence implementation.

    An index is older if it has a larger value, or the same value and a lower index.  The merge
    level is the highest path minimum connecting the candidate to any older index.  This definition
    includes boundary peaks and deliberately excludes the unique essential (oldest) class.
    """

    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size == 0 or not np.all(np.isfinite(signal)):
        raise ValueError("values must be a nonempty finite vector")
    if not 0 <= peak_index < signal.size:
        raise ValueError("peak_index is outside the signal")
    value = float(signal[peak_index])
    older = [
        index
        for index, candidate in enumerate(signal)
        if float(candidate) > value or (float(candidate) == value and index < peak_index)
    ]
    if not older:
        raise ValueError("the oldest/global peak is essential and has no finite prominence")
    best_level = -math.inf
    best_saddle = -1
    for index in older:
        lower, upper = sorted((peak_index, index))
        segment = signal[lower : upper + 1]
        level = float(np.min(segment))
        minima = np.flatnonzero(segment == level) + lower
        saddle = int(minima[0])
        if level > best_level or (level == best_level and saddle < best_saddle):
            best_level = level
            best_saddle = saddle
    return value - best_level, best_saddle


def prominence_matches(spectrum: NormalizedSpectrum) -> tuple[ProminenceMatch, ...]:
    """Match every finite path-persistence class to the independent prominence control."""

    _, peaks = localized_peak_persistence(spectrum)
    matches: list[ProminenceMatch] = []
    for peak in peaks:
        if peak.essential or peak.persistence is None or peak.saddle_index is None:
            continue
        prominence, saddle = independent_path_prominence(spectrum.values, peak.peak_index)
        matches.append(
            ProminenceMatch(
                peak_index=peak.peak_index,
                persistence=peak.persistence,
                prominence=prominence,
                persistence_saddle_index=peak.saddle_index,
                prominence_saddle_index=saddle,
                boundary_peak=peak.boundary_peak,
            )
        )
    return tuple(matches)


def _weighted_quantile(values: FloatArray, weights: FloatArray, quantile: float) -> float:
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must lie in [0, 1]")
    order = np.argsort(values, kind="mergesort")
    ordered_values = values[order]
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    cutoff = quantile * float(cumulative[-1])
    index = min(int(np.searchsorted(cumulative, cutoff, side="left")), values.size - 1)
    return float(ordered_values[index])


def _peak_sample(
    peaks: Sequence[SpectralPeak],
    search_uHz: tuple[float, float],
    min_persistence: float,
) -> tuple[FloatArray, FloatArray]:
    if (
        not all(math.isfinite(value) for value in search_uHz)
        or search_uHz[0] >= search_uHz[1]
        or not math.isfinite(min_persistence)
        or min_persistence < 0
    ):
        raise ValueError("invalid search interval or persistence threshold")
    selected = [
        peak
        for peak in peaks
        if not peak.essential
        and peak.persistence is not None
        and peak.persistence >= min_persistence
        and search_uHz[0] <= peak.birth_frequency_uHz <= search_uHz[1]
    ]
    if not selected:
        raise ValueError("no finite persistence peaks satisfy the registered search")
    frequency = np.asarray([peak.birth_frequency_uHz for peak in selected], dtype=np.float64)
    persistence = np.asarray(
        [float(peak.persistence) if peak.persistence is not None else 0.0 for peak in selected],
        dtype=np.float64,
    )
    weights = np.maximum(persistence - min_persistence, np.finfo(float).eps)
    return frequency, weights


def persistence_weighted_location(
    peaks: Sequence[SpectralPeak],
    *,
    search_uHz: tuple[float, float],
    min_persistence: float = 0.0,
    method: LocationMethod = "centroid",
) -> float:
    """Locate an envelope from finite peak births weighted by their persistence."""

    frequency, weights = _peak_sample(peaks, search_uHz, min_persistence)
    if method == "centroid":
        return float(np.average(frequency, weights=weights))
    if method == "weighted_median":
        return _weighted_quantile(frequency, weights, 0.5)
    if method != "huber":
        raise ValueError(f"unknown location method: {method}")
    location = _weighted_quantile(frequency, weights, 0.5)
    scale = max(
        1.4826 * _weighted_quantile(np.abs(frequency - location), weights, 0.5),
        np.finfo(float).eps,
    )
    for _ in range(50):
        residual = (frequency - location) / scale
        robust = np.ones_like(residual)
        outside = np.abs(residual) > 1.345
        robust[outside] = 1.345 / np.abs(residual[outside])
        updated = float(np.average(frequency, weights=weights * robust))
        if abs(updated - location) <= 1e-10 * max(1.0, abs(location)):
            location = updated
            break
        location = updated
    return location


def estimate_numax(
    spectrum: NormalizedSpectrum,
    *,
    search_uHz: tuple[float, float],
    min_persistence: float = 0.0,
    method: LocationMethod = "centroid",
    interval_level: float = 0.95,
    bootstrap_values: NDArray[np.floating] | None = None,
    bootstrap_replicates: int = 256,
    seed: int = 0,
    minimum_half_width_uHz: float = 0.0,
) -> NumaxEstimate:
    """Estimate ``nu_max`` and a resampling interval from localized finite classes.

    Callers may provide posterior-predictive or bootstrap normalized spectra.  Otherwise a
    weighted peak bootstrap is used.  The minimum half-width is a registered calibration floor,
    not a post-hoc widening rule.
    """

    if not 0 < interval_level < 1:
        raise ValueError("interval_level must lie strictly between zero and one")
    if bootstrap_replicates < 8 or minimum_half_width_uHz < 0:
        raise ValueError("bootstrap_replicates must be at least eight and width nonnegative")
    _, peaks = localized_peak_persistence(spectrum)
    frequency, weights = _peak_sample(peaks, search_uHz, min_persistence)
    point = persistence_weighted_location(
        peaks,
        search_uHz=search_uHz,
        min_persistence=min_persistence,
        method=method,
    )
    rng = np.random.default_rng(seed)
    replicates: list[float] = []
    if bootstrap_values is not None:
        matrix = np.asarray(bootstrap_values, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[1] != spectrum.values.size or not np.all(np.isfinite(matrix)):
            raise ValueError("bootstrap_values must be a finite matrix matching the spectrum bins")
        for values in matrix:
            draw = NormalizedSpectrum(
                spectrum.frequency_uHz,
                spectrum.power,
                spectrum.background,
                np.asarray(values, dtype=np.float64),
                spectrum.method,
                spectrum.primary,
                spectrum.background_sigma,
            )
            _, draw_peaks = localized_peak_persistence(draw)
            try:
                replicates.append(
                    persistence_weighted_location(
                        draw_peaks,
                        search_uHz=search_uHz,
                        min_persistence=min_persistence,
                        method=method,
                    )
                )
            except ValueError:
                continue
    else:
        probabilities = weights / float(np.sum(weights))
        for _ in range(bootstrap_replicates):
            indices = rng.choice(frequency.size, size=frequency.size, replace=True, p=probabilities)
            sampled_frequency = frequency[indices]
            sampled_weights = weights[indices]
            if method == "centroid":
                value = float(np.average(sampled_frequency, weights=sampled_weights))
            elif method == "weighted_median":
                value = _weighted_quantile(sampled_frequency, sampled_weights, 0.5)
            else:
                synthetic = tuple(
                    SpectralPeak(
                        f"BOOT-{index}",
                        index,
                        float(item),
                        float(sampled_weights[index]),
                        0,
                        float(item),
                        0.0,
                        float(sampled_weights[index]),
                        False,
                        False,
                    )
                    for index, item in enumerate(sampled_frequency)
                )
                value = persistence_weighted_location(
                    synthetic,
                    search_uHz=search_uHz,
                    method="huber",
                )
            replicates.append(value)
    if len(replicates) < 8:
        raise ValueError("fewer than eight valid bootstrap estimates were produced")
    tail = 0.5 * (1.0 - interval_level)
    lower, upper = np.quantile(np.asarray(replicates), [tail, 1.0 - tail])
    lower = min(float(lower), point - minimum_half_width_uHz)
    upper = max(float(upper), point + minimum_half_width_uHz)
    effective = float(np.sum(weights) ** 2 / np.sum(weights**2))
    finite_persistence = [float(peak.persistence) for peak in peaks if peak.persistence is not None]
    return NumaxEstimate(
        numax_uHz=point,
        lower_uHz=lower,
        upper_uHz=upper,
        interval_level=interval_level,
        method=method,
        effective_peak_count=effective,
        finite_peak_count=len(frequency),
        detection_statistic=max(finite_persistence, default=0.0),
        bootstrap_replicates=len(replicates),
    )


def smoothed_envelope_numax(
    frequency_uHz: Sequence[float] | NDArray[np.floating],
    ratio: Sequence[float] | NDArray[np.floating],
    *,
    search_uHz: tuple[float, float],
    smoothing_uHz: float,
) -> float:
    """Return the topology-free smoothed-envelope maximum on a uniform grid."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    values = np.asarray(ratio, dtype=np.float64)
    if frequency.ndim != 1 or values.shape != frequency.shape or frequency.size < 5:
        raise ValueError("frequency and ratio must be equally sized one-dimensional arrays")
    if not np.all(np.isfinite(frequency)) or not np.all(np.isfinite(values)):
        raise ValueError("frequency and ratio must be finite")
    spacing = float(np.median(np.diff(frequency)))
    if smoothing_uHz <= 0 or spacing <= 0 or not np.allclose(np.diff(frequency), spacing, rtol=1e-3):
        raise ValueError("control requires a uniform grid and positive smoothing")
    selected = (frequency >= search_uHz[0]) & (frequency <= search_uHz[1])
    if np.count_nonzero(selected) < 3:
        raise ValueError("search interval contains too few bins")
    smoothed = gaussian_filter1d(values, smoothing_uHz / spacing, mode="nearest")
    indices = np.flatnonzero(selected)
    return float(frequency[int(indices[np.argmax(smoothed[selected])])])


def adapt_pysyd_numax(result: Mapping[str, object]) -> tuple[float, float | None]:
    """Validate the minimal external pySYD result needed for a fair Stage 6 comparison.

    The adapter accepts either ``numax`` or ``numax_uHz`` and optional ``numax_err`` or
    ``numax_err_uHz``.  It intentionally does not import pySYD, allowing offline validation while
    keeping genuine external executions clearly distinguished from the registered style control.
    """

    raw = result.get("numax_uHz", result.get("numax"))
    if not isinstance(raw, (int, float)) or not math.isfinite(float(raw)) or float(raw) <= 0:
        raise ValueError("pySYD result must contain a positive finite numax")
    raw_error = result.get("numax_err_uHz", result.get("numax_err"))
    if raw_error is None:
        return float(raw), None
    if (
        not isinstance(raw_error, (int, float))
        or not math.isfinite(float(raw_error))
        or float(raw_error) < 0
    ):
        raise ValueError("pySYD numax uncertainty must be finite and nonnegative")
    return float(raw), float(raw_error)


def _finite_peak_arrays(peaks: Sequence[SpectralPeak]) -> tuple[FloatArray, FloatArray]:
    finite = [peak for peak in peaks if not peak.essential and peak.persistence is not None]
    if len(finite) < 2:
        raise ValueError("comb estimation requires at least two finite persistence peaks")
    frequency = np.asarray([peak.birth_frequency_uHz for peak in finite], dtype=np.float64)
    weights = np.asarray(
        [float(peak.persistence) if peak.persistence is not None else 0.0 for peak in finite],
        dtype=np.float64,
    )
    return frequency, weights


def persistence_difference_score(
    peak_frequency_uHz: Sequence[float] | NDArray[np.floating],
    persistence: Sequence[float] | NDArray[np.floating],
    spacing_uHz: float,
    *,
    bandwidth_uHz: float,
    harmonics: int = 4,
) -> float:
    """Score repeated pair differences at integer multiples of a trial spacing."""

    frequency = np.asarray(peak_frequency_uHz, dtype=np.float64)
    weights = np.asarray(persistence, dtype=np.float64)
    if (
        frequency.ndim != 1
        or weights.shape != frequency.shape
        or frequency.size < 2
        or not np.all(np.isfinite(frequency))
        or not np.all(np.isfinite(weights))
        or np.any(weights < 0)
    ):
        raise ValueError("peak frequencies and nonnegative weights must be finite vectors")
    if spacing_uHz <= 0 or bandwidth_uHz <= 0 or harmonics < 1:
        raise ValueError("spacing, bandwidth, and harmonics must be positive")
    left, right = np.triu_indices(frequency.size, k=1)
    differences = np.abs(frequency[right] - frequency[left])
    pair_weights = weights[left] * weights[right]
    if not np.any(pair_weights > 0):
        return 0.0
    response = np.zeros_like(differences)
    for harmonic in range(1, harmonics + 1):
        response = np.maximum(
            response,
            np.exp(-0.5 * ((differences - harmonic * spacing_uHz) / bandwidth_uHz) ** 2)
            / math.sqrt(harmonic),
        )
    return float(np.sum(pair_weights * response) / np.sum(pair_weights))


def persistence_autocorrelation_score(
    peak_frequency_uHz: Sequence[float] | NDArray[np.floating],
    persistence: Sequence[float] | NDArray[np.floating],
    spacing_uHz: float,
    *,
    bandwidth_uHz: float,
) -> float:
    """Return a persistence-weighted kernel autocorrelation at one trial lag."""

    frequency = np.asarray(peak_frequency_uHz, dtype=np.float64)
    weights = np.asarray(persistence, dtype=np.float64)
    if frequency.ndim != 1 or weights.shape != frequency.shape or frequency.size < 2:
        raise ValueError("peak frequencies and weights must be equally sized vectors")
    if not np.all(np.isfinite(frequency)) or not np.all(np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError("peak frequencies and weights must be finite and nonnegative")
    if spacing_uHz <= 0 or bandwidth_uHz <= 0:
        raise ValueError("spacing and bandwidth must be positive")
    left, right = np.triu_indices(frequency.size, k=1)
    differences = np.abs(frequency[right] - frequency[left])
    pair_weights = weights[left] * weights[right]
    if not np.any(pair_weights > 0):
        return 0.0
    kernel = np.exp(-0.5 * ((differences - spacing_uHz) / bandwidth_uHz) ** 2)
    return float(np.sum(pair_weights * kernel) / np.sum(pair_weights))


def comb_score_scan(
    peaks: Sequence[SpectralPeak],
    trial_spacings_uHz: Sequence[float] | NDArray[np.floating],
    *,
    fractional_bandwidth: float = 0.06,
) -> FloatArray:
    """Evaluate the combined persistence-weighted comb score on every registered trial."""

    trials = np.asarray(trial_spacings_uHz, dtype=np.float64)
    if trials.ndim != 1 or trials.size == 0 or not np.all(np.isfinite(trials)) or np.any(trials <= 0):
        raise ValueError("trial spacings must be a nonempty positive finite vector")
    if not 0 < fractional_bandwidth < 1:
        raise ValueError("fractional_bandwidth must lie between zero and one")
    frequency, weights = _finite_peak_arrays(peaks)
    scores = []
    for spacing in trials:
        bandwidth = max(float(spacing) * fractional_bandwidth, np.finfo(float).eps)
        difference = persistence_difference_score(
            frequency, weights, float(spacing), bandwidth_uHz=bandwidth
        )
        autocorrelation = persistence_autocorrelation_score(
            frequency, weights, float(spacing), bandwidth_uHz=bandwidth
        )
        scores.append(math.sqrt(max(difference, 0.0) * max(autocorrelation, 0.0)))
    return np.asarray(scores, dtype=np.float64)


def estimate_comb_candidates(
    peaks: Sequence[SpectralPeak],
    *,
    nominal_spacing_uHz: float,
    fractional_bandwidth: float = 0.06,
    ambiguity_ratio: float = 1.15,
) -> CombEstimate:
    """Expose ``Delta nu / 2``, ``Delta nu``, and ``2 Delta nu`` alternatives."""

    if nominal_spacing_uHz <= 0 or ambiguity_ratio <= 1:
        raise ValueError("nominal spacing must be positive and ambiguity_ratio greater than one")
    labels: tuple[AliasLabel, ...] = ("half", "nominal", "double")
    spacings = np.asarray(
        [0.5 * nominal_spacing_uHz, nominal_spacing_uHz, 2.0 * nominal_spacing_uHz],
        dtype=np.float64,
    )
    frequency, weights = _finite_peak_arrays(peaks)
    raw: list[tuple[AliasLabel, float, float, float, float]] = []
    for label, spacing in zip(labels, spacings, strict=True):
        bandwidth = float(spacing) * fractional_bandwidth
        difference = persistence_difference_score(
            frequency, weights, float(spacing), bandwidth_uHz=bandwidth
        )
        autocorrelation = persistence_autocorrelation_score(
            frequency, weights, float(spacing), bandwidth_uHz=bandwidth
        )
        combined = math.sqrt(max(difference, 0.0) * max(autocorrelation, 0.0))
        raw.append((label, float(spacing), difference, autocorrelation, combined))
    order = sorted(range(3), key=lambda index: (-raw[index][4], index))
    ranks = {index: rank + 1 for rank, index in enumerate(order)}
    candidates = tuple(
        CombCandidate(label, spacing, difference, autocorrelation, combined, ranks[index])
        for index, (label, spacing, difference, autocorrelation, combined) in enumerate(raw)
    )
    top = raw[order[0]][4]
    second = raw[order[1]][4]
    ratio = math.inf if second <= 0 < top else (1.0 if top == second == 0 else top / second)
    return CombEstimate(candidates, raw[order[0]][0], ratio, ratio < ambiguity_ratio)


def autocorrelation_spacing_scores(
    frequency_uHz: Sequence[float] | NDArray[np.floating],
    values: Sequence[float] | NDArray[np.floating],
    trial_spacings_uHz: Sequence[float] | NDArray[np.floating],
) -> FloatArray:
    """Topology-free FFT autocorrelation scores interpolated at trial spacings."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    signal = np.asarray(values, dtype=np.float64)
    trials = np.asarray(trial_spacings_uHz, dtype=np.float64)
    if frequency.ndim != 1 or signal.shape != frequency.shape or frequency.size < 8:
        raise ValueError("frequency and values must be equally sized vectors of length at least eight")
    spacing = float(np.median(np.diff(frequency)))
    if spacing <= 0 or not np.allclose(np.diff(frequency), spacing, rtol=1e-3):
        raise ValueError("autocorrelation control requires a uniform frequency grid")
    if trials.ndim != 1 or trials.size == 0 or np.any(trials <= 0):
        raise ValueError("trial spacings must be positive")
    centered = signal - np.mean(signal)
    transform = np.fft.rfft(centered, n=2 * centered.size)
    correlation = np.fft.irfft(np.abs(transform) ** 2, n=2 * centered.size)[: centered.size]
    if correlation[0] <= 0:
        return np.zeros(trials.shape, dtype=np.float64)
    correlation /= correlation[0]
    lags = np.arange(centered.size, dtype=np.float64) * spacing
    return np.asarray(np.interp(trials, lags, correlation, left=0.0, right=0.0), dtype=np.float64)


def psps_spacing_scores(
    frequency_uHz: Sequence[float] | NDArray[np.floating],
    values: Sequence[float] | NDArray[np.floating],
    trial_spacings_uHz: Sequence[float] | NDArray[np.floating],
) -> FloatArray:
    """Topology-free power-spectrum-of-power-spectrum sinusoidal scores."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    signal = np.asarray(values, dtype=np.float64)
    trials = np.asarray(trial_spacings_uHz, dtype=np.float64)
    if frequency.ndim != 1 or signal.shape != frequency.shape or frequency.size < 8:
        raise ValueError("frequency and values must be equally sized vectors of length at least eight")
    if not np.all(np.isfinite(frequency)) or not np.all(np.isfinite(signal)):
        raise ValueError("PSPS inputs must be finite")
    if trials.ndim != 1 or trials.size == 0 or np.any(trials <= 0):
        raise ValueError("trial spacings must be positive")
    centered = signal - np.mean(signal)
    denominator = max(float(np.sum(centered**2)) * centered.size, np.finfo(float).eps)
    scores = [
        abs(np.sum(centered * np.exp(-2j * np.pi * frequency / spacing))) ** 2 / denominator
        for spacing in trials
    ]
    return np.asarray(scores, dtype=np.float64)


def calibrate_maximum_statistic(
    statistics: NDArray[np.floating], *, alpha: float = 0.05
) -> MaxStatisticCalibration:
    """Calibrate one threshold from per-realization maxima over all trials."""

    values = np.asarray(statistics, dtype=np.float64)
    if values.ndim != 2 or min(values.shape) < 1 or not np.all(np.isfinite(values)):
        raise ValueError("statistics must be a nonempty finite realization-by-trial matrix")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    maxima = np.max(values, axis=1)
    threshold = float(np.quantile(maxima, 1.0 - alpha, method="higher"))
    return MaxStatisticCalibration(threshold, alpha, values.shape[0], values.shape[1], maxima)


def empirical_max_pvalue(
    observed_statistics: Sequence[float] | NDArray[np.floating],
    calibration: MaxStatisticCalibration,
) -> float:
    """Return the plus-one upper-tail p-value for an observed registered maximum."""

    observed = np.asarray(observed_statistics, dtype=np.float64)
    if observed.ndim != 1 or observed.size != calibration.trial_count or not np.all(np.isfinite(observed)):
        raise ValueError("observed statistics must match the calibrated trial family")
    maximum = float(np.max(observed))
    exceedances = int(np.count_nonzero(calibration.maxima >= maximum))
    return (exceedances + 1.0) / (calibration.calibration_size + 1.0)


def evaluate_maximum_calibration(
    evaluation_statistics: NDArray[np.floating],
    calibration: MaxStatisticCalibration,
    *,
    confidence_mask: Sequence[bool] | NDArray[np.bool_] | None = None,
) -> CalibrationEvaluation:
    """Measure independent family-wise false detection and false confidence."""

    values = np.asarray(evaluation_statistics, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != calibration.trial_count
        or values.shape[0] == 0
        or not np.all(np.isfinite(values))
    ):
        raise ValueError("evaluation statistics must match the calibrated trial family")
    detected = np.max(values, axis=1) > calibration.threshold
    if confidence_mask is None:
        confident = detected
    else:
        supplied = np.asarray(confidence_mask, dtype=np.bool_)
        if supplied.shape != detected.shape:
            raise ValueError("confidence_mask must match the number of evaluation realizations")
        confident = detected & supplied
    return CalibrationEvaluation(
        false_positive_rate=float(np.mean(detected)),
        detections=int(np.count_nonzero(detected)),
        evaluation_size=detected.size,
        false_confidence_rate=float(np.mean(confident)),
    )


def assess_spectrum_quality(
    *,
    envelope_pvalue: float,
    alias_score_ratio: float,
    visible_orders: int,
    window_alias_power: float,
    background_relative_spread: float,
    alpha: float = 0.05,
    minimum_alias_ratio: float = 1.15,
    minimum_orders: int = 5,
    maximum_window_alias_power: float = 0.25,
    maximum_background_spread: float = 0.20,
) -> QualityAssessment:
    """Apply the complete registered Stage 6 reason-code policy."""

    numeric = (
        envelope_pvalue,
        alias_score_ratio,
        window_alias_power,
        background_relative_spread,
        alpha,
        minimum_alias_ratio,
        maximum_window_alias_power,
        maximum_background_spread,
    )
    if not all(math.isfinite(value) for value in numeric):
        raise ValueError("quality inputs and thresholds must be finite")
    if not 0 <= envelope_pvalue <= 1 or not 0 < alpha < 1:
        raise ValueError("p-values and alpha are outside their domains")
    if visible_orders < 0 or minimum_orders < 1:
        raise ValueError("order counts must be nonnegative with a positive minimum")
    flags: list[QualityFlag] = []
    if envelope_pvalue > alpha:
        flags.append(QualityFlag.ABSENT_ENVELOPE)
    if alias_score_ratio < minimum_alias_ratio:
        flags.append(QualityFlag.ALIAS_AMBIGUITY)
    if visible_orders < minimum_orders:
        flags.append(QualityFlag.INSUFFICIENT_ORDERS)
    if window_alias_power > maximum_window_alias_power:
        flags.append(QualityFlag.WINDOW_CONTAMINATION)
    if background_relative_spread > maximum_background_spread:
        flags.append(QualityFlag.UNSTABLE_BACKGROUND)
    if QualityFlag.ABSENT_ENVELOPE in flags:
        status: Literal["reliable", "limited", "not_detected"] = "not_detected"
    elif flags:
        status = "limited"
    else:
        status = "reliable"
    return QualityAssessment(tuple(flags), status)
