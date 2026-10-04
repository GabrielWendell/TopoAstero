"""Cohort reconciliation, resumable development batches and star-level catalogs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from topoastero.config import content_hash
from topoastero.echelle_topology import five_point_frequency_ratios
from topoastero.population import analyze_spectra
from topoastero.population_acquisition import monthly_spectra, verified_star_products
from topoastero.population_statistics import build_performance, operating_domain
from topoastero.population_store import (
    append_event,
    contained,
    read_json,
    read_table,
    seal,
    seal_issues,
    star_slug,
    write_json,
    write_table,
)
from topoastero.provenance import sha256_file

ROLES = ("development", "internal_validation", "descriptive_benchmark", "final_holdout")


def cohort(root: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconcile ALL stars while preserving the original grouped partition and references."""
    split_path = contained(root, cfg["partitions"])
    attestation = read_json(contained(root, cfg["split_attestation"]))
    if sha256_file(split_path) != attestation["sha256"]:
        raise ValueError("frozen Stage 2 split checksum mismatch")
    split = read_table(split_path)
    population = {r["object_id"]: r for r in read_table(contained(root, cfg["population"]))}
    if len(split) != 66 or len({r["stable_star_id"] for r in split}) != 66 or set(population) != {r["stable_star_id"] for r in split}:
        raise ValueError("cohort is not exactly the frozen 66 unique LEGACY stars")
    references = read_table(contained(root, cfg["stellar_references"]))
    products = read_table(contained(root, cfg["products"]))
    covariates = {r["stable_star_id"]: r for r in read_table(contained(root, cfg["covariates"]))}
    exclusions = read_table(contained(root, cfg["exclusions"]))
    if len({r["stable_star_id"] for r in exclusions}) != len(exclusions):
        raise ValueError("duplicate exclusion decisions")
    if any(r["stable_star_id"] not in population or r["topology_seen"] != "false" or not r["reason_code"] or not r["evidence"] for r in exclusions):
        raise ValueError("exclusions must have pre-topology evidence and cohort membership")
    excluded = {r["stable_star_id"]: r["reason_code"] for r in exclusions}
    results = []
    for row in split:
        star = row["stable_star_id"]
        star_slug(star)
        if row["role"] not in ROLES or star != "KIC " + row["kic"] or row["group_key"] != "stable_star_id":
            raise ValueError("invalid star grouping/identifier/role")
        ref = [r for r in references if r["stable_star_id"] == star]
        if {r["quantity"] for r in ref} < {"numax", "dnu", "teff"}:
            raise ValueError(f"missing global reference for {star}")
        lookup = {r["quantity"]: r for r in ref}
        if any(sum(r["quantity"] == q for r in ref) != 1 for q in ("numax", "dnu", "teff")):
            raise ValueError("duplicate global reference quantity")
        candidate = [r for r in products if r["stable_star_id"] == star]
        if any(r["partition_role"] != row["role"] for r in candidate):
            raise ValueError("product partition differs from its parent star")
        if len({r["product_filename"] for r in candidate}) != len(candidate):
            raise ValueError("duplicate mission product")
        record: dict[str, Any] = {"stable_star_id": star, "kic": row["kic"], "role": row["role"],
                                  "stratum": row["stratum"], "candidate_products": len(candidate),
                                  "exclusion": excluded.get(star), "reference_scope": "published_metadata_visible_before_holdout",
                                  "source_id": lookup["numax"]["source_id"],
                                  "numax_uHz": float(lookup["numax"]["value"]), "dnu_uHz": float(lookup["dnu"]["value"]),
                                  "teff_K": float(lookup["teff"]["value"]),
                                  "kp_mag": float(covariates[star]["kp_mag"]),
                                  "linewidth_uHz": float(covariates[star]["linewidth_uHz"]) if covariates[star]["linewidth_uHz"] else None,
                                  "mode_category": covariates[star]["mode_category"],
                                  "evolutionary_state": covariates[star]["evolutionary_state"]}
        for q in ("numax", "dnu"):
            r = lookup[q]
            if r["unit"] != "uHz" or float(r["value"]) <= 0 or not r["source_id"] or not r["uncertainty_type"] or min(float(r["uncertainty_minus"]), float(r["uncertainty_plus"])) < 0:
                raise ValueError("invalid reference units, provenance or uncertainty semantics")
            record[q + "_reference_minus"] = float(r["uncertainty_minus"])
            record[q + "_reference_plus"] = float(r["uncertainty_plus"])
            record[q + "_uncertainty_semantics"] = r["uncertainty_type"]
        results.append(record)
    return results


def source_fingerprint(root: Path) -> str:
    paths = sorted((root / "src/topoastero").glob("*.py")) + sorted((root / "workflows").glob("*stage11*.py"))
    return content_hash([seal(root, path) for path in paths])


def star_input_id(root: Path, cfg: dict[str, Any], star: str) -> str:
    manifest = read_json(contained(root, cfg["acquisition"]))
    return content_hash({"configuration": cfg, "code": source_fingerprint(root),
                         "products": [r for r in manifest["products"] if r["stable_star_id"] == star]})


def run_star(root: Path, cache: Path, cfg: dict[str, Any], member: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Process one star and seal its first completed checkpoint; errors are reason-coded."""
    star = member["stable_star_id"]
    fingerprint = star_input_id(root, cfg, star)
    checkpoint = directory / "star_manifest.json"
    if checkpoint.exists():
        old = read_json(checkpoint)
        issues = seal_issues(root, old["files"])
        if old["input_id"] != fingerprint or issues:
            raise ValueError("star checkpoint inputs/seals changed; use a new development output directory")
        return read_json(directory / "analysis.json")
    paths, expected = verified_star_products(root, cache, cfg, star)
    result: dict[str, Any] = {"stable_star_id": star, "role": member["role"], "input_id": fingerprint,
                              "available_products": len(paths), "expected_products": expected,
                              "reference_values_used_in_estimation": False}
    directory.mkdir(parents=True, exist_ok=True)
    if member["exclusion"]:
        result.update(status="excluded", quality_flags=["preregistered_exclusion"], reason=member["exclusion"])
    elif len(paths) < cfg["observation"]["minimum_months"]:
        result.update(status="missing_input", quality_flags=["missing_products"], reason="fewer_than_three_nonoverlapping_months")
    else:
        try:
            frequency, spectra, weights, meta = monthly_spectra(paths, cfg)
            seed = cfg["master_seed"] + int(member["kic"])
            science, mean, background, bootstrap = analyze_spectra(frequency, spectra, weights, cfg, seed=seed, duty_cycle=meta["duty_cycle"])
            result.update(science)
            result.update(meta)
            if len(paths) < expected:
                result["quality_flags"].append("incomplete_products")
                if result["status"] == "ok":
                    result["status"] = "limited"
            write_table(directory / "mean_spectrum.csv", [{"frequency_uHz": float(f), "power_ppm2_per_uHz": float(p), "background_ppm2_per_uHz": float(b)} for f, p, b in zip(frequency, mean, background, strict=True)])
            np.savez_compressed(directory / "monthly_spectra.npz", frequency_uHz=frequency, spectra=spectra, exposure_cadences=weights)
            write_table(directory / "segment_bootstrap.csv", bootstrap, ["draw", "classical_numax", "classical_dnu", "topology_numax", "topology_dnu"])
        except (ValueError, RuntimeError, OSError, FloatingPointError) as exc:
            result.update(status="pipeline_failure", quality_flags=["pipeline_failure"], reason=f"{type(exc).__name__}: {exc}")
    write_json(directory / "analysis.json", result)
    files = [seal(root, p) for p in sorted(directory.iterdir()) if p.is_file() and p.name != "star_manifest.json"]
    write_json(checkpoint, {"schema_version": 1, "stable_star_id": star, "role": member["role"], "input_id": fingerprint, "files": files}, exclusive=True)
    return result


def ratio_benchmark(root: Path, cfg: dict[str, Any], member: dict[str, Any], result: dict[str, Any], directory: Path) -> list[dict[str, Any]]:
    """Formula checks plus reference-anchored PSD localization, explicitly conditional.

    Degree and radial order are supplied by the corrected mode table. This is
    NEVER a blind topological r02 measurement. Missing modes remain missing;
    source covariance is unavailable, so joint ratio uncertainty is withheld.
    """
    star = member["stable_star_id"]
    modes = [r for r in read_table(contained(root, cfg["mode_references"])) if r["stable_star_id"] == star]
    published = [r for r in read_table(contained(root, cfg["ratio_references"])) if r["stable_star_id"] == star]
    mode_map = {(int(r["radial_order_n"]), int(r["angular_degree_l"])): float(r["frequency_uHz"]) for r in modes}
    formula = {int(str(r["radial_order_n"])): r for r in five_point_frequency_ratios(mode_map)}
    located: dict[tuple[int, int], float] = {}
    adequate = result.get("envelope_ratio", 0) >= cfg["quality"]["minimum_envelope_ratio"] and (directory / "mean_spectrum.csv").exists()
    if adequate:
        spectrum = read_table(directory / "mean_spectrum.csv")
        frequency = np.asarray([float(r["frequency_uHz"]) for r in spectrum])
        ratio = np.asarray([float(r["power_ppm2_per_uHz"]) / float(r["background_ppm2_per_uHz"]) for r in spectrum])
        from scipy.signal import find_peaks  # type: ignore[import-untyped]

        peaks, _ = find_peaks(ratio)
        used = set()
        for key, at in sorted(mode_map.items()):
            candidates = [int(i) for i in peaks if abs(frequency[i] - at) <= cfg["quality"]["reference_anchor_tolerance_uHz"] and int(i) not in used]
            if candidates:
                winner = max(candidates, key=lambda i: ratio[i])
                located[key] = float(frequency[winner])
                used.add(winner)
    measurements = {int(str(r["radial_order_n"])): r for r in five_point_frequency_ratios(located)}
    rows = []
    for ref in published:
        n, kind = int(ref["radial_order_n"]), ref["ratio_type"]
        exact = formula.get(n, {}).get(kind)
        measured = measurements.get(n, {}).get(kind)
        rows.append({"stable_star_id": star, "role": member["role"], "radial_order_n": n, "ratio_type": kind,
                     "published": float(ref["value"]), "published_minus": float(ref["uncertainty_minus"]), "published_plus": float(ref["uncertainty_plus"]),
                     "formula_from_published_medians": exact, "formula_minus_published": float(exact) - float(ref["value"]) if exact is not None else None,
                     "anchored_psd_ratio": measured, "anchored_minus_published": float(measured) - float(ref["value"]) if measured is not None else None,
                     "adequate_envelope": adequate, "source_edition": ref["source_edition"],
                     "interpretation": "reference_conditioned_degree_order_localization; median_of_ratio_need_not_equal_ratio_of_medians",
                     "blind_geometric_ratio": None, "joint_uncertainty": "withheld_no_published_covariance"})
    return rows


def catalog_rows(member: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for method in ("classical", "topology"):
        for quantity in ("numax", "dnu"):
            key = method + "_" + quantity
            interval = result.get("intervals", {}).get(key, {})
            measured = result.get(key) if result["status"] not in ("excluded", "not_detected", "missing_input", "pipeline_failure") else None
            rows.append({"stable_star_id": member["stable_star_id"], "role": member["role"], "method": method, "quantity": quantity,
                         "estimate": measured, "lower": interval.get("lower") if measured is not None else None,
                         "upper": interval.get("upper") if measured is not None else None,
                         "reference": member[quantity + "_uHz"], "reference_minus": member[quantity + "_reference_minus"],
                         "reference_plus": member[quantity + "_reference_plus"], "reference_semantics": member[quantity + "_uncertainty_semantics"],
                         "status": result["status"], "flags": ";".join(result["quality_flags"]),
                         "numax_uHz": member["numax_uHz"], "dnu_uHz": member["dnu_uHz"], "teff_K": member["teff_K"],
                         "kp_mag": member["kp_mag"], "linewidth_uHz": member["linewidth_uHz"], "evolutionary_state": member["evolutionary_state"],
                         "mode_category": member["mode_category"], "envelope_ratio": result.get("envelope_ratio"),
                         "duty_cycle": result.get("duty_cycle"), "duration_days": result.get("duration_days"),
                         "available_products": result["available_products"], "expected_products": result["expected_products"],
                         "input_id": result["input_id"]})
    return rows


def run_role(root: Path, cache: Path, cfg: dict[str, Any], role: str, directory: Path, *, confirmation: bool = False) -> dict[str, Any]:
    """Never select holdout stars through the development entry point."""
    if role not in ROLES or (role == "final_holdout" and not confirmation):
        raise ValueError("holdout analysis requires the one-time confirmation entry point")
    if role == "final_holdout":
        state_path = contained(root, cfg["confirmation_state"])
        if not state_path.exists():
            raise ValueError("holdout opening state has not been reserved")
        state = read_json(state_path)
        release_path = contained(root, cfg["release"])
        if (state["status"] != "running" or state["opening_count"] != 1 or not release_path.exists()
                or state["configuration_sha256"] != content_hash(cfg) or state["code_sha256"] != source_fingerprint(root)
                or state["release_sha256"] != sha256_file(release_path)):
            raise ValueError("holdout opening state/release is not the reserved exact attempt")
    members = [m for m in cohort(root, cfg) if m["role"] == role]
    batch_code = source_fingerprint(root)
    catalog, ratios, statuses = [], [], []
    for index, member in enumerate(members, 1):
        print(f"[{role} {index}/{len(members)}] {member['stable_star_id']}", flush=True)
        star_dir = directory / "stars" / star_slug(member["stable_star_id"])
        result = run_star(root, cache, cfg, member, star_dir)
        if source_fingerprint(root) != batch_code:
            raise ValueError("source changed during a batch; log the general fix and rerun in a new development directory")
        catalog.extend(catalog_rows(member, result))
        ratios.extend(ratio_benchmark(root, cfg, member, result, star_dir))
        statuses.append({"stable_star_id": member["stable_star_id"], "status": result["status"],
                         "flags": result["quality_flags"], "input_id": result["input_id"]})
    performance, comparison = build_performance(catalog, cfg, role=role)
    write_table(directory / "catalog.csv", catalog)
    write_json(directory / "catalog.json", {"schema_version": 1, "role": role, "rows": catalog})
    write_table(directory / "performance.csv", performance)
    write_table(directory / "paired_comparisons.csv", comparison)
    write_table(directory / "operating_domain.csv", operating_domain(catalog, cfg))
    write_table(directory / "ratio_benchmark.csv", ratios)
    summary = {"schema_version": 1, "role": role, "stars": len(members), "statuses": statuses,
               "stars_with_estimates": len({r["stable_star_id"] for r in catalog if r["estimate"] is not None}),
               "configuration_sha256": content_hash(cfg), "code_sha256": batch_code,
               "holdout_used": role == "final_holdout", "bootstrap_unit": "star_for_population_month_for_star_interval",
               "primary_quantities": cfg["statistics"]["primary_quantities"], "multiplicity": "holm_primary_tost",
               "probability_calibration": "withheld_positive_only_no_null_validation",
               "ridge_inference": "geometry_only", "split_sha256": sha256_file(contained(root, cfg["partitions"]))}
    write_json(directory / "summary.json", summary)
    write_json(directory / "run_manifest.json", {"schema_version": 1, "role": role,
                                                "files": [seal(root, p) for p in sorted(directory.rglob("*")) if p.is_file() and p.name != "run_manifest.json"]})
    if not confirmation:
        append_event(contained(root, cfg["qa_log"]), {"event": "development_batch", "role": role,
                                                     "configuration_sha256": content_hash(cfg), "code_sha256": source_fingerprint(root),
                                                     "result_manifest_sha256": sha256_file(directory / "run_manifest.json"),
                                                     "holdout_used": False})
    return summary
