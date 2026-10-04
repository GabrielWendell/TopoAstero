"""Build quality reasons, classical controls, ratio checks and claim evidence.

This is a deterministic downstream analysis of the benchmark tables. Echelle
uncertainty is a diagnostic distribution, because G8 did not validate coverage.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from run_stage8_echelle import _conventional_score, _hough_score
from run_stage10_rudy import (
    CADENCE,
    ROOT,
    full_diagnostics,
    periodogram,
    processed_months,
    read_csv,
    scan_echelle,
    table,
)
from scipy.ndimage import gaussian_filter1d

from topoastero.classical import harvey_background, scaling_relations, spectral_window
from topoastero.config import load_yaml
from topoastero.echelle_topology import make_echelle_field, score_echelle, trial_spacing_grid
from topoastero.portability import write_json_lf, write_text_lf
from topoastero.provenance import sha256_file
from topoastero.rudy_benchmark import (
    holm_adjust,
    monte_carlo_tail,
    rebin_spectrum,
    weighted_segment_bootstrap,
)


def build(output: Path, cache: Path) -> None:
    from acquire_stage3_inputs import acquire

    from topoastero.classical import HarveyComponent

    cfg = load_yaml(ROOT / "configs/stage10_rudy.yaml")
    results, reports = output / "results/stage10", output / "reports/stage10"
    summary = json.loads((results / "summary.json").read_text())
    branches = read_csv(results / "classical_branches.csv")
    robustness = read_csv(results / "robustness.csv")
    models = json.loads((results / "background_models.json").read_text())["models"]
    spectra = read_csv(results / "branch_spectra.csv")
    echelle_rows = []
    for branch in cfg["preprocessing"]["kepler_branches"]:
        data = [row for row in spectra if row["branch_id"] == branch]
        frequency = np.array([float(row["frequency_uHz"]) for row in data])
        power = np.array([float(row["power_ppm2_per_uHz"]) for row in data])
        anchor = float(next(row for row in branches if row["branch_id"] == "PP-01")["classical_dnu_uHz"])
        smoothed = gaussian_filter1d(power, cfg["topology"]["peak_smoothing_uHz"] / np.median(np.diff(frequency)), mode="nearest")
        for model in [row for row in models if row["branch_id"] == branch]:
            components = tuple(HarveyComponent(**item) for item in model["components"])
            background = harvey_background(frequency, model["white_noise_ppm2_per_uHz"], components)
            for family, spacing in trial_spacing_grid(anchor):
                field = make_echelle_field(frequency, smoothed, background, spacing_uHz=spacing, phase_bins=cfg["topology"]["echelle_phase_bins"])
                score, _, _ = score_echelle(field)
                echelle_rows.append({"branch_id": branch, "background_id": model["model_id"], "alias_family": family, **asdict(score), "conventional_control": _conventional_score(field), "hough_control": _hough_score(field), "primary_anchor_uHz": anchor, "interpretation": "diagnostic_no_G8_utility_or_coverage_claim"})
    table(results / "echelle_branch_controls.csv", echelle_rows)

    products = acquire(ROOT / "data/manifests/stage2", cache, download=False)
    paths = [cache / "kepler" / row["product_filename"] for row in products if row["mission"] == "Kepler"]
    months = processed_months(paths, "PP-01")
    primary = [row for row in spectra if row["branch_id"] == "PP-01"]
    grid = np.array([float(row["frequency_uHz"]) for row in primary])
    background = np.array([float(row["background_ppm2_per_uHz"]) for row in primary])
    segment_spectra = [rebin_spectrum(*periodogram(month, 1499, 2801), grid) * spectral_window(np.asarray(month.time.value), CADENCE).duty_cycle / summary["duty_cycle"] for month in months]
    monthly_records = []
    for index, spectrum in enumerate(segment_spectra):
        monthly_records.extend({"segment_index": index, "cadences": len(months[index]), "frequency_uHz": value, "power_ppm2_per_uHz": spectrum[position]} for position, value in enumerate(grid))
    table(results / "monthly_spectra.csv", monthly_records)
    draws = weighted_segment_bootstrap(np.array(segment_spectra), [len(month) for month in months], replicates=cfg["uncertainty"]["monthly_bootstrap_replicates"], seed=cfg["master_seed"] + cfg["uncertainty"]["seed_offset"])
    echelle_bootstrap = []
    for index, draw in enumerate(draws[:64]):
        anchor = full_diagnostics(grid, draw, background, cfg)["classical_dnu_uHz"]
        scan = scan_echelle(grid, draw, background, anchor, cfg)
        winner = max(scan, key=lambda row: row["combined"])
        graph = max(scan, key=lambda row: row["graph_only"])
        echelle_bootstrap.append({"draw": index, "spacing_uHz": winner["spacing_uHz"], "alias_family": winner["alias_family"], "graph_spacing_uHz": graph["spacing_uHz"], "graph_alias": graph["alias_family"], "interpretation": "resampling_diagnostic_not_coverage_validated_confidence_interval"})
    table(results / "echelle_bootstrap.csv", echelle_bootstrap)

    bootstrap = read_csv(results / "monthly_bootstrap.csv")
    scaling = []
    rng = np.random.default_rng(cfg["master_seed"] + cfg["uncertainty"]["seed_offset"] + 900)
    for row in bootstrap:
        numax, dnu = float(row["classical_numax_uHz"]), float(row["classical_dnu_uHz"])
        teff = cfg["classical"]["teff_K"] + cfg["classical"]["teff_sigma_K"] * rng.normal()
        seismic = scaling_relations(numax, dnu, cfg["classical"]["teff_K"])
        with_temperature = scaling_relations(numax, dnu, teff)
        scaling.append({"draw": int(row["draw"]), "numax_uHz": numax, "dnu_uHz": dnu, "teff_K": float(teff), **{f"seismic_{key}": value for key, value in seismic._asdict().items()}, **with_temperature._asdict(), "stellar_scaling_systematic_budget": "unquantified_not_assumed_zero", "role": "conditional_uncorrected_scaling_calculus_not_stellar_posterior"})
    table(results / "scaling_draws.csv", scaling)
    scaling_summary = []
    for key in ("mass_solar", "radius_solar", "logg_cgs"):
        values = np.array([row[key] for row in scaling])
        seismic = np.array([row[f"seismic_{key}"] for row in scaling])
        pipeline = np.array([getattr(scaling_relations(float(row["classical_numax_uHz"]), float(row["classical_dnu_uHz"]), cfg["classical"]["teff_K"]), key) for row in robustness])
        scaling_summary.append({"quantity": key, "point_uncorrected": float(branches[0][key]), "seismic_bootstrap_sigma": float(np.std(seismic, ddof=1)), "temperature_plus_seismic_lower95": float(np.quantile(values, 0.025)), "temperature_plus_seismic_upper95": float(np.quantile(values, 0.975)), "pipeline_minimum": float(np.min(pipeline)), "pipeline_maximum": float(np.max(pipeline)), "stellar_systematic": "unquantified", "physical_stellar_interval_issued": False})
    table(results / "scaling_uncertainty.csv", scaling_summary)

    formula = read_csv(results / "published_frequency_ratios.csv")
    references = read_csv(ROOT / cfg["inputs"]["ratios"])
    ratios = []
    for row in references:
        if row["stable_star_id"] != "KIC 10963065":
            continue
        key = row["ratio_type"].replace("_", "")
        n = int(row["radial_order_n"])
        calculated = next((item[key] for item in formula if int(item["radial_order_n"]) == n), "")
        if not calculated:
            continue
        difference = float(calculated) - float(row["value"])
        sigma = float(row["uncertainty_plus"] if difference >= 0 else row["uncertainty_minus"])
        ratios.append({"order": n, "ratio": key, "formula_value": float(calculated), "published_value": float(row["value"]), "difference": difference, "side_uncertainty": sigma, "uncertainty_normalized_difference": abs(difference) / sigma, "role": "external_mode_formula_audit_not_new_measurement"})
    table(results / "ratio_reference_audit.csv", ratios)

    null_tests = read_csv(results / "conditional_null_tests.csv")
    envelope = next(row for row in null_tests if row["statistic"] == "classical_envelope_snr")
    backgrounds = [harvey_background(grid, model["white_noise_ppm2_per_uHz"], tuple(HarveyComponent(**item) for item in model["components"])) for model in models if model["branch_id"] == "PP-01"]
    spread = float(np.max(np.ptp(np.array(backgrounds), axis=0) / background))
    maximum_alias = max((value[1] for value in summary["window_aliases"]), default=0)
    flags = [
        {"flag": "absent_envelope", "active": float(envelope["holm_pvalue"]) > 0.05, "value": float(envelope["holm_pvalue"]), "threshold": 0.05, "reason": "seven_family_Holm_conditional_background_test"},
        {"flag": "alias_ambiguity", "active": summary["primary"]["comb_top_two_ratio"] < cfg["topology"]["alias_ambiguity_ratio"] or summary["primary"]["comb_winner_uHz"] in (20.0, 300.0) or abs(summary["primary"]["acf_winner_uHz"] - summary["primary"]["psps_winner_uHz"]) > 10.0, "value": summary["primary"]["comb_top_two_ratio"], "threshold": cfg["topology"]["alias_ambiguity_ratio"], "reason": "comb_boundary_winner_and_ACF_PSPS_disagreement"},
        {"flag": "insufficient_orders", "active": int(1300 / summary["primary"]["classical_dnu_uHz"]) < 5, "value": int(1300 / summary["primary"]["classical_dnu_uHz"]), "threshold": 5, "reason": "frequency_support_orders_not_degree_identification"},
        {"flag": "window_contamination", "active": maximum_alias > 0.25, "value": maximum_alias, "threshold": 0.25, "reason": "largest_nonzero_cadence_mask_alias"},
        {"flag": "unstable_background", "active": spread > 0.20, "value": spread, "threshold": 0.20, "reason": "all_registered_Harvey_families_support_not_posterior_spread"},
        {"flag": "unvalidated_persistence_location", "active": True, "value": abs(summary["primary"]["persistence_numax_uHz"] - summary["primary"]["classical_numax_uHz"]), "threshold": "no_Rudy_coverage_validation", "reason": "do_not_translate_centroid_into_calibrated_stellar_error_bar"},
    ]
    table(results / "quality_flags.csv", flags)
    claims = [
        ("P1-C01", "The public-product capsule and tutorial baseline are reproducible.", "descriptive_reproduction", "results/stage10/benchmark_capsule.json;results/stage10/classical_branches.csv", "Lightkurve baseline;frozen payload SHA256", "single_star_and_locked_pipeline"),
        ("P1-C02", "Finite path H0 lifetimes are elder-rule prominence, with frequency localization.", "known_identity_application", "results/stage10/localized_peaks.json;results/stage10/summary.json", "independent_path_prominence", "no_incremental_information_or_novelty_claim"),
        ("P1-C03", "Conditional fitted-background null results are reported with full search maxima and Holm correction.", "conditional_model_test", "results/stage10/null_draws.csv;results/stage10/conditional_null_tests.csv", "window_matched_stationary_Gaussian_background;ACF;PSPS;graph", "background_fit_uncertainty_and_instrument_systematics_not_calibrated"),
        ("P1-C04", "Rudy comb and cylindrical scores remain ambiguous diagnostics.", "negative_or_limited_result", "results/stage10/spectral_score_scan.csv;results/stage10/echelle_branch_controls.csv;results/stage10/echelle_bootstrap.csv", "ACF;PSPS;conventional_echelle;Hough;ridge_graph", "G8_geometry_only_no_utility_or_validated_coverage"),
        ("P1-C05", "Monthly resampling, stochastic scatter and registered pipeline ranges target different uncertainties.", "uncertainty_decomposition", "results/stage10/monthly_bootstrap.csv;results/stage10/stochastic_draws.csv;results/stage10/uncertainty_budget.csv;results/stage10/scaling_uncertainty.csv", "quarter_and_cumulative_baselines;72_registered_branches", "no_combined_stellar_posterior_no_population_inference"),
        ("P1-C06", "TESS degradation is tested with all real sector windows and actual sectors retained as context.", "conditional_transfer_experiment", "results/stage10/kepler_to_tess.csv;results/stage10/tess_sectors.csv", "boxcar_integration;duration;duty;noise_ablations", "same_Kepler_source_reused_not_independent_stars_or_TESS_confirmation"),
        ("P1-C07", "Delay topology is omitted under the registered Stage 7 negative decision.", "registered_negative_result", "reports/stage7/G7_ACCEPTANCE.json", "PSD_preserving_phase_and_IAAFT_surrogates;classical_features", "no_new_Rudy_phase_claim"),
        ("P1-C08", "Published identified modes support overlays and formula audits only.", "external_reference_audit", "results/stage10/published_mode_overlay.csv;results/stage10/ratio_reference_audit.csv;results/stage10/cylinder.json", "Lund2017_modes_and_ratios", "no_blind_degree_inference_or_topological_r01_r10"),
    ]
    claim_rows = [{"claim_id": claim, "claim": text, "classification": kind, "evidence": evidence, "controls": controls, "limit": limit, "frozen_before_manuscript": True, "population_claim": False} for claim, text, kind, evidence, controls, limit in claims]
    null_draws = read_csv(results / "null_draws.csv")
    adjusted = holm_adjust([float(row["pvalue"]) for row in null_tests])
    null_correct = all(np.isclose(monte_carlo_tail(float(row["observed"]), np.array([float(draw[row["statistic"]]) for draw in null_draws])).pvalue, float(row["pvalue"]), atol=1e-12) and np.isclose(float(row["holm_pvalue"]), holm, atol=1e-12) for row, holm in zip(null_tests, adjusted, strict=True))
    cylinder = json.loads((results / "cylinder.json").read_text())
    guards = {
        "P1-C01": summary["product_count"] == 21 and len(branches) == 4,
        "P1-C02": summary["maximum_prominence_equivalence_error"] <= 1e-10,
        "P1-C03": len(null_draws) == 256 and len(null_tests) == 7 and null_correct,
        "P1-C04": summary["echelle_claim"] == "geometry_only_no_estimator_utility" and len(echelle_rows) == 180,
        "P1-C05": len(robustness) == 72 and len(bootstrap) == 256,
        "P1-C06": len(read_csv(results / "kepler_to_tess.csv")) == 396 and len(read_csv(results / "tess_sectors.csv")) == 11,
        "P1-C07": summary["delay_status"] == "not_run_G7_preregistered_drop",
        "P1-C08": len(ratios) >= 30 and all(cylinder.get(key) is None for key in ("inferred_r02", "inferred_r01", "inferred_r10")),
    }
    unsupported = [claim for claim, valid in guards.items() if not valid]
    if unsupported:
        raise ValueError(f"unsupported Paper I claims: {unsupported}")
    table(reports / "claim_evidence.csv", claim_rows)
    write_json_lf(reports / "claim_audit.json", {"run_id": cfg["run_id"], "status": "pass", "claim_count": len(claim_rows), "unsupported_claims": [], "population_claims": [], "new_G9_proposition_headline_claims": [], "proof_review_status": summary["G9_proof_status"], "independent_human_review": "pending", "claims_frozen_before_manuscript": True, "claim_evidence_sha256": sha256_file(reports / "claim_evidence.csv")})
    write_text_lf(reports / "LIMITATIONS_AND_NEGATIVE_RESULTS.md", """# Paper I limits and negative results

The experiment is a descriptive benchmark of one already studied star. No
population spectra or final holdout were inspected. The implementation lock is
not an externally timestamped preregistration; Stage 3 results were already known.

* Path H0 is exactly elder-rule prominence. Frequency localization is useful
  organization; incremental information and novelty are not established.
* The broad comb scan has competing aliases and a boundary winner. G8 remains
  geometry_only, with no calibrated cylindrical estimator or interval coverage.
* Cylindrical paths lack degree anchors. New r02/r01/r10 measurements are withheld;
  published degree-identified frequencies are only overlaid and formula-checked.
* All registered H0/H1/H2 background families and all preprocessing/normalization
  branches remain visible. BIC is descriptive for correlated spectrum ordinates.
* Null tails condition on a stationary Gaussian fitted Harvey continuum and the
  actual window. Fits are not repeated in null draws; background uncertainty,
  nonlinear detrending and nonstationary instrument residuals are not calibrated.
* Gaussian spectral draws match a conditional smoothed PSD, not a full model of
  stochastic mode excitation and nonlinear stellar physics. No lifetime is inferred.
* Monthly averaged-spectrum bootstrap intervals do not cover the coherent full-span
  estimator by construction. Quarter/cumulative results overlap; noise realizations,
  window changes and pipeline ranges must not be added as independent error bars.
* Scaling draws preserve joint seismic bootstrap pairs and temperature uncertainty,
  but astrophysical correction budgets are unquantified. No physical stellar
  posterior or observational topological stellar error bar is issued.
* Transfer uses ideal 120-second boxcar exposures of a piecewise-linear Kepler
  curve. It cannot undo Kepler exposure attenuation or match TESS bandpass,
  detector systematics or nonlinear cotrending. Real sector gaps and additional
  source coverage loss are recorded. Reused Q5 offsets are correlated.
* Actual TESS marginal candidates are not confirmations. The feasibility rule is
  a fixed reference-conditioned diagnostic, not a blind detection significance.
* G7 dropped delay PH after negative phase/surrogate and prediction tests; no
  new Rudy delay calculation or positive phase-information claim is introduced.
* G9 independent proof review and G10 independent human reproduction/claim review
  remain pending. Automated clean-process reproduction is a separate check.
""")
    print(f"Stage 10 claim/evidence freeze: {len(claim_rows)} bounded claims", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--cache-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.output_root, args.cache_dir)


if __name__ == "__main__":
    main()
