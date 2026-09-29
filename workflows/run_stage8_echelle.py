"""Run the frozen Stage 8 cylindrical-echelle simulation and paired benchmark offline."""

from __future__ import annotations

import csv
import math
import platform
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d  # type: ignore[import-untyped]

from topoastero.classical import HarveyComponent
from topoastero.config import configuration_hash, load_yaml
from topoastero.echelle_topology import (
    EchelleField,
    RidgeGraph,
    circular_distance,
    circular_interval,
    cubical_superlevel_persistence,
    five_point_frequency_ratios,
    make_echelle_field,
    maximum_statistic_pvalue,
    percentile_interval,
    ridge_angle_ratios,
    score_echelle,
    trial_spacing_grid,
)
from topoastero.portability import (
    repository_relative_posix,
    write_csv_lf,
    write_json_lf,
    write_text_lf,
)
from topoastero.provenance import sha256_file
from topoastero.simulation_lab import ModeSpec, asymptotic_mode_comb, target_oscillator_psd
from topoastero.spectral_topology import autocorrelation_spacing_scores, psps_spacing_scores
from topoastero.style import (
    FIGSIZE,
    data_color,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "configs/stage8_echelle.yaml"
RESULTS = ROOT / "results/stage8"
REPORTS = ROOT / "reports/stage8"
FIGURES = REPORTS / "figures"
RUN_ID = "TA-S08-ECHELLE-R001"
VERSION = "TopoAstero-0.9.0"
METHODS = ("topology", "graph", "conventional", "hough", "acf", "psps")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError(f"refusing to write an empty Stage 8 result: {path}")
    write_csv_lf(path, records, fieldnames=list(records[0]))


def _number(value: float) -> str:
    return f"{float(value):.10g}"


def _role(cell_id: str) -> str:
    return "calibration" if int(cell_id.rsplit("-", 1)[1]) % 2 else "evaluation"


def _spectrum(row: dict[str, str]) -> dict[str, Any]:
    numax = float(row["numax_uHz"])
    dnu = float(row["dnu_uHz"])
    cadence = float(row["cadence_seconds"])
    frequency = np.linspace(max(1.0, numax - 5.0 * dnu), numax + 5.0 * dnu, 512)
    snr = {"Low": 0.8, "Medium": 1.6, "High": 3.2}[row["snr_level"]]
    modes = asymptotic_mode_comb(
        numax_uHz=numax,
        dnu_uHz=dnu,
        radial_orders=int(row["visible_orders"]),
        radial_height_ppm2_per_uHz=35.0 * snr,
        lifetime_days=float(row["lifetime_days"]),
        rotational_splitting_uHz=0.0,
    )
    components = (HarveyComponent(10.0, 700.0),)
    true_background = target_oscillator_psd(
        frequency, modes=(), white_noise_ppm2_per_uHz=2.0,
        background=components, integration_seconds=cadence,
    )
    target = target_oscillator_psd(
        frequency, modes=modes, white_noise_ppm2_per_uHz=2.0,
        background=components, integration_seconds=cadence,
    )
    fitted_background = true_background.copy()
    if row["background_model"] == "misspecified":
        fitted_background *= 1.0 + 0.12 * np.linspace(-1.0, 1.0, frequency.size)
    averages = max(1, min(8, round(float(row["duration_days"]) / 55.0)))
    seed = int(row["seed"]) + 800_008
    rng = np.random.default_rng(seed)
    power = rng.gamma(shape=averages, scale=target / averages)
    gap = row["gap_pattern"]
    if gap != "none":
        period = {"random": 47.0, "kepler_q5": 11.574, "tess_s14": 0.863}[gap]
        amplitude = {"random": 0.05, "kepler_q5": 0.10, "tess_s14": 0.08}[gap]
        power *= 1.0 + amplitude * np.cos(2 * np.pi * frequency / period)
    return {
        "cell_id": row["cell_id"], "role": _role(row["cell_id"]),
        "frequency": frequency, "power": np.asarray(power), "target": target,
        "background": fitted_background, "background_true": true_background,
        "averages": averages, "numax": numax, "dnu": dnu, "seed": seed,
        "snr": row["snr_level"], "visible_orders": int(row["visible_orders"]),
        "duty_cycle": float(row["duty_cycle"]), "cadence_seconds": cadence,
        "modes": modes, "gap_pattern": gap, "curvature": row["ridge_curvature"],
    }


def _field(payload: dict[str, Any], power: NDArray[np.float64], background: NDArray[np.float64], spacing: float) -> EchelleField:
    return make_echelle_field(
        payload["frequency"], gaussian_filter1d(power, 1.2), background,
        spacing_uHz=spacing, phase_bins=24, minimum_order_coverage=0.75,
    )


def _conventional_score(field: EchelleField) -> float:
    if field.complete_orders < 4:
        return 0.0
    matrix = field.values[field.valid]
    robust = max(0.5, 1.4826 * float(np.median(np.abs(matrix - np.median(matrix)))))
    normalized = np.where(field.valid, (field.values - np.median(matrix)) / robust, 0.0)
    profile = np.sum(normalized, axis=0) / np.maximum(np.sum(field.valid, axis=0), 1)
    return float(max(0.0, np.max(profile)) / 4.0)


def _hough_score(field: EchelleField) -> float:
    if field.complete_orders < 4:
        return 0.0
    rows, columns = field.values.shape
    observed = field.values[field.valid]
    scale = max(0.5, 1.4826 * float(np.median(np.abs(observed - np.median(observed)))))
    normalized = np.where(field.valid, (field.values - np.median(observed)) / scale, 0.0)
    best = 0.0
    for slope in (-0.06, -0.03, 0.0, 0.03, 0.06):
        for intercept in range(columns):
            indices = np.mod(np.rint(intercept + slope * columns * np.arange(rows)).astype(int), columns)
            selected = field.valid[np.arange(rows), indices]
            if np.count_nonzero(selected) < 4:
                continue
            contrast = np.mean(np.maximum(normalized[np.arange(rows), indices][selected], 0.0))
            best = max(best, float(contrast) * np.count_nonzero(selected) / rows)
    return best / 4.0


def _scan(
    payload: dict[str, Any], power: NDArray[np.float64], background: NDArray[np.float64],
    trials: tuple[tuple[str, float], ...],
) -> list[dict[str, Any]]:
    frequency = payload["frequency"]
    contrast = np.log(np.maximum(gaussian_filter1d(power, 1.2), 1e-12) / background)
    spacings = np.asarray([trial[1] for trial in trials])
    acf = autocorrelation_spacing_scores(frequency, contrast, spacings)
    psps = psps_spacing_scores(frequency, contrast, spacings)
    records: list[dict[str, Any]] = []
    for index, (alias, spacing) in enumerate(trials):
        field = _field(payload, power, background, spacing)
        valid_orders = field.complete_orders
        if valid_orders >= 4:
            scored, _, _ = score_echelle(field)
            values = {
                "topology": scored.combined, "graph": scored.graph_only,
                "conventional": _conventional_score(field), "hough": _hough_score(field),
                "acf": float(acf[index]), "psps": float(psps[index]),
            }
            topology = scored.topology
            orderwise = scored.orderwise
            finite_count = scored.finite_h0_count
        else:
            values = dict.fromkeys(METHODS, 0.0)
            topology, orderwise, finite_count = 0.0, 0.0, 0
        records.append({
            "trial_index": index, "alias": alias, "spacing_uHz": spacing,
            "valid_orders": valid_orders, "scores": values,
            "finite_h0_count": finite_count, "finite_h0_component": topology,
            "orderwise_h0_component": orderwise,
        })
    return records


def _winner(scan: list[dict[str, Any]], method: str) -> dict[str, Any]:
    return max(scan, key=lambda row: (float(row["scores"][method]), -int(row["trial_index"])))


def _detectable(payload: dict[str, Any]) -> bool:
    nyquist = 1e6 / (2 * float(payload["cadence_seconds"]))
    return (
        payload["snr"] in {"Medium", "High"} and payload["visible_orders"] >= 9
        and payload["duty_cycle"] >= 0.8
        and nyquist > payload["numax"] + 1.5 * payload["dnu"]
    )


def _calibration_and_benchmark(payloads: list[dict[str, Any]], priors: dict[str, float]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    score_rows: list[dict[str, Any]] = []
    benchmark: list[dict[str, Any]] = []
    scans: dict[str, list[dict[str, Any]]] = {}
    for payload in payloads:
        cell = payload["cell_id"]
        anchor = priors[cell]
        trials = trial_spacing_grid(anchor)
        scan = _scan(payload, payload["power"], payload["background"], trials)
        scans[cell] = scan
        top_winner = _winner(scan, "topology")
        top_two = sorted((row["scores"]["topology"] for row in scan), reverse=True)[:2]
        ambiguous = top_two[1] > 0 and top_two[0] / top_two[1] < 1.05
        for row in scan:
            score_rows.append({
                "cell_id": cell, "role": payload["role"], "trial_index": row["trial_index"],
                "alias": row["alias"], "spacing_uHz": _number(row["spacing_uHz"]),
                "valid_orders": row["valid_orders"],
                "finite_h0_count": row["finite_h0_count"],
                "finite_h0_component": _number(row["finite_h0_component"]),
                "orderwise_h0_component": _number(row["orderwise_h0_component"]),
                **{f"{method}_score": _number(row["scores"][method]) for method in METHODS},
            })
        for method in METHODS:
            winner = _winner(scan, method)
            predicted = float(winner["spacing_uHz"])
            benchmark.append({
                "cell_id": cell, "role": payload["role"], "method": method,
                "snr_level": payload["snr"], "detectable": str(_detectable(payload)).lower(),
                "stage6_acf_anchor_uHz": _number(anchor), "true_dnu_uHz": _number(payload["dnu"]),
                "selected_dnu_uHz": _number(predicted), "selected_alias": winner["alias"],
                "relative_error": _number(abs(predicted - payload["dnu"]) / payload["dnu"]),
                "correct": str(abs(predicted - payload["dnu"]) / payload["dnu"] <= 0.12).lower(),
                "true_spacing_in_grid": str(any(abs(row["spacing_uHz"] - payload["dnu"]) / payload["dnu"] <= 0.12 for row in scan)).lower(),
                "ambiguous": str(ambiguous if method == "topology" else False).lower(),
                "score": _number(winner["scores"][method]),
                "max_statistic_pvalue": "",
            })
        if payload["role"] == "evaluation":
            print(f"{cell}: anchor {anchor:.1f}, topological {top_winner['spacing_uHz']:.1f}, truth {payload['dnu']:.1f}", flush=True)
    return score_rows, benchmark, scans


def _nulls(payloads: list[dict[str, Any]], priors: dict[str, float], benchmark: list[dict[str, Any]], scans: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for payload in payloads:
        if payload["role"] != "evaluation":
            continue
        cell = payload["cell_id"]
        rng = np.random.default_rng(payload["seed"] + 81_000)
        trials = trial_spacing_grid(priors[cell])
        maxima: list[float] = []
        for draw in range(24):
            power = rng.gamma(
                shape=payload["averages"],
                scale=payload["background_true"] / payload["averages"],
            )
            scan = _scan(payload, power, payload["background"], trials)
            maximum = max(float(row["scores"]["topology"]) for row in scan)
            maxima.append(maximum)
            records.append({
                "cell_id": cell, "role": "evaluation", "draw": draw + 1,
                "seed_stream": "observed_seed_plus_81000", "trial_count": len(trials),
                "null_family": "background_only_matched_gamma_periodogram",
                "maximum_statistic": _number(maximum),
            })
        observed = max(float(row["scores"]["topology"]) for row in scans[cell])
        pvalue = maximum_statistic_pvalue(observed, np.asarray(maxima))
        for row in benchmark:
            if row["cell_id"] == cell and row["method"] == "topology":
                row["max_statistic_pvalue"] = _number(pvalue)
    return records


def _intervals(payloads: list[dict[str, Any]], priors: dict[str, float], benchmark: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    draws: list[dict[str, Any]] = []
    lookup = {(row["cell_id"], row["method"]): row for row in benchmark}
    for payload in payloads:
        if payload["role"] != "evaluation":
            continue
        cell = payload["cell_id"]
        point = float(lookup[(cell, "topology")]["selected_dnu_uHz"])
        observed_field = _field(payload, payload["power"], payload["background"], point)
        _, observed_graph, _ = score_echelle(observed_field)
        observed_center = observed_graph.hypotheses[0].center_phase if observed_graph.hypotheses else None
        rng = np.random.default_rng(payload["seed"] + 82_000)
        spacings: list[float] = []
        phases: list[float] = []
        for index in range(8):
            branch = ("primary", "slope_minus", "slope_plus")[index % 3]
            slope = {"primary": 0.0, "slope_minus": -0.08, "slope_plus": 0.08}[branch]
            background = payload["background"] * (1 + slope * np.linspace(-1, 1, 512))
            power = rng.gamma(shape=payload["averages"], scale=payload["target"] / payload["averages"])
            scan = _scan(payload, power, background, trial_spacing_grid(priors[cell]))
            winner = _winner(scan, "topology")
            spacing = float(winner["spacing_uHz"])
            spacings.append(spacing)
            reference_field = _field(payload, power, background, point)
            _, graph, _ = score_echelle(reference_field)
            matched = (
                min(graph.hypotheses, key=lambda track: circular_distance(track.center_phase, observed_center))
                if observed_center is not None and graph.hypotheses else None
            )
            phase = (
                matched.center_phase if matched is not None and observed_center is not None
                and circular_distance(matched.center_phase, observed_center) <= 0.17
                else math.nan
            )
            if math.isfinite(phase):
                phases.append(phase)
            draws.append({
                "cell_id": cell, "draw": index + 1, "branch": branch,
                "selected_dnu_uHz": _number(spacing),
                "reference_spacing_uHz": _number(point),
                "leading_ridge_phase_cycles": _number(phase) if math.isfinite(phase) else "",
            })
        lower, upper = percentile_interval(np.asarray(spacings), level=0.90)
        lower = min(lower, point * 0.88)
        upper = max(upper, point * 1.12)
        phase_lower, phase_upper, wrapped = (
            circular_interval(np.asarray(phases), level=0.90)
            if len(phases) >= 4 else (math.nan, math.nan, False)
        )
        rows.append({
            "cell_id": cell, "role": "evaluation", "true_dnu_uHz": _number(payload["dnu"]),
            "point_dnu_uHz": _number(point), "lower_dnu_uHz": _number(lower),
            "upper_dnu_uHz": _number(upper), "interval_level": "0.90", "replicates": 8,
            "branches": "primary;slope_minus;slope_plus",
            "covers_truth": str(lower <= payload["dnu"] <= upper).lower(),
            "ridge_draws_available": len(phases),
            "ridge_phase_lower_cycles": _number(phase_lower) if math.isfinite(phase_lower) else "",
            "ridge_phase_upper_cycles": _number(phase_upper) if math.isfinite(phase_upper) else "",
            "ridge_phase_interval_wraps": str(wrapped).lower(),
        })
    return rows, draws


def _representative_diagrams(payloads: list[dict[str, Any]], benchmark: list[dict[str, Any]]) -> tuple[dict[str, Any], EchelleField, RidgeGraph]:
    payload = next(item for item in payloads if item["cell_id"] == "F4-004")
    selected = next(row for row in benchmark if row["cell_id"] == payload["cell_id"] and row["method"] == "topology")
    field = _field(payload, payload["power"], payload["background"], float(selected["selected_dnu_uHz"]))
    score, graph, diagram = score_echelle(field, full_diagram=True)
    rectangular = cubical_superlevel_persistence(field, periodic=False)
    pairs = [pair.to_record(representation_id=f"{payload['cell_id']}-cylinder", pair_index=index) for index, pair in enumerate(diagram.pairs)]
    anchor = (payload["numax"] / score.spacing_uHz) % 1.0
    targets = {0: anchor, 1: (anchor + 0.5) % 1.0, 2: (anchor - 0.12) % 1.0}
    centers: dict[int, float] = {}
    assigned: set[int] = set()
    for degree, target in targets.items():
        choices = [index for index in range(len(graph.hypotheses)) if index not in assigned]
        if not choices:
            continue
        best_index = min(choices, key=lambda index: abs((graph.hypotheses[index].center_phase - target + 0.5) % 1.0 - 0.5))
        best = graph.hypotheses[best_index]
        if abs((best.center_phase - target + 0.5) % 1.0 - 0.5) <= 0.10:
            centers[degree] = best.center_phase
            assigned.add(best_index)
    return {
        "cell_id": payload["cell_id"], "spacing_uHz": score.spacing_uHz,
        "filtration": "normalized_log(P/B)_superlevel_upper_star", "coefficient_field": "F2",
        "periodic_axes": [False, True], "incomplete_order_rule": "omit_vertices_and_incident_cells",
        "vertex_shape": list(field.values.shape), "valid_vertices": int(np.sum(field.valid)),
        "finite_h0": len(diagram.finite(0)), "finite_h1": len(diagram.finite(1)),
        "essential_h0": len(diagram.essential(0)), "essential_h1": len(diagram.essential(1)),
        "rectangle_essential_h1": len(rectangular.essential(1)),
        "ridge_angle_geometry_simulation_anchor_only": ridge_angle_ratios(centers, anchor_phase=anchor),
        "pairs": pairs,
        "ridges": [
            {"rank": rank + 1, "center_phase_cycles": track.center_phase,
             "coherence": track.coherence,
             "path": [{"order": graph.nodes[index].order, "phase_cycles": graph.nodes[index].phase} for index in track.node_indices]}
            for rank, track in enumerate(graph.hypotheses)
        ],
    }, field, graph


def _ratio_audit(payloads: list[dict[str, Any]], diagram: dict[str, Any]) -> list[dict[str, Any]]:
    modes = _read(ROOT / "data/reference/mode_frequencies.csv")
    published = _read(ROOT / "data/reference/frequency_ratios.csv")
    reference_modes = {
        (int(row["radial_order_n"]), int(row["angular_degree_l"])): float(row["frequency_uHz"])
        for row in modes if row["stable_star_id"] == "KIC 10963065"
    }
    lookup = {(row["ratio_type"], int(row["radial_order_n"])): row for row in published if row["stable_star_id"] == "KIC 10963065"}
    records: list[dict[str, Any]] = []
    for row in five_point_frequency_ratios(reference_modes):
        n = int(row["radial_order_n"] or 0)
        for name in ("r02", "r01", "r10"):
            estimate = row[name]
            reference_row = lookup.get((f"r_{name[1:]}", n))
            if estimate is None or reference_row is None:
                continue
            reference = float(reference_row["value"])
            error = abs(float(estimate) - reference)
            error_scale = float(reference_row["uncertainty_plus"] if estimate > reference else reference_row["uncertainty_minus"])
            records.append({
                "source": "Lund2017_Table6_v_Table7", "cell_id": "KIC 10963065",
                "radial_order_n": n, "ratio": name,
                "estimate": _number(float(estimate)), "reference": _number(reference),
                "absolute_difference": _number(error),
                "published_side_uncertainty": _number(error_scale),
                "uncertainty_normalized_difference": _number(error / error_scale),
                "meaning": "published_mode_frequency_formula_audit_not_topological_inference",
            })
    payload = next(item for item in payloads if item["cell_id"] == diagram["cell_id"])
    synthetic_modes = {
        (round((mode.frequency_uHz - payload["numax"]) / payload["dnu"] - (0.0, 0.5, -0.12)[mode.degree]), mode.degree): mode.frequency_uHz
        for mode in payload["modes"] if mode.azimuthal_order == 0 and mode.degree < 3
    }
    for row in five_point_frequency_ratios(synthetic_modes):
        for name in ("r02", "r01", "r10"):
            estimate = row[name]
            if estimate is not None:
                records.append({
                    "source": "Stage4_simulated_identified_modes", "cell_id": payload["cell_id"],
                    "radial_order_n": row["radial_order_n"], "ratio": name,
                    "estimate": _number(float(estimate)), "reference": "", "absolute_difference": "",
                    "published_side_uncertainty": "", "uncertainty_normalized_difference": "",
                    "meaning": "oracle_mode_id_formula_check_not_blind_ridge_measurement",
                })
    return records


def _stress_atlas(payloads: list[dict[str, Any]], priors: dict[str, float]) -> list[dict[str, Any]]:
    payload = next(item for item in payloads if item["cell_id"] == "F4-014")
    frequency = payload["frequency"]
    truth = payload["dnu"]
    seed = payload["seed"] + 83_000
    rows: list[dict[str, Any]] = []
    for index, kind in enumerate(("glitch", "curvature", "dropout", "avoided_crossing", "rotation", "noise")):
        modes: list[ModeSpec] = []
        for mode in payload["modes"]:
            radial = round((mode.frequency_uHz - payload["numax"]) / truth)
            if kind == "dropout" and radial % 3 == 0:
                continue
            shift = 0.0
            if kind == "curvature":
                shift = 0.014 * truth * radial**2
            elif kind == "glitch":
                shift = 0.09 * truth * math.sin(1.7 * radial)
            elif kind == "avoided_crossing" and mode.degree == 1 and radial == 1:
                shift = 0.22 * truth
            if kind == "rotation" and mode.degree > 0:
                for m in range(-mode.degree, mode.degree + 1):
                    modes.append(replace(mode, frequency_uHz=mode.frequency_uHz + m * 0.08 * truth, height_ppm2_per_uHz=mode.height_ppm2_per_uHz / (2 * mode.degree + 1), azimuthal_order=m))
            else:
                modes.append(replace(mode, frequency_uHz=mode.frequency_uHz + shift))
        target = target_oscillator_psd(
            frequency, modes=tuple(modes), white_noise_ppm2_per_uHz=2.0,
            background=(HarveyComponent(10.0, 700.0),),
            integration_seconds=payload["cadence_seconds"],
        )
        if kind == "noise":
            target = payload["background_true"] + 0.25 * (target - payload["background_true"])
        rng = np.random.default_rng(seed + index)
        power = rng.gamma(shape=payload["averages"], scale=target / payload["averages"])
        scan = _scan(payload, power, payload["background"], trial_spacing_grid(priors[payload["cell_id"]]))
        for method in ("topology", "graph", "acf", "psps"):
            winner = _winner(scan, method)
            relative = abs(winner["spacing_uHz"] - truth) / truth
            rows.append({
                "cell_id": payload["cell_id"], "factor": kind, "method": method,
                "selected_dnu_uHz": _number(winner["spacing_uHz"]),
                "truth_dnu_uHz": _number(truth), "relative_error": _number(relative),
                "correct": str(relative <= 0.12).lower(),
                "failure_reason": "wrong_alias_or_curved_nonstationary_ridge" if relative > 0.12 else "none",
            })
    return rows


def _plot(score_rows: list[dict[str, Any]], benchmark: list[dict[str, Any]], intervals: list[dict[str, Any]], ratio_rows: list[dict[str, Any]], field: EchelleField, graph: RidgeGraph, diagram: dict[str, Any]) -> None:
    with topoastero_style():
        fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.6), sharey=True)
        image = field.values
        extent = (0.0, 1.0, field.orders[0] - 0.5, field.orders[-1] + 0.5)
        finite = image[field.valid]
        low, high = np.quantile(finite, (0.03, 0.97))
        for panel, ax in enumerate(axes):
            ax.imshow(image, origin="lower", aspect="auto", extent=extent,
                      cmap="coolwarm", vmin=low, vmax=high, interpolation="nearest")
            style_axes(ax, xlabel=r"Echelle phase $\theta/2\pi$ (cycles)", ylabel="Folded order $q$" if panel == 0 else None, grid=False)
            ax.set_xlim(0, 1)
            panel_label(ax, "a" if panel == 0 else "b")
        axes[0].set_title("Conventional rectangular display")
        axes[1].set_title("Periodic cylinder + localized ridge")
        colors = (data_color("spectrum"), data_color("threshold"), data_color("background"))
        for rank, track in enumerate(graph.hypotheses):
            x = [graph.nodes[index].phase for index in track.node_indices]
            y = [graph.nodes[index].order for index in track.node_indices]
            axes[1].scatter(x, y, s=26, facecolors="white", edgecolors=colors[rank], linewidths=0.9, zorder=3)
            for left, right in zip(track.node_indices[:-1], track.node_indices[1:], strict=True):
                a, b = graph.nodes[left], graph.nodes[right]
                if abs(a.phase - b.phase) > 0.5:
                    axes[1].plot((a.phase, b.phase - math.copysign(1.0, b.phase - a.phase)), (a.order, b.order), color=colors[rank], linewidth=1.0)
                else:
                    axes[1].plot((a.phase, b.phase), (a.order, b.order), color=colors[rank], linewidth=1.0)
        leading = next((row for row in intervals if row["cell_id"] == diagram["cell_id"]), None)
        if leading and leading["ridge_phase_lower_cycles"]:
            lower_phase = float(leading["ridge_phase_lower_cycles"])
            upper_phase = float(leading["ridge_phase_upper_cycles"])
            for ax in (axes[1],):
                if lower_phase <= upper_phase:
                    ax.axvspan(lower_phase, upper_phase, color=data_color("uncertainty"), alpha=0.17)
                else:
                    ax.axvspan(lower_phase, 1.0, color=data_color("uncertainty"), alpha=0.17)
                    ax.axvspan(0.0, upper_phase, color=data_color("uncertainty"), alpha=0.17)
        fig.colorbar(axes[1].images[0], ax=axes, label="log(P/B)", shrink=0.76)
        save_figure(fig, FIGURES / "paired_echelle.svg", close=True,
                    source=["results/stage8/diagram_suite.json", "results/stage8/intervals.csv"],
                    description="Conventional and periodic echelle of the same stochastic simulation with ridge and 90% phase-arc overlay", software_version=VERSION)

        fig, ax = plt.subplots(figsize=(6.0, 3.9))
        selected = [row for row in score_rows if row["cell_id"] == diagram["cell_id"]]
        for key, color, linestyle in ("topology", data_color("spectrum"), "-"), ("graph", data_color("background"), "--"), ("conventional", data_color("threshold"), ":"):
            for alias in ("half", "nominal", "double"):
                family = [row for row in selected if row["alias"] == alias]
                ax.plot([float(row["spacing_uHz"]) for row in family],
                        [float(row[f"{key}_score"]) for row in family],
                        label=str(key).capitalize() if alias == "half" else None,
                        color=color, linestyle=linestyle, marker="o", markersize=2.5)
        truth = next(float(row["true_dnu_uHz"]) for row in benchmark if row["cell_id"] == diagram["cell_id"])
        ax.axvline(truth, color="0.35", linewidth=0.9, label="Simulation truth")
        style_axes(ax, xlabel=r"Trial $\Delta\nu$ ($\mu$Hz)", ylabel="Registered score")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=4)
        save_figure(fig, FIGURES / "score_curves.svg", close=True, source="results/stage8/score_curves.csv", 
                    description="Registered half, nominal, double alias search on one evaluation cell", software_version=VERSION)

        fig, ax = plt.subplots(figsize=FIGSIZE["single"])
        evaluated = [row for row in benchmark if row["role"] == "evaluation" and row["detectable"] == "true"]
        values = [np.mean([row["correct"] == "true" for row in evaluated if row["method"] == method]) for method in METHODS]
        ax.bar(range(len(METHODS)), values, color=(data_color("spectrum"), 
                                                   data_color("background"), 
                                                   "0.65", "0.65", "0.65", "0.65"),
                                                   edgecolor="black")
        ax.set_xticks(range(len(METHODS)), [str(method).capitalize() for method in METHODS], rotation=25, ha="right")
        style_axes(ax, ylabel="Correct alias fraction", ylim=(0, 1.05))
        save_figure(fig, FIGURES / "paired_method_accuracy.svg", close=True, source="results/stage8/paired_benchmark.csv", description="Six-method alias comparison on identical detectable evaluation cells", software_version=VERSION)

        fig, ax = plt.subplots(figsize=(6.0, 3.9))
        cell_axis = np.arange(len(intervals))
        points = np.asarray([float(row["point_dnu_uHz"]) for row in intervals])
        lower = np.asarray([float(row["lower_dnu_uHz"]) for row in intervals])
        upper = np.asarray([float(row["upper_dnu_uHz"]) for row in intervals])
        truth_values = np.asarray([float(row["true_dnu_uHz"]) for row in intervals])
        ax.errorbar(cell_axis, points, yerr=np.vstack((points - lower, upper - points)), fmt="o", color=data_color("spectrum"), capsize=2, label="90% interval")
        ax.scatter(cell_axis, truth_values, marker="x", color=data_color("threshold"), label="Simulation truth")
        ax.set_xticks(cell_axis[::2], [intervals[index]["cell_id"] for index in cell_axis[::2]], rotation=35, ha="right")
        style_axes(ax, ylabel=r"$\Delta\nu$ ($\mu$Hz)", xlabel="Evaluation cell")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2)
        save_figure(fig, FIGURES / "interval_coverage.svg", close=True, source="results/stage8/intervals.csv", description="Stochastic/background-branch spacing intervals against simulation truth", software_version=VERSION)

        fig, ax = plt.subplots(figsize=(6.0, 3.9))
        modes = [row for row in ratio_rows if row["source"].startswith("Lund") and row["ratio"] in {"r02", "r01", "r10"}]
        ratio_colors = {"r02": data_color("spectrum"), "r01": data_color("background"), "r10": data_color("threshold")}
        for name in ("r02", "r01", "r10"):
            selected_rows = [row for row in modes if row["ratio"] == name]
            ax.plot([int(row["radial_order_n"]) for row in selected_rows], [float(row["estimate"]) for row in selected_rows], color=ratio_colors[name], marker="o", markersize=3, label=f"{name} from modes")
            ax.scatter([int(row["radial_order_n"]) for row in selected_rows], [float(row["reference"]) for row in selected_rows], color=ratio_colors[name], marker="x", s=22)
        style_axes(ax, xlabel="Published radial order $n$", ylabel="Dimensionless separation ratio")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3)
        save_figure(fig, FIGURES / "published_ratio_formula_audit.svg", close=True, source=["data/reference/mode_frequencies.csv", "data/reference/frequency_ratios.csv"], description="Five-point formula reproduction from published modes (circles) compared to published ratios (crosses); not ridge inference", software_version=VERSION)


def _record(path: Path) -> dict[str, Any]:
    return {"path": repository_relative_posix(path, ROOT), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def main() -> None:
    config = load_yaml(CONFIG)
    if config.get("run_id") != RUN_ID:
        raise RuntimeError("Stage 8 config identity drifted")
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    design = _read(ROOT / "registries/stage4_factorial_design.csv")[:24]
    if len(design) != 24 or design[0]["cell_id"] != "F4-001" or design[-1]["cell_id"] != "F4-024":
        raise RuntimeError("locked Stage 8 design is unavailable")
    priors = {row["cell_id"]: float(row["best_trial_uHz"]) for row in _read(ROOT / "results/stage6/comb_benchmark.csv") if row["method"] == "acf"}
    if any(row["cell_id"] not in priors for row in design):
        raise RuntimeError("locked Stage 6 ACF prior is incomplete")
    payloads = [_spectrum(row) for row in design]
    score_rows, benchmark, scans = _calibration_and_benchmark(payloads, priors)
    null_rows = _nulls(payloads, priors, benchmark, scans)
    intervals, bootstrap_rows = _intervals(payloads, priors, benchmark)
    suite, representative_field, representative_graph = _representative_diagrams(payloads, benchmark)
    ratios = _ratio_audit(payloads, suite)
    stress = _stress_atlas(payloads, priors)
    _write(RESULTS / "score_curves.csv", score_rows)
    _write(RESULTS / "paired_benchmark.csv", benchmark)
    _write(RESULTS / "null_maxima.csv", null_rows)
    _write(RESULTS / "intervals.csv", intervals)
    _write(RESULTS / "bootstrap_draws.csv", bootstrap_rows)
    _write(RESULTS / "ratio_audit.csv", ratios)
    _write(RESULTS / "failure_atlas.csv", stress)
    write_json_lf(RESULTS / "diagram_suite.json", suite)
    write_json_lf(RESULTS / "environment.json", {
        "python": platform.python_version(), "platform": platform.platform(),
        "numpy": version("numpy"), "scipy": version("scipy"),
        "matplotlib": version("matplotlib"), "software": VERSION,
    })
    _plot(score_rows, benchmark, intervals, ratios, representative_field, representative_graph, suite)
    evaluation = [row for row in benchmark if row["role"] == "evaluation" and row["detectable"] == "true"]
    accurate = {method: float(np.mean([row["correct"] == "true" for row in evaluation if row["method"] == method])) for method in METHODS}
    detectable_ids = {row["cell_id"] for row in evaluation}
    covered = float(np.mean([row["covers_truth"] == "true" for row in intervals if row["cell_id"] in detectable_ids]))
    ratio_error = max(float(row["absolute_difference"]) for row in ratios if row["source"].startswith("Lund"))
    ratio_standardized = max(float(row["uncertainty_normalized_difference"]) for row in ratios if row["source"].startswith("Lund"))
    thresholds = config["gate"]
    utility = (
        accurate["topology"] >= float(thresholds["minimum_detectable_alias_accuracy"])
        and covered >= float(thresholds["minimum_detectable_90pct_interval_coverage"])
        and accurate["topology"] - accurate["graph"] >= float(thresholds["minimum_topology_accuracy_gain_over_graph"])
    )
    decision = "retain" if utility else "geometry_only"
    checks = [
        {"check": "cylindrical_topology", "status": "pass" if suite["essential_h1"] >= 1 and suite["rectangle_essential_h1"] == 0 else "fail", "value": f"H1 cylinder={suite['essential_h1']}; rectangle={suite['rectangle_essential_h1']}"},
        {"check": "simulated_spacing_grid", "status": "pass", "value": f"{len(score_rows)} scored spacing trials; 24 cells"},
        {"check": "maximum_statistic_null", "status": "pass" if len(null_rows) == 288 else "fail", "value": f"{len(null_rows)} null maxima over all 15 trials"},
        {"check": "published_ratio_formula", "status": "pass" if ratio_standardized <= 1.0 else "fail", "value": f"maximum absolute discrepancy={ratio_error:.4g}; maximum asymmetric-uncertainty-normalized discrepancy={ratio_standardized:.3f}"},
        {"check": "alias_accuracy", "status": "pass" if accurate["topology"] >= 0.60 else "limited", "value": f"detectable={len(detectable_ids)}; topological={accurate['topology']:.3f}; graph={accurate['graph']:.3f}"},
        {"check": "interval_coverage", "status": "pass" if covered >= 0.80 else "limited", "value": f"detectable 90% coverage={covered:.3f}"},
        {"check": "topological_increment", "status": "pass" if accurate["topology"] - accurate["graph"] >= 0.05 else "limited", "value": f"paired alias-accuracy increment={accurate['topology'] - accurate['graph']:.3f}"},
    ]
    status = "pass" if all(check["status"] != "fail" for check in checks) else "fail"
    gate = {
        "gate": "G8", "status": status, "decision": decision,
        "claim": "topological_echelle_simulation_utility" if utility else "correct_cylindrical_geometry_only",
        "run_id": RUN_ID, "accepted_on": "2026-09-28", "detectable_evaluation_cells": len(detectable_ids),
        "alias_accuracy_topology": accurate["topology"], "alias_accuracy_graph": accurate["graph"],
        "interval_coverage": covered, "published_ratio_max_absolute_discrepancy": ratio_error,
        "published_ratio_max_uncertainty_normalized_discrepancy": ratio_standardized,
        "population_spectra_used": False, "final_holdout_used": False,
        "checks": checks,
    }
    write_json_lf(REPORTS / "G8_ACCEPTANCE.json", gate)
    if status != "pass":
        raise RuntimeError("Stage 8 G8 integrity checks failed")
    summary = (
        "# Stage 8 - Cylindrical topological echelle diagram\n\n"
        f"G8 status **{status.upper()}**, decision **{decision.upper()}**. "
        f"The locked detectable evaluation subset has {len(detectable_ids)} cells. "
        f"Topological alias accuracy is {accurate['topology']:.3f} versus graph-only {accurate['graph']:.3f}; "
        f"90% interval coverage is {covered:.3f}. "
        "These are simulation-only results; the published ratio table was used solely to audit formulas.\n\n"
        "The cylinder and its seam are mathematically validated. The combined score is retained "
        "only if all three frozen utility thresholds pass. In the geometry-only outcome, no claim "
        "of superior inference is made. Stage 7 delay PH remains off the critical path.\n"
    )
    write_text_lf(REPORTS / "STAGE8_REPORT.md", summary)
    write_text_lf(REPORTS / "ALIAS_AND_ABLATION_REPORT.md", (
        "# Paired alias benchmark and topology-free ablation\n\n"
        f"Detectable evaluation cells: {len(detectable_ids)}. Frozen correctness tolerance: 12%.\n\n"
        "| Method | Correct-alias fraction |\n| --- | ---: |\n"
        + "".join(f"| {method} | {accurate[method]:.3f} |\n" for method in METHODS)
        + "\nAll six methods use the identical Stage 6 ACF-seeded 15-point trial grid. "
        "Null p-values are plus-one, per-cell maxima across every registered trial; "
        "no unadjusted per-trial detection claim is made. ACF/PSPS are computed on the new spectrum.\n"
    ))
    write_text_lf(REPORTS / "UNCERTAINTY_AND_FAILURE_ATLAS.md", (
        "# Uncertainty and failure-domain atlas\n\n"
        f"Eight independent realization refits per evaluation cell cycle through three fitted-background "
        f"branches. The 90% percentile interval uses a frozen minimum half-width of 12% of the "
        f"point estimate; detectable-cell empirical coverage is {covered:.3f}. "
        "This is a finite-simulation coverage diagnostic, not a claim of universal calibration.\n\n"
        "Six prespecified injected failure modes (glitch, curvature, dropout, avoided crossing, "
        "rotation, and noise) are recorded in `results/stage8/failure_atlas.csv`. "
        "The single representative stress case is diagnostic, not a population failure rate. "
        "Angular intervals are shortest empirical arcs on S1 and can wrap the displayed seam.\n"
    ))
    write_text_lf(REPORTS / "RIDGE_ANGLES_AND_RATIO_AUDIT.md", (
        "# Ridge angles and separation ratios\n\n"
        "The ridge graph retains up to three competing circular paths. A degree-identified anchor "
        "is required to interpret their phases as l=0/1/2; unlabeled bright tracks do not yield "
        "r01 or r10. The API computes delta-theta02 and an r02 angular proxy when anchored. "
        f"Five-point r02/r01/r10 formulae on published KIC 10963065 frequencies have "
        f"maximum absolute point-estimate difference {ratio_error:.4g}; the maximum "
        f"difference relative to the appropriate asymmetric published uncertainty is {ratio_standardized:.3f}. "
        "Rounded mode-frequency ratios and separately published ratio point estimates need not agree to four decimals. "
        "This checks the ratio implementation, not a blind topological estimate on that star.\n"
    ))
    write_text_lf(REPORTS / "TRACEABILITY_MATRIX.md", (
        "# Stage 8 traceability\n\n| Task | Evidence |\n| --- | --- |\n"
        "| T8.1 | formal cylinder protocol, echelle field and cubical cell API |\n"
        "| T8.2 | exact seam/nonseam cubical regressions and G8 boundary audit |\n"
        "| T8.3 | circular maxima, graph edges and competing path hypotheses |\n"
        "| T8.4 | frozen finite-H0/graph score and orderwise/conventional controls |\n"
        "| T8.5 | 15-point half/nominal/double scan and per-cell maximum-statistic nulls |\n"
        "| T8.6 | independent stochastic refits, three background branches and 90% intervals |\n"
        "| T8.7 | circular-angle API, identified-mode five-point ratios, published formula audit |\n"
        "| T8.8 | six-factor representative failure atlas |\n"
        "| T8.9 | paired ACF/PSPS, conventional, Hough and graph-only benchmark |\n"
        "| T8.10 | source-backed paired echelle with localized ridge and uncertainty overlay |\n"
    ))
    inputs = [ROOT / path for path in (
        "registries/stage4_factorial_design.csv", "results/stage4/run_manifest.json",
        "results/stage6/run_manifest.json", "results/stage6/comb_benchmark.csv",
        "data/reference/mode_frequencies.csv", "data/reference/frequency_ratios.csv",
    )]
    outputs = sorted(path for directory in (RESULTS, REPORTS) for path in directory.rglob("*") if path.is_file() and path.name != "run_manifest.json" and path.name != "deliverable_manifest.csv")
    write_json_lf(RESULTS / "run_manifest.json", {
        "schema_version": 1, "run_id": RUN_ID, "status": "complete", "software_version": VERSION,
        "config_path": "configs/stage8_echelle.yaml", "config_sha256": configuration_hash(CONFIG),
        "style_id": "TA-PLOT-1.0", "coefficient_field": "F2", "decision": decision,
        "population_spectra_used": False, "final_holdout_used": False,
        "inputs": [_record(path) for path in inputs], "outputs": [_record(path) for path in outputs],
    })
    print(f"G8 {status}: {decision}; detectable alias accuracy={accurate['topology']:.3f}; interval coverage={covered:.3f}")


if __name__ == "__main__":
    main()
