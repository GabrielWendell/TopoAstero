# Reproducing Stage 10 / Paper I

From the TopoAstero repository root, in a Bash, PowerShell or VS Code terminal:

```text
uv sync --locked --group dev --extra astronomy
uv run python workflows/reproduce_stage10.py --cache-dir ../topoastero-mission-cache --download
```

The second command is the complete public-identifier entry point: verify/download
21 frozen MAST FITS products, run all analyses, freeze claim evidence, export figures,
write the manuscript and build its PDF when a TeX installation is available, then
seal the internal review snapshot. Raw payloads remain in the chosen external cache.
Any size/hash mismatch stops the run. A changed archive payload requires a new
registered acquisition, never silently accepting the new bytes.

Dependencies for analysis/figures are in `uv.lock`. PDF compilation also needs a
standard TeX distribution with `pdflatex` and `bibtex` (TeX Live or MiKTeX). Without
TeX, the command still generates editable LaTeX and all numeric/figure evidence;
it records `not_compiled` and the freeze does not claim a complete PDF reproduction.
Use `--require-tex` to make missing TeX a hard error. The delivered PDF was compiled
and visually checked. `--output-root ../stage10-rerun` keeps a rerun separate from
the delivered snapshot.

## Automated clean reproduction

```text
uv run python workflows/reproduce_stage10.py --cache-dir ../topoastero-mission-cache --clean-check
```

This creates a fresh source copy and locked virtual environment, omits existing
Stage 10 results/reports/manuscript outputs, and executes the full pipeline in a
new process using already checksum-verified mission payloads. It compares all
scientific CSV/JSON values and journal SVG figures. Numeric tolerance is
`atol=1e-8, rtol=1e-9`; strings, flags and identifiers must agree exactly. PDFs must
regenerate, but binary PDF metadata is not a numerical-science gate. The report
records the actual subprocess/environment, file comparisons and result fingerprint.
It never fills the independent reviewer fields.

The offline CI command is:

```text
uv run topoastero validate-stage10 --root .
uv run python workflows/replay_stage10_reduced.py
```

The validator checks seals, branch completeness, null-tail calculations, aliases,
claim-evidence scope, style, review honesty and prior stages without network or
astronomy extras. Reduced replay recomputes headline diagnostics from the delivered
positive PSD tables. Reduced replay alone is not a raw-product reproduction.

## Independent human review

Provide a separate reviewer the source archive, this protocol and public manifests.
They run the full entry point, inspect the eight claims and limitations, and record
their own identity/affiliation/date/independence and the SHA256 of
`reports/stage10/freeze_manifest.json` in `registries/stage10_independent_review.yaml`.
Only an actual completed review may change that record from pending to accepted.
Reseal the gate with `workflows/build_stage10_manifest.py`; do not alter the reviewed
snapshot when recording approval. G10's implementation status can pass while its
scientific/independent-review status remains pending.

## Outputs

`results/stage10/` contains machine-readable physical/numerical results, the public
product capsule and environment. `reports/stage10/` contains claims, limitations,
traceability, clean reproduction, immutable snapshot hashes and ten styled figure
sets. `paper1/` contains editable source, generated tables/macros, bibliography
and the compiled internal review draft. No publishable DOI or submission is implied.
