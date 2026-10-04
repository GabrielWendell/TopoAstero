# Paper I internal review draft

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
