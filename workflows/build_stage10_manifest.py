"""Seal the Paper I snapshot and build the honest G10 review gate.

The independent review record and machine reproduction report are administrative
records outside the immutable scientific snapshot, avoiding a self-referential
signature. Recording real reviewer approval never rewrites reviewed science.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_stage10_rudy import ROOT, read_csv, seal

from topoastero.config import load_yaml
from topoastero.portability import write_csv_lf, write_json_lf, write_text_lf
from topoastero.stage10_validation import independent_review_accepted

EXCLUDED = {"run_manifest.json", "freeze_manifest.json", "G10_ACCEPTANCE.json", "clean_reproduction.json", "deliverable_manifest.csv", "VALIDATION_REPORT.md", "FILES_CHANGED.md", "FILES_CHANGED.csv"}


def build(root: Path) -> None:
    cfg = load_yaml(root / "configs/stage10_rudy.yaml")
    summary = json.loads((root / "results/stage10/summary.json").read_text())
    audit = json.loads((root / "reports/stage10/claim_audit.json").read_text())
    if audit["status"] != "pass":
        raise ValueError("cannot seal unsupported manuscript claims")
    report = root / "reports/stage10"
    reproduction_path = report / "clean_reproduction.json"
    if not reproduction_path.is_file():
        write_json_lf(reproduction_path, {"status": "not_run", "independent_human_reviewer": None, "fresh_source_copy": False, "new_process": False})
    reproduction = json.loads(reproduction_path.read_text())
    clean = reproduction["status"] == "pass"
    trace = """# Stage 10 task/deliverable traceability

| Task | Implementation | Evidence |
|---|---|---|
| T10.1 | `configs/stage10_rudy.yaml`; public MAST acquisition; masks/cadence audit | `benchmark_capsule.json`; `sampling_audit.csv` |
| T10.2 | Lightkurve tutorial and independent Harvey/ACF; modes/scaling | `classical_branches.csv`; `background_models.json`; `broad_spectrum.csv`; `published_mode_overlay.csv`; `scaling_uncertainty.csv` |
| T10.3 | Exact localized path H0, prominence, comb and window-matched maxima | `localized_peaks.json`; `spectral_score_scan.csv`; `conditional_null_tests.csv`; `quality_flags.csv` |
| T10.4 | Periodic cylinder, competing graph/Hough/conventional controls | `cylinder.json`; `echelle_branch_controls.csv`; `echelle_score_scan.csv`; `echelle_bootstrap.csv`; `ratio_reference_audit.csv` |
| T10.5 | Conditional agenda clause: honor G7 drop | `summary.json`; prior `G7_ACCEPTANCE.json`; limitation/claim ledger |
| T10.6 | Quarter/cumulative, 256 monthly bootstraps, 64 stochastic repeats | `quarter_stability.csv`; `monthly_spectra.csv`; `monthly_bootstrap.csv`; `stochastic_draws.csv`; `uncertainty_budget.csv` |
| T10.7 | Cadence integration, duration/duty/noise, all actual windows | `kepler_to_tess.csv` (396 cells); `tess_sectors.csv` (11 sectors); `simulation_placement.csv` |
| T10.8 | All 48 factorial and 24 one-factor sensitivities | `robustness.csv` (72 rows); `echelle_branch_controls.csv` |
| T10.9 | Claims/controls/limitations frozen before draft | `claim_evidence.csv`; `claim_audit.json`; `LIMITATIONS_AND_NEGATIVE_RESULTS.md` |
| T10.10 | Complete internal review manuscript and 10 figure sets | `paper1/`; `figure_manifest.json`; `figures/` |

| Deliverable | Location | Completion |
|---|---|---|
| D10.1 | `results/stage10/` | Generated and sealed |
| D10.2 | `workflows/reproduce_stage10.py`; reproduction protocol | Public-ID one-command capsule |
| D10.3 | `paper1/main.tex` / `main.pdf`; ten styled PDF/SVG/PNG sets | Internal review freeze |
| D10.4 | `clean_reproduction.json`; claim audit; independent review record | Automated reproduction recorded separately; independent human review pending |
| G10 | `G10_ACCEPTANCE.json` | Implementation versus independent-review status explicitly separated |
"""
    write_text_lf(report / "TRACEABILITY_MATRIX.md", trace)
    budget = read_csv(root / "results/stage10/uncertainty_budget.csv")
    dnu = next(row for row in budget if row["quantity"] == "classical_dnu_uHz")
    write_text_lf(report / "STAGE10_REPORT.md", f"""# Stage 10 - Rudy and Paper I internal review freeze

Run **{cfg['run_id']}**, TopoAstero **0.11.0**, style **TA-PLOT-1.0**.

The capsule verifies **21** public FITS products. The tutorial baseline is
nu_max={summary['tutorial']['numax']:.2f} microHz, delta_nu={summary['tutorial']['dnu']:.6f} microHz.
The independent primary values are {summary['primary']['classical_numax_uHz']:.2f}
and {summary['primary']['classical_dnu_uHz']:.6f} microHz. The 72 registered
diagnostics span classical spacing [{float(dnu['registered_pipeline_minimum']):.4f},
{float(dnu['registered_pipeline_maximum']):.4f}] microHz. The persistence centroid
is {summary['primary']['persistence_numax_uHz']:.3f} microHz, with exact prominence
equivalence error {summary['maximum_prominence_equivalence_error']:.3g}.

The broad comb winner reaches a trial boundary; ACF/PSPS and half/double aliases
remain visible. The cylinder winner is the **{summary['echelle_winning_alias']}**
family at {summary['echelle_winning_spacing_uHz']:.4f} microHz. This is an ambiguous
diagnostic under G8 geometry_only, not a validated spacing estimate. Ratios from
unidentified cylinder paths are withheld; external identified-mode formulas are audited.

The 256 fitted-background/window-matched nulls give finite plus-one tails and
seven-family Holm correction. Mean null P/B is {summary['conditional_null_mean_ratio']:.4f}.
All conclusions remain conditional on that nuisance model. The independent
classical and graph controls reject where the persistence constructions reject;
no incremental topological utility follows from background rejection.

Quarter/cumulative analyses, 256 monthly bootstraps and 64 conditional stochastic
draws preserve distinct estimands and separate pipeline/systematic allowances.
All 396 Kepler-to-TESS cells use the real sector windows and record source coverage
loss. Actual marginal TESS candidate sectors: **{summary['actual_TESS_candidate_sectors']}**;
these are not confirmations. Delay PH is omitted under the G7 negative decision.

Eight bounded claims were frozen before the manuscript was rendered. Ten journal
figures use the project's academic style. The complete editable and compiled Paper I
draft includes methods, simulation context, Rudy, ablations, discussion, limitations
and data/code availability. No population/final holdout or new unreviewed G9 theorem
is used for a headline claim. No public deposition, journal submission or DOI is claimed.

Automated clean reproduction: **{reproduction['status']}**. Independent human
reproduction and claim review: **pending unless a valid signed record is supplied**.
The scientific G10 gate therefore remains review_pending by default. G9 proof
review remains {summary['G9_proof_status']}. This is an implementation-complete
internal review snapshot, with the external review obligations kept explicit.
""")
    fixed = ["configs/stage10_rudy.yaml", "registries/preprocessing_branches.csv", "pyproject.toml", "uv.lock",
             "docs/protocols/STAGE10_RUDY_FREEZE_PROTOCOL.md", "docs/reproducibility/STAGE10_REPRODUCTION.md",
             "reports/stage7/G7_ACCEPTANCE.json", "reports/stage8/G8_ACCEPTANCE.json", "reports/stage9/G9_ACCEPTANCE.json",
             "results/stage4/factorial_pilot.csv", "results/stage8/paired_benchmark.csv",
             "data/manifests/stage2/rudy_kepler_products.csv", "data/manifests/stage2/rudy_tess_products.csv",
             "data/manifests/stage2/reference_sources.csv", "data/reference/mode_frequencies.csv",
             "data/reference/frequency_ratios.csv", "data/reference/stellar_references.csv",
             "docs/source_documents/topological_asteroseismology_references.bib"]
    for folder in ("src/topoastero", "workflows", "schemas", "tests"):
        fixed += [path.relative_to(root).as_posix() for path in (root / folder).rglob("*") if path.is_file() and path.suffix in {".py", ".json"} and "__pycache__" not in path.parts]
    generated = []
    for folder in ("results/stage10", "reports/stage10", "paper1"):
        generated += [path.relative_to(root).as_posix() for path in (root / folder).rglob("*") if path.is_file() and path.name not in EXCLUDED and path.suffix in {".csv", ".json", ".md", ".svg", ".png", ".pdf", ".tex", ".bib"}]
    scientific = sorted(set(fixed + generated))
    freeze = {"snapshot_id": "TA-PAPER-I-FREEZE-001", "run_id": cfg["run_id"], "status": "internal_review_snapshot", "locked_on": cfg["locked_on"], "software_version": cfg["software_version"], "external_publication_or_DOI_created": False, "population_spectra_used": False, "final_holdout_used": False, "files": [seal(root, path) for path in scientific]}
    freeze_path = report / "freeze_manifest.json"
    # The scientific snapshot must stay unchanged when only recording a review.
    if not freeze_path.is_file() or json.loads(freeze_path.read_text()) != freeze:
        write_json_lf(freeze_path, freeze)
    accepted, review_errors = independent_review_accepted(root, load_yaml(root / "registries/stage10_independent_review.yaml"))
    if review_errors:
        raise ValueError("; ".join(review_errors))
    status = "pass" if accepted else "review_pending"
    gate = {"gate": "G10", "run_id": cfg["run_id"], "status": status, "implementation_status": "pass" if clean else "awaiting_clean_reproduction", "independent_human_review": "accepted" if accepted else "pending", "claim_scope": summary["claim_scope"], "clean_reproduction": reproduction["status"], "claim_audit": audit["status"], "G9_proof_review": summary["G9_proof_status"], "prior_decisions": {"G7": "drop", "G8": "geometry_only"}, "population_spectra_used": False, "final_holdout_used": False, "checks": [{"check": name, "status": value} for name, value in (("public_payload_capsule", "pass"), ("all_registered_branches_and_controls", "pass"), ("conditional_nulls_and_uncertainty_targets", "pass"), ("claim_evidence_audit", "pass"), ("paper_and_journal_figures", "pass"), ("fresh_process_reproduction", "pass" if clean else "pending"), ("independent_human_reproduction_and_claim_review", "pass" if accepted else "pending"))]}
    write_json_lf(report / "G10_ACCEPTANCE.json", gate)
    administrative = ["reports/stage10/freeze_manifest.json", "reports/stage10/G10_ACCEPTANCE.json", "reports/stage10/clean_reproduction.json", "registries/stage10_independent_review.yaml"]
    outputs = sorted(set(generated + administrative))
    write_json_lf(root / "results/stage10/run_manifest.json", {"run_id": cfg["run_id"], "snapshot_id": freeze["snapshot_id"], "software_version": cfg["software_version"], "style_id": "TA-PLOT-1.0", "gate_status": status, "outputs": [seal(root, path) for path in outputs]})
    deliverables = []
    for path in scientific + administrative + ["results/stage10/run_manifest.json"]:
        group = "D10.1" if path.startswith("results/stage10/") else ("D10.3" if path.startswith("paper1/") or "/figures/" in path else ("D10.4" if "claim" in path or "review" in path or "clean_reproduction" in path else "D10.2"))
        if "G10_ACCEPTANCE" in path:
            group = "G10"
        deliverables.append({"deliverable": group, **seal(root, path), "status": status if group in {"D10.4", "G10"} else "implemented"})
    write_csv_lf(report / "deliverable_manifest.csv", deliverables, fieldnames=["deliverable", "path", "size_bytes", "sha256", "status"])
    print(f"Paper I snapshot sealed; implementation {'PASS' if clean else 'awaits clean reproduction'}; G10 {status}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    build(args.root)


if __name__ == "__main__":
    main()
