"""Source-backed Stage 12 figures using the project's shared visual contract."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from topoastero.population_store import contained, read_json, read_table, seal, write_json
from topoastero.style import save_figure, style_axes, topoastero_style

LEVEL_LABELS = ("Native", "Exposure", "Duration", "Noise", "Window", "Duty", "Dilution", "Short")
COLORS = {"baseline": "#2F5C85", "hybrid": "#DD6B20"}


def build_figures(root: Path, cfg: dict[str, Any], *, formats: tuple[str, ...] = ("svg", "pdf")) -> dict[str, Any]:
    from topoastero.hybrid.transfer import LEVELS

    output = contained(root, cfg["output"])
    directory = root / "reports/stage12/figures/"
    predictions = read_table(output / "oof_predictions.csv")
    increments = read_json(output / "increment.json")["rows"]
    calibration = read_json(output / "probability_calibration.json")["tasks"]
    curves = read_table(output / "transfer_curves.csv")
    actual = read_json(output / "actual_tess.json")["rows"]
    figures: list[dict[str, Any]] = []

    def finish(fig: Any, name: str, sources: list[str], description: str) -> None:
        fig.tight_layout()
        path = directory / (name + ".png")
        save_figure(fig, path, formats=formats, source=sources, description=description, close=True)
        figures.append({"figure_id": name, "description": description,
                        "sources": [seal(root, output / s) for s in sources],
                        "files": [seal(root, path.with_suffix("." + ext)) for ext in ("png", *formats)]})

    with topoastero_style(context="paper"):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
        for ax, quantity, summary in zip(axes, ("numax", "dnu"), increments, strict=True):
            rows = [r for r in predictions if r["quantity"] == quantity]
            b = np.array([abs(float(r["baseline"]) / float(r["reference"]) - 1) for r in rows])
            h = np.array([abs(float(r["hybrid"]) / float(r["reference"]) - 1) for r in rows])
            limit = max([.01, *b, *h]) * 1.12
            ax.scatter(b, h, color=COLORS["hybrid"], s=24, edgecolors="black", linewidths=0.5, label="OOF stars")
            ax.plot([0, limit], [0, limit], color="#77838F", linestyle=":")
            ax.set(xlim=(0, limit), ylim=(0, limit), title=quantity + f" — {len(rows)} OOF stars")
            mean = summary["mean_fractional_loss_improvement"]
            ci = [summary["bootstrap95_lower"], summary["bootstrap95_upper"]]
            label = f"Mean gain: {mean:.4f}\n95% paired CI: [{ci[0]:.4f}, {ci[1]:.4f}]" if mean is not None and ci[0] is not None else "Insufficient paired support"
            ax.text(.04, .96, label + f"\nPractical margin: {summary['practical_margin']:g}", transform=ax.transAxes, va="top", fontsize=8)
            style_axes(ax, xlabel="Baseline absolute fractional error", ylabel="Hybrid absolute fractional error")
        finish(fig, "stage12_oof_increment", ["oof_predictions.csv", "increment.json"], "Paired grouped OOF errors; bootstrap conditional on fitted models. Sparse pilot, no population claim.")

        fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
        supported = [r for r in calibration if r.get("task") == "catastrophic_failure" and r.get("calibration")]
        for report in supported:
            method = report["method"]
            bins = [r for r in report["calibration"] if r["n"]]
            axes[0].plot([r["mean_predicted"] for r in bins], [r["observed_fraction"] for r in bins], "o-", color=COLORS[method], label=method)
            axes[1].plot([r["threshold"] for r in report["decision_curve"]], [r["net_benefit"] for r in report["decision_curve"]], "o-", color=COLORS[method], label=method)
        if supported:
            axes[0].plot([0, 1], [0, 1], ":", color="#77838F")
            curve = supported[0]["decision_curve"]
            axes[1].plot([r["threshold"] for r in curve], [r["flag_all"] for r in curve], ":", color="#77838F", label="flag all")
            axes[1].axhline(0, color="#77838F", linestyle="--", label="flag none")
        else:
            for ax in axes:
                ax.text(.5, .5, "Failure calibration withheld\nInsufficient independent class/fold support\nNull probability does not mean zero risk", transform=ax.transAxes, ha="center", va="center", fontsize=9)
        axes[0].set(xlim=(0, 1), ylim=(0, 1), title="OOF failure calibration")
        axes[1].set(title="Operational decision curve")
        style_axes(axes[0], xlabel="Mean predicted failure probability", ylabel="Observed failure fraction", legend=bool(supported))
        style_axes(axes[1], xlabel="Failure-action threshold", ylabel="Net benefit per star", legend=bool(supported))
        finish(fig, "stage12_quality_calibration", ["probability_calibration.json"], "Failure calibration and decision curves, or explicit class-support withholding.")

        fig, axes = plt.subplots(2, 2, figsize=(11, 7))
        for column, quantity in enumerate(("numax", "dnu")):
            for method in COLORS:
                errors, recovery = [], []
                for level in LEVELS:
                    rows = [r for r in curves if (r["quantity"], r["method"], r["level"]) == (quantity, method, level)]
                    valid = [float(r["candidate_fractional_MAE"]) for r in rows if r["candidate_fractional_MAE"]]
                    errors.append(float(np.mean(valid)) if valid else np.nan)
                    recovery.append(float(np.mean([float(r["recoverable_fraction"]) for r in rows])) if rows else np.nan)
                axes[0, column].plot(range(8), errors, "o-", color=COLORS[method], label=str(method).capitalize())
                axes[1, column].plot(range(8), recovery, "o-", color=COLORS[method], label=str(method).capitalize())
            axes[0, column].set(title=(r"$\nu_{\max}$" if quantity == "numax" else r"$\Delta\nu$") + " — One parent star")
            axes[1, column].set(ylim=(-.04, 1.04))
            for row in range(2):
                axes[row, column].set_xticks(range(8), LEVEL_LABELS, rotation=35, ha="right")
                style_axes(axes[row, column], ylabel="Candidate fractional MAE" if row == 0 else "QC-accepted recovery fraction", legend=True)
        finish(fig, "stage12_transfer_trajectories", ["transfer_curves.csv"], "Conditional Rudy cumulative operator trajectories. Candidates include rejected values; recovery requires QC. Steps are not isolated causal effects.")

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
        for ax, quantity in zip(axes, ("numax", "dnu"), strict=True):
            for method in COLORS:
                case_rows = [r for r in actual if r["quantity"] == quantity and r["method"] == method and r.get("candidate_estimate") is not None]
                for accepted, marker in ((False, "x"), (True, "o")):
                    selected = [r for r in case_rows if r["accepted"] == accepted]
                    ax.scatter([r["sector"] + (-.2 if method == "baseline" else .2) for r in selected], [r["candidate_estimate"] for r in selected],
                               marker=marker, color=COLORS[method], s=24, edgecolors="black",
                               label=str(method).capitalize() + (" accepted" if accepted else " rejected"))
            refs = [r["reference"] for r in actual if r["quantity"] == quantity]
            if refs:
                ax.axhline(refs[0], color="#2A6F55", linestyle=":", label="Published center")
            ax.set(title=(r"$\nu_{\max}$" if quantity == "numax" else r"$\Delta\nu$") + " — Actual TESS candidates")
            style_axes(
                ax, 
                xlabel="Sector", 
                ylabel=r"Candidate estimate ($\mu$Hz)", 
                legend=True
            )
        finish(fig, "stage12_actual_tess_quality", ["actual_tess.json"], "All actual sectors retained. Rejected candidates are not detections; TESS probability and interval calibration withheld.")
    manifest = {"schema_version": 1, "style": "TA-PLOT-1.0", "figures": figures}
    write_json(contained(root, cfg["reports"]) / "figure_manifest.json", manifest)
    return manifest
