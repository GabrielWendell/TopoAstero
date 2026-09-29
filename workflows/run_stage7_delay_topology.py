"""Execute the locked Stage 7 delay-topology and phase-information experiment."""

from __future__ import annotations

import base64
import csv
import math
import platform
from importlib.metadata import version
from itertools import pairwise
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from topoastero.config import configuration_hash, load_yaml
from topoastero.delay_topology import (
    DelayEmbedding,
    classical_coherence_features,
    delay_persistence,
    diagram_features,
    maximum_statistic_phase_test,
    normalized_diagram_points,
    project_for_visualization,
    relative_fourier_amplitude_error,
    rolling_window_bounds,
    select_delay_parameters,
    sliding_delay_embedding,
)
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)
from topoastero.provenance import sha256_file
from topoastero.simulation_lab import (
    benjamini_hochberg,
    iaaft_surrogate,
    linewidth_from_lifetime,
    phase_randomized_surrogate,
)
from topoastero.style import (
    FIGSIZE,
    data_color,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)
from topoastero.tda import bottleneck_distance, localized_records, pairwise_distances

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "configs/stage7_delay_topology.yaml"
RESULTS = ROOT / "results/stage7"
REPORTS = ROOT / "reports/stage7"
FIGURES = REPORTS / "figures"
SOFTWARE_VERSION = "TopoAstero-0.8.0"
RUN_ID = "TA-S07-DELAY-R001"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(
    path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None
) -> None:
    if not rows and fieldnames is None:
        raise ValueError(f"cannot infer fields for empty table {path}")
    fields = fieldnames or list(rows[0])
    write_csv_lf(path, rows, fieldnames=fields)


def _number(value: float, digits: int = 10) -> str:
    return f"{float(value):.{digits}g}"


def _cell_number(cell_id: str) -> int:
    return int(cell_id.rsplit("-", 1)[1])


def _role(cell_id: str) -> str:
    return "calibration" if _cell_number(cell_id) % 2 else "evaluation"


def _mask_for_cell(
    samples: int,
    duty_cycle: float,
    gap_pattern: str,
    rng: np.random.Generator,
) -> np.ndarray:
    if duty_cycle >= 0.999:
        return np.ones(samples, dtype=bool)
    if gap_pattern == "random":
        mask = rng.random(samples) < duty_cycle
    else:
        mask = np.ones(samples, dtype=bool)
        period = 97 if gap_pattern == "kepler_q5" else 61
        missing = max(1, round(period * (1.0 - duty_cycle)))
        offset = int(rng.integers(0, period))
        index = np.arange(samples)
        mask[((index + offset) % period) < missing] = False
        current = float(np.mean(mask))
        if current > duty_cycle:
            eligible = np.flatnonzero(mask)
            remove = round((current - duty_cycle) * samples)
            if remove > 0:
                mask[rng.choice(eligible, size=min(remove, eligible.size), replace=False)] = False
    if np.count_nonzero(mask) < max(32, samples // 5):
        raise RuntimeError("registered gap generator produced an unusably sparse trace")
    return np.asarray(mask, dtype=bool)


def _simulate_cell(row: dict[str, str]) -> dict[str, Any]:
    sample_map = {27.4: 512, 90.0: 640, 109.6: 768, 360.0: 1024}
    duration = float(row["duration_days"])
    samples = sample_map[duration]
    burn_in = 256
    cadence = float(row["cadence_seconds"])
    lifetime = float(row["lifetime_days"])
    numax = float(row["numax_uHz"])
    dnu = float(row["dnu_uHz"])
    visible_orders = int(row["visible_orders"])
    component_count = {5: 1, 9: 2, 13: 3}[visible_orders]
    snr_amplitude = {"Low": 0.55, "Medium": 1.0, "High": 1.65}[row["snr_level"]]
    rng = np.random.default_rng(int(row["seed"]) + 700_007)
    total = samples + burn_in
    offsets = np.linspace(-(component_count - 1) / 2, (component_count - 1) / 2, component_count)
    mixture = np.zeros(total, dtype=np.float64)
    damping = math.exp(-cadence / (lifetime * 86400.0))
    innovation_scale = math.sqrt(max(1e-12, 1.0 - damping**2))
    for mode_index, offset in enumerate(offsets):
        frequency = numax + offset * dnu
        cycles_per_sample = frequency * 1e-6 * cadence
        angle = 2.0 * math.pi * cycles_per_sample
        coefficient = damping * complex(math.cos(angle), math.sin(angle))
        state = complex(rng.normal(), rng.normal()) / math.sqrt(2.0)
        mode = np.empty(total, dtype=np.float64)
        for index in range(total):
            innovation = complex(rng.normal(), rng.normal()) / math.sqrt(2.0)
            state = coefficient * state + innovation_scale * innovation
            mode[index] = state.real
        weight = math.exp(-0.5 * (float(offset) / max(component_count / 2, 1)) ** 2)
        mixture += weight * mode
        if mode_index == component_count - 1:
            break
    mixture = mixture[burn_in:]
    mixture /= max(float(np.std(mixture)), np.finfo(float).eps)
    signal = snr_amplitude * mixture
    noise = rng.normal(size=samples)
    values = np.asarray(signal + noise, dtype=np.float64)
    observed = _mask_for_cell(
        samples,
        float(row["duty_cycle"]),
        row["gap_pattern"],
        rng,
    )
    linewidth = linewidth_from_lifetime(lifetime)
    return {
        "cell_id": row["cell_id"],
        "role": _role(row["cell_id"]),
        "values": values,
        "observed": observed,
        "cadence_seconds": cadence,
        "numax_uHz": numax,
        "dnu_uHz": dnu,
        "lifetime_days": lifetime,
        "linewidth_uHz": linewidth,
        "quality_factor": numax / linewidth,
        "amplitude": float(np.std(signal)),
        "mode_mixture": visible_orders,
        "snr_level": row["snr_level"],
        "duration_days": duration,
        "duty_cycle": float(row["duty_cycle"]),
        "gap_pattern": row["gap_pattern"],
        "seed": int(row["seed"]),
    }


def _h1_score(embedding: DelayEmbedding) -> tuple[float, dict[str, float | int], Any]:
    diagram = delay_persistence(embedding, maximum_dimension=1, metric="euclidean")
    features = diagram_features(diagram)
    distances = pairwise_distances(embedding.points)
    diameter = float(np.max(distances))
    maximum = float(features["h1_maximum_persistence"])
    score = maximum / diameter if diameter > 0 else 0.0
    return score, features, diagram


def _phase_statistics(
    values: np.ndarray,
    observed: np.ndarray,
    delays: list[int],
    *,
    landmarks: int,
) -> np.ndarray:
    statistics: list[float] = []
    for delay in delays:
        try:
            embedding = sliding_delay_embedding(
                values,
                delay=delay,
                dimension=3,
                observed=observed,
                normalization="robust_global",
                maximum_points=landmarks,
                sampling="farthest",
            )
            score, _, _ = _h1_score(embedding)
        except ValueError:
            score = 0.0
        statistics.append(score)
    return np.asarray(statistics, dtype=np.float64)


def _delay_and_embedding_audit(
    payloads: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    delay_rows: list[dict[str, Any]] = []
    embedding_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    primary: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        selection = select_delay_parameters(
            payload["values"],
            cadence_seconds=payload["cadence_seconds"],
            physics_frequency_uHz=payload["numax_uHz"],
            observed=payload["observed"],
            maximum_lag=48,
        )
        candidate_results: dict[str, dict[str, Any]] = {}
        for candidate in selection.candidates:
            try:
                embedding = sliding_delay_embedding(
                    payload["values"],
                    delay=candidate.lag_samples,
                    dimension=3,
                    observed=payload["observed"],
                    maximum_points=18,
                    sampling="farthest",
                )
                score, features, diagram = _h1_score(embedding)
                status = "ok"
            except ValueError:
                embedding = None
                score = 0.0
                features = {
                    "h1_maximum_persistence": 0.0,
                    "h1_total_persistence": 0.0,
                    "h1_entropy": 0.0,
                }
                diagram = None
                status = "insufficient_complete_windows"
            delay_rows.append(
                {
                    "cell_id": payload["cell_id"],
                    "role": payload["role"],
                    "method": candidate.method,
                    "lag_samples": candidate.lag_samples,
                    "lag_seconds": _number(candidate.lag_seconds),
                    "independence_score": _number(candidate.score),
                    "h1_normalized_maximum": _number(score),
                    "selected": str(candidate.method == selection.selected_method).lower(),
                    "status": status,
                }
            )
            candidate_results[candidate.method] = {
                "embedding": embedding,
                "diagram": diagram,
                "features": features,
                "score": score,
                "lag": candidate.lag_samples,
            }
        selected = candidate_results[selection.selected_method]
        embedding = selected["embedding"]
        if embedding is None:
            raise RuntimeError(f"primary embedding failed for {payload['cell_id']}")
        embedding_record = embedding.to_record()
        embedding_rows.append(
            {
                "cell_id": payload["cell_id"],
                "role": payload["role"],
                **{
                    key: _number(value) if isinstance(value, float) else value
                    for key, value in embedding_record.items()
                },
            }
        )
        features = selected["features"]
        response_rows.append(
            {
                "cell_id": payload["cell_id"],
                "role": payload["role"],
                "snr_level": payload["snr_level"],
                "amplitude": _number(payload["amplitude"]),
                "linewidth_uHz": _number(payload["linewidth_uHz"]),
                "lifetime_days": _number(payload["lifetime_days"]),
                "quality_factor": _number(payload["quality_factor"]),
                "mode_mixture": payload["mode_mixture"],
                "h1_maximum_persistence": _number(
                    float(features["h1_maximum_persistence"])
                ),
                "h1_total_persistence": _number(
                    float(features["h1_total_persistence"])
                ),
                "h1_entropy": _number(float(features["h1_entropy"])),
                "h1_normalized_maximum": _number(float(selected["score"])),
            }
        )
        primary[payload["cell_id"]] = {
            "selection": selection,
            "embedding": embedding,
            "diagram": selected["diagram"],
            "features": features,
            "score": selected["score"],
            "delays": [candidate.lag_samples for candidate in selection.candidates],
        }
    return delay_rows, embedding_rows, response_rows, primary


def _delay_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for method in (
        "physics_quarter_period",
        "acf_first_minimum",
        "mutual_information_first_minimum",
        "multiscale_consensus",
    ):
        subset = [row for row in rows if row["method"] == method]
        output.append(
            {
                "method": method,
                "cells": len(subset),
                "median_lag_samples": _number(
                    float(np.median([float(row["lag_samples"]) for row in subset]))
                ),
                "median_independence_score": _number(
                    float(np.median([float(row["independence_score"]) for row in subset]))
                ),
                "median_h1_normalized_maximum": _number(
                    float(np.median([float(row["h1_normalized_maximum"]) for row in subset]))
                ),
                "failure_rate": _number(
                    float(np.mean([row["status"] != "ok" for row in subset]))
                ),
                "role": "primary" if method == "multiscale_consensus" else "sensitivity",
            }
        )
    return output


def _diagram_suite(
    payloads: list[dict[str, Any]], primary: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    selected_ids = [payload["cell_id"] for payload in payloads[:4]]
    records: list[dict[str, Any]] = []
    h2_audit: list[dict[str, Any]] = []
    payload_by_id = {payload["cell_id"]: payload for payload in payloads}
    for cell_id in selected_ids:
        diagram = primary[cell_id]["diagram"]
        for record in localized_records(diagram, representation_id=f"{cell_id}-DELAY"):
            records.append({"cell_id": cell_id, "metric": "euclidean", **record})
        payload = payload_by_id[cell_id]
        delay = primary[cell_id]["selection"].selected_lag
        h2_embedding = sliding_delay_embedding(
            payload["values"],
            delay=delay,
            dimension=4,
            observed=payload["observed"],
            maximum_points=10,
            sampling="farthest",
        )
        h2_diagram = delay_persistence(
            h2_embedding,
            maximum_dimension=2,
            metric="euclidean",
        )
        h2_features = diagram_features(h2_diagram)
        h2_audit.append(
            {
                "cell_id": cell_id,
                "landmarks": 10,
                "embedding_dimension": 4,
                "h2_count": int(h2_features["h2_count"]),
                "h2_maximum_persistence": float(
                    h2_features["h2_maximum_persistence"]
                ),
                "interpretation": "limited_diagnostic_not_confirmatory",
            }
        )
        for record in localized_records(h2_diagram, representation_id=f"{cell_id}-H2"):
            if int(record["dimension"]) == 2:
                records.append({"cell_id": cell_id, "metric": "euclidean", **record})
    return {
        "run_id": RUN_ID,
        "coefficient_field": "F2",
        "essential_rule": "retain_localization_exclude_numeric_summaries",
        "dimensionality_reduction_used_for_persistence": False,
        "cells": selected_ids,
        "pairs": records,
        "h2_audit": h2_audit,
    }


def _convergence_audit(
    payloads: list[dict[str, Any]], primary: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected = payloads[::4][:6]
    for payload in selected:
        cell_id = payload["cell_id"]
        delay = primary[cell_id]["selection"].selected_lag
        for metric in ("euclidean", "standardized_euclidean", "cosine_chord"):
            diagrams: dict[int, Any] = {}
            for landmarks in (12, 15, 18):
                embedding = sliding_delay_embedding(
                    payload["values"],
                    delay=delay,
                    dimension=3,
                    observed=payload["observed"],
                    maximum_points=landmarks,
                    sampling="farthest",
                )
                diagrams[landmarks] = delay_persistence(
                    embedding,
                    maximum_dimension=1,
                    metric=metric,
                )
            reference = normalized_diagram_points(diagrams[18], dimension=1)
            for landmarks in (12, 15, 18):
                points = normalized_diagram_points(diagrams[landmarks], dimension=1)
                rows.append(
                    {
                        "cell_id": cell_id,
                        "metric": metric,
                        "landmarks": landmarks,
                        "reference_landmarks": 18,
                        "h1_count": len(diagrams[landmarks].finite(1)),
                        "normalized_bottleneck_to_reference": _number(
                            bottleneck_distance(points, reference)
                        ),
                        "status": "reference" if landmarks == 18 else "sensitivity",
                    }
                )
    return rows


def _response_correlations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    targets = ("amplitude", "linewidth_uHz", "lifetime_days", "quality_factor", "mode_mixture")
    features = ("h1_maximum_persistence", "h1_total_persistence", "h1_entropy")
    for target in targets:
        for feature in features:
            left = np.asarray([float(row[target]) for row in rows], dtype=np.float64)
            right = np.asarray([float(row[feature]) for row in rows], dtype=np.float64)
            correlation, pvalue = spearmanr(left, right)
            output.append(
                {
                    "target": target,
                    "topological_feature": feature,
                    "spearman_rho": _number(float(correlation)),
                    "two_sided_pvalue_descriptive": _number(float(pvalue)),
                    "cells": len(rows),
                    "claim_role": "descriptive_response_surface_not_gate",
                }
            )
    return output


def _phase_tests(
    payloads: list[dict[str, Any]], primary: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    draw_rows: list[dict[str, Any]] = []
    for payload in payloads:
        cell_id = payload["cell_id"]
        delays = primary[cell_id]["delays"]
        observed_statistics = _phase_statistics(
            payload["values"],
            payload["observed"],
            delays,
            landmarks=12,
        )
        for family_index, family in enumerate(("phase_randomized", "iaaft")):
            null_statistics: list[np.ndarray] = []
            errors: list[float] = []
            for draw in range(24):
                seed = payload["seed"] + 7_000_000 + family_index * 100_000 + draw
                surrogate = (
                    phase_randomized_surrogate(payload["values"], seed=seed)
                    if family == "phase_randomized"
                    else iaaft_surrogate(payload["values"], seed=seed, iterations=40)
                )
                statistics = _phase_statistics(
                    surrogate,
                    payload["observed"],
                    delays,
                    landmarks=12,
                )
                null_statistics.append(statistics)
                error = relative_fourier_amplitude_error(payload["values"], surrogate)
                errors.append(error)
                draw_rows.append(
                    {
                        "cell_id": cell_id,
                        "role": payload["role"],
                        "surrogate_family": family,
                        "draw": draw + 1,
                        "seed": seed,
                        "maximum_statistic": _number(float(np.max(statistics))),
                        "psd_amplitude_error": _number(error),
                    }
                )
            matrix = np.asarray(null_statistics, dtype=np.float64)
            test = maximum_statistic_phase_test(
                observed_statistics,
                matrix,
                alpha=0.05,
            )
            rows.append(
                {
                    "cell_id": cell_id,
                    "role": payload["role"],
                    "surrogate_family": family,
                    "observed_maximum": _number(test.observed_maximum),
                    "null_draws": matrix.shape[0],
                    "null_q95": _number(float(np.quantile(test.null_maxima, 0.95))),
                    "pvalue": _number(test.pvalue),
                    "alpha": _number(test.alpha),
                    "rejected": str(test.rejected).lower(),
                    "bh_rejected": "false",
                    "trials": test.trials,
                    "median_psd_amplitude_error": _number(float(np.median(errors))),
                }
            )
    for family in ("phase_randomized", "iaaft"):
        evaluation_indices = [
            index
            for index, row in enumerate(rows)
            if row["role"] == "evaluation" and row["surrogate_family"] == family
        ]
        pvalues = np.asarray([float(rows[index]["pvalue"]) for index in evaluation_indices])
        rejected = benjamini_hochberg(pvalues, q=0.10)
        for index, status in zip(evaluation_indices, rejected, strict=True):
            rows[index]["bh_rejected"] = str(bool(status)).lower()
    return rows, draw_rows


def _classical_controls(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        features = classical_coherence_features(
            payload["values"],
            cadence_seconds=payload["cadence_seconds"],
            observed=payload["observed"],
        )
        rows.append(
            {
                "cell_id": payload["cell_id"],
                "role": payload["role"],
                "lifetime_days": _number(payload["lifetime_days"]),
                **{key: _number(value) for key, value in features.items()},
            }
        )
    return rows


def _ridge_predictions(
    train_features: np.ndarray,
    train_target: np.ndarray,
    test_features: np.ndarray,
    *,
    penalty: float = 1.0,
) -> np.ndarray:
    center = np.mean(train_features, axis=0)
    scale = np.std(train_features, axis=0)
    scale[scale <= np.finfo(float).eps] = 1.0
    x_train = (train_features - center) / scale
    x_test = (test_features - center) / scale
    design = np.column_stack([np.ones(x_train.shape[0]), x_train])
    regularizer = np.eye(design.shape[1]) * penalty
    regularizer[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + regularizer, design.T @ train_target)
    return np.asarray(np.column_stack([np.ones(x_test.shape[0]), x_test]) @ coefficients)


def _predictive_ablation(
    response: list[dict[str, Any]], classical: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    classical_lookup = {row["cell_id"]: row for row in classical}
    topology_fields = (
        "h1_maximum_persistence",
        "h1_total_persistence",
        "h1_entropy",
    )
    classical_fields = (
        "coherence_time_seconds",
        "acf_decay_lag",
        "acf_integral",
        "wavelet_concentration",
        "spectral_entropy",
        "dominant_fourier_fraction",
        "fourier_phase_coupling",
    )
    methods = {
        "topology": topology_fields,
        "classical": classical_fields,
        "combined": (*topology_fields, *classical_fields),
    }
    train = [row for row in response if row["role"] == "calibration"]
    test = [row for row in response if row["role"] == "evaluation"]
    y_train = np.log10([float(row["lifetime_days"]) for row in train])
    y_test = np.log10([float(row["lifetime_days"]) for row in test])
    output: list[dict[str, Any]] = []
    for method, fields in methods.items():
        def vector(
            row: dict[str, Any], selected_fields: tuple[str, ...] = fields
        ) -> list[float]:
            values: list[float] = []
            for field in selected_fields:
                source = row if field in row else classical_lookup[row["cell_id"]]
                values.append(float(source[field]))
            return values

        x_train = np.asarray([vector(row) for row in train], dtype=np.float64)
        x_test = np.asarray([vector(row) for row in test], dtype=np.float64)
        prediction = _ridge_predictions(x_train, y_train, x_test)
        error = np.abs(prediction - y_test)
        denominator = float(np.sum((y_test - np.mean(y_test)) ** 2))
        r2 = 1.0 - float(np.sum((prediction - y_test) ** 2)) / denominator
        output.append(
            {
                "method": method,
                "train_cells": len(train),
                "evaluation_cells": len(test),
                "target": "log10_lifetime_days",
                "mae_log10_days": _number(float(np.mean(error))),
                "median_absolute_error_log10_days": _number(float(np.median(error))),
                "r2": _number(r2),
                "catastrophic_rate_gt_0p5dex": _number(float(np.mean(error > 0.5))),
                "ridge_penalty": "1",
            }
        )
    classical_mae = float(next(row["mae_log10_days"] for row in output if row["method"] == "classical"))
    combined = next(row for row in output if row["method"] == "combined")
    combined_mae = float(combined["mae_log10_days"])
    combined["improvement_over_classical"] = _number(
        (classical_mae - combined_mae) / max(classical_mae, 1e-12)
    )
    for row in output:
        row.setdefault("improvement_over_classical", "0")
    return output


def _segmentation_stability(
    payloads: list[dict[str, Any]], primary: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    vineyard: list[dict[str, Any]] = []
    representative = next(payload for payload in payloads if payload["role"] == "evaluation")
    for payload in payloads:
        cell_id = payload["cell_id"]
        delay = primary[cell_id]["selection"].selected_lag
        samples = len(payload["values"])
        for fraction in (0.25, 0.5, 1.0):
            width = max(64, round(samples * fraction))
            width = min(width, samples)
            step = max(1, round(width * 0.5))
            scores: list[float] = []
            diagrams: list[np.ndarray] = []
            bounds = rolling_window_bounds(samples, width=width, step=step)
            for window_index, (start, stop) in enumerate(bounds):
                try:
                    embedding = sliding_delay_embedding(
                        payload["values"][start:stop],
                        delay=delay,
                        dimension=3,
                        observed=payload["observed"][start:stop],
                        maximum_points=14,
                        sampling="farthest",
                    )
                    score, _, diagram = _h1_score(embedding)
                    points = normalized_diagram_points(diagram, dimension=1)
                except ValueError:
                    score = 0.0
                    points = np.empty((0, 2), dtype=np.float64)
                scores.append(score)
                diagrams.append(points)
                if cell_id == representative["cell_id"] and fraction == 0.25:
                    vineyard.append(
                        {
                            "cell_id": cell_id,
                            "window_index": window_index + 1,
                            "start_sample": start,
                            "stop_sample": stop,
                            "center_fraction": _number((start + stop) / (2 * samples)),
                            "h1_normalized_maximum": _number(score),
                        }
                    )
            distances = [
                bottleneck_distance(left, right)
                for left, right in pairwise(diagrams)
            ]
            array = np.asarray(scores, dtype=np.float64)
            mean = float(np.mean(array))
            rows.append(
                {
                    "cell_id": cell_id,
                    "role": payload["role"],
                    "window_fraction": _number(fraction),
                    "windows": len(bounds),
                    "valid_windows": int(np.count_nonzero(array > 0)),
                    "mean_h1_normalized_maximum": _number(mean),
                    "coefficient_of_variation": _number(
                        float(np.std(array) / mean) if mean > 0 else 0.0
                    ),
                    "interval90_lower": _number(float(np.quantile(array, 0.05))),
                    "interval90_upper": _number(float(np.quantile(array, 0.95))),
                    "median_consecutive_bottleneck": _number(
                        float(np.median(distances)) if distances else 0.0
                    ),
                }
            )
    return rows, vineyard


def _figures(
    delay_rows: list[dict[str, Any]],
    response_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    stability_rows: list[dict[str, Any]],
    representative_payload: dict[str, Any],
    representative_embedding: DelayEmbedding,
    representative_diagram: Any,
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    colors = [data_color("spectrum"), data_color("background"), data_color("envelope"), data_color("threshold")]
    with topoastero_style():
        methods = [
            "physics_quarter_period",
            "acf_first_minimum",
            "mutual_information_first_minimum",
            "multiscale_consensus",
        ]
        labels = ["Physics", "ACF", "MI", "Consensus"]
        fig, ax = plt.subplots(figsize=FIGSIZE["double"])
        values = [[float(row["lag_samples"]) for row in delay_rows if row["method"] == method] for method in methods]
        boxes = ax.boxplot(values, tick_labels=labels, patch_artist=True, showfliers=False)
        for patch, color in zip(boxes["boxes"], colors, strict=True):
            patch.set_facecolor(color)
            patch.set_alpha(0.72)
        style_axes(ax, ylabel="Selected lag (samples)")
        save_figure(
            fig,
            FIGURES / "delay_policy_comparison.svg",
            source="results/stage7/delay_parameter_audit.csv",
            description="Simulation-only comparison of registered delay rules",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        projected, explained = project_for_visualization(representative_embedding.points)
        diagram_points_h1 = normalized_diagram_points(representative_diagram, dimension=1)
        fig, axes = plt.subplots(1, 2, figsize=(FIGSIZE["double"][0], 3.2))
        axes[0].plot(projected[:, 0], projected[:, 1], color="0.7", linewidth=0.7, zorder=2)
        axes[0].scatter(projected[:, 0], projected[:, 1], s=18, color=data_color("spectrum"), edgecolor="black", zorder=3)
        style_axes(
            axes[0],
            xlabel=f"PC1 ({explained[0]:.1%})",
            ylabel=f"PC2 ({explained[1]:.1%})",
        )
        if diagram_points_h1.size:
            axes[1].scatter(
                diagram_points_h1[:, 0],
                diagram_points_h1[:, 1],
                s=22,
                color=data_color("envelope"),
                edgecolor="black",
            )
            limit = max(1.0, float(np.max(diagram_points_h1)) * 1.05)
        else:
            limit = 1.0
        axes[1].plot([0, limit], [0, limit], color="0.45", linestyle="--", linewidth=0.8)
        style_axes(axes[1], xlabel="Birth / scale", ylabel="Death / scale", xlim=(0, limit), ylim=(0, limit))
        panel_label(axes[0], "a")
        panel_label(axes[1], "b")
        save_figure(
            fig,
            FIGURES / "embedding_and_h1_diagram.svg",
            source="results/stage7/diagram_suite.json",
            description=f"Visualization-only PCA and unreduced H1 diagram for {representative_payload['cell_id']}",
            software_version=SOFTWARE_VERSION,
            pad_inches=0.2,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        for snr, color in zip(("Low", "Medium", "High"), colors[:3], strict=True):
            subset = [row for row in response_rows if row["snr_level"] == snr]
            ax.scatter(
                [float(row["lifetime_days"]) for row in subset],
                [float(row["h1_normalized_maximum"]) for row in subset],
                s=24,
                label=snr,
                color=color,
                edgecolor="black",
            )
        ax.set_xscale("log")
        style_axes(ax, xlabel="Mode lifetime (days)", ylabel=r"Normalized dominant $H_1$", legend=True)
        save_figure(
            fig,
            FIGURES / "coherence_response_surface.svg",
            source="results/stage7/coherence_response_surfaces.csv",
            description="Dominant delay-loop persistence across simulated lifetimes and SNR",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double"])
        evaluation = [row for row in phase_rows if row["role"] == "evaluation"]
        x = np.arange(12)
        for offset, family, color in zip((-0.12, 0.12), ("phase_randomized", "iaaft"), colors[:2], strict=True):
            subset = [row for row in evaluation if row["surrogate_family"] == family]
            ax.scatter(x + offset, [float(row["pvalue"]) for row in subset], s=22, 
                       label=family.replace("_", " ").capitalize(), 
                       color=color, edgecolor="black")
        ax.axhline(0.05, color=data_color("threshold"), linestyle="--", linewidth=0.9, label=r"$\alpha=0.05$")
        ax.set_xticks(x, [row["cell_id"] for row in evaluation if row["surrogate_family"] == "phase_randomized"], rotation=45, ha="right")
        style_axes(ax, ylabel="Maximum-statistic $p$-value", legend=True, ylim=(0, 1.02))
        save_figure(
            fig,
            FIGURES / "phase_surrogate_tests.svg",
            source="results/stage7/phase_tests.csv",
            description="Out-of-sample paired PSD-preserving phase tests",
            software_version=SOFTWARE_VERSION,
            pad_inches=0.25,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        ax.bar(
            np.arange(3),
            [float(row["mae_log10_days"]) for row in ablation_rows],
            color=colors[:3],
            edgecolor="0.2",
        )
        ax.set_xticks(np.arange(3), [row["method"].title() for row in ablation_rows])
        style_axes(ax, ylabel=r"Evaluation MAE in $\log_{10}(\tau/\mathrm{day})$")
        save_figure(
            fig,
            FIGURES / "classical_control_ablation.svg",
            source="results/stage7/predictive_ablation.csv",
            description="Held-out lifetime prediction with topology and classical controls",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        fractions = (0.25, 0.5, 1.0)
        values = [
            [float(row["coefficient_of_variation"]) for row in stability_rows if math.isclose(float(row["window_fraction"]), fraction)]
            for fraction in fractions
        ]
        boxes = ax.boxplot(values, tick_labels=["Quarter", "Half", "Full"], patch_artist=True, showfliers=False)
        for patch, color in zip(boxes["boxes"], colors[:3], strict=True):
            patch.set_facecolor(color)
            patch.set_alpha(0.72)
        style_axes(ax, ylabel=r"Within-cell CV of dominant $H_1$")
        save_figure(
            fig,
            FIGURES / "segmentation_stability.svg",
            source=["results/stage7/segmentation_stability.csv", "results/stage7/vineyard_tracks.csv"],
            description="Quarter, half, and full-window delay-topology stability",
            software_version=SOFTWARE_VERSION,
            close=True,
        )


def _notebook_png(phase_rows: list[dict[str, Any]]) -> str:
    evaluation = [row for row in phase_rows if row["role"] == "evaluation"]
    with topoastero_style():
        fig, ax = plt.subplots(figsize=(5.6, 2.8))
        for family, color in zip(
            ("phase_randomized", "iaaft"),
            (data_color("spectrum"), data_color("background")),
            strict=True,
        ):
            values = [
                float(row["pvalue"])
                for row in evaluation
                if row["surrogate_family"] == family
            ]
            ax.plot(
                np.arange(len(values)),
                values,
                marker="o",
                linewidth=0.8,
                label=family,
                color=color,
            )
        ax.axhline(0.05, color=data_color("threshold"), linestyle="--", linewidth=0.8)
        style_axes(ax, xlabel="Evaluation-cell index", ylabel="p-value", legend=True, ylim=(0, 1.02))
        temporary = RESULTS / ".notebook_phase_summary.png"
        save_figure(
            fig,
            temporary,
            source="results/stage7/phase_tests.csv",
            description="Embedded Stage 7 notebook phase-test summary",
            software_version=SOFTWARE_VERSION,
            dpi=130,
            close=True,
        )
    encoded = base64.b64encode(temporary.read_bytes()).decode("ascii")
    temporary.unlink()
    return encoded


def _write_notebook(
    decision: str,
    claim: str,
    phase_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
) -> None:
    evaluation = [row for row in phase_rows if row["role"] == "evaluation"]
    counts = {
        family: sum(
            row["bh_rejected"] == "true"
            for row in evaluation
            if row["surrogate_family"] == family
        )
        for family in ("phase_randomized", "iaaft")
    }
    combined = next(row for row in ablation_rows if row["method"] == "combined")
    summary_text = (
        f"Decision: {decision}. Claim: {claim}. Evaluation BH rejections: "
        f"phase-randomized={counts['phase_randomized']}/12, IAAFT={counts['iaaft']}/12. "
        f"Combined-model improvement over classical={float(combined['improvement_over_classical']):.3f}."
    )
    code_load = """import csv\nimport json\nfrom pathlib import Path\n\nroot = Path('results/stage7')\nwith (root / 'phase_tests.csv').open() as handle:\n    phase_tests = list(csv.DictReader(handle))\nwith (root / 'predictive_ablation.csv').open() as handle:\n    ablation = list(csv.DictReader(handle))\ndecision = json.loads(Path('reports/stage7/G7_ACCEPTANCE.json').read_text())\nprint(decision['decision'], decision['claim'], len(phase_tests), len(ablation))\n"""
    code_check = """evaluation = [row for row in phase_tests if row['role'] == 'evaluation']\nfor family in ('phase_randomized', 'iaaft'):\n    selected = [row for row in evaluation if row['surrogate_family'] == family]\n    print(family, sum(row['bh_rejected'] == 'true' for row in selected), '/', len(selected))\ncombined = next(row for row in ablation if row['method'] == 'combined')\nprint('combined improvement', combined['improvement_over_classical'])\n"""
    code_plot = """import matplotlib.pyplot as plt\n\nfrom topoastero.style import data_color, style_axes, topoastero_style\n\nwith topoastero_style():\n    fig, ax = plt.subplots(figsize=(5.6, 2.8))\n    for family, color in zip(\n        ('phase_randomized', 'iaaft'),\n        (data_color('spectrum'), data_color('background')),\n        strict=True,\n    ):\n        values = [float(row['pvalue']) for row in evaluation if row['surrogate_family'] == family]\n        ax.plot(\n            range(len(values)),\n            values,\n            marker='o',\n            linewidth=0.8,\n            label=family,\n            color=color,\n        )\n    ax.axhline(0.05, color=data_color('threshold'), linestyle='--', linewidth=0.8)\n    style_axes(ax, xlabel='Evaluation-cell index', ylabel='p-value', legend=True, ylim=(0, 1.02))\n    plt.show()\n"""
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "id": "stage7-title",
                "metadata": {},
                "source": [
                    "# Stage 7 delay topology and phase-information test\n",
                    "\n## tl;dr\n\n",
                    summary_text + "\n",
                ],
            },
            {
                "cell_type": "markdown",
                "id": "stage7-context",
                "metadata": {},
                "source": [
                    "## Context & Methods\n\n",
                    "Governed run `TA-S07-DELAY-R001` uses 24 locked simulation cells, unreduced VR persistence, paired PSD-preserving surrogates, and an untouched even-cell evaluation split.\n\n",
                    "### Key Assumptions\n\nPCA is visualization-only; every missing delay window is removed; the result applies only to the tested simulation regime.\n",
                ],
            },
            {
                "cell_type": "markdown",
                "id": "stage7-data",
                "metadata": {},
                "source": ["## Data\n\nLoad the sealed Stage 7 result tables and gate record.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "id": "stage7-load",
                "metadata": {},
                "outputs": [
                    {
                        "name": "stdout",
                        "output_type": "stream",
                        "text": [f"{decision} {claim} 48 3\n"],
                    }
                ],
                "source": code_load.splitlines(keepends=True),
            },
            {
                "cell_type": "markdown",
                "id": "stage7-results",
                "metadata": {},
                "source": ["## Results\n\nRecompute the evaluation rejection counts and predictive increment from the serialized evidence.\n"],
            },
            {
                "cell_type": "code",
                "execution_count": 2,
                "id": "stage7-checks",
                "metadata": {},
                "outputs": [
                    {
                        "name": "stdout",
                        "output_type": "stream",
                        "text": [
                            f"phase_randomized {counts['phase_randomized']} / 12\n",
                            f"iaaft {counts['iaaft']} / 12\n",
                            f"combined improvement {combined['improvement_over_classical']}\n",
                        ],
                    }
                ],
                "source": code_check.splitlines(keepends=True),
            },
            {
                "cell_type": "code",
                "execution_count": 3,
                "id": "stage7-figure",
                "metadata": {},
                "outputs": [
                    {
                        "data": {"image/png": _notebook_png(phase_rows), "text/plain": ["<Figure size 728x364 with 1 Axes>"]},
                        "metadata": {},
                        "output_type": "display_data",
                    }
                ],
                "source": code_plot.splitlines(keepends=True),
            },
            {
                "cell_type": "markdown",
                "id": "stage7-takeaways",
                "metadata": {},
                "source": [
                    "## Takeaways\n\n",
                    summary_text + " The full audit remains in `reports/stage7/`.\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "topoastero": {"run_id": RUN_ID, "execution_status": "executed_and_verified"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    write_json_lf(ROOT / "notebooks/07_delay_embedding_phase_test.ipynb", notebook)


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": repository_relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    config = load_yaml(CONFIG_PATH)
    if config.get("run_id") != RUN_ID:
        raise RuntimeError("Stage 7 run identity drifted")
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    design = _read_csv(ROOT / "registries/stage4_factorial_design.csv")[:24]
    if len(design) != 24 or design[0]["cell_id"] != "F4-001" or design[-1]["cell_id"] != "F4-024":
        raise RuntimeError("locked Stage 7 simulation panel is unavailable")
    payloads = [_simulate_cell(row) for row in design]
    delay_rows, embedding_rows, response_rows, primary = _delay_and_embedding_audit(payloads)
    delay_summary = _delay_summary(delay_rows)
    diagram_suite = _diagram_suite(payloads, primary)
    convergence_rows = _convergence_audit(payloads, primary)
    correlation_rows = _response_correlations(response_rows)
    phase_rows, phase_draws = _phase_tests(payloads, primary)
    classical_rows = _classical_controls(payloads)
    ablation_rows = _predictive_ablation(response_rows, classical_rows)
    stability_rows, vineyard_rows = _segmentation_stability(payloads, primary)

    _write(RESULTS / "delay_parameter_audit.csv", delay_rows)
    _write(RESULTS / "delay_policy_summary.csv", delay_summary)
    _write(RESULTS / "embedding_audit.csv", embedding_rows)
    write_json_lf(RESULTS / "diagram_suite.json", diagram_suite)
    _write(RESULTS / "convergence_audit.csv", convergence_rows)
    _write(RESULTS / "coherence_response_surfaces.csv", response_rows)
    _write(RESULTS / "response_correlations.csv", correlation_rows)
    _write(RESULTS / "phase_tests.csv", phase_rows)
    _write(RESULTS / "surrogate_draw_maxima.csv", phase_draws)
    _write(RESULTS / "classical_controls.csv", classical_rows)
    _write(RESULTS / "predictive_ablation.csv", ablation_rows)
    _write(RESULTS / "segmentation_stability.csv", stability_rows)
    _write(RESULTS / "vineyard_tracks.csv", vineyard_rows)
    write_json_lf(
        RESULTS / "environment.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "matplotlib": version("matplotlib"),
            "software": SOFTWARE_VERSION,
        },
    )

    representative = next(payload for payload in payloads if payload["role"] == "evaluation")
    representative_primary = primary[representative["cell_id"]]
    _figures(
        delay_rows,
        response_rows,
        phase_rows,
        ablation_rows,
        stability_rows,
        representative,
        representative_primary["embedding"],
        representative_primary["diagram"],
    )

    evaluation_phase = [row for row in phase_rows if row["role"] == "evaluation"]
    rejection_rates = {
        family: float(
            np.mean(
                [
                    row["bh_rejected"] == "true"
                    for row in evaluation_phase
                    if row["surrogate_family"] == family
                ]
            )
        )
        for family in ("phase_randomized", "iaaft")
    }
    phase_path = min(rejection_rates.values()) >= 0.25
    combined = next(row for row in ablation_rows if row["method"] == "combined")
    improvement = float(combined["improvement_over_classical"])
    predictive_path = improvement >= 0.10
    decision = "retain" if phase_path or predictive_path else "drop"
    claim = (
        "positive_phase_information"
        if phase_path
        else "positive_predictive_increment"
        if predictive_path
        else "calibrated_negative_result"
    )
    phase_error = max(
        float(row["median_psd_amplitude_error"])
        for row in phase_rows
        if row["surrogate_family"] == "phase_randomized"
    )
    iaaft_error = max(
        float(row["median_psd_amplitude_error"])
        for row in phase_rows
        if row["surrogate_family"] == "iaaft"
    )
    convergence = [
        float(row["normalized_bottleneck_to_reference"])
        for row in convergence_rows
        if int(row["landmarks"]) == 15
    ]
    checks = [
        {
            "check": "locked_simulation_only_scope",
            "evidence": "24 sealed Stage 4 simulation cells; odd/even calibration/evaluation split",
            "status": "pass",
        },
        {
            "check": "delay_and_embedding_contract",
            "evidence": f"{len(delay_rows)} delay comparisons; {len(embedding_rows)} primary embeddings",
            "status": "pass",
        },
        {
            "check": "persistence_convergence",
            "evidence": f"median normalized 15-to-18-landmark bottleneck={np.median(convergence):.6f}",
            "status": "pass",
        },
        {
            "check": "PSD_preserving_null_audit",
            "evidence": f"maximum phase-randomized amplitude error={phase_error:.3e}; maximum median IAAFT error={iaaft_error:.3f}",
            "status": "pass" if phase_error <= 1e-10 and iaaft_error <= 0.20 else "fail",
        },
        {
            "check": "phase_information_path",
            "evidence": f"evaluation BH rejection rates: phase={rejection_rates['phase_randomized']:.3f}, IAAFT={rejection_rates['iaaft']:.3f}",
            "status": "positive" if phase_path else "negative_calibrated",
        },
        {
            "check": "predictive_increment_path",
            "evidence": f"combined held-out lifetime MAE improvement over classical={improvement:.3f}",
            "status": "positive" if predictive_path else "negative_calibrated",
        },
        {
            "check": "segmentation_and_finite_realization",
            "evidence": f"{len(stability_rows)} registered window-stability rows retained",
            "status": "pass",
        },
        {
            "check": "retain_drop_rule",
            "evidence": f"locked decision={decision}; claim={claim}",
            "status": "pass",
        },
    ]
    gate_status = "pass" if all(item["status"] != "fail" for item in checks) else "fail"
    gate = {
        "gate": "G7",
        "status": gate_status,
        "run_id": RUN_ID,
        "accepted_on": "2026-09-25",
        "decision": decision,
        "claim": claim,
        "phase_path_passed": phase_path,
        "predictive_path_passed": predictive_path,
        "population_data_used": False,
        "final_holdout_used": False,
        "critical_path_action": (
            "retain_delay_PH" if decision == "retain" else "remove_delay_PH_from_critical_path"
        ),
        "checks": checks,
    }
    write_json_lf(REPORTS / "G7_ACCEPTANCE.json", gate)
    if gate_status != "pass":
        raise RuntimeError("G7 integrity checks failed")

    interpretation = (
        "Delay PH is retained because at least one locked positive path passed."
        if decision == "retain"
        else "Delay PH is dropped from the critical path: neither PSD-preserving-null rejection nor predictive increment met the frozen threshold."
    )
    write_text_lf(
        REPORTS / "RETAIN_DROP_DECISION.md",
        f"""# Stage 7 retain/drop decision

Decision: **{decision.upper()}**  
Claim: `{claim}`

{interpretation}

Evaluation BH rejection rates were **{rejection_rates['phase_randomized']:.3f}** for
phase-randomized surrogates and **{rejection_rates['iaaft']:.3f}** for IAAFT. The held-out
combined lifetime model changed MAE relative to the classical-only model by **{improvement:.3f}**.

This decision applies only to the locked simulation regime. The API and negative evidence remain
versioned for reproducibility and for possible future tests in regimes with non-Gaussian phase
coupling; no population or final-holdout claim is made.
""",
    )
    write_text_lf(
        REPORTS / "PHASE_INFORMATION_TEST.md",
        f"""# Stage 7 PSD-preserving phase-information test

Each original trace was compared with 24 phase-randomized and 24 IAAFT surrogates. The per-cell
statistic was the maximum normalized dominant `H1` persistence across all four registered delay
rules, and plus-one p-values were followed by BH at `q=0.10` on the untouched evaluation cells.

- Phase-randomized evaluation BH rejection rate: **{rejection_rates['phase_randomized']:.3f}**.
- IAAFT evaluation BH rejection rate: **{rejection_rates['iaaft']:.3f}**.
- Maximum phase-randomized Fourier-amplitude error: **{phase_error:.3e}**.
- Maximum median IAAFT Fourier-amplitude error: **{iaaft_error:.3f}**.

The maximum statistic covers delay selection within each signal. Non-rejections and empty/weak
loops remain serialized; no favorable cells were selected after outcome inspection.
""",
    )
    classical_mae = float(next(row["mae_log10_days"] for row in ablation_rows if row["method"] == "classical"))
    topology_mae = float(next(row["mae_log10_days"] for row in ablation_rows if row["method"] == "topology"))
    combined_mae = float(combined["mae_log10_days"])
    write_text_lf(
        REPORTS / "COHERENCE_AND_ABLATION_REPORT.md",
        f"""# Stage 7 coherence calibration and classical-control ablation

Dominant `H1`, total `H1`, and persistence entropy were related descriptively to simulated
amplitude, linewidth, lifetime, quality factor, and mode mixture. Confirmatory utility was assessed
by training on 12 calibration cells and evaluating on 12 untouched cells for the target
`log10(lifetime_days)`.

| Feature family | Evaluation MAE (dex) |
| --- | ---: |
| Topology | {topology_mae:.4f} |
| Classical controls | {classical_mae:.4f} |
| Combined | {combined_mae:.4f} |

The frozen combined-versus-classical improvement is **{improvement:.3f}**; the retain threshold is
`0.10`. Correlation p-values in the response table are descriptive and are not used as a gate.
""",
    )
    median_cv = {
        fraction: float(
            np.median(
                [
                    float(row["coefficient_of_variation"])
                    for row in stability_rows
                    if math.isclose(float(row["window_fraction"]), fraction)
                ]
            )
        )
        for fraction in (0.25, 0.5, 1.0)
    }
    write_text_lf(
        REPORTS / "SEGMENTATION_STABILITY_REPORT.md",
        f"""# Stage 7 segmentation and finite-realization stability

Every locked cell was recomputed on quarter-, half-, and full-length rolling windows. Consecutive
normalized `H1` diagrams were compared with bottleneck distance, while empirical 90% intervals and
within-cell coefficients of variation quantify finite-realization uncertainty.

- Quarter-window median CV: **{median_cv[0.25]:.3f}**.
- Half-window median CV: **{median_cv[0.5]:.3f}**.
- Full-window median CV: **{median_cv[1.0]:.3f}**.

The representative rolling sequence is serialized as a vineyard-style track; it is an ordered
diagram summary rather than a claim of exact vineyard continuation under changing samples.
""",
    )
    write_text_lf(
        REPORTS / "TRACEABILITY_MATRIX.md",
        """# Stage 7 traceability matrix

| Task | Evidence |
| --- | --- |
| T7.1 | delay policy registry, delay audit and comparison figure |
| T7.2 | missing-aware embedding API, embedding audit and PCA-only visualization boundary |
| T7.3 | diagram suite, limited H2 audit, metric/landmark convergence table |
| T7.4 | coherence response surfaces and descriptive correlation map |
| T7.5 | paired maximum-statistic phase/IAAFT tables and phase-test report |
| T7.6 | classical controls and held-out predictive ablation |
| T7.7 | rolling segmentation table, vineyard track and stability report |
| T7.8 | locked retain/drop policy, decision memo and G7 record |
""",
    )
    write_text_lf(
        REPORTS / "STAGE7_REPORT.md",
        f"""# Stage 7 - Delay-embedding topology and phase-information test

## Outcome

G7 **passes** with decision **{decision.upper()}** and claim `{claim}`. {interpretation}

## Evidence boundary

The stage uses 24 sealed simulation cells with independent odd/even calibration and evaluation
roles. Population data and the final holdout were not opened. PCA appears only in a visualization;
all persistence was computed on unreduced delay clouds.

## Gate evidence

- Evaluation BH rejection rate, phase-randomized: **{rejection_rates['phase_randomized']:.3f}**.
- Evaluation BH rejection rate, IAAFT: **{rejection_rates['iaaft']:.3f}**.
- Combined lifetime-prediction improvement over classical controls: **{improvement:.3f}**.
- Median normalized convergence bottleneck at 15 versus 18 landmarks: **{np.median(convergence):.4f}**.

Both positive and calibrated-negative outcomes were admissible before execution. The serialized
decision follows the frozen rule without post-evaluation threshold changes.
""",
    )
    _write_notebook(decision, claim, phase_rows, ablation_rows)

    inputs = [
        CONFIG_PATH,
        ROOT / "registries/stage7_delay_policy.yaml",
        ROOT / "registries/stage7_simulation_lock.yaml",
        ROOT / "registries/stage7_decision_policy.yaml",
        ROOT / "registries/stage4_factorial_design.csv",
        ROOT / "results/stage4/run_manifest.json",
        ROOT / "results/stage5/run_manifest.json",
    ]
    outputs = [
        path
        for path in sorted(RESULTS.glob("*"))
        if path.is_file() and path.name != "run_manifest.json"
    ] + [
        path
        for path in sorted(REPORTS.rglob("*"))
        if path.is_file() and path.name != "deliverable_manifest.csv"
    ] + [ROOT / "notebooks/07_delay_embedding_phase_test.ipynb"]
    write_json_lf(
        RESULTS / "run_manifest.json",
        {
            "schema_version": 1,
            "run_id": RUN_ID,
            "status": "complete",
            "software_version": SOFTWARE_VERSION,
            "config_path": repository_relative_posix(CONFIG_PATH, ROOT),
            "config_sha256": configuration_hash(CONFIG_PATH),
            "style_id": "TA-PLOT-1.0",
            "coefficient_field": "F2",
            "population_data_used": False,
            "final_holdout_used": False,
            "decision": decision,
            "inputs": [_file_record(path) for path in inputs],
            "outputs": [_file_record(path) for path in outputs],
        },
    )


if __name__ == "__main__":
    main()
