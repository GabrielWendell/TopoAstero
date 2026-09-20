# Stage 3 implementation report

**Stage:** Classical asteroseismic baseline and observation model  
**Tasks:** T3.1-T3.9  
**Completed:** 2026-09-20  
**Gate:** G3 PASS

## Outcome

The exact four-quarter Lightkurve case is reproduced from ten checksum-verified Kepler products:
`numax=2145.000 uHz`, `dnu=103.1121 uHz`, `M=1.0816 Msun`, `R=1.2291 Rsun`, and
`logg=4.2930 dex(cgs)`. These agree with the tutorial point values to its displayed precision.

An independent minimum-BIC Harvey/ACF pipeline yields `numax=2231.5686 uHz` and
`dnu=103.3662 uHz`. Its scaling products are `1.2043 Msun`, `1.2718 Rsun`, and
`4.3099 dex(cgs)`. The difference is not hidden: both paths share the products, time/frequency
axes, PSD sidedness, and units, leaving background/estimator choice as the traced cause. Both sets
overlap the authoritative LEGACY `numax` and `dnu` under the registered random, pipeline-choice,
and reference components.

## Task completion

- **T3.1:** exact official Lightkurve Q2/Q5/Q6/Q7 cleaning, PSD, ACF2D, and scaling workflow,
  versioned in one command and summarized in the executed benchmark notebook.
- **T3.2:** astronomy-package-independent Harvey-whitened envelope plus FFT-ACF estimator, with
  explicit convention and output reconciliation.
- **T3.3:** H0/H1/H2 backgrounds compared by exponential likelihood, AIC, BIC, residual RMS, and
  covariance diagnostics; H2 is selected (`BIC=845384.45`).
- **T3.4:** Q2/Q5/Q6/Q7 and combined window atlas. Absolute combination has a 0.6006 duty cycle and
  0.02371-uHz resolution; compressing gaps changes duty cycle to 0.9740 and is diagnostic only.
- **T3.5:** conventional echelle suite at three trial spacings with frozen orientation, order range,
  smoothing, and circular phase boundary.
- **T3.6:** all 42 published modes matched under one rule. All are within 2.5 uHz, 30 are within
  1 uHz, and residual RMS is 1.030 uHz. Publisher-to-echelle order offsets are explicitly +1 (29
  rows) or +2 (13 rows), corresponding to degree/order conventions rather than silent relabeling.
- **T3.7:** six branches frozen; four Kepler sensitivity branches, one analytic PSD branch, and one
  sector-wise TESS transfer branch. Every selection record states that topology was not inspected.
- **T3.8:** 500 segment bootstraps separate random uncertainty from half-range pipeline-choice and
  published-reference terms. The `numax` random component is 93.78 uHz and the pipeline component
  43.28 uHz; `dnu` components are 0.096 and 0.412 uHz.
- **T3.9:** eleven SPOC sectors assessed independently. Sector 15 is a marginal candidate; ten
  sectors are non-detections. No combined detection is claimed or optimized.

## Deliverables

| Agenda deliverable | Implementation |
| --- | --- |
| D3.1 | `workflows/run_stage3_classical.py`; `notebooks/03_rudy_classical_baseline.ipynb` |
| D3.2 | `results/stage3/rudy_baseline.csv`; pipeline and uncertainty tables |
| D3.3 | `reports/stage3/SENSITIVITY_REPORT.md`; background/window/branch tables |
| D3.4 | `reports/stage3/figures/`; `mode_audit.csv`; `echelle_trials.csv` |
| D3.5 | `reports/stage3/TESS_FEASIBILITY_NOTE.md`; sector table/figure |

## Gate rationale

G3 passes because the Lightkurve context result is exactly reproduced, all baseline-reference
residuals lie inside joint uncertainty, every estimator difference is tied to a named modeling
choice, and analytic PSD/injection tests enforce normalization. H2 background recovery, circular
echelle behavior, window accounting, mode localization, and manifest hashes are under automated
tests. Raw data are not redistributed, no holdout was opened, and no topological appearance entered
preprocessing or gate selection.

The broad bootstrap `numax` interval is retained rather than narrowed post hoc. The TESS pilot is
also intentionally inconclusive. These limitations are accepted evidence, not missing returns.
