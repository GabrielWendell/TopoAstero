# Classical observation model

Stage 3 treats an observed spectrum as the convolution of a stochastic stellar signal with the
mission sampling window, plus a frequency-dependent granulation background and white noise. The
model is descriptive: it is not used to claim that a scaling-relation mass or radius is truth.

## Frozen conventions

| Element | Convention |
| --- | --- |
| time | mission TDB day coordinate, absolute gaps retained |
| frequency | microhertz (`uHz`) |
| spectrum | one-sided power spectral density |
| package representation | relative-flux squared per `uHz` |
| reported representation | `ppm^2/uHz` (multiply relative-flux PSD by `10^12`) |
| Parseval check | PSD integral equals mean-subtracted variance in `ppm^2` |
| Nyquist | derived from native cadence; never inferred from plotted range |
| background | white noise plus 0/1/2 fixed-exponent Harvey-like components |
| window | normalized squared transform of the observed cadence mask |
| echelle | ascending order, ascending phase, circular phase smoothing |

The independent path and the Lightkurve path share the same sidedness, frequency unit, time axis,
and products. `results/stage3/pipeline_comparison.csv` is the normative reconciliation table.

## Interpretation boundaries

- The Lightkurve ACF2D tutorial intentionally reports no native uncertainty. TopoAstero adds a
  segment bootstrap but does not relabel it as a Lightkurve uncertainty.
- The Harvey-component covariance is a local pipeline approximation, not a full physical posterior.
- Window peaks describe sampling aliases; they are not oscillation detections.
- Nearest-peak mode residuals audit localization and order labels; they are not a new peak-bagging
  catalog.
- A TESS marginal candidate is retained as feasibility evidence only and is not promoted by
  combining sectors after inspecting the result.

## Machine-readable evidence

The result tables, exact input/output checksums, software versions, seed, and conventions are in
`results/stage3/`. Figure recipes are in `workflows/run_stage3_classical.py`; SVG figures are in
`reports/stage3/figures/`. Raw products remain recoverable by the Stage 2 manifest identities.
