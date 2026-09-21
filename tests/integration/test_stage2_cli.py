from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from topoastero.cli import main

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_stage2_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    main(["validate-stage2", "--root", str(ROOT), "--without-prior-stages"])
    assert "Stage 2 data, provenance, and canonical-model contract: PASS" in capsys.readouterr().out


@pytest.mark.integration
def test_stage2_cli_reports_missing_contract(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="1"):
        main(["validate-stage2", "--root", str(tmp_path), "--without-prior-stages"])
    assert "Stage 2 data contract failed" in capsys.readouterr().err


@pytest.mark.integration
def test_cache_cli_passes_and_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    payload = cache / "product.fits"
    payload.write_bytes(b"payload")
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["product_key", "product_filename", "size_bytes", "sha256"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "product_key": "P-1",
                "product_filename": payload.name,
                "size_bytes": payload.stat().st_size,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        )
    arguments = [
        "verify-stage2-cache",
        "--manifest",
        str(manifest),
        "--cache-dir",
        str(cache),
    ]
    main(arguments)
    assert "cached payload verification: PASS" in capsys.readouterr().out
    payload.write_bytes(b"changed")
    with pytest.raises(SystemExit, match="1"):
        main(arguments)
    assert "cached payload verification failed" in capsys.readouterr().err
