# Solar-like oscillation physics map

## Scope

This map fixes the physical interpretation of future topological observables. It does not claim
that topology discovers new stellar physics. The machine-readable authority is
`evidence/literature/physics_matrix.csv`; citations resolve through
`evidence/references/topoastero_stage1.bib`.

## Signal model

A working power spectral density model is

\[
P(\nu)=W+\sum_j \frac{A_j}{1+(2\pi\nu\tau_j)^{\alpha_j}}
+G(\nu;\nu_{\max},\sigma_{\rm env})
+\sum_{n\ell m}L(\nu;\nu_{n\ell m},H_{n\ell m},\Gamma_{n\ell m}),
\]

where `W` is white noise; the first sum represents granulation or activity components; `G` is a
convenient envelope description; and each `L` is a stochastically excited damped mode. This is a
conceptual decomposition. Later stages must state their exact normalization and background model.

For high-order low-degree p modes the idealized asymptotic structure is approximately

\[
\nu_{n\ell}\simeq\Delta\nu\left(n+\frac{\ell}{2}+\epsilon\right)-d_{0\ell},
\]

with departures caused by curvature, acoustic glitches, rotation, surface effects, evolution,
and fitting choices [@Tassoul1980; @GarciaBallot2019]. A topological echelle representation may
target ridge continuity under this approximation; it must not assume exact periodicity.

## Physics-to-evaluation consequences

| Physical feature | Consequence for Stage 2+ evaluation |
| --- | --- |
| Stochastic excitation | Use repeat realizations and uncertainty coverage; never score a single spectral height as truth. |
| Finite damping time | Stratify by linewidth and observing duration; unresolved and blended modes are legitimate regimes. |
| Granulation | Compare to an explicit classical background fit and perturb its component choices. |
| Degree and azimuthal visibility | Treat absent or blended components as visibility/geometry cases before labelling method failure. |
| Approximate comb | Report both global spacing error and ridge-level recovery; include half/double-spacing errors. |
| Gaps and cadence | Apply mission-realistic masks and duration degradation to every competing method. |
| LEGACY selection | Restrict external claims: it is a high-signal benchmark population rather than an occurrence sample. |

## Claim boundary

The physics literature establishes what structure and nuisance variation exist. It does not show
that a persistent-homology statistic is sensitive, calibrated, or useful for those structures.
Those are empirical claims requiring the preregistered simulations, controls, and star-grouped
validation already defined in Stage 0.

