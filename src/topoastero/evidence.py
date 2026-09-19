"""Small, dependency-free readers for Stage 1 evidence artifacts."""

from __future__ import annotations

import csv
import re
from pathlib import Path


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV as strings and reject duplicate or missing headers."""
    source = Path(path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {source}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"CSV has duplicate headers: {source}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError(f"CSV has fields beyond its header: {source}")
    if any(value is None for row in rows for value in row.values()):
        raise ValueError(f"CSV has rows shorter than its header: {source}")
    return rows


def split_source_keys(value: str) -> set[str]:
    """Parse the semicolon-delimited source-key convention."""
    return {item.strip() for item in value.split(";") if item.strip()}


def bibtex_keys(path: str | Path) -> set[str]:
    """Return entry keys from the deliberately simple checked-in BibTeX library."""
    text = Path(path).read_text(encoding="utf-8")
    return set(re.findall(r"@\w+\{([^,\s]+),", text))


def normalized_doi(value: str) -> str:
    """Normalize a DOI for duplicate detection."""
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix) :]
    return doi
