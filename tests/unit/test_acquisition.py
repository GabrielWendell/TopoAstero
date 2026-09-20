from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from topoastero.acquisition import index_cache, read_product_manifest, verify_cached_products


def write_manifest(path: Path, payload: Path, *, digest: str | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
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
                "sha256": digest or hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        )


def test_cached_product_verification(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    payload = cache / "payload.fits"
    payload.write_bytes(b"verified bytes")
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, payload)
    assert read_product_manifest(manifest)[0]["product_key"] == "P-1"
    files, duplicates = index_cache(cache)
    assert files[payload.name] == payload
    assert duplicates == set()
    assert verify_cached_products([manifest], cache) == []


def test_cached_product_failures(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    payload = cache / "payload.fits"
    payload.write_bytes(b"payload")
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, payload, digest="0" * 64)
    assert "SHA-256 mismatch" in verify_cached_products([manifest], cache)[0]
    payload.write_bytes(b"changed size")
    assert "size mismatch" in verify_cached_products([manifest], cache)[0]
    payload.unlink()
    assert "payload missing" in verify_cached_products([manifest], cache)[0]
    assert index_cache(tmp_path / "absent") == ({}, set())


def test_duplicate_basenames_and_invalid_size(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    first = cache / "a" / "same.fits"
    second = cache / "b" / "same.fits"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"a")
    second.write_bytes(b"a")
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, first)
    assert "duplicate basename" in verify_cached_products([manifest], cache)[0]
    second.unlink()
    rows = read_product_manifest(manifest)
    rows[0]["size_bytes"] = "bad"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert "invalid size_bytes" in verify_cached_products([manifest], cache)[0]
