"""Physical degradation, matched seeds, and optional astronomy adapters."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.classical import spectral_window
from topoastero.config import content_hash
from topoastero.echelle_topology import make_echelle_field, score_echelle
from topoastero.hybrid.features import feature_row
from topoastero.population import estimate_points, fit_population_background
from topoastero.population_acquisition import load_config
from topoastero.population_store import contained, read_json
from topoastero.provenance import sha256_file
from topoastero.rudy_benchmark import added_noise_sigma, integrate_cadences, rebin_spectrum

LEVELS = ("native", "exposure", "duration", "noise", "window", "duty", "contamination", "short_duration")
RUDY = "KIC 10963065"


def degrade(source_time: np.ndarray[Any, Any], source_flux: np.ndarray[Any, Any], window_time: np.ndarray[Any, Any],
            cfg: dict[str, Any], *, level: str, offset_days: float, seed: int, source_white: float, target_white: float) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], dict[str, Any]]:
    """Integrate real exposures, never fill long gaps, and retain paired random numbers.

    All time axes are seconds. Contamination dilutes source variability before
    additional instrumental noise; inherited Kepler noise is not subtracted.
    A unit color-response assumption is recorded, not claimed as Kepler/TESS physics.
    """
    if level not in LEVELS or offset_days < 0 or not math.isfinite(offset_days):
        raise ValueError("invalid degradation level or source offset")
    if source_time.ndim != 1 or len(source_time) < 3 or source_flux.shape != source_time.shape or not np.all(np.isfinite(source_time)) or not np.all(np.isfinite(source_flux)) or np.any(np.diff(source_time) <= 0):
        raise ValueError("invalid source time series")
    if window_time.ndim != 1 or len(window_time) < 3 or window_time[0] < 0 or np.any(np.diff(window_time) <= 0) or not np.all(np.isfinite(window_time)):
        raise ValueError("invalid real sector window")
    index = LEVELS.index(level)
    source_cadence = float(np.median(np.diff(source_time)))
    cadence = source_cadence if index == 0 else cfg["cadence_seconds"]
    exposure = source_cadence if index == 0 else cfg["exposure_seconds"]
    if cadence < source_cadence * .98 or exposure < source_cadence * .98 or exposure > cadence:
        raise ValueError("unsupported upsampling or exposure/cadence")
    duration = min(60 * 86400.0, float(source_time[-1] - offset_days * 86400)) if index < 2 else float(window_time[-1])
    if level == "short_duration":
        duration = min(duration, cfg["short_duration_days"] * 86400)
    centers = window_time[window_time <= duration] if index >= 4 else np.arange(0, duration, cadence)
    values, valid = integrate_cadences(source_time, source_flux, centers + offset_days * 86400,
                                      exposure_seconds=exposure, maximum_gap_seconds=cfg["maximum_source_gap_seconds"])
    coverage = float(np.mean(valid))
    # Same length-independent random sequence for each named parent/window/offset/draw.
    rng_mask = np.random.default_rng(seed)
    uniform = rng_mask.uniform(size=len(centers))
    if index >= 5:
        valid &= uniform < cfg["additional_duty"]
    if sum(valid) < 128:
        raise ValueError("insufficient_supported_exposures")
    dilution = 1.0 / (1.0 + cfg["contaminating_to_target_flux"]) if index >= 6 else 1.0
    if not 0 < dilution <= 1:
        raise ValueError("contaminating flux must be nonnegative")
    color = cfg["additional_signal_color_response"]
    if not math.isfinite(color) or color <= 0:
        raise ValueError("positive finite color response required")
    retained = centers[valid]
    duty = spectral_window(retained / 86400, cadence).duty_cycle
    sigma = added_noise_sigma(target_white, source_white * (color * dilution) ** 2, cadence, duty) if index >= 3 else 0.0
    normals = np.random.default_rng(seed + 1).normal(size=len(centers))
    flux = values[valid] * color * dilution + sigma * normals[valid]
    metadata = {"level": level, "seed": seed, "cadence_seconds": cadence, "exposure_seconds": exposure,
                "duration_days": float((retained[-1] - retained[0]) / 86400), "duty_cycle": duty,
                "supported_exposure_fraction": coverage, "dilution": dilution, "noise_sigma_ppm": sigma,
                "color_response": color, "color_response_scope": "assumed_sensitivity_not_measured_passband_conversion",
                "resolution_uHz": 1e6 / (retained[-1] - retained[0]), "cadences": len(retained),
                "inherited_noise_removed": False, "common_random_numbers": True}
    return retained / 86400, np.asarray(flux, dtype=np.float64), metadata


def analyze_curve(time_days: np.ndarray[Any, Any], flux_ppm: np.ndarray[Any, Any], root: Path, cfg: dict[str, Any], cadence: float) -> tuple[dict[str, Any], np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    import astropy.units as u  # type: ignore[import-untyped]
    import lightkurve as lk  # type: ignore[import-untyped]

    if len(time_days) < 128 or flux_ppm.shape != time_days.shape or not np.all(np.isfinite(flux_ppm)) or np.any(np.diff(time_days) <= 0):
        raise ValueError("invalid transfer time series")
    lo, hi, step = cfg["transfer"]["frequency_grid_uHz"]
    if hi >= 1e6 / (2 * cadence):
        raise ValueError("transfer frequency range exceeds cadence Nyquist frequency")
    grid = np.arange(lo, hi + step / 2, step, dtype=np.float64)
    curve = lk.LightCurve(time=time_days, flux=1 + flux_ppm / 1e6)
    # Explicit units and multiple native-bin padding prevent endpoint extrapolation.
    native_step = 1e6 / ((time_days[-1] - time_days[0]) * 86400)
    pg = curve.to_periodogram(normalization="psd", minimum_frequency=max(1, lo - 3 * native_step) * u.microhertz,
                             maximum_frequency=(hi + 3 * native_step) * u.microhertz, freq_unit=u.microhertz)
    power = rebin_spectrum(np.asarray(pg.frequency.value), np.asarray(pg.power.value) * 1e12, grid)
    population_cfg = load_config(root)
    population_cfg["classical"]["envelope_search_uHz"] = [500.0, 3500.0]
    background, _ = fit_population_background(grid, power, population_cfg)
    analysis = estimate_points(grid, power, background, population_cfg)
    mask = np.abs(grid - analysis["classical_numax"]) <= analysis["envelope_half_width_uHz"]
    field = make_echelle_field(grid[mask], power[mask], background[mask], spacing_uHz=analysis["classical_dnu"], phase_bins=24)
    score, _, _ = score_echelle(field)
    analysis["echelle_scan"] = [{"alias_family": "nominal", "spacing_uHz": analysis["classical_dnu"], "graph_only": score.graph_only, "topology": score.topology}]
    window = spectral_window(time_days, cadence)
    analysis.update({"duty_cycle": window.duty_cycle, "duration_days": float(time_days[-1] - time_days[0]),
                     "native_window_resolution_uHz": window.resolution_uHz})
    analysis["features"] = feature_row(analysis)
    return analysis, grid, power


def white_floor(time_days: np.ndarray[Any, Any], flux_ppm: np.ndarray[Any, Any]) -> float:
    """Registered native high-frequency median/log(2) noise-floor approximation."""
    import astropy.units as u
    import lightkurve as lk

    curve = lk.LightCurve(time=time_days, flux=1 + flux_ppm / 1e6)
    spectrum = curve.to_periodogram(normalization="psd", minimum_frequency=3200 * u.microhertz, maximum_frequency=3900 * u.microhertz)
    values = np.asarray(spectrum.power.value, dtype=np.float64) * 1e12
    if len(values) < 64 or not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("invalid native noise-floor support")
    return float(np.median(values) / np.log(2))


def read_mission_inputs(root: Path, cache: Path) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    import lightkurve as lk

    capsule = read_json(root / "results/stage10/benchmark_capsule.json")
    sources, targets, files = [], [], []
    for product in capsule["products"]:
        mission = product["mission"].lower()
        path = contained(cache, mission + "/" + product["product_filename"])
        if sha256_file(path) != product["sha256"]:
            raise ValueError("changed mission payload: " + path.name)
        curve = lk.read(path).remove_nans().normalize()
        time = np.asarray(curve.time.value, dtype=np.float64)
        flux = np.asarray(curve.flux.value, dtype=np.float64)
        if np.any(np.diff(time) <= 0) or not np.all(np.isfinite(flux)):
            raise ValueError("invalid mission cadence order or flux")
        if mission == "kepler":
            if int(curve.meta["KEPLERID"]) != 10963065:
                raise ValueError("Kepler star identifier mismatch")
            if int(curve.meta["QUARTER"]) == 5:
                sources.append((time, (flux - 1) * 1e6))
        elif mission == "tess":
            if int(curve.meta["TICID"]) != 48450369:
                raise ValueError("TESS star identifier mismatch")
            cadence = float(np.median(np.diff(time)) * 86400)
            targets.append({"sector": int(curve.meta["SECTOR"]), "time": time,
                            "flux": (flux - 1) * 1e6, "cadence_seconds": cadence})
        else:
            raise ValueError("unsupported mission")
        files.append({"name": path.name, "sha256": product["sha256"], "bytes": path.stat().st_size})
    if len(sources) != 3 or len(targets) != 11 or len({r["sector"] for r in targets}) != 11:
        raise ValueError("complete 3-month Q5 source and 11 TESS sectors are required")
    source_time = np.concatenate([s[0] for s in sources])
    source_flux = np.concatenate([s[1] for s in sources])
    order = np.argsort(source_time)
    source_time, source_flux = source_time[order], source_flux[order]
    if np.any(np.diff(source_time) <= 0):
        raise ValueError("overlapping Kepler source exposures")
    return (source_time - source_time[0]) * 86400, source_flux, sorted(targets, key=lambda r: r["sector"]), files


def calibration_layer(rows: list[dict[str, Any]], cfg: dict[str, Any], authorization: str) -> dict[str, Any]:
    """Prespecified log-offset layer fit only to non-Rudy DEVELOPMENT simulations."""
    if not authorization.strip() or not rows:
        raise ValueError("explicit recalibration authorization and simulation rows required")
    if any(r.get("role") != "development" or r["stable_star_id"] == RUDY or r.get("origin") != "degradation_simulation" for r in rows):
        raise ValueError("recalibration forbids holdout stars, Rudy, and actual test sectors")
    groups = sorted({r["stable_star_id"] for r in rows})
    if len(groups) < cfg["transfer"]["minimum_calibration_stars"]:
        raise ValueError("insufficient independent calibration stars")
    offsets = {}
    for method in ("baseline", "hybrid"):
        for quantity in ("numax", "dnu"):
            group_residual = []
            for group in groups:
                subset = [r for r in rows if r["method"] == method and r["quantity"] == quantity and r["stable_star_id"] == group]
                if not subset or any(not math.isfinite(r["estimate"]) or not math.isfinite(r["reference"]) or r["estimate"] <= 0 or r["reference"] <= 0 for r in subset):
                    raise ValueError("calibration needs both methods/endpoints for every star")
                group_residual.append(float(np.mean([math.log(r["reference"] / r["estimate"]) for r in subset])))
            offsets[method + "_" + quantity] = float(np.median(group_residual))
    return {"schema_version": 1, "kind": "star_weighted_median_log_offset", "authorization": authorization,
            "training_stars": groups, "offsets": offsets, "inputs_sha256": content_hash(rows), "feature_redesign": False,
            "application_scope": "TESS_like_transfer_only_never_Kepler_primary_confirmation",
            "validation": "must_be_evaluated_on_disjoint_nontraining_simulation_stars", "actual_sectors_used": False}
