# T0.6 - Data-management plan

**DMP version:** 1.0  
**Frozen:** 2026-09-18  
**Data steward:** principal researcher until formally reassigned

## Data tiers

| Tier | Contents | Mutability | Versioned in Git |
| --- | --- | --- | --- |
| Raw | Exact downloaded mission files and external reference tables | Immutable; replace only under a new product ID/hash | Manifests only |
| Derived | Canonical light curves, spectra, simulations, diagrams, model outputs | Regenerated into content-addressed paths | Schemas and compact release tables only |
| Archive | Release manifests, configurations, compact tables, figure inputs, reports, expensive intermediates | Immutable release snapshot | Index/checksums; payload by size/license |

Scratch caches are disposable and cannot be the only copy of a result or manifest.

## Identity, checksums, and provenance

Raw observations are identified by mission, collection, KIC/TIC/Gaia alias, observation/product ID,
cadence, segment, author/pipeline, flux type, data release/version, and retrieval query/time. Each
payload receives a byte-level SHA-256 checksum. Derived products name every parent checksum,
configuration hash, producing experiment, code version, and schema version.

The canonical manifest schema is `schemas/data_manifest.schema.json`. Stage 2 populates exact MAST
IDs after a new archive query. Proposal-stage quarter/sector lists are marked provisional and cannot
be silently promoted to verified identities.

## Naming

Payload names are descriptive conveniences, not identities:

```text
{dataset_id}__{mission}__{target_id}__{segment}__{product_id}__{sha256_12}.{ext}
```

Derived paths additionally include `{experiment_id}__cfg-{config_hash_12}`. Use ASCII filenames,
UTC ISO-8601 timestamps, lower-case extensions, explicit units in schema fields, and no spaces.

## Retention and deletion

- Raw public mission products: retain manifest indefinitely; retain a local payload through the
  active project and at least five years after the related publication when storage permits.
- Published compact tables, manifests, configurations, figure inputs, and reports: retain
  indefinitely in DOI-bearing archives.
- Expensive derived products: retain when regeneration exceeds the registered cost threshold or
  depends on a fragile external version; otherwise retain the command and parents.
- Disposable caches: delete after checksum-verified outputs and backups exist.
- Superseded records: tombstone and link to the replacement; never silently overwrite.

Deletion requires a recorded target, reason, parent/child impact check, and backup confirmation.

## Backup and integrity

Maintain three copies of release-critical artifacts on at least two storage systems, with one
off-site or institutional/DOI copy. Working data have daily or filesystem-managed snapshots where
available; release candidates receive an explicit snapshot. Verify a rotating checksum sample
monthly and the complete release inventory at every gate.

## Access, privacy, and security

Kepler/TESS observations and simulations are non-personal research data. Source access and
redistribution terms still apply. Credentials never enter configs or manifests. Final-holdout
assignments are access-controlled until opening, even though the underlying observations are
public, because the protection is inferential rather than privacy-based.

## Licensing and citation

- TopoAstero code: BSD-3-Clause.
- Project-authored documentation and publishable tables: intended CC BY 4.0 at release.
- MAST, catalog, and literature-derived materials: retain provider terms and required citations;
  never relicense source payloads.
- MESA: LGPL-3.0; use an official release rather than an unpinned development branch.
- GYRE: GPL-3.0; record exact release and citations if used.

`license_or_terms` and `citation` are required manifest fields. Mixed-license bundles include a
machine-readable rights table.

## DOI targets

1. Zenodo software DOI for the first public tagged package release and later versions.
2. Zenodo or institutional dataset DOI for manifests, compact derived tables, figure inputs, and
   reproduction reports.
3. Optional OSF registration or equivalent timestamped protocol record before final holdout.

No DOI is invented at Stage 0. Planned records use `doi: null` and `status: target` until deposited.

## FAIR and release requirements

Released tables include field definitions, units, null/missing conventions, uncertainty semantics,
quality flags, sample counts, exclusions, software/configuration versions, and provenance links.
Machine-readable data accompany human-readable interpretation. A release fails if a headline figure
cannot be regenerated from archived tables.

