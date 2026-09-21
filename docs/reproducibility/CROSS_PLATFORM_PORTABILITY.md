# Cross-platform artifact portability

TopoAstero records exact SHA-256 digests for governed repository artifacts. Therefore, text files
must have the same bytes on Windows, Linux, and macOS. The portability contract has two rules:

1. version-controlled text uses UTF-8 and LF (`\n`) line endings; and
2. repository-relative paths stored in JSON/CSV/YAML use POSIX `/` separators.

`.gitattributes` and `.editorconfig` define the checkout/editor policy. Code that *generates*
artifacts must additionally use `topoastero.portability` so a file is canonical before its digest is
computed. In particular, use `write_csv_lf`, `write_json_lf`, `write_text_lf`, and
`repository_relative_posix` rather than relying on host defaults.

## Validation

Run the portability contract directly:

```bash
uv run topoastero check-portability --root .
```

The CI matrix runs this check before the scientific/governance tests.

## Repairing an existing Windows-authored tree

The repair workflow is intentionally non-scientific: it does not rerun the asteroseismic analysis.
It normalizes tracked text, converts serialized paths, and refreshes only the dependent byte-level
SHA-256/size seals.

```bash
uv run python workflows/repair_portability.py --root .
uv run topoastero check-portability --root .
uv run pytest
```

After inspection, stage the canonical representation with:

```bash
git add --renormalize .
git add .
git diff --cached --check
```

Do not replace exact checksums with floating-point tolerances. Checksummed repository artifacts
should be byte-deterministic; tolerances are reserved for platform-sensitive numerical results.
