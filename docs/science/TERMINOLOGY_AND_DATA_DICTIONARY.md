# T0.2 - Terminology and data dictionary

The authoritative entries are `registries/terminology.yaml`; this document summarizes their use.

## Frozen scientific language

- **Persistence:** birth-to-death filtration interval of a localized homology class, with filtration,
  domain, homology degree, coefficient field, and essential-class convention stated.
- **Ridge:** an order-linked, physically localized high-intensity locus on the periodic echelle
  cylinder. A bright pixel chain without order linkage is not automatically a ridge.
- **Coherence:** reproducible persistence/continuity across order, time, or stochastic realization
  after comparison with an appropriate null. It is not merely a large peak.
- **Topological echelle:** a periodic-domain construction on `S1 x I` that computes persistent or
  graph-localized ridge structure while enforcing circular phase adjacency. A rectangular echelle
  image with disconnected left/right boundaries is not topological echelle.
- **Detection:** rejection/decision under a frozen statistic, search correction, null, and threshold,
  with the operating point reported.
- **Calibration:** empirical agreement between nominal and realized probability, interval coverage,
  or error rate under the declared data-generating domain.
- **Robustness:** performance stability over a preregistered perturbation set, reported as a curve or
  worst/quantile change; survival of one convenient branch is insufficient.
- **Complementarity:** out-of-sample conditional information after strong classical variables are
  included, with uncertainty and a practical-equivalence margin.
- **Failure:** a prespecified invalid/no-estimate or falsification state. It is an outcome to record,
  not a row to delete.

## Core coordinates and units

| Field | Meaning | Unit/convention |
| --- | --- | --- |
| `time` | Mission time attached to a cadence | BKJD for Kepler; BTJD for TESS; conversion metadata required |
| `flux` | Declared raw or corrected photometric series | Relative/dimensionless unless source unit retained |
| `flux_uncertainty` | Per-cadence uncertainty matching flux state | Same unit as flux; nonnegative |
| `frequency` | One-sided positive Fourier frequency unless stated | microhertz |
| `psd` | Power spectral density with declared normalization | unit declared as flux-unit squared per microhertz |
| `nu_max` | Frequency of maximum oscillation-envelope power under a declared model | microhertz |
| `Delta_nu` | Large frequency separation under a declared estimator/order range | microhertz |
| `delta_nu_02` | Small separation between adjacent l=0 and l=2 modes | microhertz |
| `r02`, `r01`, `r10` | Declared dimensionless separation ratio with indexing convention | dimensionless |
| `echelle_phase` | `frequency mod Delta` represented periodically | radians in `[0, 2*pi)` or normalized phase in `[0,1)` |
| `radial_order` | Integer order under the stated labeling convention | integer |
| `persistence` | Birth minus death in filtration units | same unit as filtration scalar unless normalized |

Every canonical data table later defined in S2 must include a schema version, stable star/product
identity, provenance link, processing state, quality/mask reason, units, and missing-value semantics.

## Reserved claim words

Use **identity/equivalence** only for a proof or tested exact discrete equivalence. Use **estimator**
for a specified map with sampling properties, **proxy** for a calibrated but indirect relation,
**candidate** before lock, **exploratory** after data-informed selection, and **confirmatory** only
for a registered one-time test. "Stable" without a metric and perturbation norm is prohibited.

