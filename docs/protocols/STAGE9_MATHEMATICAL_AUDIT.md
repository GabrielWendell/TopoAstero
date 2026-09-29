# Stage 9 registered mathematical audit

This protocol fixes run `TA-S09-MATH-R001` and the YAML parameters before
the output tables. The agenda scope is T9.1–T9.8. The public claim register
is in `docs/science/STAGE9_THEOREMS_AND_PROOFS.md`; all bounds are conditional.

1. Compare the independent minimax peak calculation with the exact path
   union-find on 128 seeded distinct-height paths, including endpoint cases.
   Compare delay-map singular values with the closed ellipse formula.
2. Perturb path and masked-cylinder fields on an identical complex, calculate
   finite-diagram bottleneck distance, and check essential birth levels
   separately. Use unnormalized fields, never a changed mask.
3. Evaluate the new candidate-ridge inequalities for 160 seeded finite
   tracks and scan deterministic nominal and alias constructions. The tested
   frequency model must state consecutiveness of **trial rows**; alias
   examples deliberately violate it.
4. Invert a Gamma/Chernoff union bound for 24 raw bins, shape 8, alpha 0.1.
   Evaluate 4096 independent Gamma vectors with the registered seed and show
   empirical exceedances and Wilson uncertainty. This tests calibration only
   in the stated Gamma family, not mission spectra.
5. Check exact logarithmic scaling propagation against perturbed monomials
   while varying both systematics independently. Publish no seismic/stellar
   error bar for the Stage 8 geometry-only estimator.
6. Catalog merged peaks, endpoint births, missing trial rows, curvature,
   crossing/pruning, half/double aliases, multimodal score geometry, and
   stochastic peak reordering. Label which assumptions fail; do not turn a
   simulated example into a theorem.
7. Run `uv sync --locked --group dev`, `uv run pytest`, `uv run ruff check .`,
   `uv run mypy src`, `uv run topoastero validate-stage9 --root .`, and
   `uv run python workflows/execute_stage9_notebook.py` in a fresh extraction.
   The proof reviewer is a different named human, unaffiliated with these
   computations, and should annotate claim S9-T1 and any objections.

Input restrictions: read Stage 8's **negative** gate decision; do not access
population spectra or the final holdout. Outputs are serialized as LF text,
seeded and SHA-256 sealed. An automated audit is an implementation pass; the
G9 science gate stays pending until external proof review.

