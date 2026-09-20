# Stage 2 implementation report

**Stage:** Data acquisition, provenance, and canonical data model
**Tasks:** T2.1-T2.8
**Completed:** 2026-09-20
**Gate:** G2 PASS

## Outcome

Stage 2 creates an offline-verifiable boundary between archive discovery, payload-verified inputs,
canonical derived rows, and inventory-only candidates. Rudy is resolved across catalogs and has 43
content-hashed mission products. All 66 LEGACY stars have exact Kepler short-cadence archive
candidate inventories, but those 2,159 candidates cannot enter analysis until their payload SHA-256
is computed. Published modes, ratios, and stellar/global values are normalized into versioned
reference tables with row-level provenance.

## Task completion

- **T2.1:** resolved KIC 10963065 / HD 176693 / Kepler-408 / TIC 48450369 / Gaia DR3
  2131593785132997632 and froze ICRS coordinates plus aliases.
- **T2.2:** recorded the tutorial's 10 Kepler monthly files across Q2, Q5, Q6, and Q7, plus exact
  archive metadata for all population candidates.
- **T2.3:** recorded 11 TESS sectors and three deliberately separate product families (SPOC,
  TESS-SPOC, QLP), including cadence, aperture, crowding, quality, and window metadata.
- **T2.4:** implemented a closed light-curve schema and standard-library dataclass with explicit
  time, flux, errors, quality, cadence, masks, preprocessing state, and lineage.
- **T2.5:** implemented a spectrum schema with frequency/PSD units, sidedness, Nyquist, window,
  background components, and lineage.
- **T2.6:** produced 42 mode-frequency, 38 frequency-ratio, and 264 stellar/global reference rows.
- **T2.7:** passed 11 pre-topology integrity checks and retained an explicit, empty exclusion
  ledger. Missing QLP uncertainties remain missing and nonblocking for the optional transfer case.
- **T2.8:** froze a deterministic grouped split of 39 development, 13 internal-validation, 13 final
  holdout, and one descriptive Rudy benchmark; no star crosses roles.

## Reproducibility

The runtime model and validator have no astronomy-library dependency. Network and FITS packages are
needed only to refresh the acquisition snapshot or rebuild its examples. Checked-in scripts record
the exact queries, source checksums, resolver fallback for the two 16 Cyg targets, split algorithm,
configuration hash, and manifest-building logic.

The accepted package version is 0.3.0. CI enforces formatting, strict typing, unit/integration/
governance tests, Stage 0/1/2 contracts, deterministic Stage 0 smoke reproduction, and wheel/sdist
builds.

## Boundaries retained at G2

- TESS transfer is optional and does not block the Kepler core.
- Raw FITS and raw publisher payloads are not redistributed.
- The portable repository has no secret store, so split identities are auditable cleartext; the
  holdout's analysis use remains unopened and access-controlled by policy/log.
- A LEGACY candidate metadata digest is not a payload checksum and cannot authorize analysis.
- Stage 2 specifies spectral representation semantics but does not select later-stage estimators.
