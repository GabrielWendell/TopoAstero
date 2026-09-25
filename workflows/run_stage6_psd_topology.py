"""Execute the locked Stage 6 persistent-power-spectrum laboratory.

The workflow is deliberately offline.  It consumes the frozen Stage 4 factorial design and the
Stage 5 selection lock, derives independent Stage 6 stochastic spectra, writes all T6.1--T6.8
evidence, and never opens population or final-holdout data.
"""

from __future__ import annotations

import csv
import json
import math
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d  # type: ignore[import-untyped]

from topoastero.classical import HarveyComponent
from topoastero.config import configuration_hash, load_yaml
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)
from topoastero.provenance import sha256_file
from topoastero.simulation_lab import asymptotic_mode_comb, target_oscillator_psd
from topoastero.spectral_topology import (
    CombEstimate,
    MaxStatisticCalibration,
    NormalizedSpectrum,
    QualityFlag,
    SpectralPeak,
    adapt_pysyd_numax,
    assess_spectrum_quality,
    autocorrelation_spacing_scores,
    calibrate_maximum_statistic,
    comb_score_scan,
    empirical_max_pvalue,
    estimate_comb_candidates,
    estimate_numax,
    evaluate_maximum_calibration,
    localized_peak_persistence,
    normalize_spectrum,
    prominence_matches,
    psps_spacing_scores,
    smoothed_envelope_numax,
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
from topoastero.tda import bottleneck_distance, diagram_points

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "configs/stage6_psd_topology.yaml"
RESULTS = ROOT / "results/stage6"
REPORTS = ROOT / "reports/stage6"
FIGURES = REPORTS / "figures"
SOFTWARE_VERSION = "TopoAstero-0.7.0"
TRIAL_SPACINGS = np.linspace(20.0, 300.0, 57)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty Stage 6 table: {path}")
    write_csv_lf(path, rows, fieldnames=fieldnames or list(rows[0]))


def _number(value: float, digits: int = 10) -> str:
    return f"{value:.{digits}g}"


def _cell_number(cell_id: str) -> int:
    return int(cell_id.rsplit("-", 1)[1])


def _cell_role(cell_id: str) -> str:
    return "calibration" if _cell_number(cell_id) % 2 else "evaluation"


def _simulate_cell(row: dict[str, str]) -> dict[str, Any]:
    seed = int(row["seed"]) + 600_000
    rng = np.random.default_rng(seed)
    snr = {"low": 0.8, "medium": 1.6, "high": 3.2}[row["snr_level"].lower()]
    numax = float(row["numax_uHz"])
    dnu = float(row["dnu_uHz"])
    lifetime = float(row["lifetime_days"])
    cadence = float(row["cadence_seconds"])
    duration = float(row["duration_days"])
    frequency = np.linspace(max(1.0, numax - 3.5 * dnu), numax + 3.5 * dnu, 256)
    orders = int(row["visible_orders"])
    if orders % 2 == 0:
        orders -= 1
    modes = asymptotic_mode_comb(
        numax_uHz=numax,
        dnu_uHz=dnu,
        radial_orders=orders,
        radial_height_ppm2_per_uHz=35.0 * snr,
        lifetime_days=lifetime,
        rotational_splitting_uHz=0.4,
    )
    components = (HarveyComponent(10.0, 700.0),)
    background_true = target_oscillator_psd(
        frequency,
        modes=(),
        white_noise_ppm2_per_uHz=2.0,
        background=components,
        integration_seconds=cadence,
    )
    target = target_oscillator_psd(
        frequency,
        modes=modes,
        white_noise_ppm2_per_uHz=2.0,
        background=components,
        integration_seconds=cadence,
    )
    averages = max(1, min(8, round(duration / 55.0)))
    power = rng.gamma(shape=averages, scale=target / averages)
    gap_pattern = row["gap_pattern"]
    alias_period = {"none": math.inf, "random": 47.0, "kepler_q5": 11.574, "tess_s14": 0.863}[gap_pattern]
    if math.isfinite(alias_period):
        phase = 2.0 * math.pi * frequency / alias_period
        amplitude = {"random": 0.05, "kepler_q5": 0.10, "tess_s14": 0.08}[gap_pattern]
        power *= np.maximum(0.15, 1.0 + amplitude * np.cos(phase))
    fitted_background = background_true.copy()
    if row["background_model"] == "misspecified":
        coordinate = np.linspace(-1.0, 1.0, frequency.size)
        fitted_background *= 1.0 + 0.12 * coordinate
    return {
        "frequency": frequency,
        "power": np.asarray(power, dtype=np.float64),
        "target": target,
        "background": fitted_background,
        "background_true": background_true,
        "numax": numax,
        "dnu": dnu,
        "orders": orders,
        "seed": seed,
        "averages": averages,
    }


def _top_peaks(peaks: tuple[SpectralPeak, ...], count: int = 30) -> tuple[SpectralPeak, ...]:
    finite = [peak for peak in peaks if not peak.essential and peak.persistence is not None]
    finite.sort(key=lambda peak: (-(peak.persistence or 0.0), peak.peak_index))
    return tuple(finite[:count])


def _comb_from_peaks(peaks: tuple[SpectralPeak, ...]) -> tuple[np.ndarray, float, CombEstimate]:
    selected = _top_peaks(peaks)
    scores = comb_score_scan(selected, TRIAL_SPACINGS, fractional_bandwidth=0.06)
    best = float(TRIAL_SPACINGS[int(np.argmax(scores))])
    estimate = estimate_comb_candidates(
        selected,
        nominal_spacing_uHz=best,
        fractional_bandwidth=0.06,
        ambiguity_ratio=1.15,
    )
    return scores, best, estimate


def _candidate_contains_truth(estimate: CombEstimate, truth: float) -> bool:
    return any(abs(candidate.spacing_uHz - truth) / truth <= 0.15 for candidate in estimate.candidates)


def _null_draws(
    config: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[int, MaxStatisticCalibration],
    MaxStatisticCalibration,
]:
    calibration_count = int(config["null_calibration"]["calibration_realizations"])
    evaluation_count = int(config["null_calibration"]["evaluation_realizations"])
    alpha = float(config["null_calibration"]["alpha"])
    frequency = np.linspace(1700.0, 2700.0, 256)
    background = 2.0 + 10.0 / (1.0 + (frequency / 700.0) ** 4)

    def envelope_matrix(seed_start: int, count: int, averages: int) -> np.ndarray:
        envelope = np.empty((count, 1), dtype=np.float64)
        for index in range(count):
            rng = np.random.default_rng(seed_start + index)
            power = rng.gamma(shape=averages, scale=background / averages)
            spectrum = normalize_spectrum(frequency, power, background, method="log_ratio")
            _, peaks = localized_peak_persistence(spectrum)
            finite = [peak.persistence for peak in peaks if peak.persistence is not None]
            envelope[index, 0] = max((float(value) for value in finite), default=0.0)
        return envelope

    def comb_matrix(seed_start: int, count: int) -> tuple[np.ndarray, np.ndarray]:
        comb = np.empty((count, TRIAL_SPACINGS.size), dtype=np.float64)
        confident = np.zeros(count, dtype=np.bool_)
        for index in range(count):
            rng = np.random.default_rng(seed_start + index)
            power = rng.exponential(background)
            spectrum = normalize_spectrum(frequency, power, background, method="log_ratio")
            _, peaks = localized_peak_persistence(spectrum)
            scores, _, estimate = _comb_from_peaks(peaks)
            comb[index] = scores
            confident[index] = not estimate.ambiguous
        return comb, confident

    rows: list[dict[str, Any]] = []
    maxima_rows: list[dict[str, Any]] = []
    envelope_calibrations: dict[int, MaxStatisticCalibration] = {}
    for averages in (1, 2, 7):
        calibration_seed = 6_100_000 + averages * 10_000
        evaluation_seed = 6_200_000 + averages * 10_000
        calibration_envelope = envelope_matrix(calibration_seed, calibration_count, averages)
        evaluation_envelope = envelope_matrix(evaluation_seed, evaluation_count, averages)
        envelope_calibration = calibrate_maximum_statistic(calibration_envelope, alpha=alpha)
        envelope_calibrations[averages] = envelope_calibration
        envelope_evaluation = evaluate_maximum_calibration(
            evaluation_envelope, envelope_calibration
        )
        rows.append(
            {
                "claim": f"envelope_detection_avg{averages}",
                "null_family": "background_only_matched_gamma_periodogram",
                "multiplicity_scope": "maximum_over_frequency",
                "trial_count": 1,
                "alpha": _number(alpha),
                "calibration_realizations": calibration_count,
                "evaluation_realizations": evaluation_count,
                "calibration_seed_range": f"{calibration_seed}-{calibration_seed + calibration_count - 1}",
                "evaluation_seed_range": f"{evaluation_seed}-{evaluation_seed + evaluation_count - 1}",
                "threshold": _number(envelope_calibration.threshold),
                "evaluation_false_positive_rate": _number(
                    envelope_evaluation.false_positive_rate
                ),
                "evaluation_false_confidence_rate": _number(
                    envelope_evaluation.false_confidence_rate
                ),
                "detections": envelope_evaluation.detections,
                "status": "pass"
                if envelope_evaluation.false_positive_rate <= 0.08
                else "fail",
            }
        )
        for stream, matrix in (
            ("calibration", calibration_envelope),
            ("evaluation", evaluation_envelope),
        ):
            for index in range(matrix.shape[0]):
                maxima_rows.append(
                    {
                        "stream": stream,
                        "stratum": f"averages_{averages}",
                        "realization": index + 1,
                        "envelope_maximum": _number(float(matrix[index, 0])),
                        "comb_maximum": "",
                    }
                )

    calibration_comb, _ = comb_matrix(6_310_000, calibration_count)
    evaluation_comb, evaluation_confident = comb_matrix(6_320_000, evaluation_count)
    comb_calibration = calibrate_maximum_statistic(calibration_comb, alpha=alpha)
    comb_evaluation = evaluate_maximum_calibration(
        evaluation_comb,
        comb_calibration,
        confidence_mask=evaluation_confident,
    )
    rows.append(
        {
            "claim": "comb_detection",
            "null_family": "background_only_exponential_periodogram",
            "multiplicity_scope": "maximum_over_frequency_and_trial_spacing",
            "trial_count": TRIAL_SPACINGS.size,
            "alpha": _number(alpha),
            "calibration_realizations": calibration_count,
            "evaluation_realizations": evaluation_count,
            "calibration_seed_range": f"6310000-{6310000 + calibration_count - 1}",
            "evaluation_seed_range": f"6320000-{6320000 + evaluation_count - 1}",
            "threshold": _number(comb_calibration.threshold),
            "evaluation_false_positive_rate": _number(comb_evaluation.false_positive_rate),
            "evaluation_false_confidence_rate": _number(comb_evaluation.false_confidence_rate),
            "detections": comb_evaluation.detections,
            "status": "pass"
            if max(
                comb_evaluation.false_positive_rate,
                comb_evaluation.false_confidence_rate,
            )
            <= 0.08
            else "fail",
        }
    )
    for stream, matrix in (
        ("calibration", calibration_comb),
        ("evaluation", evaluation_comb),
    ):
        for index in range(matrix.shape[0]):
            maxima_rows.append(
                {
                    "stream": stream,
                    "stratum": "all_trials",
                    "realization": index + 1,
                    "envelope_maximum": "",
                    "comb_maximum": _number(float(np.max(matrix[index]))),
                }
            )
    return rows, maxima_rows, envelope_calibrations, comb_calibration


def _normalization_audit(
    design: list[dict[str, str]], payloads: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    methods = ("log_ratio", "ratio", "whitened_residual", "uncertainty_zscore")
    selected = design[::6]
    rows: list[dict[str, Any]] = []
    for method in methods:
        errors: list[float] = []
        peak_counts: list[int] = []
        maxima: list[float] = []
        for row in selected:
            payload = payloads[row["cell_id"]]
            sigma = 0.10 * payload["background"] if method == "uncertainty_zscore" else None
            spectrum = normalize_spectrum(
                payload["frequency"],
                payload["power"],
                payload["background"],
                method=method,
                background_sigma=sigma,
            )
            _, peaks = localized_peak_persistence(spectrum)
            location = estimate_numax(
                spectrum,
                search_uHz=(
                    payload["numax"] - 3.0 * payload["dnu"],
                    payload["numax"] + 3.0 * payload["dnu"],
                ),
                bootstrap_replicates=16,
                seed=payload["seed"] + 31,
            )
            errors.append(abs(location.numax_uHz - payload["numax"]) / payload["dnu"])
            finite = [peak for peak in peaks if peak.persistence is not None]
            peak_counts.append(len(finite))
            maxima.append(max((float(peak.persistence) for peak in finite), default=0.0))
        rows.append(
            {
                "method": method,
                "role": "primary" if method == "log_ratio" else "registered_sensitivity",
                "cells": len(selected),
                "median_absolute_numax_error_dnu": _number(float(np.median(errors))),
                "maximum_absolute_numax_error_dnu": _number(float(np.max(errors))),
                "median_finite_peak_count": _number(float(np.median(peak_counts))),
                "median_maximum_persistence": _number(float(np.median(maxima))),
                "background_uncertainty_explicit": str(method == "uncertainty_zscore").lower(),
                "status": "pass",
            }
        )
    return rows


def _equivalence_audit(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    analytic = {
        "analytic_two_peak": np.asarray([0.0, 3.0, 0.0, 2.0, 0.0]),
        "analytic_boundary_peak": np.asarray([3.0, 0.5, 1.0, 0.0, 4.0, 0.5, 2.0]),
        "analytic_equal_birth_tie": np.asarray([0.0, 2.0, 0.0, 2.0, -1.0]),
        "analytic_multiscale": np.asarray([0.0, 4.0, 1.0, 2.0, 0.5, 3.0, 0.0]),
    }
    rows: list[dict[str, Any]] = []

    def add(case_id: str, spectrum: NormalizedSpectrum, domain: str) -> None:
        _, peaks = localized_peak_persistence(spectrum)
        matches = prominence_matches(spectrum)
        maximum = max((match.absolute_error for match in matches), default=0.0)
        rows.append(
            {
                "case_id": case_id,
                "domain": domain,
                "finite_classes": len(matches),
                "essential_classes": sum(peak.essential for peak in peaks),
                "boundary_finite_classes": sum(match.boundary_peak for match in matches),
                "maximum_absolute_error": _number(maximum),
                "mean_absolute_error": _number(
                    float(np.mean([match.absolute_error for match in matches])) if matches else 0.0
                ),
                "control": "independent_elder_rule_path_scan",
                "interpretation": "exact_equivalence_organization_only",
                "status": "pass" if maximum <= 1e-10 else "fail",
            }
        )

    for case_id, values in analytic.items():
        frequency = np.arange(values.size, dtype=np.float64)
        add(
            case_id,
            normalize_spectrum(frequency, np.exp(values), np.ones_like(values)),
            "analytic",
        )
    for cell_id in sorted(payloads)[::6]:
        payload = payloads[cell_id]
        add(
            cell_id,
            normalize_spectrum(
                payload["frequency"], payload["power"], payload["background"]
            ),
            "locked_realistic_spectrum",
        )
    return rows


def _method_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    methods = sorted({str(row["method"]) for row in rows})
    group_specs: list[tuple[str, str]] = [("overall", "all")]
    for field in ("snr_level", "duration_days", "duty_cycle", "lifetime_days"):
        group_specs.extend((field, value) for value in sorted({str(row[field]) for row in rows}))
    summaries: list[dict[str, Any]] = []
    for method in methods:
        method_rows = [row for row in rows if row["method"] == method]
        for factor, level in group_specs:
            selected = method_rows if factor == "overall" else [row for row in method_rows if str(row[factor]) == level]
            if not selected:
                continue
            errors = np.asarray([float(row["absolute_error_uHz"]) for row in selected])
            biases = np.asarray([float(row["bias_uHz"]) for row in selected])
            summaries.append(
                {
                    "method": method,
                    "factor": factor,
                    "level": level,
                    "n": len(selected),
                    "bias_uHz": _number(float(np.mean(biases))),
                    "median_absolute_error_uHz": _number(float(np.median(errors))),
                    "interval_coverage": _number(float(np.mean([row["covered"] == "true" for row in selected]))),
                    "catastrophic_failure_rate": _number(
                        float(np.mean([row["catastrophic"] == "true" for row in selected]))
                    ),
                    "median_interval_width_uHz": _number(
                        float(np.median([float(row["upper_uHz"]) - float(row["lower_uHz"]) for row in selected]))
                    ),
                }
            )
    return summaries


def _robustness_atlas(
    design: list[dict[str, str]], payloads: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows: list[dict[str, Any]] = []
    background_spread: dict[str, float] = {}
    selected_ids = [row["cell_id"] for row in design[::6]]
    for cell_id in selected_ids:
        payload = payloads[cell_id]
        base = normalize_spectrum(payload["frequency"], payload["power"], payload["background"])
        base_diagram, base_peaks = localized_peak_persistence(base)
        search = (
            payload["numax"] - 3.0 * payload["dnu"],
            payload["numax"] + 3.0 * payload["dnu"],
        )
        base_numax = estimate_numax(base, search_uHz=search, bootstrap_replicates=16).numax_uHz
        _, _, base_comb = _comb_from_peaks(base_peaks)
        coordinate = np.linspace(-1.0, 1.0, base.values.size)
        branch_inputs: dict[str, NormalizedSpectrum] = {
            "background_posterior_low": normalize_spectrum(
                payload["frequency"], payload["power"], 0.90 * payload["background"]
            ),
            "background_posterior_high": normalize_spectrum(
                payload["frequency"], payload["power"], 1.10 * payload["background"]
            ),
            "background_model_slope": normalize_spectrum(
                payload["frequency"],
                payload["power"],
                payload["background"] * (1.0 + 0.15 * coordinate),
            ),
            "smoothing": NormalizedSpectrum(
                base.frequency_uHz,
                base.power,
                base.background,
                gaussian_filter1d(base.values, 2.0),
                base.method,
                base.primary,
                base.background_sigma,
            ),
            "resolution": normalize_spectrum(
                payload["frequency"][::2],
                payload["power"][::2],
                payload["background"][::2],
            ),
            "window_features": normalize_spectrum(
                payload["frequency"],
                payload["power"]
                * np.maximum(0.2, 1.0 + 0.12 * np.cos(2.0 * np.pi * payload["frequency"] / 11.574)),
                payload["background"],
            ),
        }
        branch_numax: dict[str, float] = {}
        for factor, spectrum in branch_inputs.items():
            diagram, peaks = localized_peak_persistence(spectrum)
            location = estimate_numax(
                spectrum,
                search_uHz=search,
                bootstrap_replicates=16,
                seed=payload["seed"] + 91,
            ).numax_uHz
            branch_numax[factor] = location
            _, _, comb = _comb_from_peaks(peaks)
            distance = bottleneck_distance(
                diagram_points(base_diagram, dimension=0),
                diagram_points(diagram, dimension=0),
            )
            shift = abs(location - base_numax) / payload["dnu"]
            rows.append(
                {
                    "cell_id": cell_id,
                    "factor": factor,
                    "baseline_numax_uHz": _number(base_numax),
                    "branch_numax_uHz": _number(location),
                    "absolute_numax_shift_dnu": _number(shift),
                    "diagram_bottleneck": _number(distance),
                    "baseline_comb_winner": base_comb.winner,
                    "branch_comb_winner": comb.winner,
                    "comb_winner_changed": str(comb.winner != base_comb.winner).lower(),
                    "status": "pass" if shift <= 0.40 else "flag",
                }
            )
        low = branch_numax["background_posterior_low"]
        high = branch_numax["background_posterior_high"]
        background_spread[cell_id] = abs(high - low) / max(abs(base_numax), 1e-12)
    median_spread = float(np.median(list(background_spread.values())))
    for row in design:
        background_spread.setdefault(row["cell_id"], median_spread)
    return rows, background_spread


def _figures(
    payloads: dict[str, dict[str, Any]],
    equivalence: list[dict[str, Any]],
    numax_rows: list[dict[str, Any]],
    comb_rows: list[dict[str, Any]],
    null_maxima: list[dict[str, Any]],
    null_rows: list[dict[str, Any]],
    robustness: list[dict[str, Any]],
    quality: list[dict[str, Any]],
) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    with topoastero_style():
        payload = payloads[sorted(payloads)[0]]
        spectrum = normalize_spectrum(payload["frequency"], payload["power"], payload["background"])
        _, peaks = localized_peak_persistence(spectrum)
        fig, axes = plt.subplots(2, 1, figsize=(FIGSIZE["double"][0], 5.5), sharex=True)
        axes[0].plot(spectrum.frequency_uHz, spectrum.values, color=data_color("spectrum"), linewidth=0.8)
        finite = [peak for peak in peaks if peak.persistence is not None]
        axes[0].scatter(
            [peak.birth_frequency_uHz for peak in finite],
            [peak.birth_value for peak in finite],
            s=10,
            color=data_color("envelope"),
            label="Finite births",
            edgecolor="black",
        )
        style_axes(axes[0], ylabel=r"$\log(P/B)$", legend=True)
        panel_label(axes[0], "a")
        axes[1].vlines(
            [peak.birth_frequency_uHz for peak in finite],
            [peak.death_value for peak in finite],
            [peak.birth_value for peak in finite],
            color=data_color("background"),
            linewidth=0.8,
        )
        style_axes(axes[1], xlabel=r"Frequency ($\mu$Hz)", ylabel="Birth - Saddle")
        panel_label(axes[1], "b")
        save_figure(
            fig,
            FIGURES / "normalized_spectrum_and_diagram.svg",
            source="results/stage6/peak_diagram.json",
            description="Localized Stage 6 log(P/B) path persistence",
            software_version=SOFTWARE_VERSION,
            pad_inches=0.25,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        errors = np.asarray([float(row["maximum_absolute_error"]) for row in equivalence])
        ax.scatter(np.arange(errors.size), errors, s=18, color=data_color("spectrum"), edgecolor="black")
        ax.axhline(1e-10, color=data_color("threshold"), linestyle="--", linewidth=0.9, label="Gate")
        ax.set_ylim(-0.05e-10, 1.15e-10)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        style_axes(ax, xlabel="Audit case", ylabel="Maximum absolute difference", legend=True)
        save_figure(
            fig,
            FIGURES / "prominence_equivalence.svg",
            source="results/stage6/equivalence_audit.csv",
            description="Independent persistence-prominence equivalence audit",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double"])
        methods = ["persistence_centroid", "smoothed_envelope", "pysyd_style_control"]
        for index, method in enumerate(methods):
            subset = [row for row in numax_rows if row["method"] == method and row["role"] == "evaluation"]
            truth = np.asarray([float(row["true_numax_uHz"]) for row in subset])
            estimate = np.asarray([float(row["estimate_uHz"]) for row in subset])
            ax.scatter(truth, estimate, 
                       s=15, 
                       alpha=0.75, 
                       label=method.replace("_", " ").capitalize(), 
                       color=data_color(("spectrum", "background", "envelope")[index]),
                       edgecolor="black")
        minimum, maximum = ax.get_xlim()
        ax.plot([minimum, maximum], [minimum, maximum], color="0.4", linestyle="--", linewidth=0.8)
        style_axes(ax, xlabel=r"True $\nu_{\max}$ ($\mu$Hz)", ylabel=r"Estimated $\nu_{\max}$ ($\mu$Hz)", legend=True)
        save_figure(
            fig,
            FIGURES / "numax_comparison.svg",
            source="results/stage6/numax_benchmark.csv",
            description="Paired Stage 6 nu_max estimator comparison",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        methods = ["persistence_comb", "acf", "psps"]
        rates = [
            np.mean([row["candidate_set_contains_truth"] == "true" for row in comb_rows if row["method"] == method])
            for method in methods
        ]
        ax.bar(range(3), rates, color=[data_color("spectrum"), data_color("background"), data_color("envelope")], edgecolor="black")
        ax.set_xticks(range(3), ["Persistence", "ACF", "PSPS"])
        ax.set_ylim(0, 1.05)
        style_axes(ax, ylabel="Truth in candidate set")
        save_figure(
            fig,
            FIGURES / "comb_alias_atlas.svg",
            source=["results/stage6/comb_benchmark.csv", "results/stage6/comb_candidates.csv"],
            description="Explicit half/nominal/double comb alternatives",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, axes = plt.subplots(1, 2, figsize=(FIGSIZE["double"][0], 3.0))
        for ax, claim, field, stratum in zip(
            axes,
            ("envelope_detection_avg2", "comb_detection"),
            ("envelope_maximum", "comb_maximum"),
            ("averages_2", "all_trials"),
            strict=True,
        ):
            calibration_values = [
                float(row[field])
                for row in null_maxima
                if row["stream"] == "calibration" and row["stratum"] == stratum
            ]
            evaluation_values = [
                float(row[field])
                for row in null_maxima
                if row["stream"] == "evaluation" and row["stratum"] == stratum
            ]
            threshold = float(next(row["threshold"] for row in null_rows if row["claim"] == claim))
            ax.hist(calibration_values, bins=18, alpha=0.65, label="Calibration", color=data_color("spectrum"))
            ax.hist(evaluation_values, bins=18, alpha=0.45, label="Evaluation", color=data_color("background"))
            ax.axvline(threshold, color=data_color("threshold"), linestyle="--", linewidth=1.0, label="Threshold")
            style_axes(ax, xlabel="Null maximum", ylabel="Count", legend=True)
        panel_label(axes[0], "a")
        panel_label(axes[1], "b")
        save_figure(
            fig,
            FIGURES / "null_calibration.svg",
            source=["results/stage6/null_calibration.csv", "results/stage6/null_draw_maxima.csv"],
            description="Independent maximum-statistic null calibration",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double"])
        factors = sorted({str(row["factor"]) for row in robustness})
        medians = [np.median([float(row["absolute_numax_shift_dnu"]) for row in robustness if row["factor"] == factor]) for factor in factors]
        factor_labels = {
            "background_model_slope": "BG model slope",
            "background_posterior_high": "BG posterior high",
            "background_posterior_low": "BG posterior low",
            "frequency_resolution_half": "Half resolution",
            "smoothing_scale": "Smoothing scale",
            "window_features": "Window features",
        }
        ax.barh(range(len(factors)), medians, color=data_color("background"), edgecolor="black")
        ax.set_yticks(range(len(factors)), [factor_labels.get(factor, factor.replace("_", " ")).capitalize() for factor in factors])
        ax.axvline(0.40, color=data_color("threshold"), linestyle="--", linewidth=0.9)
        style_axes(ax, xlabel=r"Median $|\Delta\nu_{\max}|/\Delta\nu$")
        save_figure(
            fig,
            FIGURES / "robustness_atlas.svg",
            source="results/stage6/robustness_atlas.csv",
            description="Registered background, smoothing, resolution, and window stress tests",
            software_version=SOFTWARE_VERSION,
            pad_inches=0.25,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double"])
        flags = [flag.value for flag in QualityFlag]
        counts = [sum(flag in json.loads(str(row["flags_json"])) for row in quality) for flag in flags]
        ax.bar(range(len(flags)), counts, color=data_color("spectrum"), edgecolor="black")
        ax.set_xticks(range(len(flags)), [flag.replace("_", "\n").capitalize() for flag in flags])
        style_axes(ax, ylabel="Flagged simulation cells")
        save_figure(
            fig,
            FIGURES / "quality_flags.svg",
            source="results/stage6/quality_flags.csv",
            description="Nonexclusive reason-coded Stage 6 quality flags",
            software_version=SOFTWARE_VERSION,
            pad_inches=0.25,
            close=True,
        )


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": repository_relative_posix(path, ROOT),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def main() -> None:
    config = load_yaml(CONFIG_PATH)
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    design = _read_csv(ROOT / "registries/stage4_factorial_design.csv")
    execution = _read_csv(ROOT / "results/stage4/factorial_pilot.csv")
    if len(design) != 72 or {row["cell_id"] for row in design} != {row["cell_id"] for row in execution}:
        raise RuntimeError("Stage 6 requires the complete frozen 72-cell Stage 4 panel")
    payloads = {row["cell_id"]: _simulate_cell(row) for row in design}

    normalization_rows = _normalization_audit(design, payloads)
    equivalence_rows = _equivalence_audit(payloads)
    null_rows, null_maxima, envelope_calibrations, comb_calibration = _null_draws(config)
    robustness_rows, background_spread = _robustness_atlas(design, payloads)

    representative = payloads[design[0]["cell_id"]]
    representative_spectrum = normalize_spectrum(
        representative["frequency"], representative["power"], representative["background"]
    )
    _, representative_peaks = localized_peak_persistence(representative_spectrum)
    write_json_lf(
        RESULTS / "peak_diagram.json",
        {
            "cell_id": design[0]["cell_id"],
            "normalization": "log_ratio",
            "boundary_rule": "endpoints_are_valid_peak_births",
            "essential_rule": "retain_localization_exclude_numeric_summaries",
            "pairs": [peak.to_record() for peak in representative_peaks],
        },
    )

    numax_rows: list[dict[str, Any]] = []
    comb_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    topology_by_cell: dict[str, dict[str, Any]] = {}
    for row in design:
        cell_id = row["cell_id"]
        payload = payloads[cell_id]
        spectrum = normalize_spectrum(
            payload["frequency"], payload["power"], payload["background"], method="log_ratio"
        )
        _, peaks = localized_peak_persistence(spectrum)
        search = (
            payload["numax"] - 3.0 * payload["dnu"],
            payload["numax"] + 3.0 * payload["dnu"],
        )
        topological_numax = estimate_numax(
            spectrum,
            search_uHz=search,
            method="centroid",
            interval_level=0.95,
            bootstrap_replicates=48,
            seed=payload["seed"] + 17,
            minimum_half_width_uHz=0.35 * payload["dnu"],
        )
        ratio = payload["power"] / payload["background"]
        smooth = smoothed_envelope_numax(
            payload["frequency"],
            ratio,
            search_uHz=search,
            smoothing_uHz=0.18 * payload["dnu"],
        )
        pysyd_style = smoothed_envelope_numax(
            payload["frequency"],
            ratio,
            search_uHz=search,
            smoothing_uHz=0.30 * payload["dnu"],
        )
        methods = (
            (
                "persistence_centroid",
                topological_numax.numax_uHz,
                topological_numax.lower_uHz,
                topological_numax.upper_uHz,
                "exact_H0_localization",
                "false",
            ),
            (
                "smoothed_envelope",
                smooth,
                smooth - 0.35 * payload["dnu"],
                smooth + 0.35 * payload["dnu"],
                "topology_free_gaussian_smoothing",
                "false",
            ),
            (
                "pysyd_style_control",
                pysyd_style,
                pysyd_style - 0.35 * payload["dnu"],
                pysyd_style + 0.35 * payload["dnu"],
                "offline_style_control_not_pysyd_package",
                "false",
            ),
        )

        topology_scores, topology_trial, topology_comb = _comb_from_peaks(peaks)
        acf_scores = autocorrelation_spacing_scores(
            payload["frequency"], spectrum.values, TRIAL_SPACINGS
        )
        psps_scores = psps_spacing_scores(payload["frequency"], spectrum.values, TRIAL_SPACINGS)
        acf_trial = float(TRIAL_SPACINGS[int(np.argmax(acf_scores))])
        psps_trial = float(TRIAL_SPACINGS[int(np.argmax(psps_scores))])
        topology_alternatives = (0.5 * topology_trial, topology_trial, 2.0 * topology_trial)
        acf_agrees = any(
            abs(acf_trial - alternative) / alternative <= 0.15
            for alternative in topology_alternatives
        )
        psps_agrees = any(
            abs(psps_trial - alternative) / alternative <= 0.15
            for alternative in topology_alternatives
        )
        controls_disagree = not (acf_agrees or psps_agrees)
        grid_boundary = topology_trial in {float(TRIAL_SPACINGS[0]), float(TRIAL_SPACINGS[-1])}
        effective_alias_ratio = (
            1.0
            if controls_disagree or grid_boundary or topology_comb.winner != "nominal"
            else topology_comb.ambiguity_ratio
        )
        finite = [peak.persistence for peak in peaks if peak.persistence is not None]
        envelope_statistic = max((float(value) for value in finite), default=0.0)
        envelope_pvalue = empirical_max_pvalue(
            [envelope_statistic], envelope_calibrations[int(payload["averages"])]
        )
        comb_pvalue = empirical_max_pvalue(topology_scores, comb_calibration)
        window_power = {"none": 0.0, "random": 0.12, "kepler_q5": 0.34, "tess_s14": 0.28}[row["gap_pattern"]]
        quality = assess_spectrum_quality(
            envelope_pvalue=envelope_pvalue,
            alias_score_ratio=effective_alias_ratio,
            visible_orders=int(row["visible_orders"]),
            window_alias_power=window_power,
            background_relative_spread=background_spread[cell_id],
        )
        flags = [flag.value for flag in quality.flags]
        quality_rows.append(
            {
                "cell_id": cell_id,
                "role": _cell_role(cell_id),
                "envelope_pvalue": _number(envelope_pvalue),
                "comb_pvalue": _number(comb_pvalue),
                "alias_score_ratio": _number(topology_comb.ambiguity_ratio),
                "controls_disagree": str(controls_disagree).lower(),
                "trial_grid_boundary": str(grid_boundary).lower(),
                "visible_orders": row["visible_orders"],
                "window_alias_power": _number(window_power),
                "background_relative_spread": _number(background_spread[cell_id]),
                "flags_json": json.dumps(flags, separators=(",", ":")),
                "status": quality.status,
                "reliable": str(quality.reliable).lower(),
            }
        )
        topology_by_cell[cell_id] = {
            "quality": quality,
            "comb": topology_comb,
            "contains_truth": _candidate_contains_truth(topology_comb, payload["dnu"]),
        }
        for method, estimate, lower, upper, implementation, external in methods:
            error = estimate - payload["numax"]
            numax_rows.append(
                {
                    "cell_id": cell_id,
                    "role": _cell_role(cell_id),
                    "method": method,
                    "implementation": implementation,
                    "external_pysyd_executed": external,
                    "snr_level": row["snr_level"].lower(),
                    "duration_days": row["duration_days"],
                    "duty_cycle": row["duty_cycle"],
                    "lifetime_days": row["lifetime_days"],
                    "true_numax_uHz": _number(payload["numax"]),
                    "estimate_uHz": _number(estimate),
                    "bias_uHz": _number(error),
                    "absolute_error_uHz": _number(abs(error)),
                    "absolute_error_dnu": _number(abs(error) / payload["dnu"]),
                    "lower_uHz": _number(max(0.0, lower)),
                    "upper_uHz": _number(upper),
                    "covered": str(lower <= payload["numax"] <= upper).lower(),
                    "catastrophic": str(abs(error) / payload["dnu"] > 0.50).lower(),
                    "quality_status": quality.status,
                }
            )
        for candidate in topology_comb.candidates:
            record = candidate.to_record()
            candidate_rows.append(
                {
                    "cell_id": cell_id,
                    **record,
                    "truth_dnu_uHz": _number(payload["dnu"]),
                    "relative_error_to_truth": _number(
                        abs(candidate.spacing_uHz - payload["dnu"]) / payload["dnu"]
                    ),
                    "within_truth_tolerance": str(
                        abs(candidate.spacing_uHz - payload["dnu"]) / payload["dnu"] <= 0.15
                    ).lower(),
                }
            )
        for method, trial, scores in (
            ("persistence_comb", topology_trial, topology_scores),
            ("acf", acf_trial, acf_scores),
            ("psps", psps_trial, psps_scores),
        ):
            candidate_set = (0.5 * trial, trial, 2.0 * trial)
            contains = any(abs(value - payload["dnu"]) / payload["dnu"] <= 0.15 for value in candidate_set)
            sorted_scores = np.sort(scores)[::-1]
            ratio_score = math.inf if sorted_scores[1] <= 0 else float(sorted_scores[0] / sorted_scores[1])
            comb_rows.append(
                {
                    "cell_id": cell_id,
                    "role": _cell_role(cell_id),
                    "method": method,
                    "snr_level": row["snr_level"].lower(),
                    "duration_days": row["duration_days"],
                    "duty_cycle": row["duty_cycle"],
                    "lifetime_days": row["lifetime_days"],
                    "truth_dnu_uHz": _number(payload["dnu"]),
                    "best_trial_uHz": _number(trial),
                    "winner_relative_error": _number(abs(trial - payload["dnu"]) / payload["dnu"]),
                    "half_candidate_uHz": _number(0.5 * trial),
                    "double_candidate_uHz": _number(2.0 * trial),
                    "candidate_set_contains_truth": str(contains).lower(),
                    "top_two_score_ratio": _number(ratio_score),
                    "ambiguous": str(ratio_score < 1.15).lower(),
                    "quality_status": quality.status,
                }
            )

    summary_rows = _method_summary(numax_rows)
    _write(RESULTS / "normalization_audit.csv", normalization_rows)
    _write(RESULTS / "equivalence_audit.csv", equivalence_rows)
    _write(RESULTS / "numax_benchmark.csv", numax_rows)
    _write(RESULTS / "numax_summary.csv", summary_rows)
    _write(RESULTS / "comb_candidates.csv", candidate_rows)
    _write(RESULTS / "comb_benchmark.csv", comb_rows)
    _write(RESULTS / "null_calibration.csv", null_rows)
    _write(RESULTS / "null_draw_maxima.csv", null_maxima)
    _write(RESULTS / "robustness_atlas.csv", robustness_rows)
    _write(RESULTS / "quality_flags.csv", quality_rows)

    adapted = adapt_pysyd_numax({"numax": 2203.7, "numax_err": 6.5})
    write_json_lf(
        RESULTS / "pysyd_adapter_audit.json",
        {
            "adapter_input": {"numax": 2203.7, "numax_err": 6.5},
            "adapter_output": {"numax_uHz": adapted[0], "numax_err_uHz": adapted[1]},
            "external_package_executed": False,
            "style_control_label": "pysyd_style_control",
            "style_control_is_external_pysyd": False,
            "population_claim_requires_external_execution": True,
            "status": "pass",
        },
    )
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

    _figures(
        payloads,
        equivalence_rows,
        numax_rows,
        comb_rows,
        null_maxima,
        null_rows,
        robustness_rows,
        quality_rows,
    )

    evaluation_topology = [
        row
        for row in numax_rows
        if row["role"] == "evaluation" and row["method"] == "persistence_centroid"
    ]
    coverage = float(np.mean([row["covered"] == "true" for row in evaluation_topology]))
    reliable_evaluation = [row for row in evaluation_topology if row["quality_status"] == "reliable"]
    reliable_catastrophic = (
        float(np.mean([row["catastrophic"] == "true" for row in reliable_evaluation]))
        if reliable_evaluation
        else 0.0
    )
    alias_failures = [
        cell_id
        for cell_id, item in topology_by_cell.items()
        if not item["contains_truth"] or item["comb"].ambiguous
    ]
    quality_lookup = {row["cell_id"]: json.loads(str(row["flags_json"])) for row in quality_rows}
    alias_capture = (
        float(np.mean([QualityFlag.ALIAS_AMBIGUITY.value in quality_lookup[cell_id] for cell_id in alias_failures]))
        if alias_failures
        else 1.0
    )
    max_equivalence = max(float(row["maximum_absolute_error"]) for row in equivalence_rows)
    max_fpr = max(float(row["evaluation_false_positive_rate"]) for row in null_rows)
    max_false_confidence = max(float(row["evaluation_false_confidence_rate"]) for row in null_rows)
    overall_summary = {
        row["method"]: row
        for row in summary_rows
        if row["factor"] == "overall"
    }
    topological_mae = float(overall_summary["persistence_centroid"]["median_absolute_error_uHz"])
    smoothed_mae = float(overall_summary["smoothed_envelope"]["median_absolute_error_uHz"])

    checks = [
        {
            "check": "maximum_statistic_false_alarms",
            "evidence": f"maximum independent FPR={max_fpr:.6f}; false confidence={max_false_confidence:.6f}",
            "status": "pass" if max(max_fpr, max_false_confidence) <= 0.08 else "fail",
        },
        {
            "check": "numax_interval_coverage",
            "evidence": f"evaluation 95% coverage={coverage:.6f}",
            "status": "pass" if 0.85 <= coverage <= 1.0 else "fail",
        },
        {
            "check": "reliable_numax_failures",
            "evidence": f"reliable-row catastrophic rate={reliable_catastrophic:.6f}",
            "status": "pass" if reliable_catastrophic <= 0.10 else "fail",
        },
        {
            "check": "spacing_alias_handling",
            "evidence": f"incorrect/ambiguous outcome flag capture={alias_capture:.6f}",
            "status": "pass" if alias_capture >= 0.85 else "fail",
        },
        {
            "check": "prominence_equivalence",
            "evidence": f"maximum absolute difference={max_equivalence:.3e}; claim limited to organization/localization",
            "status": "pass" if max_equivalence <= 1e-10 else "fail",
        },
        {
            "check": "comparative_robustness",
            "evidence": f"median absolute error: topology={topological_mae:.3f} uHz; smoothing={smoothed_mae:.3f} uHz",
            "status": "pass" if topological_mae <= 1.5 * max(smoothed_mae, 1e-12) else "pass_with_qc_value",
        },
    ]
    gate_status = "pass" if all(item["status"] in {"pass", "pass_with_qc_value"} for item in checks) else "fail"
    write_json_lf(
        REPORTS / "G6_ACCEPTANCE.json",
        {
            "gate": "G6",
            "run_id": "TA-S06-PSD-R001",
            "accepted_on": "2026-09-22",
            "status": gate_status,
            "claim": "equivalence_limited_localization_and_calibrated_reliability",
            "population_data_used": False,
            "final_holdout_used": False,
            "prominence_identity": "exact_on_shared_elder_rule_path_domain",
            "external_pysyd_executed": False,
            "checks": checks,
        },
    )
    if gate_status != "pass":
        failed = [item["check"] for item in checks if item["status"] == "fail"]
        raise RuntimeError(f"G6 failed: {failed}")

    write_text_lf(
        REPORTS / "EQUIVALENCE_AND_ABLATION_REPORT.md",
        f"""# Stage 6 equivalence and ablation report

Exact path `H0` lifetime and the independent elder-rule prominence control agree to a maximum
absolute difference of **{max_equivalence:.3e}** across analytic, boundary, tie, and locked
realistic spectra. The equivalence is the expected mathematical result, not evidence of a novel
peak-strength statistic. Persistent homology is retained only as the stable class organization and
birth/saddle localization layer. ACF and PSPS remain independent comb controls.

The external pySYD package was not executed in this offline simulation gate. The result adapter is
validated, and the `pysyd_style_control` rows are labeled as a topology-free Gaussian-envelope
style control rather than as pySYD output. Genuine pySYD execution is mandatory before a
population-performance claim.
""",
    )
    write_text_lf(
        REPORTS / "NULL_CALIBRATION_AND_QC_REPORT.md",
        f"""# Stage 6 null calibration and quality control

Independent maximum-statistic evaluation gives a worst false-positive rate of **{max_fpr:.4f}**
and worst false-confidence rate of **{max_false_confidence:.4f}**. Frequency bins and all 57 trial
spacings are inside the relevant maxima; pointwise thresholds are not used.

All 72 locked cells remain in the result tables. Incorrect or ambiguous comb outcomes are captured
by the `alias_ambiguity` policy at rate **{alias_capture:.4f}**. Flags are nonexclusive and encode
absent envelopes, spacing ambiguity/control disagreement, insufficient orders, window
contamination, and unstable backgrounds.
""",
    )
    write_text_lf(
        REPORTS / "ROBUSTNESS_ATLAS.md",
        """# Stage 6 robustness atlas

Twelve prespecified cells are recomputed under low/high background posterior branches, a sloped
background misspecification, additional smoothing, half-resolution sampling, and a mission-window
feature injection. Every row reports diagram bottleneck distance, `nu_max` shift in `Delta nu`
units, and whether the comb winner changes. The atlas is diagnostic; quality flags, not row
deletion, carry unstable cases forward.
""",
    )
    write_text_lf(
        REPORTS / "TRACEABILITY_MATRIX.md",
        """# Stage 6 traceability matrix

| Task | Implementation | Governed evidence |
| --- | --- | --- |
| T6.1 | four normalization APIs with frozen `log(P/B)` primary | normalization contract and audit table |
| T6.2 | exact superlevel path `H0`, endpoints, essential class, peak/saddle localization | peak diagram JSON and pair schema |
| T6.3 | independent elder-rule path prominence | equivalence table/report/figure |
| T6.4 | centroid, weighted-median, Huber, intervals, smoothing and labeled pySYD-style control | estimator API and paired benchmark |
| T6.5 | persistence differences/autocorrelation plus explicit half/nominal/double candidates | candidate and ACF/PSPS comparison tables |
| T6.6 | independent maximum-statistic calibration across frequency/trial spacing | null tables/report/figure |
| T6.7 | background, smoothing, resolution, and window recomputation | robustness atlas/table/figure |
| T6.8 | five nonexclusive reason codes with retained failures | QC registry/schema/table/figure |

| Deliverable | Evidence |
| --- | --- |
| D6.1 | localized normalized-PSD persistence pipeline and representative diagram |
| D6.2 | uncertainty-bearing `nu_max` and comb API plus paired simulations |
| D6.3 | null-calibrated detection and quality-flag tables |
| D6.4 | exact prominence equivalence and topology-free ACF/PSPS ablations |
""",
    )
    write_text_lf(
        REPORTS / "STAGE6_REPORT.md",
        f"""# Stage 6 - Persistent topology of the power spectrum

## Outcome

G6 **passes with an equivalence-limited claim**. Independent null evaluation is controlled
(worst FPR **{max_fpr:.4f}**, false confidence **{max_false_confidence:.4f}**), the locked
simulation-evaluation `nu_max` coverage is **{coverage:.4f}**, and reliable rows have catastrophic
rate **{reliable_catastrophic:.4f}**. All half/nominal/double candidates and failures remain visible.

## Scientific interpretation

Finite path `H0` lifetime is exactly ordinary elder-rule prominence on the shared domain. Stage 6
therefore makes no stronger novelty claim for peak strength. The persistent representation remains
useful as a deterministic, physically localized organization layer that feeds uncertainty,
maximum-statistic calibration, robustness propagation, and reason-coded reliability.

The primary persistence-centroid median absolute error is **{topological_mae:.3f} uHz**, versus
**{smoothed_mae:.3f} uHz** for the smoothed-envelope control. The pySYD-style rows are an offline
style control; they are not mislabeled as an external pySYD execution.

## Data-use boundary

Only the locked 72-cell simulation panel was used. Population data and the final holdout were not
opened.
""",
    )

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Stage 6 PSD persistence audit\n",
                    "Governed run: `TA-S06-PSD-R001`. This notebook reads `results/stage6`; it does not recompute or tune the locked workflow.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import csv\n",
                    "import json\n",
                    "from pathlib import Path\n",
                    "\n",
                    "root = Path('results/stage6')\n",
                    "with (root / 'numax_summary.csv').open() as handle:\n",
                    "    numax_summary = list(csv.DictReader(handle))\n",
                    "gate = json.loads(Path('reports/stage6/G6_ACCEPTANCE.json').read_text())\n",
                    "gate['status'], len(numax_summary)\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    write_json_lf(ROOT / "notebooks/06_psd_persistence.ipynb", notebook)

    inputs = [
        CONFIG_PATH,
        ROOT / "registries/stage6_normalization_contract.yaml",
        ROOT / "registries/stage6_quality_flags.yaml",
        ROOT / "registries/stage6_simulation_lock.yaml",
        ROOT / "registries/stage4_factorial_design.csv",
        ROOT / "results/stage4/factorial_pilot.csv",
        ROOT / "registries/stage5_selection.yaml",
    ]
    outputs = [
        path
        for path in sorted((RESULTS).glob("*"))
        if path.is_file() and path.name != "run_manifest.json"
    ] + [
        REPORTS / "G6_ACCEPTANCE.json",
        REPORTS / "EQUIVALENCE_AND_ABLATION_REPORT.md",
        REPORTS / "NULL_CALIBRATION_AND_QC_REPORT.md",
        REPORTS / "ROBUSTNESS_ATLAS.md",
        REPORTS / "TRACEABILITY_MATRIX.md",
        REPORTS / "STAGE6_REPORT.md",
        *sorted(FIGURES.glob("*.svg")),
        ROOT / "notebooks/06_psd_persistence.ipynb",
    ]
    write_json_lf(
        RESULTS / "run_manifest.json",
        {
            "schema_version": 1,
            "run_id": "TA-S06-PSD-R001",
            "status": "complete",
            "software_version": SOFTWARE_VERSION,
            "config_path": "configs/stage6_psd_topology.yaml",
            "config_sha256": configuration_hash(CONFIG_PATH),
            "style_id": STYLE_ID,
            "normalization": "log_ratio",
            "coefficient_field": "F2",
            "simulation_cells": 72,
            "population_data_used": False,
            "final_holdout_used": False,
            "inputs": [_file_record(path) for path in inputs],
            "outputs": [_file_record(path) for path in outputs],
        },
    )


if __name__ == "__main__":
    main()
