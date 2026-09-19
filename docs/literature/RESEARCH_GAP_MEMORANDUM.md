# Research-gap memorandum

**Evidence cut-off:** 2026-09-19  
**Decision:** proceed past G1 with bounded novelty claims and a mandatory quarterly search update.

## Established

The following are established foundations and are not TopoAstero novelty claims:

- solar-like spectra contain stochastically excited and damped modes superposed on granulation and
  instrumental noise;
- asymptotic p-mode regularity motivates `dnu`, echelle diagrams, and ridge diagnostics;
- classical global pipelines, ACF/PSPS-like spacing estimators, background fits, scaling relations,
  and Bayesian peak-bagging already exist;
- persistent homology, stable persistence diagrams, sliding-window topology, cubical persistence,
  zigzag persistence, vineyards, and inferential tools already exist; and
- TDA already has adjacent applications to astronomical maps and Kepler light-curve morphology.

## Plausible but unestablished for this task

It is plausible that stable peak prominence, delay-embedded loops, or cubical echelle-ridge
features contain information about oscillation envelopes or comb regularity. It is also plausible
that such information is complementary to classical features. Stage 1 supplies no performance
evidence for those statements. Each remains a preregistered empirical question subject to
topology-free controls, realistic nulls, perturbations, calibration, and star-grouped validation.

## Candidate genuinely novel contribution

Under the dated audit, no direct precedent was located for a validated and uncertainty-aware
pipeline that uses persistent homology to estimate solar-like `numax`, `dnu`, or individual mode
frequencies, nor for a quantitatively evaluated “topological echelle” representation. The candidate
novel contribution is therefore narrow:

> A reproducible evaluation of explicitly defined persistent-homology representations for
> solar-like oscillation detection and seismic estimation, measured against named classical
> baselines with matched inputs, nulls, uncertainty, failure accounting, and held-out stars.

The novelty is not “using topology”, “using persistence”, detecting periodicity, building an
echelle diagram, or analyzing Kepler data. A negative or equivalence result can still satisfy the
project charter if the comparison is rigorous and diagnostic.

## Claim-to-baseline obligations

The normative mapping is `evidence/literature/hypothesis_baseline_crosswalk.csv`. In particular:

- H1 must beat or complement pySYD/background fitting;
- H2 must beat or complement ACF, PSPS, and conventional echelle measures;
- H3 must be evaluated against frequency-level peak-bagging;
- H4 must survive topology-free PSD and surrogate controls;
- H5 must use identical folds and capacity for classical-only and combined models; and
- H6 must distinguish diagram stability from downstream estimator robustness.

## Novelty-redefinition rule

If a direct precedent is discovered, do not suppress or relabel it as merely adjacent. Within one
review cycle:

1. add the primary paper to the clean bibliography and reference audit;
2. record the query and screening decision in the novelty log;
3. reproduce or document the precedent's relevant benchmark;
4. change the contribution from invention to independent validation, comparison, extension, or
   failure analysis; and
5. update H1-H6 wording through the Stage 0 change/deviation process before new final-holdout work.

## Residual risk

Search indexes have incomplete coverage; terminology varies; the OpenAlex broad queries returned
many lexical false positives; and Semantic Scholar was rate limited. The G1 statement is therefore
“no duplicate direct precedent found in the recorded search,” not “no such work exists.”

