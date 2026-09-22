"""Physical representations and topology-free controls for the Stage 5 audit."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d  # type: ignore[import-untyped]
from scipy.signal import find_peaks, peak_prominences  # type: ignore[import-untyped]

from topoastero.tda import (
    FloatArray,
    PersistenceDiagram,
    diagram_summary,
    exact_path_persistence,
    farthest_point_landmarks,
    grid_persistence,
    pairwise_distances,
    vietoris_rips_persistence,
)

FeatureMap: TypeAlias = dict[str, float | int | None]


@dataclass(frozen=True, slots=True)
class RepresentationResult:
    """One representation, its diagram, compact summaries, and matched simple controls."""

    representation_id: str
    diagram: PersistenceDiagram
    summaries: FeatureMap
    controls: dict[str, float]
    data: FloatArray


def robust_standardize(values: NDArray[np.floating]) -> FloatArray:
    """Median/MAD standardization with a standard-deviation fallback."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 0 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("values must be a nonempty finite array")
    median = float(np.median(array))
    scale = 1.4826 * float(np.median(np.abs(array - median)))
    if scale <= np.finfo(float).eps:
        scale = float(np.std(array))
    if scale <= np.finfo(float).eps:
        scale = 1.0
    return np.asarray((array - median) / scale, dtype=np.float64)


def _peak_controls(values: FloatArray) -> dict[str, float]:
    peaks, _ = find_peaks(values)
    if peaks.size == 0:
        return {"peak_count": 0.0, "maximum_prominence": 0.0, "total_prominence": 0.0}
    prominence = peak_prominences(values, peaks)[0]
    return {
        "peak_count": float(peaks.size),
        "maximum_prominence": float(np.max(prominence)),
        "total_prominence": float(np.sum(prominence)),
    }


def light_curve_filtration(
    time_days: NDArray[np.floating], relative_flux: NDArray[np.floating]
) -> RepresentationResult:
    """Upper-star path filtration of robustly standardized flux excursions."""

    time = np.asarray(time_days, dtype=np.float64)
    flux = np.asarray(relative_flux, dtype=np.float64)
    if time.ndim != 1 or flux.shape != time.shape or time.size < 3:
        raise ValueError("time and relative_flux must be matching vectors of length at least three")
    if not np.all(np.isfinite(time)) or not np.all(np.isfinite(flux)) or np.any(np.diff(time) <= 0):
        raise ValueError("light-curve samples must be finite and strictly time ordered")
    normalized = robust_standardize(flux)
    metadata = [
        {"sample_index": index, "time_days": float(at), "normalized_flux": float(value)}
        for index, (at, value) in enumerate(zip(time, normalized, strict=True))
    ]
    diagram = exact_path_persistence(normalized, vertex_metadata=metadata)
    return RepresentationResult(
        "light_curve_filtration",
        diagram,
        diagram_summary(diagram, dimension=0, location_key="time_days"),
        _peak_controls(normalized),
        normalized,
    )


def psd_superlevel_filtration(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    *,
    background: NDArray[np.floating] | None = None,
    smoothing_bins: float = 1.0,
) -> RepresentationResult:
    """Upper-star path filtration of robustly normalized ``log(P/B)``."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    values = np.asarray(power, dtype=np.float64)
    if frequency.ndim != 1 or values.shape != frequency.shape or frequency.size < 3:
        raise ValueError("frequency and power must be matching vectors of length at least three")
    if np.any(values <= 0) or not np.all(np.isfinite(frequency)) or np.any(np.diff(frequency) <= 0):
        raise ValueError("PSD coordinates must be ordered and power must be finite and positive")
    if background is None:
        baseline = np.full_like(values, np.median(values))
    else:
        baseline = np.asarray(background, dtype=np.float64)
        if baseline.shape != values.shape or np.any(baseline <= 0) or not np.all(np.isfinite(baseline)):
            raise ValueError("background must be positive, finite, and match power")
    if not math.isfinite(smoothing_bins) or smoothing_bins < 0:
        raise ValueError("smoothing_bins must be finite and nonnegative")
    log_ratio = np.log(values / baseline)
    smoothed = gaussian_filter1d(log_ratio, smoothing_bins, mode="nearest") if smoothing_bins else log_ratio
    normalized = robust_standardize(smoothed)
    metadata = [
        {
            "frequency_index": index,
            "frequency_uHz": float(at),
            "normalized_log_power": float(value),
        }
        for index, (at, value) in enumerate(zip(frequency, normalized, strict=True))
    ]
    diagram = exact_path_persistence(normalized, vertex_metadata=metadata)
    return RepresentationResult(
        "psd_superlevels",
        diagram,
        diagram_summary(diagram, dimension=0, location_key="frequency_uHz"),
        _peak_controls(normalized)
        | {
            "envelope_centroid_uHz": float(
                np.sum(frequency * np.maximum(normalized, 0.0))
                / max(np.sum(np.maximum(normalized, 0.0)), np.finfo(float).eps)
            )
        },
        normalized,
    )


def delay_coordinates(
    values: NDArray[np.floating], *, lag: int, dimension: int
) -> tuple[FloatArray, NDArray[np.int64]]:
    """Construct a standardized delay embedding and its source-time indices."""

    signal = np.asarray(values, dtype=np.float64)
    if signal.ndim != 1 or signal.size < 4 or not np.all(np.isfinite(signal)):
        raise ValueError("values must be a finite vector with at least four samples")
    if lag < 1 or dimension < 2 or (dimension - 1) * lag >= signal.size - 1:
        raise ValueError("lag/dimension do not leave enough embedded points")
    normalized = robust_standardize(signal)
    count = signal.size - (dimension - 1) * lag
    coordinates = np.column_stack(
        [normalized[offset * lag : offset * lag + count] for offset in range(dimension)]
    )
    return np.asarray(coordinates, dtype=np.float64), np.arange(count, dtype=np.int64)


def delay_embedding_filtration(
    values: NDArray[np.floating],
    *,
    lag: int,
    dimension: int = 2,
    landmark_count: int = 24,
    max_edge_quantile: float = 0.85,
) -> RepresentationResult:
    """Vietoris--Rips ``H_0/H_1`` persistence of a delay landmark cloud."""

    coordinates, source = delay_coordinates(values, lag=lag, dimension=dimension)
    count = min(landmark_count, coordinates.shape[0])
    if count < 4:
        raise ValueError("at least four delay landmarks are required")
    landmarks, selected = farthest_point_landmarks(coordinates, count)
    source_indices = source[selected]
    distances = pairwise_distances(landmarks)
    positive = distances[distances > 0]
    if not 0 < max_edge_quantile <= 1 or positive.size == 0:
        raise ValueError("max_edge_quantile must be in (0, 1] and landmarks must be distinct")
    max_edge = float(np.quantile(positive, max_edge_quantile))
    metadata = [
        {
            "landmark_index": index,
            "source_index": int(source_index),
            "coordinate_0": float(point[0]),
            "coordinate_1": float(point[1]),
        }
        for index, (source_index, point) in enumerate(
            zip(source_indices, landmarks, strict=True)
        )
    ]
    diagram = vietoris_rips_persistence(
        landmarks, max_dimension=1, max_edge=max_edge, vertex_metadata=metadata
    )
    summary_h0 = diagram_summary(diagram, dimension=0)
    summary_h1 = diagram_summary(diagram, dimension=1)
    centered = robust_standardize(np.asarray(values, dtype=np.float64))
    autocorrelation = float(np.corrcoef(centered[:-lag], centered[lag:])[0, 1])
    spectrum = np.abs(np.fft.rfft(centered)) ** 2
    probabilities = spectrum / max(float(np.sum(spectrum)), np.finfo(float).eps)
    entropy = -float(np.sum(probabilities * np.log(probabilities + np.finfo(float).eps)))
    features: FeatureMap = {
        "h0_total_persistence": summary_h0["total_persistence"],
        "h0_maximum_persistence": summary_h0["maximum_persistence"],
        "h1_total_persistence": summary_h1["total_persistence"],
        "h1_maximum_persistence": summary_h1["maximum_persistence"],
        "h1_finite_count": summary_h1["finite_count"],
    }
    return RepresentationResult(
        "delay_embedding",
        diagram,
        features,
        {"lag_autocorrelation": autocorrelation, "spectral_entropy": entropy},
        landmarks,
    )


def mode_frequency_cloud_filtration(
    frequency_uHz: NDArray[np.floating],
    degree: NDArray[np.integer],
    *,
    dnu_uHz: float,
) -> RepresentationResult:
    """Vietoris--Rips persistence of normalized frequency/degree mode geometry."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    degrees = np.asarray(degree, dtype=np.int64)
    if frequency.ndim != 1 or degrees.shape != frequency.shape or frequency.size < 4:
        raise ValueError("frequency and degree must be matching vectors with at least four modes")
    if not np.all(np.isfinite(frequency)) or dnu_uHz <= 0 or np.any(degrees < 0):
        raise ValueError("mode cloud values are outside the physical domain")
    order_coordinate = (frequency - np.min(frequency)) / dnu_uHz
    degree_coordinate = degrees / max(2.0, float(np.max(degrees)))
    points = np.column_stack((order_coordinate, degree_coordinate))
    metadata = [
        {
            "mode_index": index,
            "frequency_uHz": float(at),
            "degree": int(ell),
            "radial_order_coordinate": float(order),
        }
        for index, (at, ell, order) in enumerate(
            zip(frequency, degrees, order_coordinate, strict=True)
        )
    ]
    diagram = vietoris_rips_persistence(points, max_dimension=1, vertex_metadata=metadata)
    h0 = diagram_summary(diagram, dimension=0)
    h1 = diagram_summary(diagram, dimension=1)
    distances = pairwise_distances(points)
    nearest = np.partition(distances + np.eye(points.shape[0]) * 1e12, 0, axis=1)[:, 0]
    nearest_mean = float(np.mean(nearest))
    return RepresentationResult(
        "mode_frequency_cloud",
        diagram,
        {
            "h0_total_persistence": h0["total_persistence"],
            "h0_maximum_persistence": h0["maximum_persistence"],
            "h1_maximum_persistence": h1["maximum_persistence"],
        },
        {
            "nearest_neighbor_mean": nearest_mean,
            "nearest_neighbor_cv": float(np.std(nearest)) / max(nearest_mean, 1e-12),
        },
        np.asarray(points, dtype=np.float64),
    )


def cylindrical_echelle_field(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    *,
    trial_dnu_uHz: float,
    order_bins: int = 8,
    phase_bins: int = 16,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Bin ``log(power)`` on ``I x S1`` and return field, orders, and circular phases."""

    frequency = np.asarray(frequency_uHz, dtype=np.float64)
    values = np.asarray(power, dtype=np.float64)
    if frequency.ndim != 1 or values.shape != frequency.shape or frequency.size < 16:
        raise ValueError("frequency/power must be matching vectors with at least 16 samples")
    if (
        not np.all(np.isfinite(frequency))
        or np.any(np.diff(frequency) <= 0)
        or np.any(values <= 0)
        or trial_dnu_uHz <= 0
        or order_bins < 2
        or phase_bins < 3
    ):
        raise ValueError("invalid cylindrical echelle inputs")
    minimum = float(np.min(frequency))
    scaled = (frequency - minimum) / trial_dnu_uHz
    raw_order = np.floor(scaled).astype(int)
    order_edges = np.linspace(float(np.min(raw_order)), float(np.max(raw_order) + 1), order_bins + 1)
    order_index = np.clip(np.digitize(raw_order, order_edges) - 1, 0, order_bins - 1)
    phase = np.mod(scaled, 1.0)
    phase_index = np.minimum((phase * phase_bins).astype(int), phase_bins - 1)
    sums = np.zeros((order_bins, phase_bins), dtype=np.float64)
    counts = np.zeros((order_bins, phase_bins), dtype=np.int64)
    log_power = np.log(values)
    np.add.at(sums, (order_index, phase_index), log_power)
    np.add.at(counts, (order_index, phase_index), 1)
    field = np.divide(sums, counts, out=np.full_like(sums, np.nan), where=counts > 0)
    global_fill = float(np.nanmedian(field))
    for row in range(order_bins):
        valid = np.flatnonzero(np.isfinite(field[row]))
        if valid.size == 0:
            field[row] = global_fill
        elif valid.size == 1:
            field[row] = field[row, valid[0]]
        else:
            extended_x = np.concatenate((valid - phase_bins, valid, valid + phase_bins))
            extended_y = np.tile(field[row, valid], 3)
            field[row] = np.interp(np.arange(phase_bins), extended_x, extended_y)
    normalized = robust_standardize(field)
    order_centers = 0.5 * (order_edges[:-1] + order_edges[1:])
    phase_centers = (np.arange(phase_bins, dtype=np.float64) + 0.5) / phase_bins
    return normalized, np.asarray(order_centers), phase_centers


def cylindrical_echelle_filtration(
    frequency_uHz: NDArray[np.floating],
    power: NDArray[np.floating],
    *,
    trial_dnu_uHz: float,
    order_bins: int = 8,
    phase_bins: int = 16,
    max_dimension: int = 1,
    periodic: bool = True,
) -> RepresentationResult:
    """Upper-star persistence of a periodic echelle field and ridge-linearity control."""

    field, orders, phases = cylindrical_echelle_field(
        frequency_uHz,
        power,
        trial_dnu_uHz=trial_dnu_uHz,
        order_bins=order_bins,
        phase_bins=phase_bins,
    )
    metadata = [
        {
            "pixel_index": row * phase_bins + column,
            "radial_order_coordinate": float(orders[row]),
            "phase": float(phases[column]),
            "field_value": float(field[row, column]),
        }
        for row in range(order_bins)
        for column in range(phase_bins)
    ]
    diagram = grid_persistence(
        field,
        periodic_axes=(False, periodic),
        max_dimension=max_dimension,
        vertex_metadata=metadata,
    )
    h0 = diagram_summary(diagram, dimension=0)
    h1 = diagram_summary(diagram, dimension=1) if max_dimension else {
        "total_persistence": 0.0,
        "maximum_persistence": 0.0,
        "finite_count": 0,
    }
    ridge_columns = np.argmax(field, axis=1)
    angles = 2.0 * np.pi * phases[ridge_columns]
    resultant = abs(np.mean(np.exp(1j * angles)))
    row_contrast = np.max(field, axis=1) - np.median(field, axis=1)
    features: FeatureMap = {
        "h0_total_persistence": h0["total_persistence"],
        "h0_ridge_lifetime": h0["maximum_persistence"],
        "h1_total_persistence": h1["total_persistence"],
        "h1_maximum_persistence": h1["maximum_persistence"],
    }
    return RepresentationResult(
        "cylindrical_echelle",
        diagram,
        features,
        {
            "ridge_circular_resultant": float(resultant),
            "ridge_contrast": float(np.mean(row_contrast)),
        },
        field,
    )
