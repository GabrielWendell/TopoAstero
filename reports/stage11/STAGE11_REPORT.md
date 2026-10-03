# Stage 11 - Kepler LEGACY population validation



Implementation: pass. Scientific G11: population_pending.



The frozen cohort contains 66 stars: {'development': 39, 'final_holdout': 13, 'internal_validation': 13, 'descriptive_benchmark': 1}. Acquired 1261 of 2159 candidate products.

Confirmation status: unopened; observed opening count: 0.



Results are separated by role. Rudy remains descriptive and is excluded from population confirmation performance.

Missing stars have four explicit catalog rows, two methods by two quantities. Failed/rejected estimates are not imputed.



Parameter errors use a shared successful star set; method-specific valid/failed/limited counts are reported alongside it.

Population intervals resample stars jointly; stellar intervals resample nonoverlapping months jointly and refit backgrounds.

Coverage compares conditional intervals to published reference centers; interval overlap is reported separately. It is not coverage of a known true stellar parameter.

The LEGACY sample contains selected oscillators. Specificity, false-alarm rate, Brier score and probability calibration cannot be measured from these positive-only observations.

Cylinder scores remain geometric diagnostics. Delay PH stays dropped. H0/prominence differences are independently checked.

Reference ratio localization is conditioned on published degrees and orders. No blind r02/r01/r10 estimate is issued. Corrected asymmetric uncertainties are retained; covariance-based intervals are withheld.



An exact signed release and recorded supervisor/steward authorization precede one-time confirmation. Repeated opens, changed code/configuration and stale inputs are rejected.

Process interruption can resume the identical attempt; completed star results, including failures, are never selectively rerun.



See docs/reproducibility/STAGE11_REPRODUCTION.md for executable commands and docs/protocols/STAGE11_POPULATION_PROTOCOL.md for the analysis contract.
