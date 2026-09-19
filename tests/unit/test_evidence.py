from __future__ import annotations

from pathlib import Path

import pytest

from topoastero.evidence import bibtex_keys, normalized_doi, read_csv_rows, split_source_keys


def test_evidence_readers(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    table.write_text("a,b\n1,2\n", encoding="utf-8")
    assert read_csv_rows(table) == [{"a": "1", "b": "2"}]
    assert split_source_keys("Alpha; Beta;;") == {"Alpha", "Beta"}
    assert normalized_doi("HTTPS://DOI.ORG/10.1/ABC ") == "10.1/abc"
    assert normalized_doi("doi:10.2/X") == "10.2/x"

    bibliography = tmp_path / "sources.bib"
    bibliography.write_text("@article{Alpha,\n title={A}\n}\n@book{Beta,}\n", encoding="utf-8")
    assert bibtex_keys(bibliography) == {"Alpha", "Beta"}


def test_csv_reader_rejects_invalid_headers(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no header"):
        read_csv_rows(empty)

    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("a,a\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        read_csv_rows(duplicate)

    overflow = tmp_path / "overflow.csv"
    overflow.write_text("a\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="beyond"):
        read_csv_rows(overflow)

    short = tmp_path / "short.csv"
    short.write_text("a,b\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="shorter"):
        read_csv_rows(short)
