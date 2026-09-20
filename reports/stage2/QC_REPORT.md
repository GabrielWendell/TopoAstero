# Stage 2 quality-control report

**Report:** TA-QC-STAGE2-20260920
**Decision:** PASS
**Topology inspected:** no

The QC run inspected the frozen metadata extracted from 43 checksum-verified Rudy payloads: 10
Kepler short-cadence files and 33 TESS files across SPOC, TESS-SPOC, and QLP. The external FITS
cache was used only to compute checksums and metadata; no raw mission payload is redistributed.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Product identity | Pass | 43 unique keys and filenames |
| Payload integrity | Pass | 43 byte-size and SHA-256 matches |
| Time ordering | Pass | 0 duplicate times, 0 order violations, 0 invalid coverages |
| Same-pipeline overlap | Pass | 0 overlaps; parallel TESS pipeline products intentionally remain separate |
| Flux missingness | Pass | 760,948 finite of 794,130 source rows; 33,182 nonfinite rows recorded for later masking |
| Uncertainties | Pass | 0 negative values; five QLP products explicitly report no uncertainty column |
| Mission/cadence/units | Pass | Kepler short, TESS two-minute target, and TESS FFI pairs validated; all 43 unit records present |
| Spectral windows | Pass | 64 cadence-gap events recorded across the 43 products |
| References | Pass | 42 Rudy modes, 38 Rudy ratios, and 264 authoritative stellar/global rows |
| Split leakage | Pass | 66 unique stars; 0 stars in multiple roles |
| Checksum-change baseline | Pass | First accepted snapshot; 0 detected changes |

The five uncertainty-limited files are QLP sectors 74, 75, 80, 81, and 82. Missing uncertainties
are not converted to zero; these optional transfer products require a registered exclusion or
imputation model if a later method needs per-cadence errors.

The LEGACY archive inventory contains 2,159 short-cadence candidates across all 66 stars. Those
rows are not payload-QC promoted: metadata is sealed, while payload checksums remain intentionally
blank until acquisition. This is a status boundary, not a failed check.

## Exclusions

No exclusion-worthy defect was found, so `registries/exclusion_ledger.csv` remains header-only.
The QC protocol requires future exclusions to be decided before topology, retain evidence and
partition role, and append rather than erase history.

The authoritative machine-readable result is `qc_report.json`; `validate-stage2` verifies it
offline together with all manifests, references, schemas, split assignments, and content seals.
