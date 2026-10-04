"""Write the source-backed Paper I internal review draft, then compile with TeX."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from run_stage10_rudy import ROOT, read_csv

from topoastero.portability import write_json_lf, write_text_lf
from topoastero.provenance import sha256_file


def tex_escape(value: str) -> str:
    return value.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def build(output: Path, *, require_tex: bool = False) -> None:
    results, reports = output / "results/stage10", output / "reports/stage10"
    audit = json.loads((reports / "claim_audit.json").read_text())
    if audit["status"] != "pass" or not audit["claims_frozen_before_manuscript"] or audit["claim_evidence_sha256"] != sha256_file(reports / "claim_evidence.csv"):
        raise ValueError("freeze and audit claim evidence before drafting the manuscript")
    summary = json.loads((results / "summary.json").read_text())
    branches = read_csv(results / "classical_branches.csv")
    tests = read_csv(results / "conditional_null_tests.csv")
    budgets = read_csv(results / "uncertainty_budget.csv")
    claims = read_csv(reports / "claim_evidence.csv")
    dest = output / "paper1"
    dest.mkdir(parents=True, exist_ok=True)
    macros = {"RudyCadences": str(summary["kepler_cadences"]), "RudyBaseline": f"{summary['absolute_span_days']:.2f}", "RudyDuty": f"{summary['duty_cycle']:.3f}", "RudyNumax": f"{summary['primary']['classical_numax_uHz']:.2f}", "RudyDnu": f"{summary['primary']['classical_dnu_uHz']:.4f}", "RudyCentroid": f"{summary['primary']['persistence_numax_uHz']:.2f}", "TutorialNumax": f"{summary['tutorial']['numax']:.0f}", "TutorialDnu": f"{summary['tutorial']['dnu']:.4f}", "RudyAliasSpacing": f"{summary['echelle_winning_spacing_uHz']:.2f}", "RudyAlias": summary["echelle_winning_alias"], "NullMeanRatio": f"{summary['conditional_null_mean_ratio']:.3f}", "TessCandidateSectors": ', '.join(str(value) for value in summary["actual_TESS_candidate_sectors"]) or 'none'}
    write_text_lf(dest / "results_macros.tex", "% Generated from results/stage10/summary.json. Do not edit.\n" + "\n".join(f"\\newcommand{{\\{key}}}{{{value}}}" for key, value in macros.items()) + "\n")
    lines = [r"\begin{table}[htbp]\centering\small", r"\caption{Mandatory preprocessing branches. The tutorial and independent estimators use different whitening and envelope conventions. All frequencies are in $\mu$Hz.}", r"\begin{tabular}{lrrrrr}\toprule", r"Branch & Cadences & Tutorial $\nu_{\max}$ & Tutorial $\Delta\nu$ & Classical $\nu_{\max}$ & Classical $\Delta\nu$\\\midrule"]
    for row in branches:
        lines.append(f"{row['branch_id']} & {row['cadences']} & {float(row['tutorial_numax']):.0f} & {float(row['tutorial_dnu']):.4f} & {float(row['classical_numax_uHz']):.1f} & {float(row['classical_dnu_uHz']):.4f}" + r"\\")
    lines += [r"\bottomrule\end{tabular}\label{tab:branches}\end{table}", r"\begin{table}[htbp]\centering\small", r"\caption{Conditional fitted-background maximum-statistic tests. MC uncertainty and exceedance counts are provided in the machine-readable table. Holm controls the seven reported families within this conditional model.}", r"\begin{tabular}{lrrr}\toprule", r"Statistic family & Observed & Plus-one $p$ & Holm $p$\\\midrule"]
    labels = {"classical_envelope_snr": "Smoothed envelope", "peak_max_lifetime": "Largest finite peak lifetime", "comb_max_score": "Persistence comb maximum", "echelle_max_combined": "Cylindrical combined maximum", "echelle_max_graph": "Ridge graph maximum", "acf_max_score": "ACF maximum", "psps_max_score": "PSPS maximum"}
    for row in tests:
        lines.append(f"{labels[row['statistic']]} & {float(row['observed']):.4f} & {float(row['pvalue']):.4f} & {float(row['holm_pvalue']):.4f}" + r"\\")
    lines += [r"\bottomrule\end{tabular}\label{tab:nulls}\end{table}", r"\begin{table}[htbp]\centering\small", r"\caption{Distinct uncertainty targets. Bootstrap endpoints target the monthly averaged spectrum. The full-span point is a different estimator. Pipeline ranges include all 72 registered diagnostics; components are not combined.}", r"\begin{tabular}{lrrrr}\toprule", r"Quantity ($\mu$Hz) & Full span & Monthly point & Monthly bootstrap 95\% & Pipeline range\\\midrule"]
    labels = {"classical_numax_uHz": "Classical envelope", "classical_dnu_uHz": "Classical spacing", "persistence_numax_uHz": "Persistence centroid"}
    for row in budgets:
        lines.append(f"{labels[row['quantity']]} & {float(row['full_span_point']):.2f} & {float(row['monthly_averaged_point']):.2f} & [{float(row['monthly_bootstrap_lower95']):.2f}, {float(row['monthly_bootstrap_upper95']):.2f}] & [{float(row['registered_pipeline_minimum']):.2f}, {float(row['registered_pipeline_maximum']):.2f}]" + r"\\")
    lines += [r"\bottomrule\end{tabular}\label{tab:uncertainty}\end{table}"]
    write_text_lf(dest / "results_tables.tex", "\n".join(lines) + "\n")
    claim_lines = [r"\section*{Frozen claim--evidence ledger}"]
    for row in claims:
        claim_lines += [r"\paragraph{" + row["claim_id"] + "} " + tex_escape(row["claim"]), r"\textit{Control:} " + tex_escape(row["controls"].replace(";", ", ").replace("_", " ")) + r". \textit{Limit:} " + tex_escape(row["limit"].replace("_", " ")) + "."]
    write_text_lf(dest / "claim_ledger.tex", "\n".join(claim_lines) + "\n")
    write_text_lf(dest / "references.bib", (ROOT / "docs/source_documents/topological_asteroseismology_references.bib").read_text(encoding="utf-8") + "\n" + (ROOT / "paper1/additional_references.bib").read_text(encoding="utf-8"))
    template = (ROOT / "paper1/manuscript_template.tex").read_text(encoding="utf-8")
    write_text_lf(dest / "main.tex", template)
    write_text_lf(dest / "README.md", """# Paper I internal review draft

`main.tex` is generated from `manuscript_template.tex` after the claim-evidence
ledger is frozen. `results_macros.tex`, `results_tables.tex` and `claim_ledger.tex`
are generated from Stage 10 results. Edit the template, rerun the complete capsule,
and create a new freeze before making scientific revisions. The author field names
the project owner; author/affiliation/journal approval is still an author decision.

Build from this directory with `pdflatex main.tex`, `bibtex main`, and two further
`pdflatex main.tex` passes, or run `workflows/build_stage10_paper.py` from the root.
The generated PDF is a complete internal review manuscript, not a submitted,
externally reviewed or published paper. No DOI has been assigned. G9 proof review
and G10 independent reproduction/claim review remain pending.

Journal figures reside in `reports/stage10/figures/` as PDF, SVG and PNG, with the
academic style `TA-PLOT-1.0`. Captions and source mappings are machine-readable.
""")
    status = "not_compiled"
    if shutil.which("pdflatex") and shutil.which("bibtex"):
        env = {**os.environ, "SOURCE_DATE_EPOCH": "1790812800", "FORCE_SOURCE_DATE": "1"}
        commands = (["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], ["bibtex", "main"], ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"])
        logs = []
        for command in commands:
            run = subprocess.run(command, cwd=dest, env=env, capture_output=True, text=True, check=False)
            logs.append(run.stdout + run.stderr)
            if run.returncode:
                write_text_lf(dest / "compile.log", "\n".join(logs))
                raise RuntimeError(f"Paper I TeX compilation failed; see {dest / 'compile.log'}")
        write_text_lf(dest / "compile.log", "\n".join(logs))
        status = "compiled"
    elif require_tex:
        raise RuntimeError("pdflatex and bibtex are required by --require-tex")
    write_json_lf(dest / "build_status.json", {"status": status, "claims_frozen_before_manuscript": True, "claim_evidence_sha256": audit["claim_evidence_sha256"], "publication_status": "internal_review_draft", "external_publication_or_DOI_created": False, "engine": "pdflatex_and_bibtex" if status == "compiled" else None})
    print(f"Paper I: {status}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--require-tex", action="store_true")
    args = parser.parse_args()
    build(args.output_root, require_tex=args.require_tex)


if __name__ == "__main__":
    main()
