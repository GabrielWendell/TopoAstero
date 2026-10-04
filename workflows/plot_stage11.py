"""Role-aware Stage 11 figures from archived tables, using the academic style contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from topoastero.population_acquisition import load_config
from topoastero.population_store import contained, read_json, read_table, seal, write_json
from topoastero.style import data_color, save_figure, style_axes, topoastero_style


def plot(root: Path) -> None:
    cfg = load_config(root)
    reports = contained(root, cfg["reports"])
    output = contained(root, cfg["output"])
    evidence = read_json(reports / "evidence_manifest.json")
    cohort = read_table(reports / "cohort_ledger.csv")
    rows = []
    for name in ("development", "internal_validation", "descriptive_benchmark", "confirmation"):
        path = contained(root, evidence["role_directories"][name]) / "catalog.json"
        if path.exists():
            rows.extend(read_json(path)["rows"])
    target = reports / "figures"
    target.mkdir(exist_ok=True)
    paths = []
    with topoastero_style(context="paper"):
        fig, ax = plt.subplots(figsize=(7.2, 3.7))
        roles = ["development", "internal_validation", "descriptive_benchmark", "final_holdout"]
        sizes = [sum(r["role"] == role for r in cohort) for role in roles]
        present = [len({r["stable_star_id"] for r in rows if r["role"] == role and r["estimate"] is not None}) for role in roles]
        x = np.arange(4)
        ax.bar(x, sizes, color="0.85", label="Frozen cohort", edgecolor="black")
        ax.bar(x, present, color=data_color("spectrum"), label="Observational estimates", edgecolor="black")
        ax.set_xticks(x, ["Development", "Internal", "Rudy", "Confirmation"])
        style_axes(ax, ylabel="Unique stars", legend=True, title="Population acquisition and role coverage")
        ax.text(0.99, 0.95, "Holdout unopened" if not (output / "confirmation/catalog.json").exists() else "Confirmation archived", transform=ax.transAxes, ha="right", va="top")
        for suffix in ("png", "svg", "pdf"):
            path = target / ("01_cohort_coverage." + suffix)
            save_figure(fig, path, source="reports/stage11/cohort_ledger.csv", close=False)
            paths.append(path)
        plt.close(fig)

        for quantity, label, index in (("numax", r"$\nu_{\max}$", 2), ("dnu", r"$\Delta\nu$", 3)):
            fig, ax = plt.subplots(figsize=(6.2, 4.0))
            for method, marker, color in (("classical", "o", data_color("spectrum")), ("topology", "s", data_color("background"))):
                selected = [r for r in rows if r["quantity"] == quantity and r["method"] == method and r["estimate"] is not None]
                for role in roles:
                    subset = [r for r in selected if r["role"] == role]
                    if subset:
                        ax.scatter([r["reference"] for r in subset], [r["estimate"] for r in subset], marker=marker, color=color,
                                   label=str(method).capitalize() + " / " + ("Rudy (descriptive)" if role == "descriptive_benchmark" 
                                                                             else str(role).replace("_", " ").capitalize()),
                                   edgecolors="black", alpha=0.8, s=30)
            data = [r["reference"] for r in rows if r["quantity"] == quantity and r["estimate"] is not None]
            limits = (min(data) * 0.9, max(data) * 1.1) if data else (0.0, 1.0)
            ax.plot(limits, limits, color="0.4", linestyle="--", linewidth=1)
            style_axes(ax, xlabel=f"Published {label} ($\\mu$Hz)", ylabel=f"Estimated {label} ($\\mu$Hz)", legend=bool(data),
                       title="Reference comparison; roles shown separately")
            for suffix in ("png", "svg", "pdf"):
                path = target / (f"0{index}_{quantity}_comparison." + suffix)
                sources = "; ".join(evidence["role_directories"][name] + "/catalog.json" for name in evidence["role_directories"]
                                    if (contained(root, evidence["role_directories"][name]) / "catalog.json").exists())
                save_figure(fig, path, source=sources, close=False)
                paths.append(path)
            plt.close(fig)

        fig, ax = plt.subplots(figsize=(7.2, 4.0))
        reasons = read_table(reports / "failure_atlas.csv")
        codes = sorted({r["reason_code"] for r in reasons})
        counts = [len({(r["role"], r["stable_star_id"]) for r in reasons if r["reason_code"] == code}) for code in codes]
        ax.barh(np.arange(len(codes)), counts, color=data_color("spectrum"), edgecolor="black")
        ax.set_yticks(np.arange(len(codes)), [c.replace("_", " ").capitalize() for c in codes])
        style_axes(ax, xlabel="Unique stars with flag", title="Reason-coded acquisition and analysis limitations")
        fig.tight_layout()
        for suffix in ("png", "svg", "pdf"):
            path = target / ("04_failure_atlas." + suffix)
            save_figure(fig, path, source="reports/stage11/failure_atlas.csv", close=False)
            paths.append(path)
        plt.close(fig)
    write_json(reports / "figure_manifest.json", {"schema_version": 1, "style_id": "TA-PLOT-1.0", "files": [seal(root, p) for p in paths],
                                                "scope": "source_backed_roles_separated_no_population_claim_before_confirmation"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    plot(parser.parse_args().root.resolve())
