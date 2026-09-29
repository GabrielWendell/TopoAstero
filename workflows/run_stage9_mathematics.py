"""Regenerate Stage 9 seeded mathematical regressions, counterexamples and figures."""

from __future__ import annotations

import json
import math
import platform
import sys
from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from topoastero.config import load_yaml
from topoastero.echelle_topology import EchelleField, cubical_superlevel_persistence
from topoastero.mathematical_relations import (
    circle_distance,
    delay_ellipse_semiaxes,
    gamma_log_tail_bound,
    gamma_log_uniform_radius,
    path_peak_prominences,
    ridge_drift_bound,
    scaling_log_bounds,
)
from topoastero.persistence import superlevel_h0
from topoastero.portability import write_json_lf
from topoastero.style import FIGSIZE, data_color, save_figure, style_axes, topoastero_style
from topoastero.tda import bottleneck_distance, diagram_points

ROOT = Path(__file__).parents[1]


def _field(values: np.ndarray, mask: np.ndarray) -> EchelleField:
    rows, columns = values.shape
    orders = np.arange(10, 10 + rows, dtype=np.int64)
    phases = (np.arange(columns, dtype=float) + .5) / columns
    return EchelleField(np.where(mask, values, np.nan), mask, orders, phases,
                        100 * (orders[:, None] + phases[None, :]), 100.)


def _comparison(first: np.ndarray, second: np.ndarray, mask: np.ndarray) -> tuple[float, float, float]:
    left = cubical_superlevel_persistence(_field(first, mask))
    right = cubical_superlevel_persistence(_field(second, mask))
    distances = [bottleneck_distance(diagram_points(left, dimension=dim),
                                     diagram_points(right, dimension=dim)) for dim in (0, 1)]
    births = [max((abs(a - b) for a, b in zip(
                   sorted(pair.birth for pair in left.essential(dim)),
                   sorted(pair.birth for pair in right.essential(dim)), strict=True)), default=0.)
              for dim in (0, 1)]
    return max(distances), max(births), float(np.max(np.abs((first - second)[mask])))


def main() -> None:
    config = load_yaml(ROOT / "configs/stage9_mathematics.yaml")
    if config["prior_stage8_decision"] != "geometry_only":
        raise ValueError("Stage 9 is scoped to the Stage 8 geometry-only decision")
    stage8 = json.loads((ROOT / "reports/stage8/G8_ACCEPTANCE.json").read_text())
    if stage8["decision"] != "geometry_only" or stage8["population_spectra_used"] or stage8["final_holdout_used"]:
        raise ValueError("Stage 8 evidence boundary drifted")
    rng = np.random.default_rng(int(config["seed"]))
    results = ROOT / "results/stage9"
    figures = ROOT / "reports/stage9/figures"
    results.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    peak_error = 0.
    for _ in range(int(config["path_random_cases"])):
        values = rng.permutation(31).astype(float) + rng.uniform(-.01, .01, 31)
        reference = path_peak_prominences(values)
        observed = {pair.birth_index: pair.persistence for pair in superlevel_h0(values)}
        if reference.keys() != observed.keys():
            raise RuntimeError("peak birth identity failed")
        peak_error = max(peak_error, *(abs(reference[i] - observed[i])
                                       for i in reference if reference[i] is not None and observed[i] is not None))
    ellipse_error = 0.
    for delay in np.linspace(0, 4, 61):
        delta = 2 * np.pi * .25 * delay
        mapping = 2.3 * np.array([[1., 0.], [np.cos(delta), np.sin(delta)]])
        singular = np.linalg.svd(mapping, compute_uv=False)
        ellipse_error = max(ellipse_error, float(np.max(np.abs(singular - delay_ellipse_semiaxes(2.3, .25, float(delay))))))

    path_violation = 0.
    path_essential_violation = 0.
    for _ in range(64):
        values = rng.normal(size=23)
        perturb = rng.uniform(-.12, .12, 23)
        def points(signal: np.ndarray) -> np.ndarray:
            return np.array([(p.death, p.birth) for p in superlevel_h0(signal)
                             if p.death is not None], dtype=float).reshape((-1, 2))
        eta = float(np.max(np.abs(perturb)))
        path_violation = max(path_violation, bottleneck_distance(points(values), points(values + perturb)) - eta)
        path_essential_violation = max(path_essential_violation, abs(max(values) - max(values + perturb)) - eta)

    cylinder_violation = 0.
    essential_violation = 0.
    for _ in range(int(config["cylinder_random_cases"])):
        values = rng.normal(size=(3, 7))
        perturb = rng.uniform(-.11, .11, values.shape)
        mask = np.ones_like(values, dtype=bool)
        mask[1, 2] = False
        distance, birth, eta = _comparison(values, values + perturb, mask)
        cylinder_violation = max(cylinder_violation, distance - eta)
        essential_violation = max(essential_violation, birth - eta)

    ridge_violation = 0.
    trial_grid = np.linspace(85., 115., 121)
    lower = []
    upper = []
    for trial in trial_grid:
        bound = ridge_drift_bound(100., float(trial), 1., 1 / 48,
                                 jump_limit=float(config["stage8_ridge_jump_limit_cycles"]))
        lower.append(bound.lower_jump_cycles)
        upper.append(bound.upper_jump_cycles)
    for _ in range(int(config["ridge_random_cases"])):
        trial = float(rng.uniform(87, 113))
        curvature, epsilon = 1., 1 / 48
        residual = np.cumsum(np.r_[0., rng.uniform(-curvature, curvature, 7)])
        phase = (np.arange(8) * 100. + residual) / trial + rng.uniform(-epsilon, epsilon, 8)
        bound = ridge_drift_bound(100., trial, curvature, epsilon)
        for left, right in pairwise(phase):
            measured = circle_distance(float(left), float(right))
            ridge_violation = max(ridge_violation, bound.lower_jump_cycles - measured,
                                  measured - bound.upper_jump_cycles)

    gamma = config["gamma"]
    shape, bins, alpha, replicates = float(gamma["shape"]), int(gamma["bins"]), float(gamma["alpha"]), int(gamma["simulation_replicates"])
    radius = gamma_log_uniform_radius(shape, bins, alpha)
    samples = rng.gamma(shape=shape, scale=1 / shape, size=(replicates, bins))
    maxima = np.max(np.abs(np.log(samples)), axis=1)
    exceeds = int(np.count_nonzero(maxima > radius))
    observed_rate = exceeds / replicates
    z = 1.96
    center = (observed_rate + z * z / (2 * replicates)) / (1 + z * z / replicates)
    half = z * math.sqrt(observed_rate * (1 - observed_rate) / replicates + z * z / (4 * replicates ** 2)) / (1 + z * z / replicates)

    stellar = scaling_log_bounds(.02, .03, .01, dnu_systematic_log=.04, numax_systematic_log=.05)
    delta, nu, temperature = .06, .08, .01
    realized = (2 * delta, nu + 2 * delta + temperature / 2,
                3 * nu + 4 * delta + 1.5 * temperature, nu + temperature / 2)
    budgets = (stellar.density, stellar.radius, stellar.mass, stellar.gravity)
    scaling_violation = max(0., *(value - budget for value, budget in zip(realized, budgets, strict=True)))
    audit = {
        "run_id": config["run_id"], "claim_ids": ["S9-P1", "S9-P2", "S9-P3", "S9-P4", "S9-T1", "S9-P5", "S9-P6"],
        "seed": int(config["seed"]), "path_cases": int(config["path_random_cases"]),
        "cylinder_cases": int(config["cylinder_random_cases"]), "ridge_cases": int(config["ridge_random_cases"]),
        "max_peak_identity_error": peak_error, "max_delay_axis_error": ellipse_error,
        "max_path_stability_violation": path_violation,
        "max_path_essential_violation": path_essential_violation,
        "max_cylinder_stability_violation": cylinder_violation,
        "max_cylinder_essential_violation": essential_violation,
        "max_ridge_inequality_violation": ridge_violation,
        "max_scaling_inequality_violation": scaling_violation,
        "gamma_shape": shape, "gamma_bins": bins, "gamma_alpha": alpha,
        "gamma_radius": radius, "gamma_tail_bound": gamma_log_tail_bound(radius, shape, bins),
        "gamma_replicates": replicates, "gamma_exceedances": exceeds,
        "gamma_exceedance_rate": observed_rate, "gamma_wilson95": [center - half, center + half],
        "stage8_decision": "geometry_only", "population_spectra_used": False, "final_holdout_used": False,
    }
    if max(peak_error, ellipse_error, path_violation, path_essential_violation,
           cylinder_violation, essential_violation, ridge_violation, scaling_violation) > 1e-9:
        raise RuntimeError(f"proof-linked regression failed: {audit}")
    write_json_lf(results / "numerical_audit.json", audit)

    counterexamples = [
        {"id": "CE01", "family": "merged_peaks", "values": [4, 1, 3], "changed": [4, 3, 3], "violated_assumption": "distinct heights / positive lifetime margin"},
        {"id": "CE02", "family": "edge_birth", "values": [3, 0, 2], "changed": [1, 0, 3], "violated_assumption": "interior-only peaks or finite global survivor"},
        {"id": "CE03", "family": "missing_order", "phases": [.1, .1, None, .1], "violated_assumption": "consecutive observed trial rows"},
        {"id": "CE04", "family": "curvature", "residual_uHz": [4, 1, 0, 1, 4], "violated_assumption": "C=0 straight ridge"},
        {"id": "CE05", "family": "crossing_ridges", "phases_a": [.1, .2, .3, .4], "phases_b": [.5, .4, .3, .2], "violated_assumption": "fixed target identity and candidate retention"},
        {"id": "CE06", "family": "half_double_alias", "true_spacing_uHz": 100, "trials_uHz": [50, 100, 200], "circular_mismatches": [ridge_drift_bound(100., t, 0., 0.).mismatch_cycles for t in (50., 100., 200.)], "violated_assumption": "physical radial orders in consecutive trial rows"},
        {"id": "CE07", "family": "multimodal_spacing", "comb_spacings_uHz": [90, 110], "violated_assumption": "single true comb / unimodal score"},
        {"id": "CE08", "family": "stochastic_reordering", "gamma_shape": shape, "observed_peak_ranking_changes": bool(np.any(np.argmax(samples[:, :2], axis=1) != np.argmax(samples[0, :2]))), "violated_assumption": "realization-invariant local peak ordering"},
        {"id": "CE09", "family": "sheared_field", "transformation": "phase rotation per row on a continuous cylinder", "violated_assumption": "monotone persistence loss with ridge drift"},
    ]
    write_json_lf(results / "counterexamples.json", {"run_id": config["run_id"], "cases": counterexamples})
    write_json_lf(results / "environment.json", {
        "run_id": config["run_id"], "python": sys.version.split()[0], "numpy": np.__version__,
        "matplotlib": matplotlib.__version__, "platform": platform.platform(), "plot_style": "TA-PLOT-1.0",
    })

    with topoastero_style(context="paper"):
        fig, ax = plt.subplots(figsize=FIGSIZE["single_square"])
        ax.plot(trial_grid, lower, label="Guaranteed lower jump", color=data_color("reference"))
        ax.plot(trial_grid, upper, label="Guaranteed upper jump", color=data_color("residual"))
        ax.axhline(.17, color=data_color("threshold"), linestyle="--", label="Stage 8 edge threshold")
        style_axes(ax, xlabel="Trial spacing (µHz)", ylabel="Circular jump (cycles)", 
                   legend=True, legend_loc="upper center")
        save_figure(fig, figures / "ridge_jump_bounds.svg", source="results/stage9/numerical_audit.json",
                    description="Conditional finite-order target candidate bound, not global graph score",
                    software_version="TopoAstero-0.10.0", close=True)

        fig, ax = plt.subplots(figsize=FIGSIZE["single_square"])
        sorted_maxima = np.sort(maxima)
        ax.step(sorted_maxima, np.arange(1, replicates + 1) / replicates,
                where="post", color=data_color("spectrum"), label="Seeded Gamma realizations")
        ax.axvline(radius, color=data_color("threshold"), linestyle="--", label="Chernoff/union radius")
        style_axes(ax, xlabel="Maximum absolute log-bin ratio", ylabel="Empirical cumulative fraction", legend=True)
        save_figure(fig, figures / "gamma_calibration.svg", source="results/stage9/numerical_audit.json",
                    description="Gamma raw-bin union bound and seeded empirical distribution",
                    software_version="TopoAstero-0.10.0", close=True)
    print(json.dumps({"run_id": audit["run_id"], "regressions": "pass", "gamma_exceedances": exceeds,
                      "review": "pending_external_review"}, sort_keys=True))


if __name__ == "__main__":
    main()
