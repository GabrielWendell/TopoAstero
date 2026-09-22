# Stage 5 TDA representation specification

**Specification:** TA-S05-REPRESENTATIONS-1.0  
**Status:** locked after the simulation-development audit on 2026-09-22  
**Scope:** analytic cases and the 72 Stage 4 pilot cells only; no population or final holdout data

This document is the normative method specification for T5.1. The machine-readable values are in
`registries/stage5_representation_parameters.yaml`; the compact candidate statistics are in
`registries/stage5_feature_registry.csv`. All complexes use coefficients in \(\mathbb F_2\),
deterministic `(filtration value, simplex dimension, vertex tuple)` ordering, and a tolerance of
\(10^{-10}\). Zero-length bars are omitted. Essential classes retain localization but are excluded
from finite totals, maxima, centroids, distances, and calibrated test statistics.

## Frozen filtrations

| ID | Domain and vertices | Scalar function or distance | Direction | Maximum homology | Normalization | Essential handling |
| --- | --- | --- | --- | --- | --- | --- |
| REP-LC | observed samples joined as a time path | relative flux | superlevel | H0 | median/MAD | retain global-excursion birth; exclude from summaries |
| REP-DELAY | deterministic farthest-point landmarks in a delay cloud | Euclidean distance | increasing distance | H1 | signal and coordinates on a median/MAD scale | retain connected component and any cutoff-induced classes; exclude from summaries |
| REP-PSD | frequency bins joined as a path | \(\log(P/B)\) | superlevel | H0 | median/MAD after registered smoothing | retain global peak; exclude from summaries |
| REP-MODE | extracted mode frequencies and degrees | Euclidean distance in \(( (\nu-\nu_0)/\Delta\nu,\ell/\max(2,\ell_{max}) )\) | increasing distance | H1 | physical \(\Delta\nu\) and degree scaling | retain connected component; exclude from summaries |
| REP-ECHELLE | binned radial order by circular phase, \(I\times S^1\) | binned \(\log(P)\) field | superlevel | H1 | median/MAD | retain cylinder H1 for boundary QA; exclude essential classes from summaries |

MAD means \(1.4826\operatorname{median}|x-\operatorname{median}(x)|\), with standard deviation and
then one as deterministic fallbacks. The echelle phase edges are glued before reduction; the
displayed left/right image boundary is therefore not a physical boundary. Its pilot statistic is
H0 ridge lifetime. H1 is implemented and used to verify the domain, but no finite H1 echelle
statistic is selected at G5.

## Physical targets, controls, and nulls

| ID | Named physical target | Required topology-free control | Calibrated null | Prespecified disposition |
| --- | --- | --- | --- | --- |
| REP-LC | excursion hierarchy and activity/granulation morphology | peak prominence, peak count, distributional summaries | IAAFT | diagnostic; never a primary p-mode comb estimator |
| REP-DELAY | periodic coherence, damping/lifetime, possible phase information | lag autocorrelation and spectral entropy | phase-randomized and IAAFT | Stage 7 paired phase-information test |
| REP-PSD | spectral peak hierarchy and envelope location | ordinary prominence and smoothed-envelope centroid | background-only periodograms | Stage 6 localized estimator |
| REP-MODE | comb/ridge geometry and degree separation | nearest-neighbor geometry | matched-density randomized clouds | drop unless distinct utility survives audit |
| REP-ECHELLE | ridge connectivity and trial-spacing coherence | circular ridge resultant and contrast | randomized comb | Stage 8 periodic-echelle component |

Null p-values use the conservative plus-one upper-tail estimator. Selection never uses a
pointwise visual threshold. The Stage 5 calibration/evaluation seed streams are independent; later
claims must recalibrate over their complete registered frequency, delay, smoothing, and trial-
spacing search families.

## Reference backends

`topoastero.tda` exposes four interoperable pieces:

1. `exact_path_persistence` delegates to the Stage 0 elder-rule path implementation and maps every
   birth and merge back to physical metadata.
2. `vietoris_rips_persistence` enumerates simplices through one dimension above the requested
   output and performs explicit column reduction over \(\mathbb F_2\). It is intentionally a small-
   cloud reference implementation.
3. `grid_persistence` triangulates every pixel cell with a fixed diagonal and optionally glues
   either axis. `(False, True)` is the cylindrical echelle domain.
4. `bottleneck_distance`, `wasserstein_distance`, `diagram_summary`, and `localized_records`
   operate on the common `PersistenceDiagram` / `TopologicalPair` API.

The analytic cross-check suite compares path H0 to independent peak prominence, Rips H0 deaths to
a SciPy minimum spanning tree, a four-point square H1 bar to its exact value
\(\sqrt 2-1\), periodic versus rectangular grid homology, and the bottleneck identity/stability
cases. Accelerated future backends must reproduce these sorted diagrams within the frozen
tolerance.

## Compact summaries

Only a total, maximum, persistence-weighted centroid, ridge lifetime, diagram stability distance,
or calibrated p-value may be primary. Counts are diagnostics. The registry deliberately excludes
generic persistence images, landscapes, entropy banks, arbitrary Betti-curve grids, and unbounded
hyperparameter feature expansion. A new statistic requires a change-log entry, physical target,
null, control, and later-claim role before any confirmation data are inspected.

## Localization contract

Every pair carries the birth simplex, death simplex, and metadata for each participating vertex.
The required mappings are time/sample for REP-LC, source time and embedding landmark for
REP-DELAY, frequency/peak for REP-PSD, frequency/degree/order for REP-MODE, and pixel/order/phase
for REP-ECHELLE. `results/stage5/localization_catalog.json` is the governed example catalog; no
topological feature is accepted if it cannot be traced back to the represented physical object.

