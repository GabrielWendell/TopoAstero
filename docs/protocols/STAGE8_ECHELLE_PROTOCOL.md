# Stage 8 locked protocol (T8.1–T8.10)

Run ID: `TA-S08-ECHELLE-R001`; configuration:
`configs/stage8_echelle.yaml`; frozen policy:
`registries/stage8_decision_policy.yaml`. Run `uv run python
workflows/run_stage8_echelle.py`, then `uv run python
workflows/execute_stage8_notebook.py`, `uv run python
workflows/build_stage8_manifest.py` and `uv run topoastero validate-stage8
--root .`. The workflow is offline and uses only the first 24 Stage 4 simulation
cells. Odd cell IDs are calibration/design context; even IDs are held-out
simulation evaluation. It does not read population spectra or the final
holdout. The published KIC 10963065 reference tables are accessed only after
the scan for a formula audit.

The trial grid uses the independent, sealed Stage 6 ACF spacing for each cell
as its non-truth anchor, multiplied by five fractions (0.90, 0.95, 1.00,
1.05, 1.10) in each of the half/nominal/double families. The same 15
candidates feed all six paired methods: combined cubical-H0-plus-graph,
graph-only, fixed-column conventional ridge contrast, bounded-slope Hough
linearity, ACF, and PSPS. Report the entire grid, argmax, half/double label,
ambiguous top-two ratio, whether the true spacing was even offered, and the
12% relative correctness indicator. The latter is **never** used for
selection. The Stage 6 ACF anchor can be poor, including a Stage 6
`not_detected` case; the prior is neither recalibrated from Stage 8 truth nor
assumed reliable.

Use 24 independent matched background-only gamma periodograms **per
evaluation cell** and take each draw's maximum over the entire 15-trial
family. A plus-one upper-tail p-value is attached to the observed maximum.
No per-trial p-value or false-positive rate from 12 signal-bearing cells is
claimed. Eight independent realization refits per evaluation cell cycle
through primary, −8%, and +8% fitted-background slopes. The frozen 90%
percentile interval receives a minimum ±12% relative half-width, explicitly
reported; it is an operational interval, not a posterior credible interval.
The ridge-location interval matches each refit to the observed leading track
within 0.17 cycles, then uses the shortest circular empirical arc at the
fixed observed point spacing, so different bootstrap alias coordinates are
not averaged. No circular arc is asserted with fewer than four matched draws.

An eligibility predicate, fixed before evaluation, requires medium/high
injected SNR, at least nine injected visible orders, duty cycle ≥0.8, and
Nyquist frequency above \(\nu_{\max}+1.5\Delta\nu\). All 24 cells remain in
the benchmark; the gate reports separately the detectable evaluation subset
and its size. The six stress factors are evaluated on one registered example,
so they form a failure atlas rather than population-level failure rates.

G8 retains the combined topological score as an estimator only if all three
requirements hold on the detectable evaluation subset: ≥0.60 correct alias,
≥0.80 coverage of the declared 90% interval, and ≥0.05 absolute accuracy
increment over graph-only. Exact seam and audit integrity are required in
both outcomes. Otherwise G8 records `geometry_only`: preserve the valid
cylinder, API, and figures, and narrow the claim; do not use the score as a
validated population estimator. Stage 7 delay PH remains off the critical
path independently of this decision. This fallback is part of the original
agenda gate, not a post-evaluation threshold change.
