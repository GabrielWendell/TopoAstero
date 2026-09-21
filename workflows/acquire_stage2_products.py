"""Download frozen Stage 2 products and verify them against the committed manifest."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from topoastero.acquisition import read_product_manifest, verify_cached_products


def _download(uri: str, destination: Path) -> None:
    endpoint = "https://mast.stsci.edu/api/v0.1/Download/file?uri="
    url = endpoint + urllib.parse.quote(uri, safe="")
    temporary = destination.with_suffix(destination.suffix + ".part")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            temporary.replace(destination)
            return
        except (OSError, urllib.error.URLError):
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(float(attempt))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    cache = Path(args.cache_dir)
    if args.download:
        for manifest in args.manifest:
            for row in read_product_manifest(manifest):
                destination = cache / row["mission"].lower() / row["product_filename"]
                if destination.is_file() and destination.stat().st_size == int(row["size_bytes"]):
                    continue
                _download(row["data_uri"], destination)
    errors = verify_cached_products(args.manifest, cache)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print("Stage 2 cached payload verification: PASS")


if __name__ == "__main__":
    main()
