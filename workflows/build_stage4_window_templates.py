"""Build compact real-mission sampling-window templates from verified Stage 2 FITS payloads.

The output contains observing intervals, not fluxes.  Raw FITS files remain in an external cache.
Each interval retains the Stage 2 product key and payload checksum, making the template rebuildable
without redistributing mission data.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.portability import write_csv_lf
from topoastero.provenance import sha256_file

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "data/derived/stage4/mission_window_templates.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _intervals(time: np.ndarray[Any, Any], cadence_days: float) -> list[tuple[int, int]]:
    if time.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(time) > 1.5 * cadence_days)
    starts = np.r_[0, breaks + 1]
    stops = np.r_[breaks, time.size - 1]
    return list(zip(starts.tolist(), stops.tolist(), strict=True))


def _products() -> list[tuple[str, int, Path]]:
    return [
        ("kepler_q5", 5, ROOT / "data/manifests/stage2/rudy_kepler_products.csv"),
        ("tess_s14", 14, ROOT / "data/manifests/stage2/rudy_tess_products.csv"),
    ]


def build(cache_dir: Path) -> None:
    from astropy.io import fits

    rows: list[dict[str, Any]] = []
    template_origins: dict[str, float] = {}
    interval_id = 0
    for template_id, segment_number, manifest_path in _products():
        products = [
            row
            for row in _read_csv(manifest_path)
            if int(row["segment_number"]) == segment_number
            and (template_id.startswith("kepler") or row["author"] == "SPOC")
        ]
        for product in products:
            path = cache_dir / product["mission"].lower() / product["product_filename"]
            if not path.is_file():
                raise FileNotFoundError(path)
            if sha256_file(path) != product["sha256"]:
                raise ValueError(f"checksum mismatch: {path}")
            with fits.open(path, memmap=False) as hdul:
                table = hdul[1].data
                time = np.asarray(table[product["time_column"]], dtype=float)
                flux = np.asarray(table[product["flux_column"]], dtype=float)
            finite = np.isfinite(time) & np.isfinite(flux)
            time = np.sort(time[finite])
            if time.size < 2:
                raise ValueError(f"no usable cadences: {path}")
            origin = template_origins.setdefault(template_id, float(time[0]))
            cadence_days = float(product["cadence_seconds"]) / 86400.0
            for start_index, stop_index in _intervals(time, cadence_days):
                interval_id += 1
                rows.append(
                    {
                        "interval_id": f"WIN-{interval_id:05d}",
                        "template_id": template_id,
                        "mission": product["mission"],
                        "segment": f"{product['segment']}_{product['segment_number']}",
                        "product_key": product["product_key"],
                        "source_sha256": product["sha256"],
                        "start_day": f"{time[start_index] - origin:.12g}",
                        "stop_day": f"{time[stop_index] - origin:.12g}",
                        "cadence_seconds": product["cadence_seconds"],
                        "cadence_count": stop_index - start_index + 1,
                        "selection": "finite_PDCSAP_FLUX;quality_screen_deferred_to_pipeline",
                    }
                )
    write_csv_lf(
        OUTPUT,
        rows,
        fieldnames=[
            "interval_id",
            "template_id",
            "mission",
            "segment",
            "product_key",
            "source_sha256",
            "start_day",
            "stop_day",
            "cadence_seconds",
            "cadence_count",
            "selection",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args()
    build(args.cache_dir)


if __name__ == "__main__":
    main()
