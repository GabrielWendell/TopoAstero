"""Acquire and verify the exact external-cache inputs used by the Stage 3 workflow.

Raw MAST FITS payloads remain outside the repository.  This command selects every frozen Rudy
Kepler tutorial product and only the homogeneous two-minute SPOC TESS family used for T3.9.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ENDPOINT = "https://mast.stsci.edu/api/v0.1/Download/file?uri="


def _rows(manifest_dir: Path) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for name in ("rudy_kepler_products.csv", "rudy_tess_products.csv"):
        with (manifest_dir / name).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        selected.extend(
            row
            for row in rows
            if row["mission"] == "Kepler"
            or (row["mission"] == "TESS" and row["author"] == "SPOC")
        )
    return selected


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(row: dict[str, str], destination: Path) -> None:
    if not destination.is_file():
        raise FileNotFoundError(destination)
    if destination.stat().st_size != int(row["size_bytes"]):
        raise OSError(f"size mismatch: {destination}")
    if _sha256(destination) != row["sha256"]:
        raise OSError(f"SHA-256 mismatch: {destination}")


def _download(row: dict[str, str], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == int(row["size_bytes"]):
        _verify(row, destination)
        return f"verified {destination.name}"
    temporary = destination.with_suffix(destination.suffix + ".part")
    url = ENDPOINT + urllib.parse.quote(row["data_uri"], safe="")
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=240) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            temporary.replace(destination)
            _verify(row, destination)
            return f"downloaded {destination.name}"
        except (OSError, urllib.error.URLError):
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable")


def acquire(
    manifest_dir: Path, cache_dir: Path, *, download: bool, workers: int = 4
) -> list[dict[str, str]]:
    """Acquire (optionally) and checksum-verify the frozen Stage 3 subset."""

    rows = _rows(manifest_dir)
    if len(rows) != 21:
        raise ValueError(f"expected 10 Kepler plus 11 SPOC TESS products; found {len(rows)}")
    destinations = [cache_dir / row["mission"].lower() / row["product_filename"] for row in rows]
    if download:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_download, row, path)
                for row, path in zip(rows, destinations, strict=True)
            ]
            for future in as_completed(futures):
                print(future.result())
    else:
        for row, destination in zip(rows, destinations, strict=True):
            _verify(row, destination)
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-dir", default="data/manifests/stage2")
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    rows = acquire(
        Path(args.manifest_dir),
        Path(args.cache_dir),
        download=args.download,
        workers=args.workers,
    )
    print(f"Stage 3 input verification: PASS ({len(rows)} payloads)")


if __name__ == "__main__":
    main()
