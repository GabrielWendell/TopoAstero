"""Ten source-backed Paper I figures, using the Stage 3 academic style contract."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

from topoastero.classical import echelle_grid
from topoastero.style import (
    background_color,
    data_color,
    mode_degree_color,
    panel_label,
    save_figure,
    style_axes,
    topoastero_style,
)

ROOT = Path(__file__).parents[1]
FIGURES = (
    "01_observation_window", "02_psd_background", "03_ordinary_echelle",
    "04_localized_persistence", "05_spacing_aliases", "06_cylinder_ridges",
    "07_simulation_placement", "08_sensitivity_uncertainty", "09_quarter_stability",
    "10_kepler_tess_transfer",
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def vector(records: list[dict[str, str]], key: str) -> np.ndarray:
    return np.array([float(row[key]) for row in records])


def plot_all(output: Path, source_root: Path = ROOT) -> None:
    results = output / "results/stage10"
    dest = output / "reports/stage10/figures"
    summary = json.loads((results / "summary.json").read_text())
    spectrum = [row for row in rows(results / "branch_spectra.csv") if row["branch_id"] == "PP-01"]
    frequency, power, background = [vector(spectrum, key) for key in ("frequency_uHz", "power_ppm2_per_uHz", "background_ppm2_per_uHz")]
    spacing = summary["primary"]["classical_dnu_uHz"]
    manifest = []

    def export(fig: plt.Figure, name: str, sources: list[str], caption: str) -> None:
        save_figure(fig, dest / f"{name}.svg", formats=("pdf", "png"), dpi=220, close=True,
                    source=[f"results/stage10/{source}" for source in sources], description=caption,
                    software_version="TopoAstero-0.11.0")
        manifest.append({"figure_id": name, "sources": [f"results/stage10/{source}" for source in sources], "style_id": "TA-PLOT-1.0", "caption": caption, "formats": ["svg", "pdf", "png"]})

    with topoastero_style(context="paper"):
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        observed = rows(results / "observation_preview.csv")
        axes[0].scatter(vector(observed, "time_BKJD"), vector(observed, "relative_flux_ppm"), s=1, alpha=0.55, color=data_color("spectrum"), rasterized=True)
        style_axes(axes[0], xlabel="Time (BKJD)", ylabel="Relative flux (ppm)")
        windows = rows(results / "spectral_windows.csv")
        for label in ("Q2", "Q5", "Q6", "Q7", "combined_absolute"):
            selected = [row for row in windows if row["sample"] == label and float(row["frequency_uHz"]) > 0]
            axes[1].plot(vector(selected, "frequency_uHz"), vector(selected, "window_power"), label=label.replace("combined_absolute", "Absolute span"), lw=0.8)
        axes[1].set_yscale("log")
        axes[1].set_ylim(1e-7, 1)
        axes[1].set_xlim(0, 5)
        style_axes(axes[1], xlabel=r"Window frequency ($\mu$Hz)", ylabel="Relative window power", legend=True)
        for index, ax in enumerate(axes):
            panel_label(ax, chr(97 + index))
        export(fig, FIGURES[0], ["observation_preview.csv", "spectral_windows.csv"], "Kepler absolute-time observations (every 200th cadence for display) and cadence-mask spectral windows; no gap compression.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        broad = rows(results / "broad_spectrum.csv")
        bf = vector(broad, "frequency_uHz")
        axes[0].loglog(bf, gaussian_filter1d(vector(broad, "power_ppm2_per_uHz"), 2), color=data_color("raw"), lw=0.8, label="Observed (display smooth)")
        for model in range(3):
            axes[0].loglog(bf, vector(broad, f"background_H{model}"), color=background_color(f"H{model}"), label=f"{model} Harvey components")
        style_axes(axes[0], xlabel=r"Frequency ($\mu$Hz)", ylabel=r"PSD (ppm$^2$/$\mu$Hz)", legend=True)
        axes[1].plot(frequency, power / background, color=data_color("raw"), lw=0.35, alpha=0.45)
        axes[1].plot(frequency, gaussian_filter1d(power / background, 35 / 0.2), color=data_color("envelope"), label=r"35 $\mu$Hz envelope")
        axes[1].axvline(summary["primary"]["classical_numax_uHz"], color=data_color("envelope"), ls="--", lw=0.9, label="Classical envelope")
        axes[1].axvline(2203.7, color=data_color("reference"), ls=":", label="Published context")
        style_axes(axes[1], xlabel=r"Frequency ($\mu$Hz)", ylabel="Power / background", legend=True)
        export(fig, FIGURES[1], ["broad_spectrum.csv", "branch_spectra.csv", "summary.json"], "PSD and all three registered Harvey families; primary whitening uses minimum descriptive BIC. The published envelope location is contextual, not a tuning target.")

        fig, ax = plt.subplots(figsize=(4.2, 3.4), layout="constrained")
        ordinary = echelle_grid(frequency, power / background, spacing, frequency_range_uHz=(1500, 2800), phase_bins=128)
        mesh = ax.pcolormesh(ordinary.phase * spacing, ordinary.radial_orders, ordinary.power, shading="nearest", cmap="viridis", rasterized=True)
        modes = [row for row in rows(source_root / "data/reference/mode_frequencies.csv") if row["stable_star_id"] == "KIC 10963065" and 1500 <= float(row["frequency_uHz"]) <= 2800]
        for degree in (0, 1, 2):
            selected = [row for row in modes if int(row["angular_degree_l"]) == degree]
            f = vector(selected, "frequency_uHz")
            ax.scatter(f % spacing, np.floor(f / spacing), s=15, marker="o", facecolors="none", edgecolors=mode_degree_color(degree), label=rf"Published $\ell={degree}$")
        fig.colorbar(mesh, ax=ax, label="Power / background", shrink=0.85)
        style_axes(ax, xlabel=rf"Frequency modulo {spacing:.3f} $\mu$Hz", ylabel="Folded row index", legend=True)
        export(fig, FIGURES[2], ["branch_spectra.csv", "published_mode_overlay.csv", "summary.json"], "Conventional echelle at the primary classical ACF spacing, with externally degree-identified Lund et al. modes. Folded row indices are not physical radial-order labels.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        peaks = json.loads((results / "localized_peaks.json").read_text())["peaks"]
        finite = [row for row in peaks if not row["essential"]]
        axes[0].scatter([row["birth_frequency_uHz"] for row in finite], [row["persistence"] for row in finite], s=12, color=data_color("spectrum"), alpha=0.7, edgecolors="black")
        axes[0].axvline(summary["primary"]["persistence_numax_uHz"], color=data_color("envelope"), label="Persistence centroid")
        axes[0].axvline(summary["primary"]["classical_numax_uHz"], color=data_color("reference"), ls="--", label="Classical envelope")
        style_axes(axes[0], xlabel=r"Peak frequency ($\mu$Hz)", ylabel=r"Finite $H_0$ lifetime", legend=True)
        axes[1].scatter([row["birth_value"] for row in finite], [row["death_value"] for row in finite], s=10, color=data_color("spectrum"), alpha=0.65, edgecolors="black")
        limits = [min(row["death_value"] for row in finite) - 0.1, max(row["birth_value"] for row in finite) + 0.1]
        axes[1].plot(limits, limits, color=data_color("raw"), ls=":")
        style_axes(axes[1], xlabel="Birth log(P/B)", ylabel="Merge log(P/B)")
        export(fig, FIGURES[3], ["localized_peaks.json", "summary.json"], "Localized finite path H0 classes. Their lifetimes equal elder-rule peak prominence exactly; the essential component is retained in the JSON but omitted from numeric summaries.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        spectral = rows(results / "spectral_score_scan.csv")
        for key, label in (("persistence_comb", "Persistence comb"), ("acf", "ACF"), ("psps", "PSPS")):
            score = vector(spectral, key)
            axes[0].plot(vector(spectral, "trial_spacing_uHz"), score / max(float(np.max(np.abs(score))), 1e-12), label=label)
        for factor in (0.5, 1, 2):
            axes[0].axvline(factor * spacing, color=data_color("reference"), ls=":", lw=0.7)
        style_axes(axes[0], xlabel=r"Trial spacing ($\mu$Hz)", ylabel="Score / own maximum", legend=True)
        scan = rows(results / "echelle_score_scan.csv")
        for series_index, (key, label) in enumerate((("combined", "Frozen 0.55/0.45 score"), ("topology", "Finite $H_0$ term"), ("graph_only", "Graph control"))):
            for family in ("half", "nominal", "double"):
                selected = [row for row in scan if row["alias_family"] == family]
                axes[1].plot(vector(selected, "spacing_uHz"), vector(selected, key), marker="o", ms=3, color=f"C{series_index}", label=label if family == "half" else None)
        style_axes(axes[1], xlabel=r"Trial spacing ($\mu$Hz)", ylabel="Cylindrical diagnostic score", legend=True)
        export(fig, FIGURES[4], ["spectral_score_scan.csv", "echelle_score_scan.csv"], "Spectral and cylindrical trial scans retain half, nominal, double and boundary alternatives. Cylindrical performance remains geometry-only under G8; a matching Rudy spacing cannot establish estimator utility.")

        fig = plt.figure(figsize=(7.2, 3.1), layout="constrained")
        ax = fig.add_subplot(121, projection="3d")
        cylinder = json.loads((results / "cylinder.json").read_text())
        values = np.array(cylinder["values"])
        valid = np.array(cylinder["valid"])
        theta = 2 * np.pi * np.array(cylinder["phases"])
        orders = np.array(cylinder["orders"])
        mesh_theta, mesh_order = np.meshgrid(np.r_[theta, theta[0] + 2 * np.pi], orders)
        display = np.c_[values, values[:, 0]]
        display_valid = np.c_[valid, valid[:, 0]]
        colors = plt.get_cmap("viridis")((display - values[valid].min()) / max(np.ptp(values[valid]), 1e-12))
        colors[~display_valid, 3] = 0
        ax.plot_surface(np.cos(mesh_theta), np.sin(mesh_theta), mesh_order, facecolors=colors, shade=False, linewidth=0)
        ax.set_xlabel("cos phase")
        ax.set_ylabel("sin phase")
        # The adjacent map labels the shared folded-row coordinate; duplicating
        # the projected 3-D z label collides with that ylabel at journal scale.
        ax.set_zlabel("")
        ax.set_title("Periodic field", pad=5)
        ax.view_init(elev=20, azim=-40)
        ax = fig.add_subplot(122)
        image = ax.pcolormesh(np.array(cylinder["phases"]), orders, np.ma.array(values, mask=~valid), shading="nearest", cmap="viridis", rasterized=True)
        nodes = cylinder["graph"]["nodes"]
        for index, track in enumerate(cylinder["graph"]["hypotheses"]):
            selected = [nodes[node] for node in track["node_indices"]]
            ax.scatter([node["phase"] for node in selected], [node["order"] for node in selected], s=18, facecolors="none", edgecolors=f"C{index + 1}", label=f"Unidentified path {index + 1}")
        fig.colorbar(image, ax=ax, label="log(P/B)", shrink=0.8)
        style_axes(ax, xlabel="Circular phase (cycles)", ylabel="Folded row", legend=True)
        export(fig, FIGURES[5], ["cylinder.json"], "Periodic cylindrical field and competing ridge-graph paths. Seam duplication is display-only. The paths lack a defensible degree anchor, so no topological frequency ratios are reported.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        placement = rows(results / "simulation_placement.csv")
        for domain, label, marker, color in (("registered_stage4_simulation_pilot", "Stage 4 design", "o", data_color("raw")), ("actual_TESS_context_candidate_values_not_detections", "Actual TESS sectors", "s", "C4"), ("observed_descriptive", "Rudy Kepler", "*", data_color("reference"))):
            selected = [row for row in placement if row["domain"] == domain]
            size = 80 if marker == "*" else 15
            axes[0].scatter(vector(selected, "duration_days"), vector(selected, "duty_cycle"), marker=marker, s=size, color=color, alpha=0.7, label=label, edgecolors="black")
            axes[1].scatter(vector(selected, "numax_uHz"), 1e6 / (2 * vector(selected, "cadence_seconds")), marker=marker, s=size, color=color, alpha=0.7, label=label, edgecolors="black")
        style_axes(axes[0], xlabel="Absolute baseline (days)", ylabel="Cadence-mask duty", legend=True)
        style_axes(axes[1], xlabel=r"Envelope candidate ($\mu$Hz)", ylabel=r"Cadence Nyquist ($\mu$Hz)")
        export(fig, FIGURES[6], ["simulation_placement.csv"], "Rudy and actual TESS sectors placed against the registered simulation coordinates. This is domain context, not a calibrated inversion from simulated parameters to stellar properties.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), layout="constrained")
        audit = rows(results / "robustness.csv")
        for index, branch in enumerate(("PP-01", "PP-02", "PP-03", "PP-04")):
            selected = [row for row in audit if row["branch_id"] == branch]
            axes[0].scatter(vector(selected, "classical_dnu_uHz"), np.full(len(selected), index), s=8, alpha=0.35, label=branch, edgecolors="black")
        axes[0].axvline(103.179, color=data_color("reference"), ls=":", label="Published context")
        axes[0].set_yticks(range(4), ("PP-01", "PP-02", "PP-03", "PP-04"))
        style_axes(axes[0], xlabel=r"Classical ACF spacing ($\mu$Hz)", ylabel="Registered preprocessing")
        budgets = rows(results / "uncertainty_budget.csv")
        for index, row in enumerate(budgets):
            if row["quantity"] == "classical_dnu_uHz":
                continue
            point = float(row["monthly_averaged_point"])
            lower, upper = float(row["monthly_bootstrap_lower95"]), float(row["monthly_bootstrap_upper95"])
            axes[1].errorbar(point, index, xerr=[[max(0, point - lower)], [max(0, upper - point)]], fmt="o", color=data_color("envelope"), capsize=3)
            axes[1].plot([float(row["registered_pipeline_minimum"]), float(row["registered_pipeline_maximum"])], [index - 0.1, index - 0.1], color=data_color("raw"), lw=3)
            axes[1].scatter(float(row["full_span_point"]), index, marker="x", color=data_color("reference"), s=35, edgecolors="black", label="Full-span point" if index == 0 else None)
        axes[1].set_yticks([0, 2], ["Classical envelope", "Persistence centroid"])
        style_axes(axes[1], xlabel=r"Location ($\mu$Hz)", ylabel="Estimator")
        export(fig, FIGURES[7], ["robustness.csv", "uncertainty_budget.csv"], "All 72 registered branch/factor diagnostics. Red bars are monthly-estimator bootstrap intervals, gray bars registered pipeline ranges, and green crosses full-span points; their estimands differ and the components are not combined.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        stability = rows(results / "quarter_stability.csv")
        for kind, marker in (("quarter", "o"), ("cumulative", "s")):
            selected = [row for row in stability if row["kind"] == kind]
            for ax, quantity in zip(axes, ("classical_numax_uHz", "classical_dnu_uHz"), strict=True):
                ax.plot(vector(selected, "duration_days"), vector(selected, quantity), marker=marker, label=kind.capitalize())
        for ax, label in zip(axes, (r"Envelope ($\mu$Hz)", r"ACF spacing ($\mu$Hz)"), strict=True):
            style_axes(ax, xlabel="Absolute baseline (days)", ylabel=label, legend=True)
        export(fig, FIGURES[8], ["quarter_stability.csv"], "Quarter and cumulative-baseline diagnostics with the full-span background held fixed. Quarter scatter reflects realization plus window variation; cumulative points overlap and are not independent replicates.")

        fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), layout="constrained")
        transfer = rows(results / "kepler_to_tess.csv")
        rates = []
        for duration in (13.7, 27.4):
            values = []
            for noise in (0, 1, 2):
                selected = [row for row in transfer if float(row["requested_duration_days"]) == duration and float(row["noise_variance_factor"]) == noise]
                values.append(np.mean([row["classification"] == "marginal_candidate_not_confirmation" for row in selected]))
            rates.append(values)
        image = axes[0].imshow(rates, origin="lower", vmin=0, vmax=1, cmap="viridis", aspect="auto")
        axes[0].set_xticks(range(3), ("0", "1", "2"))
        axes[0].set_yticks(range(2), ("13.7", "27.4"))
        for row in range(2):
            for col in range(3):
                axes[0].text(col, row, f"{rates[row][col]:.0%}", ha="center", va="center", color="white" if rates[row][col] < 0.5 else "black")
        fig.colorbar(image, ax=axes[0], label="Conditional candidate fraction", shrink=0.85)
        style_axes(axes[0], xlabel="Added TESS noise variance factor", ylabel="Requested duration (days)")
        tess = rows(results / "tess_sectors.csv")
        for row in tess:
            status = row["classification"] == "marginal_candidate_not_confirmation"
            axes[1].scatter(float(row["white_psd"]), float(row["feasibility_envelope_snr"]), marker="s" if status else "o", color="C4" if status else data_color("raw"), s=22, edgecolors="black")
            axes[1].annotate(row["sector"], (float(row["white_psd"]), float(row["feasibility_envelope_snr"])), xytext=(3, 2), textcoords="offset points", fontsize=7)
        axes[1].axhline(1.2, color=data_color("threshold"), ls=":")
        axes[1].margins(x=0.20, y=0.12)
        style_axes(axes[1], xlabel=r"Actual TESS noise floor (ppm$^2$/$\mu$Hz)", ylabel="Sector feasibility envelope SNR")
        export(fig, FIGURES[9], ["kepler_to_tess.csv", "tess_sectors.csv"], "Same-star Kepler degradation through all 11 real TESS windows, three source offsets, two durations/duty factors and three added-noise factors. Reused Kepler segments are correlated; actual TESS candidates remain unconfirmed under the Stage 3 thresholds.")
    from topoastero.portability import write_json_lf
    write_json_lf(output / "reports/stage10/figure_manifest.json", {"figures": manifest})
    print("Stage 10 figures: 10 SVG/PDF/PNG exports", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    plot_all(args.output_root)


if __name__ == "__main__":
    main()
