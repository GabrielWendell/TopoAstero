# Data acquisition and provenance

**Snapshot date:** 2026-09-20
**Archive:** Mikulski Archive for Space Telescopes (MAST)
**Query client:** Lightkurve 2.6.0

## Rudy identity and queries

SIMBAD and the MAST TIC catalog resolve KIC 10963065, HD 176693, Kepler-408, TIC 48450369, and
Gaia DR3 2131593785132997632 to the same source. The coordinate difference between the SIMBAD and
TIC records is 0.0023 arcsec. `rudy_aliases.yaml` freezes the returned identifiers, coordinates,
services, and query date.

The exact Kepler tutorial query is:

```python
search_lightcurve(
    "KIC 10963065", cadence="short", author="Kepler", quarter=(2, 5, 6, 7)
)
```

It returns 10 monthly short-cadence FITS products spanning four quarters. The TESS query is
`search_lightcurve("TIC 48450369", mission="TESS")`; the registered selection keeps all products
whose author is SPOC, TESS-SPOC, or QLP. It returns 33 selected products: one from each family in
sectors 14, 15, 40, 41, 53, 55, 74, 75, 80, 81, and 82. The three families remain separate because
their apertures and cadences differ.

`workflows/query_stage2_mast.py` reproduces the query, downloads into a caller-supplied cache,
checks advertised byte size, computes payload SHA-256, and extracts FITS header/column/QC metadata.
The repository contains the dated manifests and query snapshot, not the 43 source FITS payloads.
Run the frozen acquisition without changing the manifest:

```bash
uv run python workflows/acquire_stage2_products.py \
  --manifest data/manifests/stage2/rudy_kepler_products.csv \
  --manifest data/manifests/stage2/rudy_tess_products.csv \
  --cache-dir /path/to/cache --download

uv run topoastero verify-stage2-cache \
  --manifest data/manifests/stage2/rudy_kepler_products.csv \
  --manifest data/manifests/stage2/rudy_tess_products.csv \
  --cache-dir /path/to/cache
```

A changed archive payload, partial transfer, or wrong file fails on size or SHA-256. Refreshing an
archive query requires a new query ID, date, manifest version, and change-log decision; it never
silently rewrites the accepted snapshot.

## LEGACY population inventory

`query_legacy_kepler_inventory.py` records every Kepler-author short-cadence archive candidate for
all 66 reference stars. The exact target resolver is normally `KIC N`; the two 16 Cyg identifiers
use the exact numeric target after the prefixed resolver returns zero rows, and that fallback is
explicit in `query_target_used`.

These rows are an availability inventory, not approved inputs. Their `metadata_sha256` seals exact
IDs, URI, size, query, and status; `payload_sha256` is deliberately blank. The status
`candidate_inventory_only_not_an_analysis_input` is enforced offline. Before use, a candidate must
be downloaded and promoted to a payload-verified manifest row. This boundary makes it impossible to
confuse a metadata checksum with evidence about file bytes.

## Publisher reference data

The canonical reference tables are generated from checksum-verified Stage 1 tables and Lund et al.
Table 7. Raw publisher tables are not redistributed. `reference_sources.csv` records retrieval
URLs/dates/checksums; `reference_manifest.csv` seals the three canonical outputs. Rebuild with:

```bash
uv run python workflows/build_stage2_reference_data.py \
  --table7 /path/to/checksum-verified/apjaa5593t7_mrt.txt
```

All derived rows name raw source IDs, source-row IDs, the canonical Stage 2 configuration hash, and
TopoAstero 0.3.0. Mission payloads and source tables retain their providers' terms and citations.
