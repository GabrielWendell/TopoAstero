# Classical asteroseismic pipeline map

The executable index is `evidence/literature/classical_baseline_matrix.csv`. Each H1-H6 claim has
at least one named classical comparator in `hypothesis_baseline_crosswalk.csv`.

## Reference flow

1. Retrieve mission products and prepare a light curve with explicit aperture, quality-mask,
   detrending, stitching, cadence, and gap choices [@Lightkurve2018].
2. Compute a declared PSD or periodogram normalization [@VanderPlas2018].
3. Fit white noise, granulation/activity components, and an oscillation envelope
   [@Harvey1985; @Kallinger2014].
4. Estimate `numax` from the envelope and candidate `dnu` using pySYD, autocorrelation/EACF,
   or PSPS-like approaches [@Chontos2022; @Mathur2012; @Huber2011].
5. Fold by a candidate `dnu` and assess the conventional echelle ridges.
6. Where frequency-level inference is claimed, fit Lorentzian modes and report posterior or
   confidence intervals [@Lund2017; @Davies2016].
7. Only then derive scaling-relation mass, radius, or surface gravity with their calibration
   caveats [@KjeldsenBedding1995; @Hekker2020].

## Fair-comparison contract

- Same input products, masks, frequency range, and train/validation/test star groups.
- Same information budget: a topological method cannot use a tuned `dnu` when the baseline must
  discover it blind.
- Same failure policy: non-detections and ambiguous half/double spacings remain in denominators.
- Runtime, warning, and invalid-output records accompany accuracy metrics.
- A combined model is compared both with the strongest classical-only model and with each simple
  baseline needed to interpret gains.
- Peak-bagging remains the uncertainty-bearing reference when individual frequencies are claimed;
  topological candidate ranking does not replace a likelihood.

## Rudy reconciliation baseline

The Lightkurve tutorial uses Kepler quarters 2, 5, 6, and 7 and reports `numax = 2145 uHz` and
`dnu = 103.11 uHz`, without uncertainties [@LightkurveTutorial]. The full LEGACY Table 3 reports
`2203.7 (-6.3,+6.7) uHz` and `103.179 (-0.027,+0.027) uHz` [@SilvaAguirre2017]. These are different
method/data products, not conflicting replicas. The latter is the benchmark target; the former is
a reproducible context baseline.

