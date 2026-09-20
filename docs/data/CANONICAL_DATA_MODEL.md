# Canonical data model

**Contract:** TA-CDM-1.0
**Frozen:** 2026-09-20
**Configuration:** `configs/stage2_data.yaml`

Stage 2 separates archive products, canonical observations, spectral products, and published
references. Archive-specific FITS columns may vary; downstream scientific code consumes only the
closed JSON schemas in `schemas/`. Every derived row carries its raw parent IDs, configuration
SHA-256, and TopoAstero version.

## Stable identity

`stable_star_id` is the grouping key. For the Rudy benchmark it is `KIC 10963065`; TIC, HD,
Kepler, Gaia, 2MASS, and TYC values are aliases, never alternate group keys. Coordinates use ICRS.
The resolution record and cross-service match are in
`data/manifests/stage2/rudy_aliases.yaml`.

## Mission-product layer

Each row of a mission manifest identifies one immutable archive payload by a project product key,
MAST observation/product IDs, filename, `mast:` URI, byte size, and SHA-256. It also records mission,
quarter/sector, pipeline author, cadence and effective exposure, flux/error/quality/time columns,
FITS units and time reference, coverage, aperture provenance, crowding and flux-fraction values,
and payload-level QC counts. `not_provided` is a source fact, not an empty value. In particular,
recent QLP products provide no per-cadence flux-uncertainty column.

## Canonical light curves

`schemas/light_curve.schema.json` defines one row per cadence:

| Field | Meaning |
| --- | --- |
| `time_bjd` | absolute BJD on the source TDB time scale; archive `TIME + BJDREF` |
| `flux`, `flux_uncertainty` | same explicit flux unit within a product; uncertainty is finite and nonnegative |
| `quality` | unmodified nonnegative mission bit mask |
| `cadence_seconds`, `cadence_class` | measured cadence and mission-aware class |
| `mission`, `segment_id` | mission and quarter/sector identity |
| `aperture_or_product` | pipeline/aperture provenance, not a display label |
| `mask_reason` | why the cadence is retained or removed; never inferred from a missing row |
| `preprocessing_state` | named state before any subsequent transform |
| `provenance` | raw product IDs, configuration hash, software version, and optional source rows |

Rows are strictly increasing within `(stable_star_id, mission, segment_id)`. Kepler admits `short`
and `long`; TESS admits `target_20s`, `target_2min`, and `ffi`; simulations admit `synthetic`.
Unknown mission/cadence pairs fail validation. NaNs are not canonical numeric values: a transform
must mask them with a recorded reason or omit the row while preserving an exclusion/QC count.

## Canonical spectra

`schemas/spectrum.schema.json` requires frequency in microhertz, a nonnegative power value and
explicit power unit, one of three normalization conventions (`one_sided_psd`, `two_sided_psd`, or
`amplitude_spectrum`), a positive Nyquist frequency, spectral-window identity, named background
components, and complete provenance. A spectrum cannot mix segments, pipeline authors, or cadence
classes without a registered transformation whose configuration hash names that choice.

For a one-sided power spectral density, the intended unit is normally `ppm^2/uHz`; its integral
over positive frequency has variance units. Stage 2 defines the representation but does not freeze
a later-stage estimator or background model.

## Reference tables

- `mode_frequencies.csv`: 42 Rudy `(n,l)` frequencies with asymmetric errors from the checked
  publisher Table 6 source.
- `frequency_ratios.csv`: 38 Rudy `r_02`, `r_01`, and `r_10` values with asymmetric errors from
  publisher Table 7.
- `stellar_references.csv`: 264 authoritative `nu_max`, `Delta nu`, effective-temperature, and
  metallicity values for the 66 LEGACY stars.

Each row preserves source/version, source-row identity, raw source ID, configuration hash, and
software version. Context-only tutorial and unattributed modelling-pipeline values remain in Stage
1 evidence but are not promoted to authoritative Stage 2 references.

## Serialization and examples

The Python dataclasses in `topoastero.data_model` validate the same invariants and round-trip through
plain dictionaries/JSON. `data/canonical/examples/` contains three rows for each canonical type;
the light-curve excerpt is taken from the checksum-verified first Rudy Q2 FITS file. Examples are
contract fixtures, not a substitute for the full external payload.
