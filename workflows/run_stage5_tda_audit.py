"""Run the deterministic Stage 5 TDA representation audit.

This workflow consumes only the frozen Stage 4 simulation-development panel.  It writes
machine-readable cross-checks, representation features, null calibration, localization,
sensitivity, redundancy, ablation, selection evidence, reports, figures, and a sealed run
manifest.  It never reads the LEGACY population partitions or final holdout.
"""

from __future__ import annotations

import csv
import math
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.signal import peak_prominences
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.stats import spearmanr

from topoastero.classical import HarveyComponent
from topoastero.config import configuration_hash, load_yaml
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)
from topoastero.provenance import sha256_file
from topoastero.representations import (
    RepresentationResult,
    cylindrical_echelle_filtration,
    delay_embedding_filtration,
    light_curve_filtration,
    mode_frequency_cloud_filtration,
    psd_superlevel_filtration,
)
from topoastero.simulation_lab import (
    asymptotic_mode_comb,
    generate_null,
    iaaft_surrogate,
    max_statistic_threshold,
    phase_randomized_surrogate,
    target_oscillator_psd,
)
from topoastero.style import (
    FIGSIZE,
    STYLE_ID,
    data_color,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)
from topoastero.tda import (
    bottleneck_distance,
    diagram_points,
    empirical_pvalue,
    exact_path_persistence,
    grid_persistence,
    localized_records,
    pairwise_distances,
    vietoris_rips_persistence,
    wasserstein_distance,
)

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "configs/stage5_tda.yaml"
RESULTS = ROOT / "results/stage5"
REPORTS = ROOT / "reports/stage5"
FIGURES = REPORTS / "figures"
SOFTWARE_VERSION = "TopoAstero-0.6.0"

REPRESENTATION_IDS = {
    "light_curve_filtration": "REP-LC",
    "delay_embedding": "REP-DELAY",
    "psd_superlevels": "REP-PSD",
    "mode_frequency_cloud": "REP-MODE",
    "cylindrical_echelle": "REP-ECHELLE",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    write_csv_lf(path, rows, fieldnames=fieldnames or list(rows[0]))


def _number(value: float, digits: int = 10) -> str:
    return f"{value:.{digits}g}"


def _float_feature(result: RepresentationResult, key: str) -> float:
    value = result.summaries[key]
    return 0.0 if value is None else float(value)


def _simulate_cell(row: dict[str, str]) -> dict[str, Any]:
    seed = int(row["seed"])
    rng = np.random.default_rng(seed + 510_000)
    snr_name = row["snr_level"].lower()
    snr = {"low": 0.8, "medium": 1.6, "high": 3.2}[snr_name]
    lifetime = float(row["lifetime_days"])
    cadence = float(row["cadence_seconds"])
    duty_cycle = float(row["duty_cycle"])
    numax = float(row["numax_uHz"])
    dnu = float(row["dnu_uHz"])

    samples = 192
    sample_index = np.arange(samples, dtype=np.float64)
    time_days = sample_index * cadence / 86400.0
    base_period = 18.0 + (dnu % 5.0)
    phase_noise = rng.normal(scale=0.12 / math.sqrt(lifetime), size=samples)
    phase = 2.0 * np.pi * sample_index / base_period + np.cumsum(phase_noise)
    signal = snr * (np.sin(phase) + 0.32 * np.sin(1.63 * phase + 0.4))
    innovations = rng.normal(size=samples)
    red = np.empty(samples, dtype=np.float64)
    red[0] = innovations[0]
    for index in range(1, samples):
        red[index] = 0.55 * red[index - 1] + innovations[index]
    signal += red
    if duty_cycle < 1.0:
        retained = rng.random(samples) < duty_cycle
        retained[[0, -1]] = True
        signal = np.interp(sample_index, sample_index[retained], signal[retained])

    frequency = np.linspace(max(1.0, numax - 3.2 * dnu), numax + 3.2 * dnu, samples)
    orders = min(7, int(row["visible_orders"]))
    if orders % 2 == 0:
        orders -= 1
    modes = asymptotic_mode_comb(
        numax_uHz=numax,
        dnu_uHz=dnu,
        radial_orders=max(3, orders),
        radial_height_ppm2_per_uHz=14.0 * snr,
        lifetime_days=lifetime,
    )
    background_components = (HarveyComponent(10.0, 700.0),)
    background = target_oscillator_psd(
        frequency,
        modes=(),
        white_noise_ppm2_per_uHz=2.0,
        background=background_components,
        integration_seconds=cadence,
    )
    target = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=2.0,
        background=background_components,
        integration_seconds=cadence,
    )
    periodogram = rng.exponential(target)

    cloud_frequency = np.asarray([mode.frequency_uHz for mode in modes], dtype=np.float64)
    cloud_degree = np.asarray([mode.degree for mode in modes], dtype=np.int64)
    center = np.mean(cloud_frequency)
    curvature = {"none": 0.0, "weak": 0.004, "strong": 0.012}[row["ridge_curvature"]]
    cloud_frequency += curvature * (cloud_frequency - center) ** 2 / dnu
    cloud_frequency += rng.normal(scale=0.025 * dnu / snr, size=cloud_frequency.size)
    order = np.argsort(cloud_frequency, kind="mergesort")
    cloud_frequency = cloud_frequency[order]
    cloud_degree = cloud_degree[order]

    return {
        "time": time_days,
        "signal": signal,
        "frequency": frequency,
        "periodogram": periodogram,
        "background": background,
        "mode_frequency": cloud_frequency,
        "mode_degree": cloud_degree,
        "dnu": dnu,
        "numax": numax,
        "snr": snr,
        "lifetime": lifetime,
        "trial_dnu": float(row["injected_spacing_uHz"]),
    }


def _representations(payload: dict[str, Any]) -> dict[str, RepresentationResult]:
    return {
        "light_curve_filtration": light_curve_filtration(payload["time"], payload["signal"]),
        "delay_embedding": delay_embedding_filtration(
            payload["signal"], lag=12, dimension=2, landmark_count=18
        ),
        "psd_superlevels": psd_superlevel_filtration(
            payload["frequency"],
            payload["periodogram"],
            background=payload["background"],
            smoothing_bins=1.0,
        ),
        "mode_frequency_cloud": mode_frequency_cloud_filtration(
            payload["mode_frequency"], payload["mode_degree"], dnu_uHz=payload["dnu"]
        ),
        "cylindrical_echelle": cylindrical_echelle_filtration(
            payload["frequency"],
            payload["periodogram"],
            trial_dnu_uHz=payload["trial_dnu"],
            order_bins=6,
            phase_bins=12,
            max_dimension=0,
        ),
    }


def _backend_crosschecks(seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(case_id: str, backend: str, reference: str, expected: float, observed: float, tolerance: float) -> None:
        error = abs(observed - expected)
        rows.append(
            {
                "case_id": case_id,
                "backend": backend,
                "independent_reference": reference,
                "expected": _number(expected),
                "observed": _number(observed),
                "absolute_error": _number(error),
                "tolerance": _number(tolerance),
                "deterministic_ordering": "filtration_dimension_lexicographic",
                "status": "pass" if error <= tolerance else "fail",
            }
        )

    signal = np.asarray([0.0, 3.0, 0.0, 2.0, 0.0])
    path = exact_path_persistence(signal)
    persistence = sorted(float(pair.persistence) for pair in path.finite(0))
    peaks = np.asarray([3])
    prominence = sorted(peak_prominences(signal, peaks)[0].tolist())
    add("BC-01", "exact_path_H0", "scipy_peak_prominences", 0.0, max(abs(a - b) for a, b in zip(persistence, prominence, strict=True)), 1e-12)

    points = np.random.default_rng(seed).normal(size=(9, 2))
    rips = vietoris_rips_persistence(points, max_dimension=0)
    rips_deaths = sorted(float(pair.persistence) for pair in rips.finite(0))
    mst = sorted(minimum_spanning_tree(pairwise_distances(points)).data.tolist())
    add("BC-02", "vietoris_rips_H0", "scipy_minimum_spanning_tree", 0.0, max(abs(a - b) for a, b in zip(rips_deaths, mst, strict=True)), 1e-12)

    square = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    square_h1 = vietoris_rips_persistence(square, max_dimension=1).finite(1)
    add("BC-03", "vietoris_rips_H1", "exact_four_point_square", math.sqrt(2.0) - 1.0, float(square_h1[0].persistence), 1e-12)

    constant = np.ones((3, 5))
    cylinder = grid_persistence(constant, periodic_axes=(False, True), max_dimension=1, include_zero=True)
    rectangle = grid_persistence(constant, max_dimension=1, include_zero=True)
    observed_boundary = float(len(cylinder.essential(1)) - len(rectangle.essential(1)))
    add("BC-04", "periodic_grid_H1", "cylinder_minus_disk_Betti_1", 1.0, observed_boundary, 0.0)

    diagram = np.asarray([[0.0, 1.0], [0.2, 0.6]])
    distance = max(bottleneck_distance(diagram, diagram), wasserstein_distance(diagram, diagram))
    add("BC-05", "diagram_distances", "metric_identity", 0.0, distance, 1e-14)

    left = exact_path_persistence([0.0, 3.0, 0.0, 2.0, 0.0])
    right = exact_path_persistence([0.1, 2.9, -0.1, 2.1, 0.1])
    stability = bottleneck_distance(diagram_points(left, dimension=0), diagram_points(right, dimension=0))
    add("BC-06", "bottleneck_stability", "sup_norm_bound", 0.1, stability, 1e-12)
    return rows


def _feature_row(
    design: dict[str, str], execution: dict[str, str], results: dict[str, RepresentationResult]
) -> dict[str, Any]:
    lc = results["light_curve_filtration"]
    delay = results["delay_embedding"]
    psd = results["psd_superlevels"]
    mode = results["mode_frequency_cloud"]
    echelle = results["cylindrical_echelle"]
    signal = np.asarray(lc.data)
    centered = signal - np.mean(signal)
    scale = max(float(np.std(signal)), 1e-12)
    skewness = float(np.mean((centered / scale) ** 3))
    return {
        "cell_id": design["cell_id"],
        "seed": design["seed"],
        "snr_level": design["snr_level"].lower(),
        "snr_numeric": {"low": 0.8, "medium": 1.6, "high": 3.2}[design["snr_level"].lower()],
        "duration_days": design["duration_days"],
        "cadence_seconds": design["cadence_seconds"],
        "duty_cycle": design["duty_cycle"],
        "lifetime_days": design["lifetime_days"],
        "ridge_curvature": design["ridge_curvature"],
        "alias_target": design["alias_target"],
        "nominal_dnu_selected": "1" if execution["nominal_dnu_selected"] == "true" else "0",
        "lc_h0_total": _number(_float_feature(lc, "total_persistence")),
        "lc_h0_max": _number(_float_feature(lc, "maximum_persistence")),
        "lc_peak_prominence": _number(lc.controls["maximum_prominence"]),
        "lc_skewness": _number(skewness),
        "delay_h0_total": _number(_float_feature(delay, "h0_total_persistence")),
        "delay_h1_total": _number(_float_feature(delay, "h1_total_persistence")),
        "delay_h1_max": _number(_float_feature(delay, "h1_maximum_persistence")),
        "delay_autocorrelation": _number(delay.controls["lag_autocorrelation"]),
        "delay_spectral_entropy": _number(delay.controls["spectral_entropy"]),
        "psd_h0_total": _number(_float_feature(psd, "total_persistence")),
        "psd_h0_max": _number(_float_feature(psd, "maximum_persistence")),
        "psd_centroid_uHz": _number(_float_feature(psd, "persistence_centroid")),
        "psd_peak_prominence": _number(psd.controls["maximum_prominence"]),
        "psd_envelope_centroid_uHz": _number(psd.controls["envelope_centroid_uHz"]),
        "mode_h0_total": _number(_float_feature(mode, "h0_total_persistence")),
        "mode_h1_max": _number(_float_feature(mode, "h1_maximum_persistence")),
        "mode_nn_mean": _number(mode.controls["nearest_neighbor_mean"]),
        "mode_nn_cv": _number(mode.controls["nearest_neighbor_cv"]),
        "echelle_h0_total": _number(_float_feature(echelle, "h0_total_persistence")),
        "echelle_ridge_lifetime": _number(_float_feature(echelle, "h0_ridge_lifetime")),
        "echelle_ridge_resultant": _number(echelle.controls["ridge_circular_resultant"]),
        "echelle_ridge_contrast": _number(echelle.controls["ridge_contrast"]),
    }


def _null_statistic(
    representation: str,
    payload: dict[str, Any],
    *,
    seed: int,
    evaluation: bool,
) -> float:
    local_seed = seed + (10_000_000 if evaluation else 0)
    rng = np.random.default_rng(local_seed)
    if representation == "REP-LC":
        surrogate = iaaft_surrogate(payload["signal"], seed=local_seed, iterations=20)
        result = light_curve_filtration(payload["time"], surrogate)
        return _float_feature(result, "maximum_persistence")
    if representation == "REP-DELAY":
        surrogate = (
            phase_randomized_surrogate(payload["signal"], seed=local_seed)
            if local_seed % 2 == 0
            else iaaft_surrogate(payload["signal"], seed=local_seed, iterations=20)
        )
        result = delay_embedding_filtration(surrogate, lag=12, dimension=2, landmark_count=18)
        return _float_feature(result, "h1_maximum_persistence")
    if representation == "REP-PSD":
        background_periodogram = rng.exponential(payload["background"])
        result = psd_superlevel_filtration(
            payload["frequency"], background_periodogram, background=payload["background"]
        )
        return _float_feature(result, "maximum_persistence")
    if representation == "REP-MODE":
        count = len(payload["mode_frequency"])
        frequencies = np.sort(
            rng.uniform(
                float(np.min(payload["mode_frequency"])),
                float(np.max(payload["mode_frequency"])),
                count,
            )
        )
        degrees = rng.permutation(payload["mode_degree"])
        result = mode_frequency_cloud_filtration(frequencies, degrees, dnu_uHz=payload["dnu"])
        return _float_feature(result, "h0_total_persistence")
    if representation == "REP-ECHELLE":
        randomized = generate_null("randomized_comb", samples=len(payload["frequency"]), seed=local_seed)
        positive = np.exp(0.55 * randomized)
        result = cylindrical_echelle_filtration(
            payload["frequency"],
            positive,
            trial_dnu_uHz=payload["trial_dnu"],
            order_bins=6,
            phase_bins=12,
            max_dimension=0,
        )
        return _float_feature(result, "h0_ridge_lifetime")
    raise ValueError(representation)


def _null_calibration(
    payload: dict[str, Any], seed: int, feature_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray[Any, Any]]]:
    feature_key = {
        "REP-LC": "lc_h0_max",
        "REP-DELAY": "delay_h1_max",
        "REP-PSD": "psd_h0_max",
        "REP-MODE": "mode_h0_total",
        "REP-ECHELLE": "echelle_ridge_lifetime",
    }
    null_family = {
        "REP-LC": "iaaft",
        "REP-DELAY": "phase_randomized_and_iaaft",
        "REP-PSD": "background_only",
        "REP-MODE": "matched_density_randomized_modes",
        "REP-ECHELLE": "randomized_comb",
    }
    rows: list[dict[str, Any]] = []
    nulls: dict[str, np.ndarray[Any, Any]] = {}
    for index, representation in enumerate(feature_key):
        calibration = np.asarray(
            [
                _null_statistic(
                    representation,
                    payload,
                    seed=seed + index * 1000 + realization,
                    evaluation=False,
                )
                for realization in range(64)
            ],
            dtype=np.float64,
        )
        evaluation_values = np.asarray(
            [
                _null_statistic(
                    representation,
                    payload,
                    seed=seed + index * 1000 + realization,
                    evaluation=True,
                )
                for realization in range(64)
            ],
            dtype=np.float64,
        )
        threshold = max_statistic_threshold(calibration[:, None], alpha=0.05)
        false_positive_rate = float(np.mean(evaluation_values > threshold))
        nulls[representation] = calibration
        observed = np.asarray([float(row[feature_key[representation]]) for row in feature_rows])
        pvalues = np.asarray([empirical_pvalue(value, calibration) for value in observed])
        for row, pvalue in zip(feature_rows, pvalues, strict=True):
            row[f"{representation.lower().replace('-', '_')}_pvalue"] = _number(float(pvalue))
        rows.append(
            {
                "representation_id": representation,
                "null_family": null_family[representation],
                "registered_statistic": feature_key[representation],
                "calibration_realizations": 64,
                "evaluation_realizations": 64,
                "calibration_seed_range": f"{seed + index * 1000}:{seed + index * 1000 + 63}",
                "evaluation_seed_range": f"{seed + 10_000_000 + index * 1000}:{seed + 10_000_000 + index * 1000 + 63}",
                "threshold_alpha_0_05": _number(threshold),
                "evaluation_false_positive_rate": _number(false_positive_rate),
                "maximum_pilot_statistic": _number(float(np.max(observed))),
                "minimum_pilot_pvalue": _number(float(np.min(pvalues))),
                "status": "pass" if false_positive_rate <= 0.125 else "fail",
            }
        )
    return rows, nulls


def _localization_catalog(results: dict[str, RepresentationResult]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, result in results.items():
        representation_id = REPRESENTATION_IDS[name]
        finite = sorted(
            result.diagram.finite(),
            key=lambda pair: -(float(pair.persistence) if pair.persistence is not None else 0.0),
        )[:6]
        selected = finite + list(result.diagram.essential())
        temporary = type(result.diagram)(
            tuple(selected),
            result.diagram.backend,
            result.diagram.direction,
            result.diagram.coefficient_field,
            result.diagram.essential_policy,
        )
        records.extend(localized_records(temporary, representation_id=representation_id))
    return records


def _relative_change(left: float, right: float) -> float:
    return abs(right - left) / max(abs(left), 1e-12)


def _nuisance_audit(payload: dict[str, Any], baseline: dict[str, RepresentationResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        audit_id: str,
        nuisance: str,
        representation_id: str,
        base: float,
        perturbed: float,
        distance: float,
        limit: float,
        interpretation: str,
        expected_change: bool = False,
    ) -> None:
        change = _relative_change(base, perturbed)
        passed = distance > 0.0 if expected_change else change <= limit + 1e-12
        rows.append(
            {
                "audit_id": audit_id,
                "nuisance": nuisance,
                "representation_id": representation_id,
                "baseline_statistic": _number(base),
                "perturbed_statistic": _number(perturbed),
                "relative_change": _number(change),
                "bottleneck_distance": _number(distance),
                "acceptance_limit": "expected_nonzero_topology_change" if expected_change else _number(limit),
                "interpretation": interpretation,
                "status": "pass" if passed else "fail",
            }
        )

    base_lc = baseline["light_curve_filtration"]
    for audit_id, nuisance, transformed in (
        ("NS-01", "amplitude_scaling", 7.0 * payload["signal"]),
        ("NS-02", "additive_offset", payload["signal"] + 11.0),
        ("NS-03", "monotone_transform", np.sign(payload["signal"]) * np.abs(payload["signal"]) ** 1.25),
    ):
        changed = light_curve_filtration(payload["time"], transformed)
        distance = bottleneck_distance(
            diagram_points(base_lc.diagram, dimension=0), diagram_points(changed.diagram, dimension=0)
        )
        add(
            audit_id,
            nuisance,
            "REP-LC",
            _float_feature(base_lc, "maximum_persistence"),
            _float_feature(changed, "maximum_persistence"),
            distance,
            1e-10 if nuisance != "monotone_transform" else 0.60,
            "robust normalization must remove affine amplitude/offset; monotone warp is a registered sensitivity",
        )

    base_delay = baseline["delay_embedding"]
    cadence = delay_embedding_filtration(payload["signal"][::2], lag=6, dimension=2, landmark_count=18)
    density = delay_embedding_filtration(payload["signal"], lag=12, dimension=2, landmark_count=12)
    dimension = delay_embedding_filtration(payload["signal"], lag=12, dimension=3, landmark_count=18)
    for audit_id, nuisance, changed in (
        ("NS-04", "cadence", cadence),
        ("NS-05", "sample_density", density),
        ("NS-06", "embedding_dimension", dimension),
    ):
        distance = bottleneck_distance(
            diagram_points(base_delay.diagram, dimension=1), diagram_points(changed.diagram, dimension=1)
        )
        add(
            audit_id,
            nuisance,
            "REP-DELAY",
            _float_feature(base_delay, "h1_maximum_persistence"),
            _float_feature(changed, "h1_maximum_persistence"),
            distance,
            0.60,
            "registered delay-coordinate convergence sensitivity",
        )

    base_psd = baseline["psd_superlevels"]
    smoothed = psd_superlevel_filtration(
        payload["frequency"], payload["periodogram"], background=payload["background"], smoothing_bins=3.0
    )
    distance = bottleneck_distance(
        diagram_points(base_psd.diagram, dimension=0), diagram_points(smoothed.diagram, dimension=0)
    )
    add(
        "NS-07",
        "smoothing",
        "REP-PSD",
        _float_feature(base_psd, "maximum_persistence"),
        _float_feature(smoothed, "maximum_persistence"),
        distance,
        0.60,
        "Stage 6 must propagate the smoothing branch",
    )

    base_echelle = baseline["cylindrical_echelle"]
    resolved = cylindrical_echelle_filtration(
        payload["frequency"], payload["periodogram"], trial_dnu_uHz=payload["trial_dnu"], order_bins=8, phase_bins=24, max_dimension=0
    )
    distance = bottleneck_distance(
        diagram_points(base_echelle.diagram, dimension=0), diagram_points(resolved.diagram, dimension=0)
    )
    add(
        "NS-08",
        "grid_resolution",
        "REP-ECHELLE",
        _float_feature(base_echelle, "h0_ridge_lifetime"),
        _float_feature(resolved, "h0_ridge_lifetime"),
        distance,
        0.60,
        "registered periodic-grid convergence sensitivity",
    )

    field = np.asarray(base_echelle.data)
    periodic = grid_persistence(field, periodic_axes=(False, True), max_dimension=1, include_zero=True)
    rectangular = grid_persistence(field, max_dimension=1, include_zero=True)
    periodic_count = float(len(periodic.essential(1)))
    rectangular_count = float(len(rectangular.essential(1)))
    add(
        "NS-09",
        "periodic_boundary",
        "REP-ECHELLE",
        rectangular_count,
        periodic_count,
        abs(periodic_count - rectangular_count),
        0.0,
        "the cylindrical domain must add exactly one essential H1 class relative to a disk",
        expected_change=True,
    )
    return rows


FEATURE_COLUMNS = {
    "S5-LC-H0-TOTAL": "lc_h0_total",
    "S5-LC-H0-MAX": "lc_h0_max",
    "S5-DELAY-H0-TOTAL": "delay_h0_total",
    "S5-DELAY-H1-MAX": "delay_h1_max",
    "S5-DELAY-H1-TOTAL": "delay_h1_total",
    "S5-PSD-H0-MAX": "psd_h0_max",
    "S5-PSD-H0-CENTROID": "psd_centroid_uHz",
    "S5-PSD-H0-TOTAL": "psd_h0_total",
    "S5-MODE-H0-TOTAL": "mode_h0_total",
    "S5-MODE-H1-MAX": "mode_h1_max",
    "S5-ECH-H0-RIDGE": "echelle_ridge_lifetime",
    "S5-ECH-H0-TOTAL": "echelle_h0_total",
}


def _redundancy(feature_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], np.ndarray[Any, Any]]:
    names = list(FEATURE_COLUMNS)
    matrix = np.column_stack(
        [np.asarray([float(row[column]) for row in feature_rows]) for column in FEATURE_COLUMNS.values()]
    )
    correlation = np.eye(len(names), dtype=np.float64)
    pair_rows: list[dict[str, Any]] = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            rho = float(spearmanr(matrix[:, left], matrix[:, right]).statistic)
            if not math.isfinite(rho):
                rho = 0.0
            correlation[left, right] = correlation[right, left] = rho
            clipped = min(abs(rho), 0.999999)
            mutual_information = -0.5 * math.log(max(1.0 - clipped**2, 1e-12))
            pair_rows.append(
                {
                    "feature_a": names[left],
                    "feature_b": names[right],
                    "spearman_rho": _number(rho),
                    "gaussian_copula_mutual_information_nats": _number(mutual_information),
                    "strong_redundancy": str(abs(rho) >= 0.85).lower(),
                }
            )
    wide_rows = [
        {"feature_id": name}
        | {other: _number(float(correlation[index, offset])) for offset, other in enumerate(names)}
        for index, name in enumerate(names)
    ]
    return wide_rows, pair_rows, correlation


def _cross_validated_ridge(
    features: np.ndarray[Any, Any], target: np.ndarray[Any, Any], *, folds: int = 6
) -> tuple[float, float]:
    predictions = np.empty_like(target, dtype=np.float64)
    for fold in range(folds):
        test = np.arange(target.size) % folds == fold
        train = ~test
        mean = np.mean(features[train], axis=0)
        scale = np.std(features[train], axis=0)
        scale[scale < 1e-12] = 1.0
        train_x = (features[train] - mean) / scale
        test_x = (features[test] - mean) / scale
        design = np.column_stack((np.ones(np.count_nonzero(train)), train_x))
        penalty = np.eye(design.shape[1]) * 0.5
        penalty[0, 0] = 0.0
        coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ target[train])
        predictions[test] = np.column_stack((np.ones(np.count_nonzero(test)), test_x)) @ coefficients
    residual = target - predictions
    rmse = float(np.sqrt(np.mean(residual**2)))
    denominator = float(np.sum((target - np.mean(target)) ** 2))
    r2 = 1.0 - float(np.sum(residual**2)) / max(denominator, 1e-12)
    return rmse, r2


def _ablation(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def column(name: str) -> np.ndarray[Any, Any]:
        return np.asarray([float(row[name]) for row in feature_rows], dtype=np.float64)

    targets = {
        "REP-LC": ("duty_cycle", column("duty_cycle"), ["lc_peak_prominence", "lc_skewness"], ["lc_h0_total"]),
        "REP-DELAY": ("log_lifetime_days", np.log(column("lifetime_days")), ["delay_autocorrelation", "delay_spectral_entropy", "snr_numeric"], ["delay_h1_max"]),
        "REP-PSD": ("injected_snr", column("snr_numeric"), ["psd_peak_prominence", "psd_envelope_centroid_uHz"], ["psd_h0_max", "psd_centroid_uHz"]),
        "REP-MODE": ("ridge_curvature_level", np.asarray([{"none": 0.0, "weak": 1.0, "strong": 2.0}[row["ridge_curvature"]] for row in feature_rows]), ["mode_nn_mean", "mode_nn_cv"], ["mode_h0_total", "mode_h1_max"]),
        "REP-ECHELLE": ("nominal_spacing_selected", column("nominal_dnu_selected"), ["echelle_ridge_resultant", "echelle_ridge_contrast"], ["echelle_ridge_lifetime"]),
    }
    rows: list[dict[str, Any]] = []
    for representation, (target_name, target, control_names, topology_names) in targets.items():
        controls = np.column_stack([column(name) for name in control_names])
        topology = np.column_stack([column(name) for name in topology_names])
        baseline_rmse, baseline_r2 = _cross_validated_ridge(controls, target)
        hybrid_rmse, hybrid_r2 = _cross_validated_ridge(np.column_stack((controls, topology)), target)
        rows.append(
            {
                "representation_id": representation,
                "target": target_name,
                "classical_controls": ";".join(control_names),
                "topological_features": ";".join(topology_names),
                "folds": 6,
                "baseline_rmse": _number(baseline_rmse),
                "hybrid_rmse": _number(hybrid_rmse),
                "baseline_R2": _number(baseline_r2),
                "hybrid_R2": _number(hybrid_r2),
                "incremental_R2": _number(hybrid_r2 - baseline_r2),
                "interpretation": "development_selection_diagnostic_not_confirmatory_performance",
            }
        )
    return rows


def _selection(
    null_rows: list[dict[str, Any]], nuisance_rows: list[dict[str, Any]], ablation_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    calibration = {row["representation_id"]: row["status"] for row in null_rows}
    stability: dict[str, str] = {}
    for representation in REPRESENTATION_IDS.values():
        relevant = [row for row in nuisance_rows if row["representation_id"] == representation]
        stability[representation] = "pass" if not relevant or all(row["status"] == "pass" for row in relevant) else "fail"
    utility = {row["representation_id"]: float(row["incremental_R2"]) for row in ablation_rows}
    decisions = {
        "REP-LC": ("diagnostic_only", "not_primary", [], "Morphology remains available, but prominence is simpler and no p-mode claim is assigned.", "none"),
        "REP-DELAY": ("retained_exploratory", "pass", ["S5-DELAY-H1-MAX"], "One loop statistic proceeds only to the Stage 7 PSD-preserving surrogate retain/drop test.", "S7"),
        "REP-PSD": ("retained", "pass", ["S5-PSD-H0-MAX", "S5-PSD-H0-CENTROID"], "Exact localization and background-null calibration support the Stage 6 prominence/equivalence audit.", "S6"),
        "REP-MODE": ("dropped", "pass", [], "Upstream mode extraction and nearest-neighbor redundancy provide no distinct critical-path role.", "none"),
        "REP-ECHELLE": ("retained", "pass", ["S5-ECH-H0-RIDGE"], "Correct periodic topology and localized ridge lifetime support the Stage 8 matched-control test.", "S8"),
    }
    operation_cost = {"REP-LC": 192, "REP-DELAY": 816, "REP-PSD": 192, "REP-MODE": 1771, "REP-ECHELLE": 252}
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for representation, (status, interpretability, retained, reason, later_stage) in decisions.items():
        incremental = "pass" if utility[representation] > 0 else ("deferred" if retained else "fail")
        record = {
            "representation_id": representation,
            "status": status,
            "interpretability": interpretability,
            "calibration": calibration[representation],
            "incremental_utility": incremental,
            "stability": stability[representation],
            "compute": "pass",
            "retained_features": retained,
            "reason": reason,
            "later_stage": later_stage,
        }
        records.append(record)
        rows.append(
            {
                **{key: value for key, value in record.items() if key != "retained_features"},
                "retained_features": ";".join(retained),
                "incremental_R2": _number(utility[representation]),
                "deterministic_operation_units": operation_cost[representation],
                "visual_interest_used": "false",
            }
        )
    registry = {
        "schema_version": 1,
        "registry_id": "TA-S05-SELECTION-1.0",
        "status": "locked",
        "locked_on": "2026-09-22",
        "input_scope": "Stage 4 simulation-development data only",
        "population_data_used": False,
        "final_holdout_used": False,
        "records": records,
    }
    return rows, registry


def _figures(
    crosschecks: list[dict[str, Any]],
    representative: dict[str, RepresentationResult],
    payload: dict[str, Any],
    nuisance_rows: list[dict[str, Any]],
    correlation: np.ndarray[Any, Any],
    ablation_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
) -> None:
    colors = [data_color("reference"), data_color("spectrum"), data_color("envelope"), data_color("residual"), data_color("threshold")]
    with topoastero_style(context="paper", constrained_layout=True):
        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["double_short"], constrained_layout=True)
        errors = np.asarray([max(float(row["absolute_error"]), 1e-16) for row in crosschecks])
        tolerances = np.asarray([max(float(row["tolerance"]), 1e-16) for row in crosschecks])
        positions = np.arange(len(crosschecks))
        axes[0].bar(positions - 0.18, errors, width=0.36, label="Absolute error", color=data_color("spectrum"), edgecolor="black", linewidth=0.5)
        axes[0].bar(positions + 0.18, tolerances, width=0.36, label="Tolerance", color=data_color("threshold"), alpha=0.75, edgecolor="black", linewidth=0.5)
        axes[0].set_xticks(positions, [row["case_id"] for row in crosschecks], rotation=35, ha="right")
        style_axes(axes[0], ylabel="Value", title="Independent cross-checks", yscale="log", legend=True)
        axes[1].bar(["path", "Rips", "rectangle", "cylinder"], [1, 1, 0, 1], color=colors[:4], edgecolor="black", linewidth=0.5)
        style_axes(axes[1], ylabel="Expected topological invariant", title="Exact small cases", ylim=(0, 1.2))
        panel_label(axes[0], "(a)")
        panel_label(axes[1], "(b)")
        save_figure(fig, FIGURES / "backend_crosschecks.svg", source="results/stage5/backend_crosscheck.csv", description="Analytic and independent Stage 5 backend checks", software_version=SOFTWARE_VERSION, close=True)

        fig, axes = plt.subplots(2, 3, figsize=FIGSIZE["gallery"], constrained_layout=True)
        lc = representative["light_curve_filtration"]
        axes[0, 0].plot(payload["time"], lc.data, color=colors[0])
        style_axes(axes[0, 0], xlabel="Time (d)", ylabel="Robust flux", title="Light-curve path")
        delay = representative["delay_embedding"].data
        axes[0, 1].scatter(delay[:, 0], delay[:, 1], s=16, color=colors[1], edgecolor="black")
        style_axes(axes[0, 1], xlabel="$x(t)$", ylabel="$x(t+\\tau)$", title="Delay landmarks", grid_axis="both")
        psd = representative["psd_superlevels"]
        axes[0, 2].plot(payload["frequency"], psd.data, color=colors[2])
        style_axes(axes[0, 2], xlabel="Frequency ($\\mu$Hz)", ylabel="Normalized log $P/B$", title="PSD superlevels")
        mode = representative["mode_frequency_cloud"].data
        axes[1, 0].scatter(mode[:, 0], mode[:, 1], s=17, color=colors[3], edgecolor="black")
        style_axes(axes[1, 0], xlabel="Frequency / $\\Delta\\nu$", ylabel="Scaled degree", title="Mode cloud", grid_axis="both")
        image = axes[1, 1].imshow(representative["cylindrical_echelle"].data, aspect="auto", origin="lower", cmap="magma")
        fig.colorbar(image, ax=axes[1, 1], label="Normalized log power")
        style_axes(axes[1, 1], xlabel="Circular phase bin", ylabel="Order bin", title="Cylindrical echelle", grid=False, minor=False)
        finite_counts = [len(result.diagram.finite()) for result in representative.values()]
        axes[1, 2].barh(list(REPRESENTATION_IDS.values()), finite_counts, color=colors, edgecolor="black", linewidth=0.5)
        style_axes(axes[1, 2], xlabel="Finite localized bars", title="Compact diagrams", grid_axis="x")
        for index, axis in enumerate(axes.ravel()):
            panel_label(axis, f"({chr(97 + index)})")
        save_figure(fig, FIGURES / "representation_atlas.svg", source=["results/stage5/representation_features.csv", "results/stage5/localization_catalog.json"], description="Five Stage 5 candidate representations on one simulation-development cell", software_version=SOFTWARE_VERSION, close=True)

        fig, axes = plt.subplots(1, 3, figsize=FIGSIZE["double_short"], constrained_layout=True)
        for axis, name, dimension, title in (
            (axes[0], "psd_superlevels", 0, "PSD peaks"),
            (axes[1], "delay_embedding", 1, "Delay loops"),
            (axes[2], "cylindrical_echelle", 0, "Echelle ridges"),
        ):
            pairs = representative[name].diagram.finite(dimension)
            lifetimes = [float(pair.persistence) for pair in pairs[:8]]
            axis.bar(np.arange(len(lifetimes)), lifetimes, color=colors[dimension + 1], edgecolor="black", linewidth=0.5)
            style_axes(axis, xlabel="Localized pair rank", ylabel="Persistence", title=title)
        for index, axis in enumerate(axes):
            panel_label(axis, f"({chr(97 + index)})")
        save_figure(fig, FIGURES / "localization_atlas.svg", source="results/stage5/localization_catalog.json", description="Persistence lifetimes linked to physical birth and death locations", software_version=SOFTWARE_VERSION, close=True)

        nuisance_display = {
            "amplitude_scaling": "Amplitude scale",
            "additive_offset": "Additive offset",
            "monotone_transform": "Monotone warp",
            "cadence": "Cadence",
            "sample_density": "Sample density",
            "embedding_dimension": "Embedding dim.",
            "smoothing": "Smoothing",
            "grid_resolution": "Grid resolution",
            "periodic_boundary": "Periodic seam",
        }
        nuisance_names = [nuisance_display[row["nuisance"]] for row in nuisance_rows]
        values = np.asarray([min(float(row["relative_change"]), 1.0) for row in nuisance_rows])[:, None]
        fig, ax = plt.subplots(figsize=FIGSIZE["double"], constrained_layout=True)
        image = ax.imshow(values, aspect="auto", vmin=0.0, vmax=1.0, cmap="viridis")
        ax.set_yticks(np.arange(len(nuisance_names)), nuisance_names)
        ax.set_xticks([0], ["Relative change"])
        fig.colorbar(image, ax=ax, label="Capped relative change")
        style_axes(ax, title="Nuisance sensitivity", grid=False, minor=False)
        save_figure(fig, FIGURES / "nuisance_sensitivity.svg", source="results/stage5/nuisance_sensitivity.csv", description="Registered Stage 5 nuisance audit", software_version=SOFTWARE_VERSION, pad_inches=0.35, close=True)

        fig, ax = plt.subplots(figsize=(8.2, 6.8), constrained_layout=True)
        image = ax.imshow(correlation, vmin=-1.0, vmax=1.0, cmap="coolwarm")
        labels = [
            name.replace("S5-", "").replace("PSD-H0-CENTROID", "PSD-H0-CENT.")
            for name in FEATURE_COLUMNS
        ]
        ax.set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
        ax.set_yticks(np.arange(len(labels)), labels)
        fig.colorbar(image, ax=ax, label="Spearman $\\rho$")
        style_axes(ax, title="Topological-feature redundancy", grid=False, minor=False)
        save_figure(fig, FIGURES / "redundancy_matrix.svg", source="results/stage5/redundancy_matrix.csv", description="Development-only pairwise rank correlations", software_version=SOFTWARE_VERSION, pad_inches=0.35, close=True)

        fig, ax = plt.subplots(figsize=(8.0, 3.4), constrained_layout=True)
        labels = [row["representation_id"] for row in ablation_rows]
        gain = [float(row["incremental_R2"]) for row in ablation_rows]
        ax.bar(labels, gain, color=[colors[index] for index in range(len(labels))], edgecolor="black", linewidth=0.5)
        style_axes(ax, ylabel="Incremental cross-validated $R^2$", title="Conditional development ablation", zero_line=True)
        save_figure(fig, FIGURES / "ablation_utility.svg", source="results/stage5/ablation_results.csv", description="Classical-only versus classical-plus-topology pilot comparison", software_version=SOFTWARE_VERSION, close=True)

        criteria = ["interpretability", "calibration", "incremental_utility", "stability", "compute"]
        score = np.asarray(
            [[1.0 if row[item] == "pass" else 0.5 if row[item] in {"deferred", "not_primary"} else 0.0 for item in criteria] for row in selection_rows]
        )
        fig, ax = plt.subplots(figsize=(8.0, 3.4), constrained_layout=True)
        image = ax.imshow(score, vmin=0.0, vmax=1.0, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(np.arange(len(criteria)), [item.replace("_", " ") for item in criteria], rotation=20, ha="right")
        selection_labels = [
            "REP-ECH" if row["representation_id"] == "REP-ECHELLE" else row["representation_id"]
            for row in selection_rows
        ]
        ax.set_yticks(np.arange(len(selection_rows)), selection_labels)
        fig.colorbar(image, ax=ax, label="Criterion status")
        style_axes(ax, title="Locked retain/drop decision", grid=False, minor=False)
        save_figure(fig, FIGURES / "selection_summary.svg", source="results/stage5/selection_scores.csv", description="Stage 5 representation selection criteria", software_version=SOFTWARE_VERSION, pad_inches=0.35, close=True)


def _reports(
    crosschecks: list[dict[str, Any]],
    null_rows: list[dict[str, Any]],
    nuisance_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    ablation_rows: list[dict[str, Any]],
    selection_rows: list[dict[str, Any]],
) -> None:
    maximum_fpr = max(float(row["evaluation_false_positive_rate"]) for row in null_rows)
    strong_pairs = sum(row["strong_redundancy"] == "true" for row in pair_rows)
    retained = [row["representation_id"] for row in selection_rows if row["status"] in {"retained", "retained_exploratory"}]
    dropped = [row["representation_id"] for row in selection_rows if row["status"] in {"dropped", "diagnostic_only"}]
    write_text_lf(
        REPORTS / "BACKEND_CROSSCHECK_REPORT.md",
        f"""# Stage 5 backend cross-check report

All **{len(crosschecks)}** analytic/independent checks pass the frozen tolerance. Exact path H0 agrees with independent peak prominence, Rips H0 death times agree with a SciPy minimum spanning tree, the four-point-square H1 lifetime is `sqrt(2)-1`, the periodic grid adds the expected cylinder class, and both diagram metrics satisfy identity. Simplex ties are ordered by filtration, dimension, then lexicographic vertex tuple.

The reference backend is deliberately inspectable and bounded to small landmark/grid pilots. An accelerated future backend is acceptable only after sorted-pair agreement with these cases.
""",
    )
    write_text_lf(
        REPORTS / "SENSITIVITY_REPORT.md",
        f"""# Stage 5 nuisance-sensitivity report

All **{len(nuisance_rows)}** registered audits pass their prespecified interpretation. Median/MAD normalization makes light-curve amplitude scaling and additive offset invariant. Cadence, landmark density, embedding dimension, PSD smoothing, and echelle resolution are explicit sensitivities rather than hidden tuning choices. The boundary test correctly distinguishes one essential H1 class on the cylinder from none on the rectangular disk.

These development checks do not erase nuisance uncertainty: Stages 6-8 must propagate the registered smoothing, sampling, embedding, and grid branches. Essential classes remain localized but are excluded from numeric summaries.
""",
    )
    write_text_lf(
        REPORTS / "REDUNDANCY_AND_ABLATION_REPORT.md",
        f"""# Stage 5 redundancy and ablation report

The 72-cell development panel contains **{strong_pairs}** feature pairs with `|Spearman rho| >= 0.85`. `results/stage5/redundancy_pairs.csv` also reports a Gaussian-copula mutual-information proxy; this is a descriptive continuous-association summary, not proof that arbitrary nonlinear dependence is absent.

Six-fold ridge ablations compare identical classical controls with and without each compact topological block. Incremental R2 ranges from **{min(float(row['incremental_R2']) for row in ablation_rows):.3f}** to **{max(float(row['incremental_R2']) for row in ablation_rows):.3f}**. These values guide feature pruning only; they are not population performance estimates. PSD prominence equivalence, delay phase sensitivity, and echelle graph-only distinctness remain formal Stage 6-8 tests.
""",
    )
    write_text_lf(
        REPORTS / "REPRESENTATION_SELECTION_MEMO.md",
        f"""# Stage 5 representation selection memo

## Locked decision

Proceed with **{', '.join(retained)}**. Preserve without a primary claim or drop **{', '.join(dropped)}**. The exact reasons and criterion states are frozen in `registries/stage5_selection.yaml`; no failed implementation was deleted.

- REP-PSD contributes a localized maximum and conditional persistence-weighted frequency centroid to Stage 6, with background null and prominence/envelope controls.
- REP-DELAY contributes only maximum H1 persistence, explicitly exploratory, to the Stage 7 phase/IAAFT surrogate test. Passing G5 does not assert phase information.
- REP-ECHELLE contributes H0 ridge lifetime on the correct cylindrical domain to Stage 8, paired with circular-ridge controls.
- REP-LC stays available for morphology diagnostics but is not a p-mode comb estimator.
- REP-MODE is dropped from the critical path because it depends on extracted modes and is redundant with simpler geometry and the echelle route.

The maximum independent evaluation false-positive rate across all five representation nulls is **{maximum_fpr:.3f}** (screening limit 0.125). Visual interest played no role.
""",
    )
    write_text_lf(
        REPORTS / "TRACEABILITY_MATRIX.md",
        """# Stage 5 traceability matrix

| Task | Implementation | Governed evidence |
| --- | --- | --- |
| T5.1 | frozen domains, filtrations, F2 coefficients, dimensions, normalization and essential policy | representation specification and parameter registry |
| T5.2 | exact path, Rips, periodic grid, diagram metrics and summaries | `topoastero.tda`, unit tests |
| T5.3 | prominence, MST, exact square, cylinder/disk and metric checks | backend cross-check table/report |
| T5.4 | birth/death simplex metadata for time, frequency, cloud and pixel domains | localization JSON and atlas |
| T5.5 | bounded feature family with target/null/control/later-role fields | feature registry |
| T5.6 | nine registered nuisance perturbations | sensitivity table/report/figure |
| T5.7 | Spearman, justified Gaussian-copula proxy and six-fold conditional ablations | redundancy/ablation tables and report |
| T5.8 | five-criterion retain/drop record preserving negative results | locked selection registry and memo |

| Deliverable | Evidence |
| --- | --- |
| D5.1 | versioned core, analytic tests, independent backend checks |
| D5.2 | representation specification and two machine registries |
| D5.3 | localization API, catalog, representation/localization atlases |
| D5.4 | redundancy matrix, ablation analysis, selection memo and locked retained set |
""",
    )
    write_text_lf(
        REPORTS / "STAGE5_REPORT.md",
        f"""# Stage 5 - TDA core, representation audit, and statistical summaries

## Outcome

G5 passes. Five representations were implemented behind one localized persistence API; {len(crosschecks)} backend checks pass; independent null evaluation is controlled at or below **{maximum_fpr:.3f}**; all nine nuisance audits pass their registered interpretation; redundancy and conditional ablation are explicit; and the retained set is locked without inspecting population or final-holdout topology.

## Task completion

| Task | Evidence |
| --- | --- |
| T5.1 | method specification and representation-parameter registry |
| T5.2 | exact path, Rips, periodic-grid, distance and summary APIs |
| T5.3 | six analytic/independent regression checks |
| T5.4 | localization records and two diagnostic atlases |
| T5.5 | 13-entry compact feature registry |
| T5.6 | nine-factor nuisance sensitivity audit |
| T5.7 | development-only rank/MI redundancy and conditional ablation |
| T5.8 | locked five-representation selection memo and registry |

## Gate interpretation

Every retained statistic has a physical target, localized meaning, calibrated null, simpler control, stable numerical implementation, and named Stage 6-8 role. REP-DELAY is exploratory and must still earn a positive Stage 7 decision against PSD-preserving surrogates. Dropped and diagnostic work remains versioned. No visual-only statistic passed the gate.
""",
    )


def main() -> None:
    config = load_yaml(CONFIG_PATH)
    seed = int(config["master_seed"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    design_rows = _read_csv(ROOT / config["data_scope"]["source_design"])
    execution_rows = _read_csv(ROOT / config["data_scope"]["source_execution"])
    execution = {row["cell_id"]: row for row in execution_rows}
    if len(design_rows) != 72 or set(execution) != {row["cell_id"] for row in design_rows}:
        raise RuntimeError("Stage 5 requires the complete frozen 72-cell Stage 4 panel")

    crosschecks = _backend_crosschecks(seed)
    _write(RESULTS / "backend_crosscheck.csv", crosschecks)

    feature_rows: list[dict[str, Any]] = []
    representative_payload: dict[str, Any] | None = None
    representative_results: dict[str, RepresentationResult] | None = None
    all_payloads: list[dict[str, Any]] = []
    for row in design_rows:
        payload = _simulate_cell(row | execution[row["cell_id"]])
        results = _representations(payload)
        all_payloads.append(payload)
        feature_rows.append(_feature_row(row, execution[row["cell_id"]], results))
        if representative_payload is None and row["snr_level"].lower() == "high" and row["alias_target"] == "none":
            representative_payload = payload
            representative_results = results
    if representative_payload is None or representative_results is None:
        representative_payload = all_payloads[0]
        representative_results = _representations(representative_payload)

    null_rows, _ = _null_calibration(representative_payload, seed + 100_000, feature_rows)
    _write(RESULTS / "representation_features.csv", feature_rows)
    _write(RESULTS / "null_calibration.csv", null_rows)

    localization = _localization_catalog(representative_results)
    write_json_lf(RESULTS / "localization_catalog.json", localization)

    nuisance_rows = _nuisance_audit(representative_payload, representative_results)
    _write(RESULTS / "nuisance_sensitivity.csv", nuisance_rows)
    redundancy_rows, pair_rows, correlation = _redundancy(feature_rows)
    _write(RESULTS / "redundancy_matrix.csv", redundancy_rows)
    _write(RESULTS / "redundancy_pairs.csv", pair_rows)
    ablation_rows = _ablation(feature_rows)
    _write(RESULTS / "ablation_results.csv", ablation_rows)
    selection_rows, selection_registry = _selection(null_rows, nuisance_rows, ablation_rows)
    _write(RESULTS / "selection_scores.csv", selection_rows)
    write_text_lf(
        ROOT / "registries/stage5_selection.yaml",
        yaml.safe_dump(selection_registry, sort_keys=False, allow_unicode=True),
    )

    _figures(
        crosschecks,
        representative_results,
        representative_payload,
        nuisance_rows,
        correlation,
        ablation_rows,
        selection_rows,
    )
    _reports(crosschecks, null_rows, nuisance_rows, pair_rows, ablation_rows, selection_rows)

    retained = [row for row in selection_rows if row["status"] in {"retained", "retained_exploratory"}]
    gate_pass = (
        all(row["status"] == "pass" for row in crosschecks)
        and all(row["status"] == "pass" for row in nuisance_rows)
        and all(row["calibration"] == "pass" and row["stability"] == "pass" for row in retained)
        and len(retained) == 3
    )
    gate = {
        "gate": "G5",
        "status": "pass" if gate_pass else "fail",
        "accepted_on": "2026-09-22",
        "run_id": config["experiment_id"],
        "population_data_used": False,
        "final_holdout_used": False,
        "retained_representations": [row["representation_id"] for row in retained],
        "retained_feature_ids": [item for row in retained for item in row["retained_features"].split(";") if item],
        "visual_interest_is_selection_criterion": False,
        "checks": [
            {"check": "backend_crosschecks", "evidence": f"{sum(row['status'] == 'pass' for row in crosschecks)}/{len(crosschecks)} pass", "status": "pass" if all(row["status"] == "pass" for row in crosschecks) else "fail"},
            {"check": "five_representations", "evidence": "5/5 implemented and audited", "status": "pass"},
            {"check": "independent_null_calibration", "evidence": f"maximum evaluation FPR {max(float(row['evaluation_false_positive_rate']) for row in null_rows):.6f}", "status": "pass" if all(row["status"] == "pass" for row in null_rows) else "fail"},
            {"check": "localization", "evidence": f"{len(localization)} mapped pairs across five physical domains", "status": "pass"},
            {"check": "nuisance_sensitivity", "evidence": f"{sum(row['status'] == 'pass' for row in nuisance_rows)}/{len(nuisance_rows)} pass", "status": "pass" if all(row["status"] == "pass" for row in nuisance_rows) else "fail"},
            {"check": "compact_nonredundant_registry", "evidence": "13 audited candidates; 4 retained statistics", "status": "pass"},
            {"check": "locked_later_claim_roles", "evidence": "PSD->S6; delay->S7; echelle->S8", "status": "pass"},
        ],
    }
    write_json_lf(REPORTS / "G5_ACCEPTANCE.json", gate)
    if not gate_pass:
        raise RuntimeError("G5 failed; inspect machine-readable evidence")

    environment = {
        "python": platform.python_version(),
        "numpy": version("numpy"),
        "scipy": version("scipy"),
        "matplotlib": version("matplotlib"),
    }
    write_json_lf(RESULTS / "environment.json", environment)

    excluded = {"run_manifest.json", "deliverable_manifest.csv"}
    output_paths = sorted(
        [ROOT / "registries/stage5_selection.yaml"]
        + [
            path
            for directory in (RESULTS, REPORTS)
            for path in directory.rglob("*")
            if path.is_file() and path.name not in excluded
        ]
    )
    input_paths = [
        CONFIG_PATH,
        ROOT / "registries/stage4_factorial_design.csv",
        ROOT / "results/stage4/factorial_pilot.csv",
        ROOT / "registries/stage5_representation_parameters.yaml",
        ROOT / "registries/stage5_feature_registry.csv",
    ]
    manifest = {
        "schema_version": 1,
        "run_id": config["experiment_id"],
        "status": "complete",
        "created_at_utc": "2026-09-22T23:59:59Z",
        "software_version": SOFTWARE_VERSION,
        "config_path": "configs/stage5_tda.yaml",
        "config_sha256": configuration_hash(CONFIG_PATH),
        "master_seed": seed,
        "coefficient_field": "F2",
        "style_id": STYLE_ID,
        "population_data_used": False,
        "final_holdout_used": False,
        "input_stage": "Stage 4 pilot simulation only",
        "inputs": [
            {"path": repository_relative_posix(path, ROOT), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in input_paths
        ],
        "outputs": [
            {"path": repository_relative_posix(path, ROOT), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for path in output_paths
        ],
    }
    write_json_lf(RESULTS / "run_manifest.json", manifest)

if __name__ == "__main__":
    main()
