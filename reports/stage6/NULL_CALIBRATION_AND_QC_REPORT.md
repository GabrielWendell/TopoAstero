# Stage 6 null calibration and quality control

Independent maximum-statistic evaluation gives a worst false-positive rate of **0.0625**
and worst false-confidence rate of **0.0547**. Frequency bins and all 57 trial
spacings are inside the relevant maxima; pointwise thresholds are not used.

All 72 locked cells remain in the result tables. Incorrect or ambiguous comb outcomes are captured
by the `alias_ambiguity` policy at rate **0.8750**. Flags are nonexclusive and encode
absent envelopes, spacing ambiguity/control disagreement, insufficient orders, window
contamination, and unstable backgrounds.
