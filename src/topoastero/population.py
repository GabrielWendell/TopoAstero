"""Truth-independent LEGACY estimators on exposure-weighted monthly mean spectra.

The population observation operator is explicit: estimates and segment intervals
refer to the SAME mean-spectrum estimator. Published values never enter these
functions. Cylindrical scores retain G8's geometry-only interpretation; delay PH
remains dropped. Path H0 is paired with its exact prominence control.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d, percentile_filter  # type: ignore[import-untyped]
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from topoastero.classical import estimate_envelope, estimate_large_separation
from topoastero.echelle_topology import make_echelle_field, score_echelle, trial_spacing_grid
from topoastero.rudy_benchmark import weighted_segment_bootstrap
from topoastero.spectral_topology import (
    comb_score_scan,
    localized_peak_persistence,
    normalize_spectrum,
    persistence_weighted_location,
    prominence_matches,
)

FloatArray = NDArray[np.float64]


def validate_spectra(frequency: FloatArray, spectra: FloatArray, weights: FloatArray) -> None:
    if frequency.ndim != 1 or frequency.size < 64 or not np.all(np.isfinite(frequency)) or np.any(np.diff(frequency) <= 0):
        raise ValueError("frequency must be a finite increasing vector of at least 64 bins")
    if not np.allclose(np.diff(frequency), np.median(np.diff(frequency)), rtol=1e-6):
        raise ValueError("population spectra require a uniform physical frequency grid")
    if spectra.ndim != 2 or spectra.shape[1] != frequency.size or spectra.shape[0] < 1 or weights.shape != (spectra.shape[0],):
        raise ValueError("spectra/weights must match frequency and nonoverlapping segments")
    if not np.all(np.isfinite(spectra)) or np.any(spectra <= 0) or not np.all(np.isfinite(weights)) or np.any(weights <= 0):
        raise ValueError("spectra and exposure weights must be finite and positive")


def fit_population_background(frequency: FloatArray, power: FloatArray, cfg: dict[str, Any]) -> tuple[FloatArray, list[dict[str, Any]]]:
    """Fit bin MEANS of the averaged PSD, without raw-exponential median correction.

    Fit H0/H1/H2 log residuals for a descriptive background audit. Raw-ordinate
    exponential BIC from Stage 3 is not valid for a monthly averaged spectrum,
    so no BIC or probabilistic model weight is issued here. H2 is registered as
    primary, independent of published values and of per-star fit scores.
    """
    step = float(np.median(np.diff(frequency)))
    initial = percentile_filter(power, percentile=25, size=max(5, int(cfg["classical"]["initial_continuum_smoothing_uHz"] / step)), mode="nearest")
    coarse = estimate_envelope(frequency, power, np.asarray(initial, dtype=np.float64),
                              search_uHz=tuple(cfg["classical"]["envelope_search_uHz"]))
    width = max(cfg["classical"]["minimum_half_width_uHz"], cfg["classical"]["envelope_half_width_fraction"] * coarse.numax_uHz)
    retained = np.abs(frequency - coarse.numax_uHz) > width
    edges = np.geomspace(max(1.0, float(frequency[0])), float(frequency[-1]) + step, 101)
    centers, means = [], []
    for lo, hi in pairwise(edges):
        mask = retained & (frequency >= lo) & (frequency < hi)
        if np.count_nonzero(mask) >= 4:
            centers.append(float(np.mean(frequency[mask])))
            means.append(float(np.mean(power[mask])))
    if len(means) < 12:
        raise ValueError("insufficient_background_bins")
    x, y = np.asarray(centers), np.asarray(means)
    high = max(float(np.median(y[-8:])), np.finfo(float).tiny)
    low = max(float(np.median(y[:8])) - high, high)
    audits: list[dict[str, Any]] = []
    primary: FloatArray | None = None
    for count in range(int(cfg["classical"]["background_components"]) + 1):
        start = [math.log(high)]
        bounds_lo = [math.log(float(np.min(power)) * 1e-4)]
        bounds_hi = [math.log(float(np.max(power)) * 100)]
        for k in range(count):
            start.extend([math.log(low / max(1, count)), math.log((300, 1500)[k])])
            bounds_lo.extend([bounds_lo[0], math.log(10)])
            bounds_hi.extend([bounds_hi[0], math.log(10000)])

        def model(theta: FloatArray, at: FloatArray, components: int = count) -> FloatArray:
            result = np.full(at.shape, np.exp(theta[0]), dtype=np.float64)
            for j in range(components):
                result += np.exp(theta[1 + 2 * j]) / (1 + (at / np.exp(theta[2 + 2 * j])) ** 4)
            return result

        fit = least_squares(lambda t: np.log(model(t, x)) - np.log(y), np.asarray(start),
                            bounds=(bounds_lo, bounds_hi), max_nfev=2000)
        if not fit.success:
            raise ValueError("background_optimizer_failed")
        condition = float(np.linalg.cond(fit.jac.T @ fit.jac))
        audits.append({"components": count, "log_parameters": fit.x.tolist(),
                       "log_residual_rms": float(np.sqrt(np.mean(fit.fun**2))),
                       "covariance_condition": condition if math.isfinite(condition) else None,
                       "condition_status": "finite" if math.isfinite(condition) else "singular",
                       "primary": count == cfg["classical"]["background_components"],
                       "excluded_lower_uHz": coarse.numax_uHz - width,
                       "excluded_upper_uHz": coarse.numax_uHz + width,
                       "model_selection": "registered_component_count_no_BIC_for_mean_PSD"})
        if count == cfg["classical"]["background_components"]:
            primary = model(np.asarray(fit.x, dtype=np.float64), frequency)
    if primary is None:
        raise ValueError("invalid primary background component count")
    return primary, audits


def estimate_points(frequency: FloatArray, power: FloatArray, background: FloatArray, cfg: dict[str, Any]) -> dict[str, Any]:
    """Registered classical and persistent-peak global estimators, without truth hints."""
    classical = cfg["classical"]
    topology = cfg["topology"]
    envelope = estimate_envelope(frequency, power, background,
                                 search_uHz=tuple(classical["envelope_search_uHz"]),
                                 smoothing_uHz=classical["envelope_smoothing_uHz"])
    half = max(classical["minimum_half_width_uHz"], classical["envelope_half_width_fraction"] * envelope.numax_uHz)
    separation = estimate_large_separation(frequency, power, background, envelope.numax_uHz,
                                           half_width_uHz=half)
    mask = np.abs(frequency - envelope.numax_uHz) <= half
    f, p, b = frequency[mask], power[mask], background[mask]
    smoothed = np.asarray(gaussian_filter1d(p, topology["peak_smoothing_uHz"] / np.median(np.diff(f))), dtype=np.float64)
    normalized = normalize_spectrum(f, smoothed, b, method="log_ratio")
    _, peaks = localized_peak_persistence(normalized)
    numax = persistence_weighted_location(peaks, search_uHz=(float(f[0]), float(f[-1])), method="centroid")
    lo, hi = topology["nominal_spacing_range"]
    nominal = np.linspace(lo * separation.dnu_uHz, hi * separation.dnu_uHz, topology["spacing_points"])
    trials = np.concatenate([nominal / 2, nominal, nominal * 2])
    scores = comb_score_scan(peaks, trials)
    count = len(nominal)
    selected = scores[count:2 * count]
    winner = int(np.argmax(selected))
    control = prominence_matches(normalized)
    return {"classical_numax": envelope.numax_uHz, "classical_dnu": separation.dnu_uHz,
            "topology_numax": numax, "topology_dnu": float(nominal[winner]),
            "envelope_ratio": envelope.peak_snr, "envelope_half_width_uHz": half,
            "spacing_trials_uHz": trials.tolist(), "spacing_scores": scores.tolist(),
            "alias_families": ["half"] * count + ["nominal"] * count + ["double"] * count,
            "nominal_winner_at_boundary": winner in (0, count - 1),
            "strongest_alias": ("half", "nominal", "double")[int(np.argmax(scores)) // count],
            "nominal_score": float(selected[winner]), "maximum_alias_score": float(np.max(scores)),
            "finite_peaks": len(control),
            "prominence_max_absolute_difference": max((m.absolute_error for m in control), default=0.0)}


def analyze_spectra(frequency: FloatArray, spectra: FloatArray, weights: FloatArray,
                    cfg: dict[str, Any], *, seed: int, duty_cycle: float) -> tuple[dict[str, Any], FloatArray, FloatArray, list[dict[str, Any]]]:
    """Analyze one star. Bootstrap nonoverlapping months jointly for both methods."""
    validate_spectra(frequency, spectra, weights)
    if not 0 < duty_cycle <= 1:
        raise ValueError("invalid duty cycle")
    mean = np.asarray(np.average(spectra, axis=0, weights=weights), dtype=np.float64)
    background, fits = fit_population_background(frequency, mean, cfg)
    points = estimate_points(frequency, mean, background, cfg)
    mask = np.abs(frequency - points["classical_numax"]) <= points["envelope_half_width_uHz"]
    smoothed = np.asarray(gaussian_filter1d(mean[mask], cfg["topology"]["peak_smoothing_uHz"] / np.median(np.diff(frequency))), dtype=np.float64)
    echelle = []
    for family, spacing in trial_spacing_grid(points["classical_dnu"], fractions=tuple(cfg["topology"]["echelle_trial_fractions"])):
        field = make_echelle_field(frequency[mask], smoothed, background[mask], spacing_uHz=spacing,
                                   phase_bins=cfg["topology"]["echelle_phase_bins"])
        score, _, _ = score_echelle(field)
        echelle.append({"alias_family": family, **asdict(score)})
    bootstrap = []
    failed = 0
    if spectra.shape[0] >= cfg["observation"]["minimum_months"]:
        realizations = weighted_segment_bootstrap(spectra, weights.tolist(),
                                                  replicates=cfg["uncertainty"]["segment_bootstrap_replicates"], seed=seed)
        for index, draw in enumerate(realizations):
            try:
                draw_background = fit_population_background(frequency, draw, cfg)[0] if cfg["uncertainty"]["refit_background"] else background
                estimate = estimate_points(frequency, draw, draw_background, cfg)
                bootstrap.append({"draw": index, **{k: estimate[k] for k in ("classical_numax", "classical_dnu", "topology_numax", "topology_dnu")}})
            except (ValueError, RuntimeError, FloatingPointError):
                failed += 1
    flags = []
    if points["envelope_ratio"] < cfg["quality"]["minimum_envelope_ratio"]:
        flags.append("low_envelope_ratio")
    if duty_cycle < cfg["quality"]["minimum_duty_cycle"]:
        flags.append("low_duty_cycle")
    if points["maximum_alias_score"] >= cfg["quality"]["alias_score_ratio"] * max(points["nominal_score"], np.finfo(float).eps) or points["nominal_winner_at_boundary"]:
        flags.append("alias_ambiguity")
    if max(r["valid_orders"] for r in echelle) < cfg["quality"]["minimum_orders"]:
        flags.append("insufficient_orders")
    if fits[-1]["covariance_condition"] is None or fits[-1]["covariance_condition"] > 1e12:
        flags.append("unstable_background")
    enough = len(bootstrap) == cfg["uncertainty"]["segment_bootstrap_replicates"] and failed == 0
    if not enough:
        flags.append("uncertainty_unavailable")
    intervals = {}
    level = cfg["uncertainty"]["interval_level"]
    for method in ("classical", "topology"):
        for quantity in ("numax", "dnu"):
            key = f"{method}_{quantity}"
            limits = np.quantile([r[key] for r in bootstrap], [(1 - level) / 2, (1 + level) / 2]) if enough else [None, None]
            intervals[key] = {"lower": None if limits[0] is None else float(limits[0]),
                              "upper": None if limits[1] is None else float(limits[1])}
    result = {**points, "intervals": intervals, "interval_level": level,
              "interval_scope": "conditional_nonoverlapping_month_bootstrap_for_weighted_mean_PSD",
              "bootstrap_valid": len(bootstrap), "bootstrap_failed": failed,
              "quality_flags": flags, "status": "limited" if flags else "ok",
              "detection_significance": "not_calibrated", "cylinder_inference": "geometry_only",
              "blind_ridge_ratios": "withheld_without_degree_anchors", "delay_topology": "dropped_at_G7",
              "echelle_scan": echelle, "background_models": fits,
              "primary_estimator": cfg["observation"]["estimator"], "reference_values_used_in_estimation": False}
    return result, mean, background, bootstrap
