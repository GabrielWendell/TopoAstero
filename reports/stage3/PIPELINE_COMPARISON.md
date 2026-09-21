# Rudy classical pipeline comparison

Both paths analyze the same ten Kepler products, retain absolute time gaps, express frequency in
uHz, and use a one-sided PSD. Their numerical difference is therefore an estimator/background
comparison rather than a unit-conversion artifact.

| Quantity | Lightkurve ACF2D | Independent Harvey/ACF | Difference |
| --- | ---: | ---: | ---: |
| `numax` (uHz) | 2145.000 | 2231.569 | +86.569 |
| `dnu` (uHz) | 103.112 | 103.366 | +0.254 |
| mass (`Msun`) | 1.0816 | 1.2043 | +0.1227 |
| radius (`Rsun`) | 1.2291 | 1.2718 | +0.0428 |
| log g (dex cgs) | 4.2930 | 4.3099 | +0.0169 |

The Lightkurve path applies default log-median flattening and a two-dimensional ACF. The independent
path fits the continuum outside the envelope, selects H2 by BIC, locates a 35-uHz-smoothed whitened
envelope, and uses a one-dimensional FFT autocorrelation for spacing. The Lightkurve values exactly
reproduce the tutorial; it reports no native uncertainty. The independent result is nearer the
LEGACY global `numax`, but is not declared superior: the registered segment bootstrap is broad and
the pipeline-choice component is material.

The normative values and full-precision residuals are in `results/stage3/pipeline_comparison.csv`
and `results/stage3/rudy_baseline.csv`.
