# Data manifests

`planned_datasets.yaml` is the complete Stage 0 inventory. It identifies inferential roles and the
stage that must resolve exact products. It is not a substitute for the file-level manifests created
in Stage 2.

A verified input record must validate against `schemas/data_manifest.schema.json` and contain an
archive/product identity, retrieval metadata, size, SHA-256, terms/citation, and provenance. A
proposal-stage quarter or sector number alone is not a stable product identity.

