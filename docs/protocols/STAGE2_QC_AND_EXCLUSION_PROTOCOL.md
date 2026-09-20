# Stage 2 QC and exclusion protocol

**Protocol ID:** TA-QC-2.0
**Frozen:** 2026-09-20

Quality control is performed before topology and cannot use persistence diagrams, topological
scores, benchmark errors, or partition-specific outcomes. The unit of mission QC is an immutable
raw product; the unit of population exclusion is a stable star group.

## Required checks

1. product keys and filenames are unique within the frozen input manifests;
2. byte sizes and SHA-256 values match externally cached payloads;
3. finite source times are ordered and contain no duplicates within a product;
4. time coverage increases and segment overlaps are either absent or intentionally separate
   pipeline products;
5. cadence is positive and allowed for the declared mission;
6. flux, uncertainty, quality, time columns, units, BJD reference, and aperture provenance exist or
   carry an explicit `not_provided` source state;
7. provided uncertainties contain no negative values;
8. NaN/finite, quality-zero, cadence-gap, crowding, and flux-fraction counts are retained;
9. reference row IDs, source links, units, uncertainties, versions, and checksums are complete; and
10. one star has exactly one partition role, with all observations inheriting that role.

Missing source uncertainties do not become zeros. A downstream method that requires uncertainties
must exclude that product or register an imputation model; either action creates a new preprocessing
state and configuration hash.

## Decisions and ledger

A failed check blocks promotion to an analysis input. Exclusions are appended to
`registries/exclusion_ledger.csv` with dataset, stable star and product IDs, UTC detection time,
reason code, evidence, partition role, owner, and status. `topology_seen` must be `false` for a
pre-topology decision. Corrections append a superseding row or change-control record rather than
erase history.

The Stage 2 QC run found no exclusion-worthy condition in the 43 payload-verified Rudy products.
QLP's five recent files without per-cadence uncertainties are retained as optional transfer
products with that limitation explicitly recorded. The separate LEGACY candidate index is not QC
promoted and therefore needs no fabricated payload checksums or exclusion rows.

`reports/stage2/qc_report.json` is the machine-readable result; `QC_REPORT.md` interprets it. The
offline `validate-stage2` command verifies the report, manifests, references, split seal, and Gate
G2 without contacting an external service.
