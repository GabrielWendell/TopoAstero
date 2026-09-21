"""Run the complete Stage 3 Rudy classical baseline and TESS feasibility workflow.

Example (acquire exact payloads, verify checksums, and rebuild all numerical/figure products):

    uv run --extra astronomy python workflows/run_stage3_classical.py \
        --cache-dir /path/to/external/cache --download

The raw FITS cache is never written inside the repository or included in a deliverable manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import subprocess
import time
from collections import Counter, defaultdict
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from acquire_stage3_inputs import acquire
from matplotlib.colors import PowerNorm
from scipy.ndimage import gaussian_filter1d

from topoastero.classical import (
    BackgroundFit,
    ModeReference,
    audit_mode_peaks,
    classify_tess_sector,
    echelle_grid,
    estimate_envelope,
    estimate_large_separation,
    fit_harvey_models,
    harvey_background,
    quadrature_uncertainty,
    scaling_relations,
    scaling_uncertainty,
    spectral_window,
    strongest_window_aliases,
)
from topoastero.config import configuration_hash, load_yaml
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
)
from topoastero.provenance import sha256_file
from topoastero.style import (
    FIGSIZE,
    STYLE_ID,
    WINDOW_COLORS,
    WINDOW_LINESTYLES,
    annotate_textbox,
    background_color,
    background_label,
    data_color,
    mode_degree_color,
    mode_degree_label,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)

ROOT = Path(__file__).parents[1]
SOFTWARE_VERSION = "TopoAstero-0.4.0"
TUTORIAL_VALUES = {
    "numax": 2145.0,
    "dnu": 103.11,
    "mass": 1.08,
    "radius": 1.23,
    "logg": 4.29,
}
REFERENCES = {
    "numax": (2203.7, 6.3, 6.7, "authoritative_LEGACY"),
    "dnu": (103.179, 0.027, 0.027, "authoritative_LEGACY"),
    "mass": (1.0672, 0.0320, 0.0320, "context_only_catalog"),
    "radius": (1.2215, 0.0129, 0.0129, "context_only_catalog"),
    "logg": (4.2920, 0.0042, 0.0042, "context_only_catalog"),
}
UNITS = {
    "numax": "uHz",
    "dnu": "uHz",
    "mass": "Msun",
    "radius": "Rsun",
    "logg": "dex(cgs)",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: Sequence[dict[str, Any]]) -> None:
    write_csv_lf(path, rows, fieldnames=fieldnames)


def _number(value: float, digits: int = 12) -> str:
    return f"{float(value):.{digits}g}"


def _lightkurve_globals(light_curve: Any, teff: float) -> tuple[dict[str, float], Any, Any]:
    periodogram = light_curve.to_periodogram(
        normalization="psd", minimum_frequency=1500.0, maximum_frequency=2700.0
    )
    seismology = periodogram.flatten().to_seismology()
    numax = float(seismology.estimate_numax().value)
    dnu = float(seismology.estimate_deltanu().value)
    values = {
        "numax": numax,
        "dnu": dnu,
        "mass": float(seismology.estimate_mass(teff=teff).value),
        "radius": float(seismology.estimate_radius(teff=teff).value),
        "logg": float(seismology.estimate_logg(teff=teff).value),
    }
    return values, periodogram, seismology


def _background_model(frequency: np.ndarray[Any, Any], fit: BackgroundFit) -> np.ndarray[Any, Any]:
    return harvey_background(frequency, fit.white_noise_ppm2_per_uHz, fit.components)


def _background_rows(fits: tuple[BackgroundFit, ...], selected: BackgroundFit) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fit in fits:
        record: dict[str, Any] = {
            "model_id": f"BG-H{fit.component_count}",
            "component_count": fit.component_count,
            "white_noise_ppm2_per_uHz": _number(fit.white_noise_ppm2_per_uHz),
            "component_1_amplitude_ppm2_per_uHz": "",
            "component_1_characteristic_uHz": "",
            "component_1_exponent": "",
            "component_2_amplitude_ppm2_per_uHz": "",
            "component_2_characteristic_uHz": "",
            "component_2_exponent": "",
            "log_residual_rms": _number(fit.log_residual_rms),
            "negative_log_likelihood": _number(fit.negative_log_likelihood),
            "aic": _number(fit.aic),
            "bic": _number(fit.bic),
            "covariance_condition": _number(fit.covariance_condition),
            "parameter_sigma_log": ";".join(_number(value) for value in fit.parameter_sigma_log),
            "selected_by_minimum_bic": str(fit is selected).lower(),
        }
        for index, component in enumerate(fit.components, start=1):
            record[f"component_{index}_amplitude_ppm2_per_uHz"] = _number(
                component.amplitude_ppm2_per_uHz
            )
            record[f"component_{index}_characteristic_uHz"] = _number(
                component.characteristic_uHz
            )
            record[f"component_{index}_exponent"] = _number(component.exponent)
        rows.append(record)
    return rows


def _normalize(curve: Any) -> Any:
    return curve.normalize()


def _clip_normalize(curve: Any) -> Any:
    return curve.remove_nans().remove_outliers(sigma=5).normalize()


def _sap_flatten(curve: Any) -> Any:
    return curve.remove_nans().remove_outliers(sigma=5).flatten(window_length=1001).normalize()


def _branch_light_curve(paths: list[Path], branch_id: str) -> Any:
    import lightkurve as lk

    if branch_id == "PP-01":
        curves = [lk.read(path) for path in paths]
        corrector = _normalize
    elif branch_id == "PP-02":
        curves = [
            curve[curve.quality == 0]
            for curve in (
                lk.KeplerLightCurve.read(path, flux_column="pdcsap_flux", quality_bitmask=None)
                for path in paths
            )
        ]
        corrector = _clip_normalize
    elif branch_id == "PP-03":
        curves = [
            lk.KeplerLightCurve.read(path, flux_column="sap_flux", quality_bitmask="default")
            for path in paths
        ]
        corrector = _sap_flatten
    elif branch_id == "PP-04":
        curves = [
            lk.KeplerLightCurve.read(path, flux_column="pdcsap_flux", quality_bitmask="hardest")
            for path in paths
        ]
        corrector = _clip_normalize
    else:
        raise ValueError(f"unsupported executed branch: {branch_id}")
    return lk.LightCurveCollection(curves).stitch(corrector_func=corrector)


def _bootstrap_segments(
    curves: list[Any], resamples: int, seed: int, step_uHz: float
) -> tuple[float, float, tuple[float, float], tuple[float, float]]:
    grid = np.arange(1500.0, 2700.0 + step_uHz / 2.0, step_uHz)
    spectra: list[np.ndarray[Any, Any]] = []
    for curve in curves:
        periodogram = curve.normalize().to_periodogram(
            normalization="psd", minimum_frequency=1500.0, maximum_frequency=2700.0
        )
        frequency = np.asarray(periodogram.frequency.value, dtype=float)
        power = np.asarray(periodogram.power.value, dtype=float)
        low = float(np.median(power[(frequency >= 1500.0) & (frequency < 1700.0)])) / math.log(2)
        high = float(np.median(power[(frequency > 2550.0) & (frequency <= 2700.0)])) / math.log(2)
        background = np.exp(
            np.interp(grid, [1600.0, 2625.0], [math.log(low), math.log(high)])
        )
        spectra.append(np.interp(grid, frequency, power) / background)
    stack = np.asarray(spectra)

    def estimate(mean_spectrum: np.ndarray[Any, Any]) -> tuple[float, float]:
        background = np.ones_like(mean_spectrum)
        envelope = estimate_envelope(
            grid,
            mean_spectrum,
            background,
            search_uHz=(1700.0, 2500.0),
            smoothing_uHz=35.0,
        )
        spacing = estimate_large_separation(
            grid,
            mean_spectrum,
            background,
            envelope.numax_uHz,
            half_width_uHz=275.0,
            smoothing_uHz=0.5,
        )
        return envelope.numax_uHz, spacing.dnu_uHz

    random = np.random.default_rng(seed)
    estimates = np.empty((resamples, 2), dtype=float)
    for index in range(resamples):
        draw = random.integers(0, len(stack), len(stack))
        estimates[index] = estimate(np.mean(stack[draw], axis=0))
    numax_interval = tuple(float(value) for value in np.percentile(estimates[:, 0], [16, 84]))
    dnu_interval = tuple(float(value) for value in np.percentile(estimates[:, 1], [16, 84]))
    return (
        float(np.std(estimates[:, 0], ddof=1)),
        float(np.std(estimates[:, 1], ddof=1)),
        (numax_interval[0], numax_interval[1]),
        (dnu_interval[0], dnu_interval[1]),
    )


def _compressed_quarter_times(times_by_quarter: dict[int, np.ndarray[Any, Any]], cadence: float) -> np.ndarray[Any, Any]:
    compressed: list[np.ndarray[Any, Any]] = []
    cursor = 0.0
    cadence_days = cadence / 86400.0
    for quarter in sorted(times_by_quarter):
        times = np.sort(times_by_quarter[quarter])
        shifted = times - times[0] + cursor
        compressed.append(shifted)
        cursor = float(shifted[-1]) + cadence_days
    return np.concatenate(compressed)


def _window_products(
    curves: list[Any], product_rows: list[dict[str, str]], cadence: float, maximum: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    times_by_quarter: dict[int, list[np.ndarray[Any, Any]]] = defaultdict(list)
    for curve, row in zip(curves, product_rows, strict=True):
        times_by_quarter[int(row["segment_number"])].append(np.asarray(curve.time.value, dtype=float))
    joined = {
        quarter: np.sort(np.concatenate(months)) for quarter, months in times_by_quarter.items()
    }
    variants: dict[str, np.ndarray[Any, Any]] = {
        f"Q{quarter}": times for quarter, times in joined.items()
    }
    variants["combined_absolute"] = np.sort(np.concatenate(list(joined.values())))
    variants["combined_compressed"] = _compressed_quarter_times(joined, cadence)
    rows: list[dict[str, Any]] = []
    windows: dict[str, Any] = {}
    for name, times in variants.items():
        window = spectral_window(times, cadence, maximum_frequency_uHz=maximum)
        windows[name] = window
        aliases = strongest_window_aliases(window, 3)
        record: dict[str, Any] = {
            "window_id": name,
            "sample_count": len(times),
            "duration_days": _number(float(times.max() - times.min())),
            "duty_cycle": _number(window.duty_cycle),
            "resolution_uHz": _number(window.resolution_uHz),
            "time_treatment": "compressed_quarter_time" if name.endswith("compressed") else "absolute_time",
            "alias_1_uHz": "",
            "alias_1_power": "",
            "alias_2_uHz": "",
            "alias_2_power": "",
            "alias_3_uHz": "",
            "alias_3_power": "",
            "assessment": (
                "diagnostic_only_not_primary"
                if name.endswith("compressed")
                else "retains_physical_sampling_window"
            ),
        }
        for index, (alias_frequency, alias_power) in enumerate(aliases, start=1):
            record[f"alias_{index}_uHz"] = _number(alias_frequency)
            record[f"alias_{index}_power"] = _number(alias_power)
        rows.append(record)
    return rows, windows


def _mode_references(path: Path) -> tuple[ModeReference, ...]:
    references: list[ModeReference] = []
    for row in _read_csv(path):
        uncertainty = 0.5 * (
            float(row["uncertainty_minus_uHz"]) + float(row["uncertainty_plus_uHz"])
        )
        references.append(
            ModeReference(
                row_id=row["row_id"],
                radial_order_n=int(row["radial_order_n"]),
                angular_degree_l=int(row["angular_degree_l"]),
                frequency_uHz=float(row["frequency_uHz"]),
                uncertainty_uHz=uncertainty,
            )
        )
    return tuple(references)


def _plot_products(
    figure_dir: Path,
    frequency: np.ndarray[Any, Any],
    power: np.ndarray[Any, Any],
    background: np.ndarray[Any, Any],
    fits: tuple[BackgroundFit, ...],
    windows: dict[str, Any],
    echelle_trials: list[tuple[float, Any]],
    mode_rows: list[dict[str, Any]],
    tess_rows: list[dict[str, Any]],
) -> list[Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    selected = (frequency >= 1500) & (frequency <= 2700)
    spacing = float(np.median(np.diff(frequency)))
    smoothed = gaussian_filter1d(power / background, 35.0 / spacing)
    with topoastero_style(context="paper", constrained_layout=True):
        fig, axis = plt.subplots(figsize=FIGSIZE["double"])
        axis.plot(
            frequency[selected],
            power[selected],
            color=data_color("raw"),
            lw=0.45,
            alpha=0.72,
            label="PSD",
            rasterized=True,
        )
        axis.plot(
            frequency[selected],
            background[selected],
            color=data_color("background"),
            lw=1.6,
            label="Harvey background",
        )
        axis.plot(
            frequency[selected],
            background[selected] * smoothed[selected],
            color=data_color("envelope"),
            lw=1.25,
            label=r"35-$\mu$Hz smooth",
        )
        style_axes(
            axis,
            xlabel=r"Frequency [$\mu$Hz]",
            ylabel=r"PSD [ppm$^2\,\mu$Hz$^{-1}$]",
            title="Rudy classical power spectrum",
            yscale="log",
            grid_axis="both",
            legend=True,
            legend_loc="lower left",
            legend_ncols=1,
        )
        path = figure_dir / "rudy_power_spectrum.svg"
        save_figure(
            fig,
            path,
            close=True,
            source="results/stage3/reduced_spectrum.csv",
            description="Whitened spectrum, selected background, and smoothed oscillation envelope.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)

        fig, axis = plt.subplots(figsize=FIGSIZE["double"])
        sample = slice(None, None, 40)
        axis.scatter(
            frequency[sample],
            power[sample],
            s=2.5,
            alpha=0.16,
            color=data_color("raw"),
            edgecolors="none",
            label="PSD samples",
            rasterized=True,
        )
        selected_fit = min(fits, key=lambda fit: fit.bic)
        for fit in fits:
            axis.plot(
                frequency,
                _background_model(frequency, fit),
                color=background_color(fit.component_count),
                lw=1.7 if fit is selected_fit else 1.05,
                ls="-" if fit is selected_fit else "--",
                label=rf"{background_label(fit.component_count)}; $\mathrm{{BIC}}={fit.bic:.0f}$",
            )
        axis.axvspan(
            1500,
            2800,
            color=data_color("exclusion"),
            alpha=0.12,
            label="Oscillation exclusion",
            zorder=0,
        )
        style_axes(
            axis,
            xlabel=r"Frequency [$\mu$Hz]",
            ylabel=r"PSD [ppm$^2\,\mu$Hz$^{-1}$]",
            title="Background model comparison",
            xscale="log",
            yscale="log",
            grid_axis="both",
            legend=True,
            legend_ncols=2,
        )
        annotate_textbox(axis, rf"Selected: {background_label(selected_fit.component_count)}")
        path = figure_dir / "background_comparison.svg"
        save_figure(
            fig,
            path,
            close=True,
            source="results/stage3/background_models.csv",
            description="H0/H1/H2 exponential-likelihood comparison; minimum-BIC model emphasized.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)

        fig, axis = plt.subplots(figsize=FIGSIZE["double"])
        window_widths = {
            "Q2": 1.0,
            "Q5": 1.0,
            "Q6": 1.0,
            "Q7": 1.0,
            "combined_absolute": 1.6,
            "combined_compressed": 1.25,
        }
        for name, linewidth in window_widths.items():
            window = windows[name]
            label = {
                "combined_absolute": "Absolute time",
                "combined_compressed": "Compressed time",
            }.get(name, name)
            axis.plot(
                window.frequency_uHz,
                window.power,
                color=WINDOW_COLORS[name],
                ls=WINDOW_LINESTYLES[name],
                lw=linewidth,
                label=label,
            )
        style_axes(
            axis,
            xlabel=r"Window frequency [$\mu$Hz]",
            ylabel="Normalized window power",
            title="Kepler sampling-window atlas",
            xlim=(0, 5),
            yscale="log",
            grid_axis="both",
            legend=True,
            legend_loc="upper center",
            legend_ncols=3,
        )
        path = figure_dir / "window_atlas.svg"
        save_figure(
            fig,
            path,
            close=True,
            source="results/stage3/window_atlas.csv",
            description="Four quarters plus physical and compressed-time combination diagnostics.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)

        positive = np.concatenate(
            [grid.power[grid.power > 0] for _, grid in echelle_trials]
        )
        norm = PowerNorm(
            gamma=0.55,
            vmin=float(np.percentile(positive, 2.0)),
            vmax=float(np.percentile(positive, 99.5)),
        )
        fig, axes = plt.subplots(
            1,
            len(echelle_trials),
            figsize=FIGSIZE["triple"],
            sharey=True,
        )
        echelle_cmap = plt.get_cmap("magma").copy()
        echelle_cmap.set_bad("white")
        image = None
        for index, (axis, (trial, grid)) in enumerate(
            zip(axes, echelle_trials, strict=True)
        ):
            image = axis.imshow(
                np.ma.masked_where(grid.power <= 0, grid.power),
                origin="lower",
                aspect="auto",
                extent=(0, trial, grid.radial_orders[0], grid.radial_orders[-1]),
                cmap=echelle_cmap,
                norm=norm,
            )
            style_axes(
                axis,
                xlabel=r"Frequency mod $\Delta\nu$ [$\mu$Hz]",
                title=rf"$\Delta\nu={trial:.3f}\,\mu$Hz",
                grid=False,
                minor=False,
            )
            panel_label(axis, f"({chr(97 + index)})")
        axes[0].set_ylabel("Echelle order")
        if image is not None:
            colorbar = fig.colorbar(image, ax=axes, fraction=0.026, pad=0.02)
            colorbar.set_label("Whitened power")
        path = figure_dir / "echelle_trials.svg"
        save_figure(
            fig,
            path,
            close=True,
            source=(
                "results/stage3/reduced_spectrum.csv",
                "results/stage3/echelle_trials.csv",
            ),
            description="Common normalization and orientation across three conventional trial spacings.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)

        fig, axis = plt.subplots(figsize=FIGSIZE["double"])
        axis.axhspan(
            -1,
            1,
            color=data_color("reference"),
            alpha=0.08,
            label=r"$\pm1\,\mu$Hz band",
            zorder=0,
        )
        markers = {0: "o", 1: "s", 2: "^"}
        for degree in (0, 1, 2):
            subset = [row for row in mode_rows if int(row["angular_degree_l"]) == degree]
            axis.scatter(
                [float(row["reference_frequency_uHz"]) for row in subset],
                [float(row["residual_uHz"]) for row in subset],
                s=30,
                marker=markers[degree],
                label=mode_degree_label(degree),
                color=mode_degree_color(degree),
                edgecolors="black",
                linewidths=0.45,
                zorder=3,
            )
        style_axes(
            axis,
            xlabel=r"Published mode frequency [$\mu$Hz]",
            ylabel=r"Nearest-peak residual [$\mu$Hz]",
            title="Published-mode overlay audit",
            grid_axis="both",
            legend=True,
            legend_ncols=4,
            zero_line=True,
        )
        path = figure_dir / "mode_overlay_audit.svg"
        save_figure(
            fig,
            path,
            close=True,
            source="results/stage3/mode_audit.csv",
            description="All 42 published modes under the frozen nearest-peak matching rule.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)

        fig, axis = plt.subplots(figsize=FIGSIZE["double"])
        sectors = [int(row["sector"]) for row in tess_rows]
        sector_positions = {sector: index for index, sector in enumerate(sectors)}
        marginal = [row for row in tess_rows if row["classification"].startswith("marginal")]
        non_detections = [
            row for row in tess_rows if not row["classification"].startswith("marginal")
        ]
        axis.scatter(
            [sector_positions[int(row["sector"])] for row in non_detections],
            [float(row["envelope_peak_snr"]) for row in non_detections],
            color=data_color("not_detected"),
            s=38,
            marker="o",
            edgecolors="black",
            linewidths=0.5,
            label="Non-detection",
            zorder=3,
        )
        axis.scatter(
            [sector_positions[int(row["sector"])] for row in marginal],
            [float(row["envelope_peak_snr"]) for row in marginal],
            color=data_color("marginal"),
            s=62,
            marker="*",
            edgecolors="0.25",
            linewidths=0.5,
            label="Marginal",
            zorder=4,
        )
        axis.axhline(
            1.20,
            color=data_color("threshold"),
            ls="--",
            lw=1.15,
            label="SNR = 1.20",
        )
        style_axes(
            axis,
            xlabel="TESS sector",
            ylabel="Smoothed envelope peak / background",
            title="TESS single-sector feasibility (no combined detection)",
            grid_axis="both",
            minor=False,
            legend=True,
            legend_loc="lower center",
            legend_ncols=3,
        )
        axis.set_xticks(range(len(sectors)), [str(sector) for sector in sectors])
        annotate_textbox(axis, "1 marginal / 10 not detected", x=0.97, fontsize=8.5)
        path = figure_dir / "tess_sector_feasibility.svg"
        save_figure(
            fig,
            path,
            close=True,
            source="results/stage3/tess_sector_feasibility.csv",
            description="Eleven SPOC sectors assessed independently; no aggregate detection.",
            software_version=SOFTWARE_VERSION,
        )
        paths.append(path)
    return paths


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True, text=True
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unavailable", "dirty": None}
    return {"commit": commit, "dirty": dirty}


def run(config_path: Path, cache_dir: Path, output_dir: Path, figure_dir: Path, *, download: bool) -> dict[str, Any]:
    started = time.monotonic()
    config = load_yaml(config_path)
    manifest_dir = ROOT / "data/manifests/stage2"
    selected_products = acquire(manifest_dir, cache_dir, download=download)
    kepler_rows = [row for row in selected_products if row["mission"] == "Kepler"]
    tess_rows_manifest = [row for row in selected_products if row["mission"] == "TESS"]
    kepler_paths = [cache_dir / "kepler" / row["product_filename"] for row in kepler_rows]

    import lightkurve as lk

    primary_curves = [lk.read(path) for path in kepler_paths]
    primary_lc = lk.LightCurveCollection(primary_curves).stitch()
    teff = float(config["target"]["teff_K"])
    lightkurve_values, _, _ = _lightkurve_globals(primary_lc, teff)
    for quantity, expected in TUTORIAL_VALUES.items():
        tolerance = 0.1 if quantity == "numax" else (0.01 if quantity == "dnu" else 0.02)
        if abs(lightkurve_values[quantity] - expected) > tolerance:
            raise RuntimeError(f"Lightkurve reproduction drift for {quantity}")

    broad_periodogram = primary_lc.to_periodogram(
        normalization="psd", minimum_frequency=100.0, maximum_frequency=8000.0
    )
    frequency = np.asarray(broad_periodogram.frequency.value, dtype=float)
    power = np.asarray(broad_periodogram.power.value, dtype=float) * 1e12
    fits = fit_harvey_models(frequency, power, exclusion_uHz=(1500.0, 2800.0))
    selected_fit = min(fits, key=lambda fit: fit.bic)
    background = _background_model(frequency, selected_fit)
    envelope = estimate_envelope(frequency, power, background)
    separation = estimate_large_separation(
        frequency, power, background, envelope.numax_uHz
    )
    independent_scaling = scaling_relations(envelope.numax_uHz, separation.dnu_uHz, teff)
    independent_values = {
        "numax": envelope.numax_uHz,
        "dnu": separation.dnu_uHz,
        "mass": independent_scaling.mass_solar,
        "radius": independent_scaling.radius_solar,
        "logg": independent_scaling.logg_cgs,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    background_path = output_dir / "background_models.csv"
    background_fields = [
        "model_id", "component_count", "white_noise_ppm2_per_uHz",
        "component_1_amplitude_ppm2_per_uHz", "component_1_characteristic_uHz", "component_1_exponent",
        "component_2_amplitude_ppm2_per_uHz", "component_2_characteristic_uHz", "component_2_exponent",
        "log_residual_rms", "negative_log_likelihood", "aic", "bic", "covariance_condition",
        "parameter_sigma_log", "selected_by_minimum_bic",
    ]
    _write_csv(background_path, background_fields, _background_rows(fits, selected_fit))

    branch_rows: list[dict[str, Any]] = []
    branch_values: dict[str, dict[str, float]] = {}
    for branch_id in ("PP-01", "PP-02", "PP-03", "PP-04"):
        branch_lc = primary_lc if branch_id == "PP-01" else _branch_light_curve(kepler_paths, branch_id)
        values, _, _ = _lightkurve_globals(branch_lc, teff)
        branch_values[branch_id] = values
        branch_rows.append(
            {
                "branch_id": branch_id,
                "cadence_count": len(branch_lc),
                "numax_uHz": _number(values["numax"]),
                "dnu_uHz": _number(values["dnu"]),
                "mass_Msun": _number(values["mass"]),
                "radius_Rsun": _number(values["radius"]),
                "logg_dex_cgs": _number(values["logg"]),
                "selection_used_topology": "false",
                "role": "primary" if branch_id == "PP-01" else "sensitivity",
            }
        )
    branch_values["TA-HARVEY-ACF-v1"] = independent_values
    sensitivity_path = output_dir / "preprocessing_sensitivity.csv"
    _write_csv(
        sensitivity_path,
        ["branch_id", "cadence_count", "numax_uHz", "dnu_uHz", "mass_Msun", "radius_Rsun", "logg_dex_cgs", "selection_used_topology", "role"],
        branch_rows,
    )

    uncertainty_config = config["uncertainty"]
    sigma_numax, sigma_dnu, numax_interval, dnu_interval = _bootstrap_segments(
        primary_curves,
        int(uncertainty_config["resamples"]),
        int(uncertainty_config["master_seed"]),
        float(uncertainty_config["common_grid_step_uHz"]),
    )
    pipeline_ranges = {
        quantity: 0.5 * (max(values[quantity] for values in branch_values.values()) - min(values[quantity] for values in branch_values.values()))
        for quantity in UNITS
    }
    random_scaling_lightkurve = scaling_uncertainty(
        lightkurve_values["numax"], lightkurve_values["dnu"], teff, sigma_numax, sigma_dnu, 77.0
    )
    random_scaling_independent = scaling_uncertainty(
        independent_values["numax"], independent_values["dnu"], teff, sigma_numax, sigma_dnu, 77.0
    )
    random_errors_by_pipeline = {
        "lightkurve_acf2d": {
            "numax": sigma_numax,
            "dnu": sigma_dnu,
            "mass": random_scaling_lightkurve.mass_solar,
            "radius": random_scaling_lightkurve.radius_solar,
            "logg": random_scaling_lightkurve.logg_dex,
        },
        "independent_harvey_acf": {
            "numax": sigma_numax,
            "dnu": sigma_dnu,
            "mass": random_scaling_independent.mass_solar,
            "radius": random_scaling_independent.radius_solar,
            "logg": random_scaling_independent.logg_dex,
        },
    }

    baseline_rows: list[dict[str, Any]] = []
    for pipeline_id, values in (
        ("lightkurve_acf2d", lightkurve_values),
        ("independent_harvey_acf", independent_values),
    ):
        for quantity, value in values.items():
            reference, reference_minus, reference_plus, reference_role = REFERENCES[quantity]
            reference_sigma = 0.5 * (reference_minus + reference_plus)
            random_error = random_errors_by_pipeline[pipeline_id][quantity]
            pipeline_error = pipeline_ranges[quantity]
            total = quadrature_uncertainty(random_error, pipeline_error, reference_sigma)
            residual = value - reference
            status = (
                "within_joint_uncertainty"
                if abs(residual) <= total
                else "documented_convention_or_model_difference"
            )
            baseline_rows.append(
                {
                    "result_id": f"{pipeline_id}-{quantity}",
                    "pipeline": pipeline_id,
                    "quantity": quantity,
                    "value": _number(value),
                    "unit": UNITS[quantity],
                    "pipeline_reported_uncertainty": "not_reported" if pipeline_id == "lightkurve_acf2d" else "bootstrap_reported_separately",
                    "random_uncertainty": _number(random_error),
                    "pipeline_choice_uncertainty": _number(pipeline_error),
                    "reference_value": _number(reference),
                    "reference_uncertainty_minus": _number(reference_minus),
                    "reference_uncertainty_plus": _number(reference_plus),
                    "reference_role": reference_role,
                    "residual": _number(residual),
                    "joint_uncertainty": _number(total),
                    "agreement_status": status,
                }
            )
    baseline_path = output_dir / "rudy_baseline.csv"
    baseline_fields = [
        "result_id", "pipeline", "quantity", "value", "unit", "pipeline_reported_uncertainty",
        "random_uncertainty", "pipeline_choice_uncertainty", "reference_value",
        "reference_uncertainty_minus", "reference_uncertainty_plus", "reference_role", "residual",
        "joint_uncertainty", "agreement_status",
    ]
    _write_csv(baseline_path, baseline_fields, baseline_rows)

    comparison_rows: list[dict[str, Any]] = []
    for quantity in UNITS:
        comparison_rows.append(
            {
                "quantity": quantity,
                "unit": UNITS[quantity],
                "lightkurve_value": _number(lightkurve_values[quantity]),
                "independent_value": _number(independent_values[quantity]),
                "difference_independent_minus_lightkurve": _number(independent_values[quantity] - lightkurve_values[quantity]),
                "tutorial_context_value": _number(TUTORIAL_VALUES[quantity]),
                "lightkurve_context_residual": _number(lightkurve_values[quantity] - TUTORIAL_VALUES[quantity]),
                "convention_reconciliation": (
                    "same one-sided PSD and uHz axis; Lightkurve uses logmedian flatten plus ACF2D; independent uses minimum-BIC Harvey whitening plus one-dimensional FFT ACF"
                ),
                "status": "reconciled_distinct_estimators",
            }
        )
    comparison_path = output_dir / "pipeline_comparison.csv"
    _write_csv(
        comparison_path,
        ["quantity", "unit", "lightkurve_value", "independent_value", "difference_independent_minus_lightkurve", "tutorial_context_value", "lightkurve_context_residual", "convention_reconciliation", "status"],
        comparison_rows,
    )

    uncertainty_rows: list[dict[str, Any]] = []
    for quantity in UNITS:
        reference_sigma = 0.5 * (REFERENCES[quantity][1] + REFERENCES[quantity][2])
        random_error = random_errors_by_pipeline["independent_harvey_acf"][quantity]
        total = quadrature_uncertainty(random_error, pipeline_ranges[quantity], reference_sigma)
        interval = numax_interval if quantity == "numax" else (dnu_interval if quantity == "dnu" else (math.nan, math.nan))
        uncertainty_rows.append(
            {
                "quantity": quantity,
                "unit": UNITS[quantity],
                "random_bootstrap_sigma": _number(random_error),
                "bootstrap_p16": "" if math.isnan(interval[0]) else _number(interval[0]),
                "bootstrap_p84": "" if math.isnan(interval[1]) else _number(interval[1]),
                "pipeline_choice_half_range": _number(pipeline_ranges[quantity]),
                "reference_interval_half_width": _number(reference_sigma),
                "combined_joint_uncertainty": _number(total),
                "resamples": int(uncertainty_config["resamples"]),
                "master_seed": int(uncertainty_config["master_seed"]),
            }
        )
    uncertainty_path = output_dir / "uncertainty_budget.csv"
    _write_csv(
        uncertainty_path,
        ["quantity", "unit", "random_bootstrap_sigma", "bootstrap_p16", "bootstrap_p84", "pipeline_choice_half_range", "reference_interval_half_width", "combined_joint_uncertainty", "resamples", "master_seed"],
        uncertainty_rows,
    )

    window_rows, windows = _window_products(
        primary_curves,
        kepler_rows,
        float(config["window"]["cadence_seconds"]),
        float(config["window"]["maximum_alias_frequency_uHz"]),
    )
    window_path = output_dir / "window_atlas.csv"
    _write_csv(
        window_path,
        ["window_id", "sample_count", "duration_days", "duty_cycle", "resolution_uHz", "time_treatment", "alias_1_uHz", "alias_1_power", "alias_2_uHz", "alias_2_power", "alias_3_uHz", "alias_3_power", "assessment"],
        window_rows,
    )

    references = _mode_references(ROOT / config["mode_audit"]["source"])
    whitened = power / background
    matches = audit_mode_peaks(
        frequency,
        whitened,
        references,
        separation.dnu_uHz,
        search_half_width_uHz=float(config["mode_audit"]["peak_search_half_width_uHz"]),
    )
    mode_rows = [
        {
            "row_id": match.row_id,
            "radial_order_n": match.radial_order_n,
            "angular_degree_l": match.angular_degree_l,
            "reference_frequency_uHz": _number(match.reference_frequency_uHz),
            "measured_peak_uHz": _number(match.measured_peak_uHz),
            "residual_uHz": _number(match.residual_uHz),
            "normalized_residual": _number(match.normalized_residual),
            "echelle_order": match.echelle_order,
            "published_to_echelle_order_offset": match.order_offset,
            "match_rule": "highest_whitened_ordinate_within_2.5_uHz",
        }
        for match in matches
    ]
    mode_path = output_dir / "mode_audit.csv"
    _write_csv(
        mode_path,
        ["row_id", "radial_order_n", "angular_degree_l", "reference_frequency_uHz", "measured_peak_uHz", "residual_uHz", "normalized_residual", "echelle_order", "published_to_echelle_order_offset", "match_rule"],
        mode_rows,
    )

    echelle_rows: list[dict[str, Any]] = []
    echelle_trials: list[tuple[float, Any]] = []
    echelle_config = config["echelle"]
    for trial in (float(value) for value in echelle_config["trial_dnu_uHz"]):
        grid = echelle_grid(
            frequency,
            whitened,
            trial,
            frequency_range_uHz=tuple(float(value) for value in echelle_config["frequency_range_uHz"]),
            phase_bins=int(echelle_config["phase_bins"]),
            phase_smoothing_bins=float(echelle_config["phase_smoothing_bins"]),
        )
        echelle_trials.append((trial, grid))
        echelle_rows.append(
            {
                "trial_id": f"ECH-{trial:.3f}",
                "dnu_uHz": _number(trial),
                "frequency_min_uHz": echelle_config["frequency_range_uHz"][0],
                "frequency_max_uHz": echelle_config["frequency_range_uHz"][1],
                "phase_bins": echelle_config["phase_bins"],
                "radial_order_min": int(grid.radial_orders.min()),
                "radial_order_max": int(grid.radial_orders.max()),
                "orientation": grid.orientation,
                "phase_boundary": grid.phase_boundary,
                "smoothing": f"Gaussian phase sigma={echelle_config['phase_smoothing_bins']} bins; circular wrap",
            }
        )
    echelle_path = output_dir / "echelle_trials.csv"
    _write_csv(
        echelle_path,
        ["trial_id", "dnu_uHz", "frequency_min_uHz", "frequency_max_uHz", "phase_bins", "radial_order_min", "radial_order_max", "orientation", "phase_boundary", "smoothing"],
        echelle_rows,
    )

    reduced_frequency = np.arange(1500.0, 2700.0001, 0.2)
    reduced_power = np.interp(reduced_frequency, frequency, power)
    reduced_background = np.interp(reduced_frequency, frequency, background)
    smooth_snr = gaussian_filter1d(reduced_power / reduced_background, 35.0 / 0.2)
    spectrum_rows = [
        {
            "frequency_uHz": _number(freq),
            "power_ppm2_per_uHz": _number(raw),
            "background_ppm2_per_uHz": _number(bg),
            "whitened_power": _number(raw / bg),
            "smoothed_whitened_power": _number(smooth),
        }
        for freq, raw, bg, smooth in zip(reduced_frequency, reduced_power, reduced_background, smooth_snr, strict=True)
    ]
    spectrum_path = output_dir / "reduced_spectrum.csv"
    _write_csv(
        spectrum_path,
        ["frequency_uHz", "power_ppm2_per_uHz", "background_ppm2_per_uHz", "whitened_power", "smoothed_whitened_power"],
        spectrum_rows,
    )

    tess_rows: list[dict[str, Any]] = []
    for row in tess_rows_manifest:
        curve = lk.read(cache_dir / "tess" / row["product_filename"]).normalize()
        periodogram = curve.to_periodogram(
            normalization="psd", minimum_frequency=1500.0, maximum_frequency=2700.0
        )
        sector_frequency = np.asarray(periodogram.frequency.value, dtype=float)
        sector_power = np.asarray(periodogram.power.value, dtype=float)
        step = float(np.median(np.diff(sector_frequency)))
        low = float(np.median(sector_power[sector_frequency < 1700.0])) / math.log(2)
        high = float(np.median(sector_power[sector_frequency > 2550.0])) / math.log(2)
        sector_background = np.exp(
            np.interp(sector_frequency, [1600.0, 2625.0], [math.log(low), math.log(high)])
        )
        sector_envelope = estimate_envelope(
            sector_frequency,
            sector_power,
            sector_background,
            search_uHz=(1800.0, 2500.0),
            smoothing_uHz=35.0,
        )
        sector_separation = estimate_large_separation(
            sector_frequency,
            sector_power,
            sector_background,
            sector_envelope.numax_uHz,
            half_width_uHz=275.0,
            smoothing_uHz=max(0.5, step),
        )
        duration = float(curve.time.value.max() - curve.time.value.min())
        expected_cadences = duration * 86400.0 / float(row["cadence_seconds"])
        classification = classify_tess_sector(
            sector_envelope.peak_snr,
            sector_envelope.numax_uHz,
            sector_separation.dnu_uHz,
            sector_separation.autocorrelation_peak,
            reference_numax_uHz=lightkurve_values["numax"],
            reference_dnu_uHz=lightkurve_values["dnu"],
        )
        tess_rows.append(
            {
                "sector": int(row["segment_number"]),
                "product_key": row["product_key"],
                "author": row["author"],
                "cadence_seconds": row["cadence_seconds"],
                "duration_days": _number(duration),
                "resolution_uHz": _number(11.574074074074074 / duration),
                "duty_cycle": _number(len(curve) / expected_cadences),
                "candidate_numax_uHz": _number(sector_envelope.numax_uHz),
                "envelope_peak_snr": _number(sector_envelope.peak_snr),
                "candidate_dnu_uHz": _number(sector_separation.dnu_uHz),
                "dnu_autocorrelation_peak": _number(sector_separation.autocorrelation_peak),
                "classification": classification,
                "combination_decision": "do_not_combine_for_detection_at_G3",
            }
        )
    tess_path = output_dir / "tess_sector_feasibility.csv"
    _write_csv(
        tess_path,
        ["sector", "product_key", "author", "cadence_seconds", "duration_days", "resolution_uHz", "duty_cycle", "candidate_numax_uHz", "envelope_peak_snr", "candidate_dnu_uHz", "dnu_autocorrelation_peak", "classification", "combination_decision"],
        tess_rows,
    )

    figure_paths = _plot_products(
        figure_dir, frequency, power, background, fits, windows, echelle_trials, mode_rows, tess_rows
    )
    output_paths = [
        background_path, sensitivity_path, baseline_path, comparison_path, uncertainty_path,
        window_path, mode_path, echelle_path, spectrum_path, tess_path, *figure_paths,
    ]
    config_hash = configuration_hash(config_path)
    manifest = {
        "schema_version": 1,
        "run_id": config["experiment_id"],
        "software_version": SOFTWARE_VERSION,
        "config_path": repository_relative_posix(config_path, ROOT),
        "config_sha256": config_hash,
        "command": "uv run --extra astronomy python workflows/run_stage3_classical.py --cache-dir <external-cache> [--download]",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "lightkurve": version("lightkurve"),
            "astropy": version("astropy"),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "matplotlib": version("matplotlib"),
        },
        "git": _git_state(),
        "random": {
            "master_seed": uncertainty_config["master_seed"],
            "resamples": uncertainty_config["resamples"],
            "namespace": "stage3-monthly-segment-bootstrap",
        },
        "inputs": [
            {
                "product_key": row["product_key"],
                "mission": row["mission"],
                "segment_number": int(row["segment_number"]),
                "author": row["author"],
                "filename": row["product_filename"],
                "size_bytes": int(row["size_bytes"]),
                "sha256": row["sha256"],
            }
            for row in selected_products
        ],
        "input_policy": "raw FITS payloads checksum-verified in external cache and not redistributed",
        "outputs": [
            {
                "path": repository_relative_posix(path, ROOT),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in output_paths
        ],
        "observational_conventions": {
            "frequency_unit": "uHz",
            "power_unit": "ppm2/uHz",
            "sidedness": "one-sided",
            "lightkurve_normalization": "psd",
            "background_selection": "minimum BIC among H0/H1/H2",
        },
        "plot_style": {
            "style_id": STYLE_ID,
            "module": "topoastero.style",
            "context": "paper",
            "use_tex": False,
            "primary_format": "svg",
        },
        "summary": {
            "lightkurve": lightkurve_values,
            "independent": independent_values,
            "background_model": f"BG-H{selected_fit.component_count}",
            "mode_count": len(mode_rows),
            "mode_order_offsets": dict(Counter(int(row["published_to_echelle_order_offset"]) for row in mode_rows)),
            "tess_classifications": dict(Counter(row["classification"] for row in tess_rows)),
        },
        "topology_used": False,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    manifest_path = output_dir / "run_manifest.json"
    write_json_lf(manifest_path, manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/stage3_classical.yaml")
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--output-dir", default="results/stage3")
    parser.add_argument("--figure-dir", default="reports/stage3/figures")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    manifest = run(
        ROOT / args.config,
        Path(args.cache_dir),
        ROOT / args.output_dir,
        ROOT / args.figure_dir,
        download=args.download,
    )
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
