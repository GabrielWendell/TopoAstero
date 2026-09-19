# Mathematical TDA map

The claim-level matrix is `evidence/literature/theorem_matrix.csv`. It records the result,
assumptions, intended project use, and an explicit non-claim for every mathematical tool.

## Core objects

For a filtration \(K_a\subseteq K_b\) when \(a\leq b\), homology maps track the birth and death of
features. A finite off-diagonal persistence point is \((b,d)\), with persistence \(d-b\)
[@Edelsbrunner2002; @ZomorodianCarlsson2005]. TopoAstero must always state:

- input representation and metric;
- filtration direction and parameter units;
- coefficient field and homology dimensions;
- tie handling and treatment of essential classes;
- normalization and vectorization; and
- the null or resampling procedure used for inference.

For tame functions \(f,g\) on a common domain, the stability result used by H6 is

\[
d_B(D(f),D(g))\leq\lVert f-g\rVert_\infty,
\]

under the theorem's assumptions [@CohenSteiner2007]. This bounds movement of diagrams; it does not
bound error in `numax`, `dnu`, a classifier, or a stellar property unless an additional estimator
argument is supplied.

## Representation map

| Representation | Suitable construction | Required ablation |
| --- | --- | --- |
| 1D PSD or profile | exact sub/superlevel H0 on a path | prominence/peak-count and background-fit controls |
| Delay-embedded light curve | Vietoris--Rips persistence | delay, dimension, cadence, gap, and surrogate sensitivity |
| Echelle image | cubical persistence | pixel scale, smoothing, wrap boundary, and conventional ridge metric |
| Moving windows/masks | zigzag persistence | fixed-window summaries and missingness controls |
| Parameter scan | vineyard-like feature tracking | independent re-computation and multiple-search correction |

Sliding-window periodicity is mathematically plausible [@PereaHarer2015], cubical persistence is a
computationally natural image construction [@Wagner2012], and zigzags/vineyards describe changing
filtrations [@CarlssonDeSilva2010; @CohenSteiner2006]. None is yet evidence of utility for
solar-like oscillations.

## Inference boundary

Persistence magnitude is an effect summary rather than a p-value. Confidence sets, landscape
statistics, and randomization tests exist [@Fasy2014; @Bubenik2015; @RobinsonTurner2017], but their
sampling or exchangeability assumptions must be matched to star-grouped data. Mission cadences
from the same star are not independent replicates.

