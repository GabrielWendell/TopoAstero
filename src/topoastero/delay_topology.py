"""Delay-embedding topology and phase-sensitive controls for TopoAstero Stage 7.

The module provides a small, deterministic reference implementation for simulation-only
parameter selection, missing-data-aware delay embeddings, audited Vietoris--Rips persistence,
PSD-preserving surrogate tests, and topology-free coherence controls.  Dimensionality reduction
is intentionally exposed only through :func:`project_for_visualization`; persistence is always
computed on the unreduced embedding (or its registered metric transform).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray
from scipy.signal import fftconvolve  # type: ignore[import-untyped]

from topoastero.tda import (
    PersistenceDiagram,
    diagram_points,
    farthest_point_landmarks,
    vietoris_rips_persistence,
)

FloatArray: TypeAlias = NDArray[np.float64]
BoolArray: TypeAlias = NDArray[np.bool_]
IntArray: TypeAlias = NDArray[np.int64]
DelayMethod = Literal[
    "physics_quarter_period",
    "acf_first_minimum",
    "mutual_information_first_minimum",
    "multiscale_consensus",
]
EmbeddingNormalization = Literal["robust_global", "zscore_global", "none"]
SamplingPolicy = Literal["uniform", "farthest"]
MetricPolicy = Literal["euclidean", "standardized_euclidean", "cosine_chord"]


@dataclass(frozen=True, slots=True)
class DelayCandidate:
    """One delay proposed by a registered selection rule."""

    method: DelayMethod
    lag_samples: int
    lag_seconds: float
    score: float
    available: bool = True

    def to_record(self) -> dict[str, str | int | float | bool]:
        return {
            "method": self.method,
            "lag_samples": self.lag_samples,
            "lag_seconds": self.lag_seconds,
            "score": self.score,
            "available": self.available,
        }


@dataclass(frozen=True, slots=True)
class DelaySelection:
    """Registered delay candidates and the deterministic primary choice."""

    selected_lag: int
    selected_method: DelayMethod
    candidates: tuple[DelayCandidate, ...]
    maximum_lag: int

    def to_record(self) -> dict[str, object]:
        return {
            "selected_lag": self.selected_lag,
            "selected_method": self.selected_method,
            "maximum_lag": self.maximum_lag,
            "candidates": [candidate.to_record() for candidate in self.candidates],
        }


@dataclass(frozen=True, slots=True)
class DelayEmbedding:
    """A missing-aware delay cloud with traceable source-window indices."""

    points: FloatArray
    source_indices: IntArray
    delay: int
    dimension: int
    normalization: EmbeddingNormalization
    total_windows: int
    rejected_windows: int
    sampling: SamplingPolicy

    @property
    def valid_fraction(self) -> float:
        return float((self.total_windows - self.rejected_windows) / self.total_windows)

    def to_record(self) -> dict[str, str | int | float]:
        return {
            "delay": self.delay,
            "dimension": self.dimension,
            "normalization": self.normalization,
            "total_windows": self.total_windows,
            "rejected_windows": self.rejected_windows,
            "valid_fraction": self.valid_fraction,
            "retained_points": int(self.points.shape[0]),
            "sampling": self.sampling,
        }


@dataclass(frozen=True, slots=True)
class PhaseTestResult:
    """A plus-one, maximum-statistic phase-surrogate test result."""

    observed_maximum: float
    null_maxima: FloatArray
    pvalue: float
    alpha: float
    rejected: bool
    trials: int

    def to_record(self) -> dict[str, int | float | bool]:
        return {
            "observed_maximum": self.observed_maximum,
            "null_draws": int(self.null_maxima.size),
            "pvalue": self.pvalue,
            "alpha": self.alpha,
            "rejected": self.rejected,
            "trials": self.trials,
        }


def _signal_mask(
    values: NDArray[np.floating], observed: NDArray[np.bool_] | None = None
) -> tuple[FloatArray, BoolArray]:
    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 8:
        raise ValueError("values must be a one-dimensional series with at least eight samples")
    if observed is None:
        mask = np.isfinite(signal)
    else:
        mask = np.asarray(observed, dtype=np.bool_)
        if mask.shape != signal.shape:
            raise ValueError("observed must have the same shape as values")
        mask = mask & np.isfinite(signal)
    if np.count_nonzero(mask) < 8:
        raise ValueError("at least eight finite observed samples are required")
    return signal, mask


def _filled_signal(values: FloatArray, mask: BoolArray) -> FloatArray:
    if np.all(mask):
        return values.copy()
    locations = np.arange(values.size, dtype=np.float64)
    return np.asarray(
        np.interp(locations, locations[mask], values[mask]),
        dtype=np.float64,
    )


def autocorrelation_curve(
    values: NDArray[np.floating],
    *,
    maximum_lag: int,
    observed: NDArray[np.bool_] | None = None,
) -> FloatArray:
    """Return a pairwise-complete normalized autocorrelation through ``maximum_lag``."""

    signal, mask = _signal_mask(values, observed)
    if not 1 <= maximum_lag < signal.size - 1:
        raise ValueError("maximum_lag must lie between one and len(values)-2")
    center = float(np.mean(signal[mask]))
    variance = float(np.mean((signal[mask] - center) ** 2))
    if variance <= np.finfo(float).eps:
        raise ValueError("autocorrelation is undefined for a constant signal")
    result = np.empty(maximum_lag + 1, dtype=np.float64)
    result[0] = 1.0
    for lag in range(1, maximum_lag + 1):
        valid = mask[:-lag] & mask[lag:]
        if np.count_nonzero(valid) < 2:
            result[lag] = np.nan
        else:
            covariance = np.mean(
                (signal[:-lag][valid] - center) * (signal[lag:][valid] - center)
            )
            result[lag] = float(covariance / variance)
    return result


def first_local_minimum(values: NDArray[np.floating], *, start: int = 1) -> int:
    """Return the first finite local minimum, falling back to the finite global minimum."""

    curve = np.asarray(values, dtype=np.float64)
    if curve.ndim != 1 or curve.size < 3 or not 1 <= start < curve.size:
        raise ValueError("values must be a vector and start must index a positive lag")
    for index in range(start, curve.size - 1):
        if (
            math.isfinite(curve[index - 1])
            and math.isfinite(curve[index])
            and math.isfinite(curve[index + 1])
            and curve[index] <= curve[index - 1]
            and curve[index] < curve[index + 1]
        ):
            return index
    finite = np.flatnonzero(np.isfinite(curve[start:])) + start
    if finite.size == 0:
        raise ValueError("no finite candidate minimum is available")
    return int(finite[np.argmin(curve[finite])])


def mutual_information_curve(
    values: NDArray[np.floating],
    *,
    maximum_lag: int,
    bins: int = 12,
    observed: NDArray[np.bool_] | None = None,
) -> FloatArray:
    """Estimate normalized lagged mutual information with pairwise-complete histograms."""

    signal, mask = _signal_mask(values, observed)
    if not 1 <= maximum_lag < signal.size - 1:
        raise ValueError("maximum_lag must lie between one and len(values)-2")
    if bins < 3:
        raise ValueError("bins must be at least three")
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.unique(np.quantile(signal[mask], quantiles))
    if edges.size < 4:
        raise ValueError("mutual information requires at least three occupied value bins")
    edges[0] = -np.inf
    edges[-1] = np.inf
    result = np.empty(maximum_lag + 1, dtype=np.float64)
    result[0] = 1.0
    for lag in range(1, maximum_lag + 1):
        valid = mask[:-lag] & mask[lag:]
        if np.count_nonzero(valid) < max(8, edges.size):
            result[lag] = np.nan
            continue
        joint = np.histogram2d(
            signal[:-lag][valid], signal[lag:][valid], bins=(edges, edges)
        )[0]
        probability = joint / np.sum(joint)
        left = np.sum(probability, axis=1)
        right = np.sum(probability, axis=0)
        independent = left[:, None] * right[None, :]
        positive = probability > 0
        mutual_information = float(
            np.sum(probability[positive] * np.log(probability[positive] / independent[positive]))
        )
        entropy_left = float(-np.sum(left[left > 0] * np.log(left[left > 0])))
        entropy_right = float(-np.sum(right[right > 0] * np.log(right[right > 0])))
        denominator = math.sqrt(entropy_left * entropy_right)
        result[lag] = mutual_information / denominator if denominator > 0 else np.nan
    return result


def physics_delay_samples(
    frequency_uHz: float,
    cadence_seconds: float,
    *,
    fraction_of_period: float = 0.25,
    maximum_lag: int,
) -> int:
    """Convert an oscillation frequency into a clipped fraction-of-period sample lag."""

    if not math.isfinite(frequency_uHz) or frequency_uHz <= 0:
        raise ValueError("frequency_uHz must be finite and positive")
    if not math.isfinite(cadence_seconds) or cadence_seconds <= 0:
        raise ValueError("cadence_seconds must be finite and positive")
    if not 0 < fraction_of_period <= 0.5 or maximum_lag < 1:
        raise ValueError("fraction_of_period and maximum_lag are outside their valid ranges")
    period_samples = 1e6 / (frequency_uHz * cadence_seconds)
    return int(np.clip(round(fraction_of_period * period_samples), 1, maximum_lag))


def select_delay_parameters(
    values: NDArray[np.floating],
    *,
    cadence_seconds: float,
    physics_frequency_uHz: float,
    observed: NDArray[np.bool_] | None = None,
    maximum_lag: int = 64,
    multiscale_fractions: tuple[float, ...] = (0.25, 0.5, 1.0),
) -> DelaySelection:
    """Compare four simulation-tuned delay rules and select their multiscale consensus."""

    signal, mask = _signal_mask(values, observed)
    maximum = min(maximum_lag, max(2, signal.size // 8))
    acf = autocorrelation_curve(signal, maximum_lag=maximum, observed=mask)
    mutual_information = mutual_information_curve(
        signal, maximum_lag=maximum, observed=mask
    )
    physics = physics_delay_samples(
        physics_frequency_uHz,
        cadence_seconds,
        maximum_lag=maximum,
    )
    acf_lag = first_local_minimum(acf)
    information_lag = first_local_minimum(mutual_information)

    window_lags: list[int] = []
    for fraction in multiscale_fractions:
        if not math.isfinite(fraction) or not 0 < fraction <= 1:
            raise ValueError("multiscale fractions must lie in (0, 1]")
        width = max(32, round(signal.size * fraction))
        width = min(width, signal.size)
        start = (signal.size - width) // 2
        local_maximum = min(maximum, max(2, width // 8))
        local_signal = signal[start : start + width]
        local_mask = mask[start : start + width]
        try:
            local_acf = autocorrelation_curve(
                local_signal,
                maximum_lag=local_maximum,
                observed=local_mask,
            )
            local_information = mutual_information_curve(
                local_signal,
                maximum_lag=local_maximum,
                observed=local_mask,
            )
            window_lags.extend(
                [first_local_minimum(local_acf), first_local_minimum(local_information)]
            )
        except ValueError:
            continue
    consensus_values = [physics, acf_lag, information_lag, *window_lags]
    consensus = int(np.clip(round(float(np.median(consensus_values))), 1, maximum))

    def independence_score(lag: int) -> float:
        acf_term = 1.0 - min(1.0, abs(float(acf[lag]))) if math.isfinite(acf[lag]) else 0.0
        information_term = (
            1.0 - min(1.0, float(mutual_information[lag]))
            if math.isfinite(mutual_information[lag])
            else 0.0
        )
        return float(0.5 * (acf_term + information_term))

    candidates = (
        DelayCandidate(
            "physics_quarter_period",
            physics,
            physics * cadence_seconds,
            independence_score(physics),
        ),
        DelayCandidate(
            "acf_first_minimum",
            acf_lag,
            acf_lag * cadence_seconds,
            independence_score(acf_lag),
        ),
        DelayCandidate(
            "mutual_information_first_minimum",
            information_lag,
            information_lag * cadence_seconds,
            independence_score(information_lag),
        ),
        DelayCandidate(
            "multiscale_consensus",
            consensus,
            consensus * cadence_seconds,
            independence_score(consensus),
            available=bool(window_lags),
        ),
    )
    return DelaySelection(consensus, "multiscale_consensus", candidates, maximum)


def _normalize_signal(
    values: FloatArray, mask: BoolArray, normalization: EmbeddingNormalization
) -> FloatArray:
    result = values.copy()
    if normalization == "none":
        return result
    if normalization == "zscore_global":
        center = float(np.mean(result[mask]))
        scale = float(np.std(result[mask]))
    elif normalization == "robust_global":
        center = float(np.median(result[mask]))
        scale = float(1.4826 * np.median(np.abs(result[mask] - center)))
        if scale <= np.finfo(float).eps:
            scale = float(np.std(result[mask]))
    else:
        raise ValueError(f"unsupported normalization: {normalization}")
    if not math.isfinite(scale) or scale <= np.finfo(float).eps:
        raise ValueError("embedding normalization requires nonconstant observed samples")
    result[mask] = (result[mask] - center) / scale
    return result


def sliding_delay_embedding(
    values: NDArray[np.floating],
    *,
    delay: int,
    dimension: int,
    observed: NDArray[np.bool_] | None = None,
    normalization: EmbeddingNormalization = "robust_global",
    maximum_points: int | None = None,
    sampling: SamplingPolicy = "farthest",
) -> DelayEmbedding:
    """Build a missing-data-aware sliding-window delay embedding.

    Only windows whose every delayed coordinate is observed and finite are retained.  Density
    control is deterministic and records the original starting index of every retained landmark.
    """

    signal, mask = _signal_mask(values, observed)
    if delay < 1 or dimension < 2:
        raise ValueError("delay must be positive and dimension must be at least two")
    total_windows = signal.size - (dimension - 1) * delay
    if total_windows < 4:
        raise ValueError("delay and dimension leave fewer than four embedding windows")
    normalized = _normalize_signal(signal, mask, normalization)
    offsets = np.arange(dimension, dtype=np.int64) * delay
    starts = np.arange(total_windows, dtype=np.int64)
    index_matrix = starts[:, None] + offsets[None, :]
    valid = np.all(mask[index_matrix], axis=1)
    retained_starts = starts[valid]
    points = normalized[index_matrix[valid]]
    if points.shape[0] < 4:
        raise ValueError("fewer than four complete delay windows survive missing-data filtering")
    if maximum_points is not None:
        if maximum_points < 4:
            raise ValueError("maximum_points must be at least four")
        if points.shape[0] > maximum_points:
            if sampling == "uniform":
                chosen = np.linspace(0, points.shape[0] - 1, maximum_points).round().astype(int)
            elif sampling == "farthest":
                candidate_count = min(points.shape[0], maximum_points * 8)
                candidates = (
                    np.linspace(0, points.shape[0] - 1, candidate_count).round().astype(int)
                )
                _, local = farthest_point_landmarks(points[candidates], maximum_points)
                chosen = candidates[local]
            else:
                raise ValueError(f"unsupported sampling policy: {sampling}")
            order = np.argsort(chosen)
            chosen = np.asarray(chosen[order], dtype=np.int64)
            points = points[chosen]
            retained_starts = retained_starts[chosen]
    elif sampling not in {"uniform", "farthest"}:
        raise ValueError(f"unsupported sampling policy: {sampling}")
    return DelayEmbedding(
        points=np.asarray(points, dtype=np.float64),
        source_indices=np.asarray(retained_starts, dtype=np.int64),
        delay=delay,
        dimension=dimension,
        normalization=normalization,
        total_windows=total_windows,
        rejected_windows=int(total_windows - np.count_nonzero(valid)),
        sampling=sampling,
    )


def project_for_visualization(
    points: NDArray[np.floating], *, components: int = 2
) -> tuple[FloatArray, FloatArray]:
    """Return a PCA projection and explained fractions for visualization only."""

    cloud = np.asarray(points, dtype=np.float64)
    if cloud.ndim != 2 or cloud.shape[0] < 2 or cloud.shape[1] < components:
        raise ValueError("points must be a matrix with enough rows and columns")
    if not np.all(np.isfinite(cloud)) or components not in {2, 3}:
        raise ValueError("projection requires finite points and two or three components")
    centered = cloud - np.mean(cloud, axis=0)
    _, singular, vectors = np.linalg.svd(centered, full_matrices=False)
    coordinates = centered @ vectors[:components].T
    variance = singular**2
    explained = variance[:components] / np.sum(variance) if np.sum(variance) > 0 else np.zeros(components)
    return np.asarray(coordinates, dtype=np.float64), np.asarray(explained, dtype=np.float64)


def metric_cloud(points: NDArray[np.floating], metric: MetricPolicy) -> FloatArray:
    """Transform a cloud so Euclidean VR realizes the registered metric policy."""

    cloud = np.asarray(points, dtype=np.float64)
    if cloud.ndim != 2 or cloud.shape[0] < 2 or not np.all(np.isfinite(cloud)):
        raise ValueError("points must be a finite matrix with at least two rows")
    if metric == "euclidean":
        return cloud.copy()
    if metric == "standardized_euclidean":
        scale = np.std(cloud, axis=0)
        scale[scale <= np.finfo(float).eps] = 1.0
        return np.asarray((cloud - np.mean(cloud, axis=0)) / scale, dtype=np.float64)
    if metric == "cosine_chord":
        norm = np.linalg.norm(cloud, axis=1)
        norm[norm <= np.finfo(float).eps] = 1.0
        return np.asarray(cloud / norm[:, None], dtype=np.float64)
    raise ValueError(f"unsupported metric policy: {metric}")


def delay_persistence(
    embedding: DelayEmbedding,
    *,
    maximum_dimension: int = 1,
    metric: MetricPolicy = "euclidean",
    maximum_edge: float | None = None,
) -> PersistenceDiagram:
    """Compute audited VR persistence on the unreduced registered embedding."""

    metadata = [
        {"source_index": int(index), "delay": embedding.delay}
        for index in embedding.source_indices
    ]
    return vietoris_rips_persistence(
        metric_cloud(embedding.points, metric),
        max_dimension=maximum_dimension,
        max_edge=maximum_edge,
        vertex_metadata=metadata,
    )


def persistence_entropy(diagram: PersistenceDiagram, *, dimension: int) -> float:
    """Return normalized Shannon entropy of positive finite persistence lifetimes."""

    lifetimes = np.asarray(
        [pair.persistence for pair in diagram.finite(dimension) if pair.persistence is not None],
        dtype=np.float64,
    )
    if lifetimes.size <= 1 or np.sum(lifetimes) <= 0:
        return 0.0
    weights = lifetimes / np.sum(lifetimes)
    return float(-np.sum(weights * np.log(weights)) / np.log(lifetimes.size))


def diagram_features(diagram: PersistenceDiagram) -> dict[str, float | int]:
    """Return compact H0/H1/H2 summaries without assigning deaths to essential classes."""

    features: dict[str, float | int] = {}
    for dimension in (0, 1, 2):
        pairs = diagram.finite(dimension)
        lifetimes = np.asarray(
            [pair.persistence for pair in pairs if pair.persistence is not None],
            dtype=np.float64,
        )
        features[f"h{dimension}_count"] = int(lifetimes.size)
        features[f"h{dimension}_total_persistence"] = float(np.sum(lifetimes))
        features[f"h{dimension}_maximum_persistence"] = (
            float(np.max(lifetimes)) if lifetimes.size else 0.0
        )
        features[f"h{dimension}_entropy"] = persistence_entropy(
            diagram, dimension=dimension
        )
    return features


def normalized_diagram_points(
    diagram: PersistenceDiagram, *, dimension: int
) -> FloatArray:
    """Return finite diagram points normalized by their largest death scale."""

    points = diagram_points(diagram, dimension=dimension)
    if points.size == 0:
        return points
    scale = float(np.max(points[:, 1]))
    return np.asarray(points / scale, dtype=np.float64) if scale > 0 else points


def maximum_statistic_phase_test(
    observed_statistics: NDArray[np.floating],
    surrogate_statistics: NDArray[np.floating],
    *,
    alpha: float = 0.05,
) -> PhaseTestResult:
    """Test the maximum registered statistic against paired surrogate maxima."""

    observed = np.asarray(observed_statistics, dtype=np.float64)
    null = np.asarray(surrogate_statistics, dtype=np.float64)
    if observed.ndim != 1 or observed.size == 0 or not np.all(np.isfinite(observed)):
        raise ValueError("observed_statistics must be a nonempty finite vector")
    if null.ndim != 2 or null.shape[1] != observed.size or not np.all(np.isfinite(null)):
        raise ValueError("surrogate_statistics must be a finite draw-by-trial matrix")
    if null.shape[0] < 3 or not 0 < alpha < 1:
        raise ValueError("at least three surrogate draws and alpha in (0, 1) are required")
    observed_maximum = float(np.max(observed))
    null_maxima = np.asarray(np.max(null, axis=1), dtype=np.float64)
    pvalue = float((1 + np.count_nonzero(null_maxima >= observed_maximum)) / (null.size // observed.size + 1))
    return PhaseTestResult(
        observed_maximum=observed_maximum,
        null_maxima=null_maxima,
        pvalue=pvalue,
        alpha=alpha,
        rejected=pvalue <= alpha,
        trials=int(observed.size),
    )


def _morlet_concentration(values: FloatArray) -> float:
    scales = np.geomspace(2.0, max(4.0, min(64.0, values.size / 8.0)), 10)
    energies: list[float] = []
    for scale in scales:
        half_width = max(4, math.ceil(4.0 * scale))
        support = np.arange(-half_width, half_width + 1, dtype=np.float64)
        wavelet = np.exp(1j * 5.0 * support / scale) * np.exp(
            -0.5 * (support / scale) ** 2
        )
        wavelet /= math.sqrt(float(np.sum(np.abs(wavelet) ** 2)))
        coefficients = fftconvolve(values, np.conjugate(wavelet[::-1]), mode="same")
        energies.append(float(np.mean(np.abs(coefficients) ** 2)))
    array = np.asarray(energies, dtype=np.float64)
    return float(np.max(array) / np.sum(array)) if np.sum(array) > 0 else 0.0


def classical_coherence_features(
    values: NDArray[np.floating],
    *,
    cadence_seconds: float,
    observed: NDArray[np.bool_] | None = None,
    maximum_lag: int = 128,
) -> dict[str, float]:
    """Compute registered topology-free phase/coherence controls on the same series."""

    signal, mask = _signal_mask(values, observed)
    if not math.isfinite(cadence_seconds) or cadence_seconds <= 0:
        raise ValueError("cadence_seconds must be finite and positive")
    filled = _filled_signal(signal, mask)
    centered = filled - np.mean(filled)
    scale = float(np.std(centered))
    if scale <= np.finfo(float).eps:
        raise ValueError("classical coherence features require a nonconstant signal")
    centered /= scale
    lag_limit = min(maximum_lag, centered.size // 4)
    acf = autocorrelation_curve(centered, maximum_lag=lag_limit)
    below = np.flatnonzero(np.abs(acf[1:]) <= math.exp(-1.0))
    coherence_lag = int(below[0] + 1) if below.size else lag_limit
    positive = acf[1:]
    nonpositive = np.flatnonzero(positive <= 0)
    positive_stop = int(nonpositive[0]) if nonpositive.size else positive.size
    acf_integral = float(np.sum(np.maximum(positive[:positive_stop], 0.0)))

    spectrum = np.abs(np.fft.rfft(centered)) ** 2
    spectrum = spectrum[1:]
    probability = spectrum / np.sum(spectrum)
    spectral_entropy = float(-np.sum(probability * np.log(probability + 1e-300)) / np.log(probability.size))
    dominant_fraction = float(np.max(probability))
    transform = np.fft.rfft(centered)
    phases = np.angle(transform[1:])
    if phases.size >= 3:
        coupling = float(
            abs(np.mean(np.exp(1j * (phases[:-2] + phases[2:] - 2.0 * phases[1:-1]))))
        )
    else:
        coupling = 0.0
    return {
        "coherence_time_seconds": coherence_lag * cadence_seconds,
        "acf_decay_lag": float(coherence_lag),
        "acf_integral": acf_integral,
        "wavelet_concentration": _morlet_concentration(centered),
        "spectral_entropy": spectral_entropy,
        "dominant_fourier_fraction": dominant_fraction,
        "fourier_phase_coupling": coupling,
    }


def relative_fourier_amplitude_error(
    reference: NDArray[np.floating], surrogate: NDArray[np.floating]
) -> float:
    """Return relative L2 error between centered Fourier amplitudes."""

    left, left_mask = _signal_mask(reference)
    right, right_mask = _signal_mask(surrogate)
    if left.shape != right.shape or not np.all(left_mask) or not np.all(right_mask):
        raise ValueError("reference and surrogate must be equally sized and fully finite")
    left_amplitude = np.abs(np.fft.rfft(left - np.mean(left)))
    right_amplitude = np.abs(np.fft.rfft(right - np.mean(right)))
    denominator = float(np.linalg.norm(left_amplitude))
    if denominator <= np.finfo(float).eps:
        raise ValueError("reference Fourier amplitude is degenerate")
    return float(np.linalg.norm(left_amplitude - right_amplitude) / denominator)


def rolling_window_bounds(samples: int, *, width: int, step: int) -> tuple[tuple[int, int], ...]:
    """Return deterministic half-open rolling-window bounds, including the final endpoint."""

    if samples < 4 or width < 4 or width > samples or step < 1:
        raise ValueError("rolling window samples, width, and step are inconsistent")
    starts = list(range(0, samples - width + 1, step))
    final = samples - width
    if starts[-1] != final:
        starts.append(final)
    return tuple((start, start + width) for start in starts)
