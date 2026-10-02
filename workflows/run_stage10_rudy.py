"""Reacquire public Rudy products and reproduce the complete Stage 10 benchmark.

Raw FITS files belong in an external cache. All paths in generated evidence are
repository relative. This workflow never edits earlier-stage science results.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from acquire_stage3_inputs import acquire
from run_stage3_classical import _lightkurve_globals
from scipy.ndimage import gaussian_filter1d

from topoastero import __version__
from topoastero.classical import (
    audit_mode_peaks,
    classify_tess_sector,
    estimate_envelope,
    estimate_large_separation,
    fit_harvey_models,
    harvey_background,
    scaling_relations,
    spectral_window,
    strongest_window_aliases,
)
from topoastero.config import configuration_hash, load_yaml
from topoastero.echelle_topology import (
    five_point_frequency_ratios,
    make_echelle_field,
    score_echelle,
    trial_spacing_grid,
)
from topoastero.portability import write_csv_lf, write_json_lf
from topoastero.provenance import sha256_file
from topoastero.rudy_benchmark import (
    added_noise_sigma,
    gaussian_psd_realization,
    holm_adjust,
    integrate_cadences,
    linear_interpolation_response,
    monte_carlo_tail,
    rebin_spectrum,
    spectrum_diagnostics,
    weighted_segment_bootstrap,
)
from topoastero.spectral_topology import (
    autocorrelation_spacing_scores,
    comb_score_scan,
    localized_peak_persistence,
    normalize_spectrum,
    prominence_matches,
    psps_spacing_scores,
)
from topoastero.tda import localized_records

ROOT = Path(__file__).parents[1]
CADENCE = 58.84876286
STATISTICS = (
    "classical_envelope_snr", "peak_max_lifetime", "comb_max_score",
    "echelle_max_combined", "echelle_max_graph", "acf_max_score", "psps_max_score",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def table(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty evidence table: {path}")
    write_csv_lf(path, rows, fieldnames=list(rows[0]))


def seal(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def processed_months(paths: list[Path], branch: str) -> list[Any]:
    import lightkurve as lk

    curves = []
    for path in paths:
        if branch == "PP-01":
            curve = lk.read(path).remove_nans().normalize()
        elif branch == "PP-02":
            curve = lk.KeplerLightCurve.read(path, flux_column="pdcsap_flux", quality_bitmask=None)
            curve = curve[curve.quality == 0].remove_nans().remove_outliers(sigma=5).normalize()
        elif branch == "PP-03":
            curve = lk.KeplerLightCurve.read(path, flux_column="sap_flux", quality_bitmask="default")
            curve = curve.remove_nans().remove_outliers(sigma=5).flatten(window_length=1001).normalize()
        elif branch == "PP-04":
            curve = lk.KeplerLightCurve.read(path, flux_column="pdcsap_flux", quality_bitmask="hardest")
            curve = curve.remove_nans().remove_outliers(sigma=5).normalize()
        else:
            raise ValueError(f"unknown Kepler branch {branch}")
        curves.append(curve)
    return curves


def periodogram(curve: Any, low: float = 100.0, high: float = 8000.0) -> tuple[Any, Any]:
    pg = curve.to_periodogram(normalization="psd", minimum_frequency=low, maximum_frequency=high)
    frequency, power = np.asarray(pg.frequency.value), np.asarray(pg.power.value) * 1e12
    if not np.all(np.isfinite(power)) or np.any(power <= 0):
        raise ValueError("nonpositive or nonfinite mission PSD; no silent clipping allowed")
    return frequency, power


def scan_echelle(frequency: Any, power: Any, background: Any, anchor: float, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    smoothed = gaussian_filter1d(power, cfg["topology"]["peak_smoothing_uHz"] / np.median(np.diff(frequency)), mode="nearest")
    rows = []
    trials = trial_spacing_grid(anchor, fractions=tuple(cfg["topology"]["echelle_trial_fractions"]))
    for family, spacing in trials:
        field = make_echelle_field(frequency, smoothed, background, spacing_uHz=spacing, phase_bins=cfg["topology"]["echelle_phase_bins"])
        score, _, _ = score_echelle(field)
        rows.append({"alias_family": family, **asdict(score)})
    return rows


def full_diagnostics(frequency: Any, power: Any, background: Any, cfg: dict[str, Any], *, normalization: str = "log_ratio", smoothing: float | None = None) -> dict[str, float]:
    values = spectrum_diagnostics(
        frequency, power, background, normalization=normalization,
        peak_smoothing_uHz=cfg["topology"]["peak_smoothing_uHz"] if smoothing is None else smoothing,
        background_sigma_fraction=cfg["topology"]["background_sigma_fraction"],
        comb_trials_uHz=np.linspace(*cfg["topology"]["comb_trials_uHz"]),
        search_uHz=tuple(cfg["classical"]["envelope_search_uHz"]),
    )
    return values


def extra_statistics(frequency: Any, power: Any, background: Any, diagnostic: dict[str, float], cfg: dict[str, Any]) -> dict[str, float]:
    rows = scan_echelle(frequency, power, background, diagnostic["classical_dnu_uHz"], cfg)
    trials = np.linspace(*cfg["topology"]["comb_trials_uHz"])
    ratio = gaussian_filter1d(power, cfg["topology"]["peak_smoothing_uHz"] / np.median(np.diff(frequency)), mode="nearest") / background
    return {
        **diagnostic,
        "echelle_max_combined": max(row["combined"] for row in rows),
        "echelle_max_graph": max(row["graph_only"] for row in rows),
        "acf_max_score": float(np.max(autocorrelation_spacing_scores(frequency, ratio, trials))),
        "psps_max_score": float(np.max(psps_spacing_scores(frequency, ratio, trials))),
    }


def matched_realizations(curve: Any, fit: Any, broad_frequency: Any, broad_power: Any, grid: Any, background: Any, cfg: dict[str, Any], results: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Stationary Gaussian draws on a full cadence grid, sampled at the real window.

    White-noise LS density scales as full span / retained exposure. Correct the
    generative density by the measured cadence-mask duty; then apply the same
    native Fourier frequency grid, rebin and smoothing as to the observations.
    """
    import lightkurve as lk

    time = np.asarray(curve.time.value)
    duration_seconds = (time[-1] - time[0]) * 86400
    count = int(np.ceil(duration_seconds / CADENCE)) + 2
    uniform_time = time[0] + np.arange(count) * CADENCE / 86400
    fft_frequency = np.fft.rfftfreq(count, CADENCE) * 1e6
    window = spectral_window(time, CADENCE)
    interpolation_response = linear_interpolation_response(fft_frequency, time, CADENCE)
    null_density = harvey_background(fft_frequency, fit.white_noise_ppm2_per_uHz, fit.components) * window.duty_cycle / interpolation_response
    # Smooth enough to preserve the envelope/comb but avoid conditioning on raw spikes.
    predictive_density = np.interp(fft_frequency, broad_frequency, gaussian_filter1d(broad_power, 2.0 / np.median(np.diff(broad_frequency)))) * window.duty_cycle / interpolation_response
    nulls, predictive = [], []
    seed = cfg["master_seed"]
    for kind, density, repetitions, offset, rows in (
        ("background", null_density, cfg["nulls"]["realizations"], cfg["nulls"]["seed_offset"], nulls),
        ("conditional_stochastic", predictive_density, cfg["uncertainty"]["stochastic_replicates"], cfg["uncertainty"]["stochastic_seed_offset"], predictive),
    ):
        for index in range(repetitions):
            draw_seed = seed + offset + index
            uniform_flux = gaussian_psd_realization(density, sample_count=count, cadence_seconds=CADENCE, seed=draw_seed)
            sampled_flux = np.interp(time, uniform_time, uniform_flux)
            simulated = lk.LightCurve(time=curve.time, flux=1 + sampled_flux / 1e6)
            frequency, power = periodogram(simulated, 1499.0, 2801.0)
            reduced = rebin_spectrum(frequency, power, grid)
            diagnostic = full_diagnostics(grid, reduced, background, cfg)
            if kind == "background":
                diagnostic = extra_statistics(grid, reduced, background, diagnostic, cfg)
            rows.append({"draw": index, "seed": draw_seed, "model": kind, **diagnostic,
                         "mean_ratio": float(np.mean(reduced / background))})
            if (index + 1) % 16 == 0:
                print(f"{kind}: {index + 1}/{repetitions}", flush=True)
    table(results / "null_draws.csv", nulls)
    table(results / "stochastic_draws.csv", predictive)
    return nulls, predictive


def tess_feasibility(curve: Any, cfg: dict[str, Any]) -> dict[str, Any]:
    """The exact native-grid Stage 3 continuum/search/threshold conventions."""
    frequency, power = periodogram(curve, 1500.0, 2700.0)
    step = float(np.median(np.diff(frequency)))
    low = float(np.median(power[frequency < 1700])) / np.log(2)
    high = float(np.median(power[frequency > 2550])) / np.log(2)
    background = np.exp(np.interp(frequency, [1600, 2625], np.log([low, high])))
    envelope = estimate_envelope(frequency, power, background, search_uHz=(1800.0, 2500.0))
    spacing = estimate_large_separation(frequency, power, background, envelope.numax_uHz, smoothing_uHz=max(0.5, step))
    classification = classify_tess_sector(envelope.peak_snr, envelope.numax_uHz, spacing.dnu_uHz, spacing.autocorrelation_peak, reference_numax_uHz=cfg["transfer"]["feasibility_reference_numax_uHz"], reference_dnu_uHz=cfg["transfer"]["feasibility_reference_dnu_uHz"])
    return {"feasibility_numax_uHz": envelope.numax_uHz, "feasibility_dnu_uHz": spacing.dnu_uHz, "feasibility_envelope_snr": envelope.peak_snr, "feasibility_acf_peak": spacing.autocorrelation_peak, "classification": classification}


def tess_transfer(months: list[Any], kepler_rows: list[dict[str, str]], tess_rows: list[dict[str, str]], cache: Path, cfg: dict[str, Any], results: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import lightkurve as lk

    tess_results, curves = [], []
    grid = np.arange(1500.0, 2800.0001, cfg["classical"]["grid_step_uHz"])
    for row in tess_rows:
        curve = lk.read(cache / "tess" / row["product_filename"]).remove_nans().normalize()
        frequency, power = periodogram(curve, 500.0, 4000.0)
        reduced = rebin_spectrum(frequency, power, grid)
        # Keep the Stage 3 sideband continuum estimator, not a Kepler-trained fit.
        low = float(np.median(power[(frequency > 1300) & (frequency < 1500)])) / np.log(2)
        high = float(np.median(power[(frequency > 2800) & (frequency < 3200)])) / np.log(2)
        background = np.exp(np.interp(grid, [1400, 3000], np.log([low, high])))
        diagnostic = full_diagnostics(grid, reduced, background, cfg)
        feasibility = tess_feasibility(curve, cfg)
        window = spectral_window(np.asarray(curve.time.value), 120.0)
        white = float(np.median(power[(frequency > 3200) & (frequency < 4000)])) / np.log(2)
        record = {"sector": int(row["segment_number"]), "cadences": len(curve), "duration_days": float(curve.time.value[-1] - curve.time.value[0]), "duty_cycle": window.duty_cycle, "white_psd": white, **diagnostic, **feasibility, "role": "actual_single_sector_context_not_confirmation"}
        tess_results.append(record)
        curves.append((record, curve))
    table(results / "tess_sectors.csv", tess_results)

    source_curves = [curve for curve, row in zip(months, kepler_rows, strict=True) if int(row["segment_number"]) == cfg["transfer"]["source_quarter"]]
    source = lk.LightCurveCollection(source_curves).stitch()
    source_time = (np.asarray(source.time.value) - source.time.value[0]) * 86400
    source_flux = (np.asarray(source.flux.value) - 1) * 1e6
    transferred = []
    transfer = cfg["transfer"]
    for actual, target in curves:
        target_time = (np.asarray(target.time.value) - target.time.value[0]) * 86400
        for offset_days in transfer["source_start_offsets_days"]:
            for duration in transfer["durations_days"]:
                centers = target_time[target_time <= duration * 86400] + offset_days * 86400
                integrated, coverage = integrate_cadences(source_time, source_flux, centers, exposure_seconds=transfer["cadence_seconds"], maximum_gap_seconds=transfer["maximum_source_gap_seconds"])
                for fraction in transfer["additional_duty_fractions"]:
                    mask_seed = cfg["master_seed"] + transfer["synthetic_window_seed_offset"] + actual["sector"] * 100 + int(offset_days) + int(duration * 10) + int(fraction * 1000)
                    valid = coverage & (np.random.default_rng(mask_seed).random(centers.size) < fraction)
                    times = centers[valid] / 86400
                    base_flux = integrated[valid]
                    if len(times) < 100:
                        raise ValueError("too few supported cadences in transfer cell")
                    curve = lk.LightCurve(time=times, flux=1 + base_flux / 1e6)
                    native_frequency, native_power = periodogram(curve, 500, 4000)
                    source_white = float(np.median(native_power[(native_frequency > 3200) & (native_frequency < 4000)])) / np.log(2)
                    actual_duty = spectral_window(times, 120).duty_cycle
                    sigma = added_noise_sigma(actual["white_psd"], source_white, 120, actual_duty)
                    for factor in transfer["noise_variance_factors"]:
                        draw_seed = mask_seed + transfer["noise_seed_offset"] + int(factor * 100)
                        noisy = base_flux + np.sqrt(factor) * sigma * np.random.default_rng(draw_seed).normal(size=base_flux.size)
                        curve = lk.LightCurve(time=times, flux=1 + noisy / 1e6)
                        frequency, power = periodogram(curve, 500, 4000)
                        reduced = rebin_spectrum(frequency, power, grid)
                        low = float(np.median(power[(frequency > 1300) & (frequency < 1500)])) / np.log(2)
                        high = float(np.median(power[(frequency > 2800) & (frequency < 3200)])) / np.log(2)
                        background = np.exp(np.interp(grid, [1400, 3000], np.log([low, high])))
                        diagnostic = full_diagnostics(grid, reduced, background, cfg)
                        feasibility = tess_feasibility(curve, cfg)
                        transferred.append({"sector_window": actual["sector"], "source_quarter": transfer["source_quarter"], "source_offset_days": offset_days, "requested_duration_days": duration, "duration_days": float(times[-1] - times[0]), "additional_duty_fraction": fraction, "duty_cycle": actual_duty, "cadences": len(times), "coverage_lost_fraction": float(1 - np.mean(coverage)), "noise_variance_factor": factor, "noise_sigma_ppm": float(np.sqrt(factor) * sigma), "noise_seed": draw_seed, **diagnostic, **feasibility, "meaning": "conditional_same_star_degradation_not_independent_realizations"})
        print(f"TESS window sector {actual['sector']}: transfer complete", flush=True)
    table(results / "kepler_to_tess.csv", transferred)
    return tess_results, transferred


def run(config_path: Path, cache: Path, output: Path, *, download: bool, figures: bool = True) -> dict[str, Any]:
    import lightkurve as lk
    from astropy.io import fits
    from lightkurve.utils import KeplerQualityFlags, TessQualityFlags

    cfg = load_yaml(config_path)
    if cfg["run_id"] != "TA-S10-RUDY-R001" or cfg["software_version"] != f"TopoAstero-{__version__}":
        raise ValueError("configuration/software identity mismatch")
    g7 = json.loads((ROOT / "reports/stage7/G7_ACCEPTANCE.json").read_text())
    g8 = json.loads((ROOT / "reports/stage8/G8_ACCEPTANCE.json").read_text())
    g9 = json.loads((ROOT / "reports/stage9/G9_ACCEPTANCE.json").read_text())
    if g7["decision"] != "drop" or g8["decision"] != "geometry_only":
        raise ValueError("prior gates changed; register a revised Stage 10 protocol")
    products = acquire(ROOT / "data/manifests/stage2", cache, download=download)
    results = output / "results/stage10"
    results.mkdir(parents=True, exist_ok=True)
    reports = output / "reports/stage10"
    reports.mkdir(parents=True, exist_ok=True)
    kepler = [row for row in products if row["mission"] == "Kepler"]
    tess = [row for row in products if row["mission"] == "TESS"]
    paths = [cache / "kepler" / row["product_filename"] for row in kepler]
    product_capsule = []
    for row in products:
        with fits.open(cache / row["mission"].lower() / row["product_filename"], memmap=False) as hdus:
            header = hdus[1].header
            record = {key: row[key] for key in ("product_key", "mission", "stable_star_id", "segment_number", "product_filename", "data_uri", "sha256", "size_bytes", "cadence_seconds", "exposure_seconds", "flux_column", "quality_column", "bjd_reference", "time_system", "time_unit")}
            record["FITS_BJDREFI"] = header.get("BJDREFI")
            record["FITS_BJDREFF"] = header.get("BJDREFF")
            product_capsule.append(record)
    capsule_inputs = ["configs/stage10_rudy.yaml", *cfg["inputs"].values()]
    capsule_inputs = [value for value in capsule_inputs if isinstance(value, str) and (ROOT / value).is_file()]
    capsule_inputs += ["reports/stage7/G7_ACCEPTANCE.json", "reports/stage8/G8_ACCEPTANCE.json", "reports/stage9/G9_ACCEPTANCE.json", "src/topoastero/style.py", "src/topoastero/rudy_benchmark.py", "workflows/run_stage10_rudy.py", "uv.lock"]
    capsule = {"run_id": cfg["run_id"], "config_sha256": configuration_hash(config_path), "product_count": len(products), "products": product_capsule, "inputs": [seal(ROOT, name) for name in dict.fromkeys(capsule_inputs)], "quality_masks": {"Kepler_default": KeplerQualityFlags.DEFAULT_BITMASK, "Kepler_hardest": KeplerQualityFlags.HARDEST_BITMASK, "TESS_default": TessQualityFlags.DEFAULT_BITMASK, "PP-02": "quality == 0"}, "preprocessing_selection_used_topology": False, "population_spectra_used": False, "final_holdout_used": False, "delay_decision": g7["decision"], "echelle_decision": g8["decision"], "G9_status": g9["status"], "raw_payloads_redistributed": False}
    write_json_lf(results / "benchmark_capsule.json", capsule)
    grid = np.arange(*cfg["classical"]["reduced_range_uHz"], cfg["classical"]["grid_step_uHz"])
    # Include the registered upper endpoint while avoiding machine-dependent arange length.
    grid = np.linspace(1500.0, 2800.0, 6501)
    branch_data, branches, audit_rows, backgrounds, sampling, all_spectra = {}, [], [], [], [], []
    primary_months, primary_curve = [], None
    primary_fit, primary_frequency, primary_power = None, None, None
    for branch in cfg["preprocessing"]["kepler_branches"]:
        months = processed_months(paths, branch)
        curve = lk.LightCurveCollection(months).stitch()
        tutorial, _, _ = _lightkurve_globals(curve, cfg["classical"]["teff_K"])
        frequency, power = periodogram(curve)
        models = fit_harvey_models(frequency, power, exclusion_uHz=tuple(cfg["classical"]["background_exclusion_uHz"]))
        selected = min(models, key=lambda fit: fit.bic)
        reduced = rebin_spectrum(frequency, power, grid)
        continuum = harvey_background(grid, selected.white_noise_ppm2_per_uHz, selected.components)
        diagnostic = full_diagnostics(grid, reduced, continuum, cfg)
        branch_data[branch] = {"curve": curve, "months": months, "frequency": frequency, "power": power, "reduced": reduced, "models": models, "selected": selected, "background": continuum}
        branch_scaling = scaling_relations(diagnostic["classical_numax_uHz"], diagnostic["classical_dnu_uHz"], cfg["classical"]["teff_K"])
        branches.append({"branch_id": branch, "cadences": len(curve), "background_components": selected.component_count, **diagnostic, **{f"tutorial_{key}": value for key, value in tutorial.items()}, **branch_scaling._asdict(), "role": "primary" if branch == "PP-01" else "sensitivity"})
        for row, month in zip(kepler, months, strict=True):
            sampling.append({"branch_id": branch, "product_key": row["product_key"], "quarter": int(row["segment_number"]), "source_rows": int(row["row_count"]), "retained_cadences": len(month), "relative_flux_median": float(np.median(month.flux.value)), "time_start": float(month.time.value[0]), "time_stop": float(month.time.value[-1]), "BJD_reference": int(float(row["bjd_reference"])), "absolute_timestamps_preserved": True})
        for fit in models:
            backgrounds.append({"branch_id": branch, "model_id": f"H{fit.component_count}", "selected": fit == selected, **asdict(fit)})
            bg = harvey_background(grid, fit.white_noise_ppm2_per_uHz, fit.components)
            for normalization in cfg["topology"]["normalizations"]:
                values = full_diagnostics(grid, reduced, bg, cfg, normalization=normalization)
                audit_rows.append({"branch_id": branch, "background_id": f"H{fit.component_count}", "normalization": normalization, "factor": "factorial", "factor_value": "registered", **values})
        for factor, choices in (("background_scale", cfg["robustness"]["background_factors"]), ("peak_smoothing_uHz", cfg["robustness"]["peak_smoothing_sensitivities_uHz"]), ("resolution_uHz", cfg["robustness"]["resolution_sensitivities_uHz"])):
            for choice in choices:
                axis, observed, bg = grid, reduced, continuum
                if factor == "resolution_uHz":
                    axis = np.linspace(1500, 2800, round(1300 / choice) + 1)
                    observed = rebin_spectrum(frequency, power, axis)
                    bg = harvey_background(axis, selected.white_noise_ppm2_per_uHz, selected.components)
                if factor == "background_scale":
                    bg = bg * choice
                values = full_diagnostics(axis, observed, bg, cfg, smoothing=choice if factor == "peak_smoothing_uHz" else None)
                audit_rows.append({"branch_id": branch, "background_id": f"H{selected.component_count}", "normalization": "log_ratio", "factor": factor, "factor_value": choice, **values})
        for index, value in enumerate(grid):
            all_spectra.append({"branch_id": branch, "frequency_uHz": value, "power_ppm2_per_uHz": reduced[index], "background_ppm2_per_uHz": continuum[index]})
        if branch == "PP-01":
            primary_months, primary_curve = months, curve
            primary_fit, primary_frequency, primary_power = selected, frequency, power
        print(f"{branch}: classical and all registered sensitivities complete", flush=True)
    table(results / "classical_branches.csv", branches)
    table(results / "robustness.csv", audit_rows)
    table(results / "sampling_audit.csv", sampling)
    write_json_lf(results / "background_models.json", {"models": backgrounds, "selection": "minimum_BIC_descriptive"})
    table(results / "branch_spectra.csv", all_spectra)
    primary = branch_data["PP-01"]
    broad_grid = np.arange(101.0, 7999.0, 2.0)
    broad_reduced = rebin_spectrum(primary["frequency"], primary["power"], broad_grid)
    broad_rows = []
    for index, value in enumerate(broad_grid):
        record = {"frequency_uHz": value, "power_ppm2_per_uHz": broad_reduced[index]}
        for fit in primary["models"]:
            record[f"background_H{fit.component_count}"] = float(harvey_background(np.array([value]), fit.white_noise_ppm2_per_uHz, fit.components)[0])
        broad_rows.append(record)
    table(results / "broad_spectrum.csv", broad_rows)
    primary_diagnostic = full_diagnostics(grid, primary["reduced"], primary["background"], cfg)
    full_window = spectral_window(np.asarray(primary_curve.time.value), CADENCE)
    observation = []
    windows = []
    stability, segment_spectra, segment_counts = [], [], []
    for month in primary_months:
        frequency, power = periodogram(month, 1499, 2801)
        segment_duty = spectral_window(np.asarray(month.time.value), CADENCE).duty_cycle
        segment_spectra.append(rebin_spectrum(frequency, power, grid) * segment_duty / full_window.duty_cycle)
        segment_counts.append(len(month))
    for kind in ("quarter", "cumulative"):
        for quarter in sorted({int(row["segment_number"]) for row in kepler}):
            chosen = [month for row, month in zip(kepler, primary_months, strict=True) if (int(row["segment_number"]) == quarter if kind == "quarter" else int(row["segment_number"]) <= quarter)]
            curve = lk.LightCurveCollection(chosen).stitch()
            frequency, power = periodogram(curve, 1499, 2801)
            reduced = rebin_spectrum(frequency, power, grid)
            diagnostic = full_diagnostics(grid, reduced, primary["background"], cfg)
            window = spectral_window(np.asarray(curve.time.value), CADENCE)
            reduced *= window.duty_cycle / full_window.duty_cycle
            diagnostic = full_diagnostics(grid, reduced, primary["background"], cfg)
            stability.append({"kind": kind, "last_quarter": quarter, "cadences": len(curve), "duration_days": float(curve.time.value[-1] - curve.time.value[0]), "duty_cycle": window.duty_cycle, "resolution_uHz": window.resolution_uHz, **diagnostic, "background_policy": "fixed_full_span_primary_fit"})
            if kind == "quarter":
                windows.extend({"sample": f"Q{quarter}", "frequency_uHz": f, "window_power": p} for f, p in zip(window.frequency_uHz, window.power, strict=True))
    full_window = spectral_window(np.asarray(primary_curve.time.value), CADENCE)
    windows.extend({"sample": "combined_absolute", "frequency_uHz": f, "window_power": p} for f, p in zip(full_window.frequency_uHz, full_window.power, strict=True))
    # A compact plotted light curve; each sample still carries its original time.
    for index in range(0, len(primary_curve), 200):
        observation.append({"time_BKJD": float(primary_curve.time.value[index]), "relative_flux_ppm": float((primary_curve.flux.value[index] - 1) * 1e6)})
    table(results / "observation_preview.csv", observation)
    table(results / "spectral_windows.csv", windows)
    table(results / "quarter_stability.csv", stability)
    boot = weighted_segment_bootstrap(np.asarray(segment_spectra), segment_counts, replicates=cfg["uncertainty"]["monthly_bootstrap_replicates"], seed=cfg["master_seed"] + cfg["uncertainty"]["seed_offset"])
    bootstrap = [{"draw": index, **full_diagnostics(grid, draw, primary["background"], cfg)} for index, draw in enumerate(boot)]
    table(results / "monthly_bootstrap.csv", bootstrap)
    averaged = np.average(np.asarray(segment_spectra), axis=0, weights=segment_counts)
    monthly_point = full_diagnostics(grid, averaged, primary["background"], cfg)
    smoothed = gaussian_filter1d(primary["reduced"], cfg["topology"]["peak_smoothing_uHz"] / cfg["classical"]["grid_step_uHz"], mode="nearest")
    normalized = normalize_spectrum(grid, smoothed, primary["background"])
    _, peaks = localized_peak_persistence(normalized)
    write_json_lf(results / "localized_peaks.json", {"normalization": "log_ratio", "smoothing_uHz": cfg["topology"]["peak_smoothing_uHz"], "peaks": [peak.to_record() for peak in peaks]})
    matches = prominence_matches(normalized)
    equivalence = max((row.absolute_error for row in matches), default=0)
    aliases = []
    trials = np.linspace(*cfg["topology"]["comb_trials_uHz"])
    comb = comb_score_scan(peaks, trials)
    acf = autocorrelation_spacing_scores(grid, smoothed / primary["background"], trials)
    psps = psps_spacing_scores(grid, smoothed / primary["background"], trials)
    for index, trial in enumerate(trials):
        aliases.append({"trial_spacing_uHz": trial, "persistence_comb": comb[index], "acf": acf[index], "psps": psps[index]})
    table(results / "spectral_score_scan.csv", aliases)
    echelle_scan = scan_echelle(grid, primary["reduced"], primary["background"], primary_diagnostic["classical_dnu_uHz"], cfg)
    table(results / "echelle_score_scan.csv", echelle_scan)
    field = make_echelle_field(grid, smoothed, primary["background"], spacing_uHz=primary_diagnostic["classical_dnu_uHz"], phase_bins=cfg["topology"]["echelle_phase_bins"])
    score, graph, cylinder = score_echelle(field, full_diagram=True)
    write_json_lf(results / "cylinder.json", {"score": asdict(score), "graph": asdict(graph), "degree_identification": "unidentified_competing_paths", "inferred_r02": None, "inferred_r01": None, "inferred_r10": None, "pairs": localized_records(cylinder, representation_id="RUDY-CYLINDER"), "values": np.where(field.valid, field.values, 0).tolist(), "valid": field.valid.tolist(), "orders": field.orders.tolist(), "phases": field.phases.tolist()})
    from run_stage3_classical import _mode_references

    mode_matches = audit_mode_peaks(primary_frequency, primary_power, _mode_references(ROOT / cfg["inputs"]["modes"]), primary_diagnostic["classical_dnu_uHz"])
    table(results / "published_mode_overlay.csv", [asdict(match) for match in mode_matches])
    modes = {(int(row["radial_order_n"]), int(row["angular_degree_l"])): float(row["frequency_uHz"]) for row in read_csv(ROOT / cfg["inputs"]["modes"]) if row["stable_star_id"] == cfg["scope"]["target"]}
    ratio_rows = five_point_frequency_ratios(modes)
    table(results / "published_frequency_ratios.csv", [{**row, "role": "external_identified_modes_formula_audit_not_topological_measurement"} for row in ratio_rows])
    nulls, stochastic = matched_realizations(primary_curve, primary_fit, primary_frequency, primary_power, grid, primary["background"], cfg, results)
    observed = extra_statistics(grid, primary["reduced"], primary["background"], primary_diagnostic, cfg)
    tests = []
    for statistic in STATISTICS:
        tail = monte_carlo_tail(observed[statistic], np.asarray([draw[statistic] for draw in nulls]))
        tests.append({"statistic": statistic, "observed": observed[statistic], **asdict(tail), "scope": "conditional_fitted_background_registered_search_family", "background_refitted": False})
    adjusted = holm_adjust([row["pvalue"] for row in tests])
    for row, value in zip(tests, adjusted, strict=True):
        row["holm_pvalue"] = float(value)
        row["familywise_reject_0_05"] = bool(value <= cfg["nulls"]["alpha"])
    table(results / "conditional_null_tests.csv", tests)
    budgets = []
    for quantity in ("classical_numax_uHz", "classical_dnu_uHz", "persistence_numax_uHz"):
        bootstrap_values = np.asarray([row[quantity] for row in bootstrap])
        stochastic_values = np.asarray([row[quantity] for row in stochastic])
        branch_values = np.asarray([row[quantity] for row in audit_rows])
        lower, upper = np.quantile(bootstrap_values, [0.025, 0.975])
        budgets.append({"quantity": quantity, "full_span_point": primary_diagnostic[quantity], "monthly_averaged_point": monthly_point[quantity], "monthly_bootstrap_lower95": float(lower), "monthly_bootstrap_upper95": float(upper), "monthly_bootstrap_sigma": float(np.std(bootstrap_values, ddof=1)), "conditional_stochastic_sigma": float(np.std(stochastic_values, ddof=1)), "registered_pipeline_minimum": float(np.min(branch_values)), "registered_pipeline_maximum": float(np.max(branch_values)), "interval_target": "cadence_weighted_monthly_averaged_spectrum_not_full_span_LS", "combined_uncertainty": "not_combined_distinct_estimands_and_systematics"})
    table(results / "uncertainty_budget.csv", budgets)
    tess_results, transfer = tess_transfer(primary_months, kepler, tess, cache, cfg, results)
    placements = [{"object": "Rudy_Kepler", "duration_days": float(primary_curve.time.value[-1] - primary_curve.time.value[0]), "duty_cycle": full_window.duty_cycle, "cadence_seconds": CADENCE, "numax_uHz": primary_diagnostic["classical_numax_uHz"], "dnu_uHz": primary_diagnostic["classical_dnu_uHz"], "domain": "observed_descriptive"}]
    placements += [{"object": f"TESS_S{row['sector']}", "duration_days": row["duration_days"], "duty_cycle": row["duty_cycle"], "cadence_seconds": 120.0, "numax_uHz": row["classical_numax_uHz"], "dnu_uHz": row["classical_dnu_uHz"], "domain": "actual_TESS_context_candidate_values_not_detections"} for row in tess_results]
    placements += [{"object": row["cell_id"], "duration_days": float(row["duration_days"]), "duty_cycle": float(row["effective_duty_cycle"]), "cadence_seconds": float(row["cadence_seconds"]), "numax_uHz": float(row["numax_uHz"]), "dnu_uHz": float(row["dnu_uHz"]), "domain": "registered_stage4_simulation_pilot"} for row in read_csv(ROOT / "results/stage4/factorial_pilot.csv")]
    table(results / "simulation_placement.csv", placements)
    summary = {"run_id": cfg["run_id"], "primary": primary_diagnostic, "monthly_averaged": monthly_point, "tutorial": {key: branches[0][f"tutorial_{key}"] for key in ("numax", "dnu", "mass", "radius", "logg")}, "product_count": len(products), "kepler_cadences": len(primary_curve), "absolute_span_days": float(primary_curve.time.value[-1] - primary_curve.time.value[0]), "duty_cycle": full_window.duty_cycle, "window_aliases": strongest_window_aliases(full_window), "maximum_prominence_equivalence_error": equivalence, "robustness_rows": len(audit_rows), "conditional_null_replicates": len(nulls), "conditional_null_mean_ratio": float(np.mean([row["mean_ratio"] for row in nulls])), "bootstrap_replicates": len(bootstrap), "stochastic_replicates": len(stochastic), "transfer_cells": len(transfer), "actual_TESS_candidate_sectors": [row["sector"] for row in tess_results if row["classification"] == "marginal_candidate_not_confirmation"], "echelle_winning_alias": max(echelle_scan, key=lambda row: row["combined"])["alias_family"], "echelle_winning_spacing_uHz": max(echelle_scan, key=lambda row: row["combined"])["spacing_uHz"], "delay_status": "not_run_G7_preregistered_drop", "echelle_claim": "geometry_only_no_estimator_utility", "G9_proof_status": g9["status"], "population_spectra_used": False, "final_holdout_used": False, "claim_scope": "single_descriptive_star_conditional_nulls_no_population_or_incremental_utility_claim"}
    write_json_lf(results / "summary.json", summary)
    environment = {"python": platform.python_version(), "platform": platform.platform(), "software_version": f"TopoAstero-{__version__}", "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "matplotlib", "astropy", "lightkurve", "PyYAML")}, "lock_sha256": sha256_file(ROOT / "uv.lock"), "seed": cfg["master_seed"], "style_id": "TA-PLOT-1.0"}
    write_json_lf(results / "environment.json", environment)
    if figures:
        from plot_stage10 import plot_all
        plot_all(output, ROOT)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/stage10_rudy.yaml")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--skip-figures", action="store_true", help="diagnostic numerical rerun only; not a complete freeze")
    args = parser.parse_args()
    run(args.config.resolve(), args.cache_dir.resolve(), args.output_root.resolve(), download=args.download, figures=not args.skip_figures)


if __name__ == "__main__":
    main()
