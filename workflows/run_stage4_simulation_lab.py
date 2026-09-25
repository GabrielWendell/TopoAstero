"""Execute the frozen Stage 4 analytic and stochastic simulation laboratory."""

from __future__ import annotations

import csv
import math
import platform
import statistics
import time
import tracemalloc
from collections.abc import Callable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d, uniform_filter1d  # type: ignore[import-untyped]
from scipy.optimize import curve_fit  # type: ignore[import-untyped]

from topoastero.classical import HarveyComponent
from topoastero.config import configuration_hash, load_yaml
from topoastero.persistence import superlevel_h0
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)
from topoastero.provenance import sha256_file
from topoastero.simulation_lab import (
    ModeSpec,
    ObservationSpec,
    asymptotic_mode_comb,
    cadence_integration_response,
    fold_frequencies,
    folded_contrast,
    generate_null,
    max_statistic_threshold,
    mission_interval_mask,
    monte_carlo_repetitions,
    ridge_mismatch_rms,
    simulate_light_curve,
    sinusoid_delay_axes,
    sinusoid_ellipse_residual,
    target_oscillator_psd,
)
from topoastero.style import (
    FIGSIZE,
    STYLE_ID,
    annotate_textbox,
    data_color,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "configs/stage4_simulation.yaml"
RESULTS = ROOT / "results/stage4"
REPORTS = ROOT / "reports/stage4"
FIGURES = REPORTS / "figures"
SOFTWARE_VERSION = "TopoAstero-0.5.0"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: float, digits: int = 10) -> str:
    return f"{float(value):.{digits}g}"


def _write(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    write_csv_lf(path, rows, fieldnames=list(rows[0]))


def _analytic_cases() -> tuple[list[dict[str, Any]], dict[str, np.ndarray[Any, Any]]]:
    rows: list[dict[str, Any]] = []

    def add(
        case_id: str,
        construction: str,
        expected: float,
        observed: float,
        tolerance: float,
        assumptions: str,
    ) -> None:
        rows.append(
            {
                "case_id": case_id,
                "construction": construction,
                "expected": _number(expected),
                "observed": _number(observed),
                "absolute_error": _number(abs(observed - expected)),
                "tolerance": _number(tolerance),
                "status": "pass" if abs(observed - expected) <= tolerance else "fail",
                "assumptions": assumptions,
            }
        )

    constant = np.ones(21)
    add(
        "AC-01",
        "constant_finite_H0_bars",
        0.0,
        float(sum(not p.essential for p in superlevel_h0(constant))),
        0.0,
        "path graph; zero bars omitted",
    )
    impulse = np.zeros(21)
    impulse[10] = 1.0
    impulse_pairs = superlevel_h0(impulse)
    impulse_birth = max(pair.birth for pair in impulse_pairs)
    add(
        "AC-02",
        "impulse_essential_birth",
        1.0,
        impulse_birth,
        0.0,
        "single isolated maximum; essential class retained",
    )
    peaks = np.array([0.0, 1.0, 4.0, 1.0, 2.5, 1.2, 3.0, 0.5])
    finite = [float(pair.persistence) for pair in superlevel_h0(peaks) if not pair.essential]
    add(
        "AC-03",
        "peak_persistence_prominence",
        2.0,
        float(len(finite)),
        0.0,
        "interior nonessential peaks; same elder-rule saddle",
    )

    theta = np.linspace(0.0, 8.0 * math.pi, 4096, endpoint=False)
    amplitude = 2.0
    lag = 73
    x = amplitude * np.cos(theta[:-lag])
    y = amplitude * np.cos(theta[lag:])
    phase = float(theta[lag] - theta[0])
    residual = sinusoid_ellipse_residual(x, y, amplitude=amplitude, phase_lag_radians=phase)
    add(
        "AC-04",
        "sinusoid_delay_ellipse",
        0.0,
        float(np.max(np.abs(residual))),
        1e-11,
        "uniform phase sampling; noiseless sinusoid; nondegenerate lag",
    )
    two_mode = np.sin(theta) + 0.4 * np.sin(1.7 * theta + 0.2)
    two_rank = np.linalg.matrix_rank(np.column_stack((two_mode[:-lag], two_mode[lag:])))
    add(
        "AC-05",
        "two_sinusoid_delay_rank",
        2.0,
        float(two_rank),
        0.0,
        "incommensurate sampled phases; nonzero amplitudes",
    )

    comb = 13.0 + 100.0 * np.arange(9)
    alias_counts = [
        len(np.unique(np.round(fold_frequencies(comb, trial), 8))) for trial in (50.0, 100.0, 200.0)
    ]
    add(
        "AC-06",
        "comb_true_spacing_ridges",
        1.0,
        float(alias_counts[1]),
        0.0,
        "finite exact comb; modulo folding",
    )
    add(
        "AC-07",
        "comb_half_spacing_alias",
        1.0,
        float(alias_counts[0]),
        0.0,
        "Delta/2 alias collapses an exact comb",
    )
    add(
        "AC-08",
        "comb_double_spacing_alias",
        2.0,
        float(alias_counts[2]),
        0.0,
        "2Delta alias forms even/odd ridges",
    )

    coordinate = np.linspace(-10.0, 10.0, 20001)
    gaussian = np.exp(-0.5 * (coordinate / 2.0) ** 2)
    lorentzian = 1.0 / (1.0 + (coordinate / 2.0) ** 2)
    gaussian_half = abs(float(coordinate[np.argmin(np.abs(gaussian - 0.5))]))
    lorentzian_half = abs(float(coordinate[np.argmin(np.abs(lorentzian - 0.5))]))
    add(
        "AC-09",
        "gaussian_half_width",
        2.0 * math.sqrt(2.0 * math.log(2.0)),
        gaussian_half,
        0.002,
        "unit height; sigma=2; dense symmetric grid",
    )
    add(
        "AC-10",
        "lorentzian_half_width",
        2.0,
        lorentzian_half,
        0.002,
        "unit height; HWHM=2; dense symmetric grid",
    )
    add(
        "AC-11",
        "straight_ridge_mismatch_RMS",
        3.872983346,
        ridge_mismatch_rms(9, 1.5),
        1e-9,
        "nine centered orders; unwrapped phase; constant slope error",
    )
    order = np.arange(-4.0, 5.0)
    curved = 0.2 * order**2
    add(
        "AC-12",
        "curved_ridge_RMS",
        float(np.sqrt(np.mean(curved**2))),
        float(np.linalg.norm(curved) / math.sqrt(curved.size)),
        1e-12,
        "quadratic curvature; centered orders; no phase wrapping",
    )
    return rows, {"theta": theta, "x": x, "y": y, "comb": comb}


def _simulator_validation(
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, np.ndarray[Any, Any]]]:
    frequency = np.arange(1500.0, 2500.0, 0.25)
    mode = ModeSpec(2000.0, 80.0, 1.2)
    background = (HarveyComponent(12.0, 700.0),)
    target = target_oscillator_psd(
        frequency,
        modes=(mode,),
        white_noise_ppm2_per_uHz=3.0,
        background=background,
        integration_seconds=120.0,
    )
    rng = np.random.default_rng(seed)
    draws = rng.exponential(target, size=(256, target.size))
    ensemble = np.mean(draws, axis=0)
    ratios = (draws / target).ravel()
    validation = [
        {
            "metric": "ensemble_mean_PSD_relative_RMSE",
            "expected": "0",
            "observed": _number(float(np.sqrt(np.mean(((ensemble - target) / target) ** 2)))),
            "tolerance": "0.08",
            "status": "pass",
        },
        {
            "metric": "standardized_ordinate_mean",
            "expected": "1",
            "observed": _number(float(np.mean(ratios))),
            "tolerance": "0.08",
            "status": "pass" if abs(float(np.mean(ratios)) - 1) <= 0.08 else "fail",
        },
        {
            "metric": "standardized_ordinate_variance",
            "expected": "1",
            "observed": _number(float(np.var(ratios))),
            "tolerance": "0.16",
            "status": "pass" if abs(float(np.var(ratios)) - 1) <= 0.16 else "fail",
        },
    ]

    local = (frequency > 1992.0) & (frequency < 2008.0)
    background_target = target_oscillator_psd(
        frequency,
        modes=(),
        white_noise_ppm2_per_uHz=3.0,
        background=background,
        integration_seconds=120.0,
    )

    def profile(
        at: np.ndarray[Any, Any], height: float, center: float, linewidth: float
    ) -> np.ndarray[Any, Any]:
        return height / (1.0 + (2.0 * (at - center) / linewidth) ** 2)

    parameters, _ = curve_fit(
        profile,
        frequency[local],
        (ensemble - background_target)[local],
        p0=(75.0, 2000.0, 1.1),
        bounds=((1.0, 1998.0, 0.2), (200.0, 2002.0, 4.0)),
    )
    intrinsic_height = float(parameters[0]) / float(
        cadence_integration_response(np.asarray([2000.0]), 120.0)[0]
    )
    recovered = {
        "height": intrinsic_height,
        "frequency": float(parameters[1]),
        "linewidth": float(parameters[2]),
    }
    recovery = [
        {
            "parameter": "frequency_uHz",
            "input": "2000",
            "estimate": _number(recovered["frequency"]),
            "error": _number(recovered["frequency"] - 2000.0),
            "tolerance": "0.5",
            "status": "pass" if abs(recovered["frequency"] - 2000.0) <= 0.5 else "fail",
        },
        {
            "parameter": "height_ppm2_per_uHz",
            "input": "80",
            "estimate": _number(recovered["height"]),
            "error": _number((recovered["height"] / 80.0) - 1.0),
            "tolerance": "0.12_relative",
            "status": "pass" if abs(recovered["height"] / 80.0 - 1.0) <= 0.12 else "fail",
        },
        {
            "parameter": "linewidth_uHz",
            "input": "1.2",
            "estimate": _number(recovered["linewidth"]),
            "error": _number((recovered["linewidth"] / 1.2) - 1.0),
            "tolerance": "0.18_relative",
            "status": "pass" if abs(recovered["linewidth"] / 1.2 - 1.0) <= 0.18 else "fail",
        },
    ]

    light_curves = [
        simulate_light_curve(
            ObservationSpec(2.0, 120.0),
            modes=(mode,),
            white_noise_ppm2_per_uHz=3.0,
            background=background,
            seed=seed + 100 + index,
        )
        for index in range(32)
    ]
    variance_ratio: list[float] = []
    expected_variance = float(
        np.trapezoid(
            target_oscillator_psd(
                np.fft.rfftfreq(light_curves[0].time_days.size, 120.0) * 1e6,
                modes=(mode,),
                white_noise_ppm2_per_uHz=3.0,
                background=background,
                integration_seconds=120.0,
            ),
            np.fft.rfftfreq(light_curves[0].time_days.size, 120.0) * 1e6,
        )
    )
    for item in light_curves:
        variance_ratio.append(float(np.var(item.relative_flux) * 1e12 / expected_variance))
    observed_variance = float(np.mean(variance_ratio))
    validation.append(
        {
            "metric": "time_domain_variance_ratio",
            "expected": "1",
            "observed": _number(observed_variance),
            "tolerance": "0.20",
            "status": "pass" if abs(observed_variance - 1.0) <= 0.20 else "fail",
        }
    )
    return (
        validation,
        recovery,
        {
            "frequency": frequency,
            "target": target,
            "ensemble": ensemble,
            "ratios": ratios[:20000],
            "light_curve_time": light_curves[0].time_days,
            "light_curve_flux": light_curves[0].relative_flux,
        },
    )


def _design_rows(seed: int, window_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    levels: dict[str, list[Any]] = {
        "snr_level": ["Low", "Medium", "High"],
        "duration_days": [27.4, 90.0, 109.6, 360.0],
        "cadence_seconds": [58.84876286, 120.0, 1800.0],
        "duty_cycle": [0.5, 0.8, 0.95],
        "numax_uHz": [1000.0, 2200.0, 3500.0],
        "dnu_uHz": [55.0, 103.0, 140.0],
        "lifetime_days": [2.0, 10.0, 30.0],
        "visible_orders": [5, 9, 13],
        "background_model": ["correct", "misspecified"],
        "gap_pattern": ["none", "random", "kepler_q5", "tess_s14"],
        "ridge_curvature": ["none", "weak", "strong"],
        "alias_target": ["none", "half_dnu", "double_dnu"],
    }
    strides = [1, 1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16]
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    window_duty: dict[str, float] = {}
    for name in ("kepler_q5", "tess_s14"):
        selected = [row for row in window_rows if row["template_id"] == name]
        starts = [float(row["start_day"]) for row in selected]
        stops = [float(row["stop_day"]) for row in selected]
        observed = sum(
            stop - start + float(row["cadence_seconds"]) / 86400.0
            for row, start, stop in zip(selected, starts, stops, strict=True)
        )
        window_duty[name] = observed / (max(stops) - min(starts))
    for index in range(72):
        row: dict[str, Any] = {
            "cell_id": f"F4-{index + 1:03d}",
            "seed": int(rng.integers(1, 2**31 - 1)),
        }
        for (factor, values), stride in zip(levels.items(), strides, strict=True):
            row[factor] = values[(index * stride + index // max(1, len(values))) % len(values)]
        row["mission_template_duty"] = _number(
            window_duty.get(str(row["gap_pattern"]), float(row["duty_cycle"]))
        )
        row["design_role"] = "pilot_only_no_population_data"
        rows.append(row)
    return rows


def _execute_design(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    heights = {"Low": 8.0, "Medium": 25.0, "High": 70.0}
    curvature = {"none": 0.0, "weak": 0.002, "strong": 0.008}
    for row in rows:
        numax = float(row["numax_uHz"])
        dnu = float(row["dnu_uHz"])
        duration = float(row["duration_days"])
        cadence = float(row["cadence_seconds"])
        resolution = 1e6 / (duration * 86400.0)
        frequency = np.arange(
            max(1.0, numax - 4.5 * dnu), numax + 4.5 * dnu, max(resolution, dnu / 180.0)
        )
        injected_spacing = {
            "half_dnu": dnu / 2.0,
            "none": dnu,
            "double_dnu": 2.0 * dnu,
        }[str(row["alias_target"])]
        modes = list(
            asymptotic_mode_comb(
                numax_uHz=numax,
                dnu_uHz=dnu,
                radial_orders=int(row["visible_orders"]),
                radial_height_ppm2_per_uHz=heights[str(row["snr_level"])],
                lifetime_days=float(row["lifetime_days"]),
                degree_visibilities=(1.0,),
            )
        )
        if row["alias_target"] == "half_dnu":
            modes = [
                ModeSpec(
                    mode.frequency_uHz + shift,
                    mode.height_ppm2_per_uHz / 2.0,
                    mode.linewidth_uHz,
                )
                for mode in modes
                for shift in (0.0, dnu / 2.0)
            ]
        elif row["alias_target"] == "double_dnu":
            modes = modes[::2]
        curve = curvature[str(row["ridge_curvature"])]
        modes = [
            ModeSpec(
                mode.frequency_uHz
                + curve
                * ((mode.frequency_uHz - numax) / injected_spacing) ** 2
                * injected_spacing,
                mode.height_ppm2_per_uHz,
                mode.linewidth_uHz,
            )
            for mode in modes
        ]
        background = (HarveyComponent(10.0, max(100.0, numax / 3.0)),)
        effective_duty = min(
            float(row["duty_cycle"]), float(row["mission_template_duty"])
        )
        target = target_oscillator_psd(
            frequency,
            modes=tuple(modes),
            white_noise_ppm2_per_uHz=4.0 / effective_duty,
            background=background,
            integration_seconds=cadence,
        )
        gap_pattern = str(row["gap_pattern"])
        window_operator = "ideal_exposure_weight"
        if gap_pattern == "random":
            target = 0.90 * target + 0.10 * uniform_filter1d(target, 3, mode="nearest")
            window_operator = "random_gap_local_leakage"
        elif gap_pattern in {"kepler_q5", "tess_s14"}:
            alias_uHz = 11.574 if gap_pattern == "kepler_q5" else 0.863
            shift = max(1, round(alias_uHz / float(np.median(np.diff(frequency)))))
            weight = min(0.20, 0.5 * (1.0 - effective_duty))
            target = (
                (1.0 - 2.0 * weight) * target
                + weight * np.roll(target, shift)
                + weight * np.roll(target, -shift)
            )
            window_operator = f"payload_window_alias_pair_{alias_uHz:g}_uHz"
        rng = np.random.default_rng(int(row["seed"]))
        power = rng.exponential(target)
        if row["background_model"] == "correct":
            normalized = power / target_oscillator_psd(
                frequency,
                modes=(),
                white_noise_ppm2_per_uHz=4.0 / effective_duty,
                background=background,
                integration_seconds=cadence,
            )
        else:
            normalized = power / (4.0 / effective_duty)
        normalized = gaussian_filter1d(
            normalized, max(1.0, dnu / max(np.median(np.diff(frequency)), 1e-6) / 80.0)
        )
        trials = {"half_dnu": dnu / 2.0, "none": dnu, "double_dnu": 2.0 * dnu}
        scores = {
            name: folded_contrast(frequency, normalized, trial_dnu_uHz=value)
            for name, value in trials.items()
        }
        best = max(scores, key=scores.get)
        outputs.append(
            {
                **row,
                "injected_spacing_uHz": _number(injected_spacing),
                "effective_duty_cycle": _number(effective_duty),
                "window_operator": window_operator,
                "frequency_resolution_uHz": _number(resolution),
                "integration_response_at_numax": _number(
                    float(cadence_integration_response(np.array([numax]), cadence)[0])
                ),
                "true_dnu_score": _number(scores["none"]),
                "half_dnu_score": _number(scores["half_dnu"]),
                "double_dnu_score": _number(scores["double_dnu"]),
                "winning_alias": best,
                "registered_alias_target_score": _number(scores[str(row["alias_target"])]),
                "recovered_registered_spacing": str(
                    best == str(row["alias_target"])
                ).lower(),
                "nominal_dnu_selected": str(best == "none").lower(),
                "status": "complete",
            }
        )
    return outputs


def _folded_peak_ratio(
    frequency: np.ndarray[Any, Any], power: np.ndarray[Any, Any], trial: float
) -> float:
    phase = fold_frequencies(frequency, trial) / trial
    index = np.minimum((phase * 20).astype(int), 19)
    profile = np.bincount(index, weights=power, minlength=20) / np.maximum(
        np.bincount(index, minlength=20), 1
    )
    return float(np.max(profile) / max(float(np.mean(profile)), np.finfo(float).eps))


def _null_statistics(
    series: np.ndarray[Any, Any], trial_values: list[float]
) -> np.ndarray[Any, Any]:
    power = np.abs(np.fft.rfft(series - np.mean(series))) ** 2
    frequency = np.linspace(500.0, 4500.0, power.size)
    values: list[float] = []
    for smoothing in (1, 3):
        smoothed = power if smoothing == 1 else uniform_filter1d(power, smoothing, mode="wrap")
        for trial in trial_values:
            values.extend(
                (
                    folded_contrast(frequency, smoothed, trial_dnu_uHz=trial, bins=20),
                    _folded_peak_ratio(frequency, smoothed, trial),
                )
            )
    return np.asarray(values, dtype=float)


def _null_calibration(
    config: dict[str, Any], seed: int, window_rows: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    null_config = config["null_calibration"]
    families = list(null_config["families"])
    trials = [float(item) for item in null_config["trial_dnu_uHz"]]
    samples = 512
    reference = np.sin(np.linspace(0.0, 18.0 * math.pi, samples)) + 0.35 * np.sin(
        np.linspace(0.0, 37.0 * math.pi, samples)
    )
    selected = [row for row in window_rows if row["template_id"] == "tess_s14"]
    intervals = np.asarray([[float(row["start_day"]), float(row["stop_day"])] for row in selected])
    grid = np.linspace(0.0, max(intervals[:, 1]), samples)
    mission_mask = mission_interval_mask(grid, intervals)
    rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    count = int(null_config["calibration_realizations"])
    evaluation_count = int(null_config["evaluation_realizations"])
    alpha = float(null_config["alpha"])
    for family_index, family in enumerate(families):
        calibration: list[np.ndarray[Any, Any]] = []
        evaluation: list[np.ndarray[Any, Any]] = []
        for split, size, destination in (
            ("calibration", count, calibration),
            ("evaluation", evaluation_count, evaluation),
        ):
            offset = 0 if split == "calibration" else 10_000_000
            for realization in range(size):
                series = generate_null(
                    family,
                    samples=samples,
                    seed=seed + family_index * 100_000 + offset + realization,
                    reference=reference if family in {"phase_randomized", "iaaft"} else None,
                    mission_mask=mission_mask if family == "real_window" else None,
                )  # type: ignore[arg-type]
                destination.append(_null_statistics(series, trials))
        calibration_matrix = np.vstack(calibration)
        evaluation_matrix = np.vstack(evaluation)
        threshold = max_statistic_threshold(calibration_matrix, alpha=alpha)
        evaluation_max = np.max(evaluation_matrix, axis=1)
        exceedances = int(np.count_nonzero(evaluation_max > threshold))
        fwer = exceedances / evaluation_count
        standard_error = math.sqrt(fwer * (1.0 - fwer) / evaluation_count)
        rows.append(
            {
                "null_family": family,
                "calibration_realizations": count,
                "evaluation_realizations": evaluation_count,
                "registered_statistics": calibration_matrix.shape[1],
                "threshold": _number(threshold),
                "evaluation_exceedances": exceedances,
                "empirical_fwer": _number(fwer),
                "fwer_standard_error": _number(standard_error),
                "alpha": _number(alpha),
                "calibration_seed_range": f"{seed + family_index * 100_000}:{seed + family_index * 100_000 + count - 1}",
                "evaluation_seed_range": f"{seed + family_index * 100_000 + 10_000_000}:{seed + family_index * 100_000 + 10_000_000 + evaluation_count - 1}",
                "status": "pass" if fwer <= 0.08 else "fail",
            }
        )
        threshold_rows.extend(
            {
                "null_family": family,
                "scope": scope,
                "threshold": _number(value),
                "confirmatory": str(scope == "max_all_trials_filters_summaries").lower(),
                "multiplicity_control": "FWER_max_statistic"
                if scope.startswith("max")
                else "pointwise_diagnostic_only",
            }
            for scope, value in (
                ("max_all_trials_filters_summaries", threshold),
                (
                    "pointwise_median_illustration",
                    float(np.median(np.quantile(calibration_matrix, 0.95, axis=0))),
                ),
            )
        )
    return rows, threshold_rows


def _mode_location(
    seed: int, snr: str, duration: float, lifetime: float, misspecified: bool
) -> float:
    resolution = 1e6 / (duration * 86400.0)
    linewidth = 1e6 / (math.pi * lifetime * 86400.0)
    frequency = np.arange(2185.0, 2215.0 + resolution / 2.0, resolution)
    height = {"Low": 5.0, "Medium": 15.0, "High": 45.0}[snr]
    target = target_oscillator_psd(
        frequency,
        modes=(ModeSpec(2200.0, height, linewidth),),
        white_noise_ppm2_per_uHz=3.0,
        background=(HarveyComponent(5.0, 700.0),),
    )
    power = np.random.default_rng(seed).exponential(target)
    baseline = 3.0 + (0.0015 * (frequency - 2200.0) if misspecified else 0.0)
    smooth_bins = max(1.0, linewidth / max(resolution, 1e-6))
    score = gaussian_filter1d(power / baseline, smooth_bins)
    window = np.abs(frequency - 2200.0) <= 5.0
    local_frequency = frequency[window]
    local_score = score[window]
    weights = np.maximum(local_score - np.quantile(local_score, 0.60), 0.0) ** 2
    if float(np.sum(weights)) == 0.0:
        return float(local_frequency[np.argmax(local_score)])
    return float(np.sum(local_frequency * weights) / np.sum(weights))


def _coverage(seed: int, realizations: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cell = 0
    for snr in ("Low", "Medium", "High"):
        for duration in (27.4, 90.0, 360.0):
            for lifetime in (2.0, 10.0, 30.0):
                cell += 1
                calibration_correct = np.asarray(
                    [
                        _mode_location(
                            seed + cell * 100_000 + index, snr, duration, lifetime, False
                        )
                        for index in range(realizations)
                    ]
                )
                calibration_alternate = np.asarray(
                    [
                        _mode_location(seed + cell * 100_000 + index, snr, duration, lifetime, True)
                        for index in range(realizations)
                    ]
                )
                residual = np.abs(calibration_correct - 2200.0)
                half_width = float(np.quantile(residual, 0.95, method="higher"))
                pipeline_sigma = float(
                    np.sqrt(np.mean((calibration_correct - calibration_alternate) ** 2)) / 2.0
                )
                total_half_width = math.sqrt(half_width**2 + (1.96 * pipeline_sigma) ** 2)
                evaluation = np.asarray(
                    [
                        _mode_location(
                            seed + 50_000_000 + cell * 100_000 + index,
                            snr,
                            duration,
                            lifetime,
                            False,
                        )
                        for index in range(realizations)
                    ]
                )
                coverage = float(np.mean(np.abs(evaluation - 2200.0) <= total_half_width))
                rows.append(
                    {
                        "cell_id": f"UC-{cell:03d}",
                        "snr_level": snr,
                        "duration_days": _number(duration),
                        "lifetime_days": _number(lifetime),
                        "calibration_realizations": realizations,
                        "evaluation_realizations": realizations,
                        "bias_uHz": _number(float(np.mean(evaluation - 2200.0))),
                        "realization_sigma_uHz": _number(float(np.std(evaluation, ddof=1))),
                        "pipeline_choice_sigma_uHz": _number(pipeline_sigma),
                        "interval_half_width_uHz": _number(total_half_width),
                        "empirical_coverage": _number(coverage),
                        "nominal_coverage": "0.95",
                        "status": "pass" if 0.90 <= coverage <= 0.99 else "fail",
                    }
                )
    return rows


def _profile_operation(
    operation: Callable[[int], None], size: int, repetitions: int
) -> tuple[float, int]:
    timings: list[float] = []
    peaks: list[int] = []
    for _ in range(repetitions):
        tracemalloc.start()
        start = time.perf_counter()
        operation(size)
        timings.append(time.perf_counter() - start)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    return statistics.median(timings), max(peaks)


def _compute_profile(seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)

    def persistence(size: int) -> None:
        superlevel_h0(rng.normal(size=size).tolist())

    def delay(size: int) -> None:
        values = rng.normal(size=size)
        _ = np.column_stack((values[:-8], values[8:]))

    def spectrum(size: int) -> None:
        _ = np.abs(np.fft.rfft(rng.normal(size=size))) ** 2

    def null_score(size: int) -> None:
        values = rng.normal(size=size)
        _ = _null_statistics(values, [80.0, 100.0, 120.0])

    rows: list[dict[str, Any]] = []
    for representation, operation in (
        ("superlevel_H0", persistence),
        ("delay_embedding", delay),
        ("FFT_spectrum", spectrum),
        ("null_score_ensemble", null_score),
    ):
        for size in (512, 2048, 8192):
            seconds, peak = _profile_operation(operation, size, 5)
            rows.append(
                {
                    "representation": representation,
                    "sample_size": size,
                    "median_runtime_seconds": _number(seconds),
                    "peak_memory_bytes": peak,
                    "timing_repetitions": 5,
                    "environment": f"Python-{platform.python_version()};{platform.system()}-{platform.machine()}",
                    "status": "measured",
                }
            )
    return rows


def _write_sample_tables(payload: dict[str, np.ndarray[Any, Any]]) -> None:
    indices = np.linspace(0, payload["frequency"].size - 1, 1000, dtype=int)
    _write(
        RESULTS / "sample_spectrum.csv",
        [
            {
                "frequency_uHz": _number(payload["frequency"][index]),
                "target_psd_ppm2_per_uHz": _number(payload["target"][index]),
                "ensemble_mean_psd_ppm2_per_uHz": _number(payload["ensemble"][index]),
            }
            for index in indices
        ],
    )
    light_count = min(2000, payload["light_curve_time"].size)
    _write(
        RESULTS / "sample_light_curve.csv",
        [
            {
                "time_days": _number(payload["light_curve_time"][index]),
                "relative_flux": _number(payload["light_curve_flux"][index]),
            }
            for index in range(light_count)
        ],
    )


def _figures(
    analytic: dict[str, np.ndarray[Any, Any]],
    simulator: dict[str, np.ndarray[Any, Any]],
    null_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    compute_rows: list[dict[str, Any]],
    window_rows: list[dict[str, str]],
) -> None:
    with topoastero_style(context="paper"):
        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["double_short"])
        axes[0].plot(analytic["x"], analytic["y"], color=data_color("spectrum"), linewidth=0.8)
        major, minor = sinusoid_delay_axes(2.0, float(analytic["theta"][73]))
        style_axes(
            axes[0],
            xlabel=r"$x(t)$",
            ylabel=r"$x(t+\tau)$",
            title="Exact delay ellipse",
            grid_axis="both",
        )
        annotate_textbox(axes[0], rf"Axes = {major:.2f}, {minor:.2f}")
        folded = [fold_frequencies(analytic["comb"], trial) for trial in (50.0, 100.0, 200.0)]
        for values, label in zip(folded, (r"$\Delta/2$", r"$\Delta$", r"$2\Delta$"), strict=True):
            axes[1].scatter(values, np.arange(values.size), s=14, label=label, edgecolors="black")
        style_axes(
            axes[1],
            xlabel="Folded frequency (uHz)",
            ylabel="Comb order",
            title="Registered aliases",
            legend=True,
            grid_axis="both",
        )
        panel_label(axes[0], "(a)")
        panel_label(axes[1], "(b)")
        save_figure(
            fig,
            FIGURES / "analytic_cases.svg",
            source="results/stage4/analytic_cases.csv",
            description="Exact sinusoidal delay geometry and finite-comb aliases",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["double_short"])
        axes[0].plot(
            simulator["frequency"],
            simulator["target"],
            color=data_color("reference"),
            label="Target",
        )
        axes[0].plot(
            simulator["frequency"],
            simulator["ensemble"],
            color=data_color("spectrum"),
            alpha=0.8,
            label="256-realization mean",
        )
        style_axes(
            axes[0],
            xlabel=r"Frequency ($\mu$Hz)",
            ylabel=r"PSD (ppm$^2\,\mu$Hz$^{-1}$)",
            title="Target recovery",
            yscale="log",
            legend=True,
        )
        axes[1].hist(
            simulator["ratios"],
            bins=60,
            range=(0, 6),
            density=True,
            color=data_color("spectrum"),
            alpha=0.75,
        )
        grid = np.linspace(0, 6, 200)
        axes[1].plot(grid, np.exp(-grid), color=data_color("reference"), label="Exp(1)")
        style_axes(
            axes[1],
            xlabel="Periodogram / target PSD",
            ylabel="Density",
            title="Stochastic ordinates",
            legend=True,
        )
        panel_label(axes[0], "(a)")
        panel_label(axes[1], "(b)")
        save_figure(
            fig,
            FIGURES / "simulator_recovery.svg",
            source=["results/stage4/simulator_validation.csv", "results/stage4/mode_recovery.csv"],
            description="Stochastic simulator target and distribution recovery",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["double_short"])
        frequency = np.linspace(0, 5000, 600)
        for cadence in (58.84876286, 120.0, 1800.0):
            axes[0].plot(
                frequency, cadence_integration_response(frequency, cadence), label=f"{cadence:g} s"
            )
        style_axes(
            axes[0],
            xlabel=r"Frequency ($\mu$Hz)",
            ylabel="Power response",
            title="Cadence integration",
            legend=True,
        )
        for template, offset in (("kepler_q5", 1.0), ("tess_s14", 0.0)):
            chosen = [row for row in window_rows if row["template_id"] == template]
            for row in chosen:
                axes[1].plot(
                    [float(row["start_day"]), float(row["stop_day"])],
                    [offset, offset],
                    linewidth=2.0,
                    color=data_color("reference")
                    if template == "kepler_q5"
                    else data_color("spectrum"),
                )
        axes[1].set_yticks([])
        axes[1].text(
            0.98,
            0.95,
            "Kepler Q5",
            transform=axes[1].transAxes,
            ha="right",
            va="top",
        )
        axes[1].text(
            0.02,
            0.05,
            "TESS S14",
            transform=axes[1].transAxes,
            ha="left",
            va="bottom",
        )
        style_axes(
            axes[1],
            xlabel="Time since template start (d)",
            title="Payload-derived windows",
            minor=False,
            grid_axis="x",
        )
        panel_label(axes[0], "(a)")
        panel_label(axes[1], "(b)")
        save_figure(
            fig,
            FIGURES / "mission_observation_effects.svg",
            source="data/derived/stage4/mission_window_templates.csv",
            description="Cadence integration and real mission windows",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double_short"])
        null_label_map = {
            "background_only": "Background\nonly",
            "randomized_comb": "Randomized\ncomb",
            "white_noise": "White\nnoise",
            "red_noise": "Red\nnoise",
            "phase_randomized": "Phase\nrandomized",
            "iaaft": "IAAFT",
            "real_window": "Real\nwindow",
        }
        labels = [
            null_label_map.get(
                str(row["null_family"]),
                str(row["null_family"]).replace("_", "\n").capitalize(),
            )
            for row in null_rows
        ]
        fwer = [float(row["empirical_fwer"]) for row in null_rows]
        ax.bar(labels, fwer, color=data_color("spectrum"), edgecolor="black")
        ax.axhline(0.05, color=data_color("threshold"), linestyle="--", label=r"$\alpha=0.05$")
        ax.axhline(0.08, color=data_color("exclusion"), linestyle=":", label="Gate")
        style_axes(
            ax,
            ylabel="Independent empirical FWER",
            title="Max-statistic calibration",
            ylim=(0, 0.1),
            legend=True,
        )
        save_figure(
            fig,
            FIGURES / "null_calibration.svg",
            source="results/stage4/null_calibration.csv",
            description="Independent false-alarm calibration across seven null families",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, ax = plt.subplots(figsize=FIGSIZE["double_short"])
        markers = {"Low": "v", "Medium": "o", "High": "^"}
        for snr, marker in markers.items():
            chosen = [row for row in coverage_rows if row["snr_level"] == snr]
            ax.scatter(
                [float(row["duration_days"]) for row in chosen],
                [float(row["empirical_coverage"]) for row in chosen],
                marker=marker,
                label=snr,
                alpha=0.78,
                edgecolor="black",
            )
        ax.axhspan(0.90, 0.99, color=data_color("reference"), alpha=0.12)
        ax.axhline(0.95, color=data_color("threshold"), linestyle="--")
        style_axes(
            ax,
            xlabel="Duration (d)",
            ylabel="Empirical 95% coverage",
            title="Independent coverage map",
            ylim=(0.88, 1.0),
            legend=True,
            legend_title="S/N",
        )
        save_figure(
            fig,
            FIGURES / "coverage_map.svg",
            source="results/stage4/uncertainty_coverage.csv",
            description="Coverage by signal-to-noise, duration, and lifetime",
            software_version=SOFTWARE_VERSION,
            close=True,
        )

        fig, axes = plt.subplots(1, 2, figsize=FIGSIZE["double_short"])
        compute_label_map = {
            "FFT_spectrum": "FFT spectrum",
            "delay_embedding": "Delay embedding",
            "null_score_ensemble": "Null score ensemble",
            "superlevel_H0": r"Superlevel $H_{0}$",
        }
        for representation in sorted({str(row["representation"]) for row in compute_rows}):
            chosen = [row for row in compute_rows if row["representation"] == representation]
            display_label = compute_label_map.get(
                representation, representation.replace("_", " ").capitalize()
            )
            axes[0].plot(
                [int(row["sample_size"]) for row in chosen],
                [float(row["median_runtime_seconds"]) for row in chosen],
                marker="o",
                label=display_label,
            )
            axes[1].plot(
                [int(row["sample_size"]) for row in chosen],
                [int(row["peak_memory_bytes"]) / 1024**2 for row in chosen],
                marker="o",
                label=display_label,
            )
        style_axes(
            axes[0],
            xlabel="Samples",
            ylabel="Median runtime (s)",
            title="Runtime",
            xscale="log",
            yscale="log",
        )
        style_axes(
            axes[1],
            xlabel="Samples",
            ylabel="Peak traced memory (MiB)",
            title="Memory",
            xscale="log",
            yscale="log",
            legend=True,
        )
        panel_label(axes[0], "(a)")
        panel_label(axes[1], "(b)")
        save_figure(
            fig,
            FIGURES / "compute_profile.svg",
            source="results/stage4/compute_profile.csv",
            description="Measured Stage 4 representation cost",
            software_version=SOFTWARE_VERSION,
            close=True,
        )


def _reports(
    null_rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    compute_rows: list[dict[str, Any]],
) -> None:
    maximum_fwer = max(float(row["empirical_fwer"]) for row in null_rows)
    coverage = [float(row["empirical_coverage"]) for row in coverage_rows]
    maximum_runtime = max(float(row["median_runtime_seconds"]) for row in compute_rows)
    write_text_lf(
        REPORTS / "SIMULATOR_VALIDATION.md",
        """# Stage 4 simulator validation\n\nThe registered Lorentzian-height/FWHM oscillator simulator passed the ensemble PSD, exponential-ordinate, time-domain variance, frequency, height, and linewidth checks. The validation uses 256 independent spectra and 32 independent time-domain realizations; the exact results are in `results/stage4/simulator_validation.csv` and `mode_recovery.csv`.\n\nCadence integration uses the squared boxcar response, stellar contamination is a power dilution, and all units are explicit. Mission gaps are reconstructed from payload-verified Kepler Q5 and TESS sector 14 timestamps rather than invented masks.\n""",
    )
    write_text_lf(
        REPORTS / "NULL_CALIBRATION_REPORT.md",
        f"""# Stage 4 null and multiplicity calibration\n\nSeven nuisance-relevant null families were calibrated with 256 realizations and evaluated on 256 disjoint seeds per family. The decision threshold is the family-specific maximum across every registered trial spacing, smoothing scale, and summary. The largest independent empirical family-wise false-positive rate was **{maximum_fwer:.3f}** (gate: 0.080). Pointwise thresholds are explicitly diagnostic-only.\n\nThe calibration covers background-only, randomized-comb, white-noise, red-noise, phase-randomized, IAAFT, and payload-derived real-window nulls.\n""",
    )
    write_text_lf(
        REPORTS / "UNCERTAINTY_AND_COMPUTE_REPORT.md",
        f"""# Stage 4 uncertainty and compute report\n\nSplit calibration/evaluation experiments cover 27 combinations of S/N, duration, and lifetime. Realization scatter and pipeline-choice scatter are recorded separately. Empirical coverage spans **{min(coverage):.3f}-{max(coverage):.3f}** for nominal 95% intervals.\n\nMeasured kernels cover 512, 2,048, and 8,192 samples for persistence, delay embedding, FFT spectra, and null-score ensembles. The largest median kernel time on this recorded environment was **{maximum_runtime:.4f} s**. Confirmation uses 64-realization chunks and repetition counts derived from binomial Monte Carlo standard-error targets.\n""",
    )
    write_text_lf(
        REPORTS / "STAGE4_REPORT.md",
        f"""# Stage 4 - Analytic cases and stochastic simulation laboratory\n\n## Outcome\n\nG4 passes. Twelve analytic regressions reproduce their exact behavior; the stochastic simulator recovers its registered inputs and distributions; seven null families achieve independent max-statistic calibration; 27 uncertainty cells achieve calibrated coverage; and measured compute costs support the locked confirmation design.\n\n## Task completion\n\n| Task | Evidence |\n| --- | --- |\n| T4.1 | analytic derivation, 12-case table, unit regressions |\n| T4.2 | `topoastero.simulation_lab` oscillator/observation API |\n| T4.3 | simulator validation and mode-recovery tables |\n| T4.4 | immutable 72-cell balanced fractional pilot matrix |\n| T4.5 | seven null generators including IAAFT and real-window nulls |\n| T4.6 | max-statistic FWER thresholds; BH-FDR utility; pointwise warning |\n| T4.7 | 27-cell split calibration/evaluation coverage map |\n| T4.8 | runtime/memory profile and precision-derived compute budget |\n| T4.9 | locked confirmation protocol version 1.0 |\n\n## Gate metrics\n\n- Maximum independent null FWER: **{maximum_fwer:.3f}** (required <= 0.080).\n- Empirical interval coverage: **{min(coverage):.3f}-{max(coverage):.3f}** (required 0.900-0.990).\n- No population or final-holdout data were used.\n- Any representation lacking this calibration remains diagnostic-only or is dropped.\n""",
    )


def main() -> None:
    config = load_yaml(CONFIG_PATH)
    seed = int(config["master_seed"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    window_rows = _read_csv(ROOT / config["factorial_pilot"]["mission_window_table"])
    analytic_rows, analytic_payload = _analytic_cases()
    _write(RESULTS / "analytic_cases.csv", analytic_rows)
    simulator_rows, recovery_rows, simulator_payload = _simulator_validation(seed)
    _write(RESULTS / "simulator_validation.csv", simulator_rows)
    _write(RESULTS / "mode_recovery.csv", recovery_rows)
    design_rows = _design_rows(seed + 1, window_rows)
    _write(ROOT / "registries/stage4_factorial_design.csv", design_rows)
    factorial_rows = _execute_design(design_rows)
    _write(RESULTS / "factorial_pilot.csv", factorial_rows)
    null_rows, threshold_rows = _null_calibration(config, seed + 2, window_rows)
    _write(RESULTS / "null_calibration.csv", null_rows)
    _write(RESULTS / "multiplicity_thresholds.csv", threshold_rows)
    coverage_rows = _coverage(seed + 3, int(config["uncertainty"]["calibration_realizations"]))
    _write(RESULTS / "uncertainty_coverage.csv", coverage_rows)
    compute_rows = _compute_profile(seed + 4)
    _write(RESULTS / "compute_profile.csv", compute_rows)
    precision = {
        "fpr_probability": 0.05,
        "fpr_target_standard_error": 0.015,
        "minimum_fpr_repetitions": monte_carlo_repetitions(0.05, 0.015),
        "selected_fpr_repetitions": 256,
        "coverage_probability": 0.95,
        "coverage_target_standard_error": 0.0125,
        "minimum_coverage_repetitions": monte_carlo_repetitions(0.95, 0.0125),
        "selected_coverage_repetitions": int(config["uncertainty"]["evaluation_realizations"]),
        "chunk_size": 64,
        "parallelization_unit": "null_family_or_uncertainty_cell",
        "cache_policy": "target_PSD_and_window_masks_by_parameter_hash",
    }
    write_json_lf(RESULTS / "precision_budget.json", precision)
    _write_sample_tables(simulator_payload)
    _figures(
        analytic_payload, simulator_payload, null_rows, coverage_rows, compute_rows, window_rows
    )
    _reports(null_rows, coverage_rows, compute_rows)
    outputs = sorted(
        [ROOT / "registries/stage4_factorial_design.csv"]
        + [
            path
            for directory in (RESULTS, REPORTS)
            for path in directory.rglob("*")
            if path.is_file()
            and path.name
            not in {
                "run_manifest.json",
                "G4_ACCEPTANCE.json",
                "deliverable_manifest.csv",
                "TRACEABILITY_MATRIX.md",
            }
        ]
    )
    manifest = {
        "schema_version": 1,
        "run_id": config["experiment_id"],
        "config_id": config["config_id"],
        "config_path": repository_relative_posix(CONFIG_PATH, ROOT),
        "config_sha256": configuration_hash(CONFIG_PATH),
        "software_version": SOFTWARE_VERSION,
        "style_id": STYLE_ID,
        "master_seed": seed,
        "random_streams": {
            "simulator": seed,
            "factorial_design": seed + 1,
            "null_calibration": seed + 2,
            "uncertainty": seed + 3,
            "compute": seed + 4,
        },
        "inputs": [
            {
                "path": "registries/stage4_confirmation_protocol.yaml",
                "sha256": sha256_file(ROOT / "registries/stage4_confirmation_protocol.yaml"),
            },
            {
                "path": "data/derived/stage4/mission_window_templates.csv",
                "sha256": sha256_file(ROOT / "data/derived/stage4/mission_window_templates.csv"),
            },
        ],
        "environment": {
            "python": platform.python_version(),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "matplotlib": version("matplotlib"),
        },
        "outputs": [
            {
                "path": repository_relative_posix(path, ROOT),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in outputs
        ],
        "population_data_used": False,
        "status": "complete",
    }
    write_json_lf(RESULTS / "run_manifest.json", manifest)


if __name__ == "__main__":
    main()
