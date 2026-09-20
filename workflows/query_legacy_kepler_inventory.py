"""Freeze an inventory-only MAST index for all 66 Kepler LEGACY stars.

The index proves archive identity and availability without pretending that unacquired candidate
payloads have content checksums.  A candidate becomes an analysis input only after the separate
acquisition workflow records and verifies its SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
QUERY_DATE = "2026-09-20"
PRODUCT_FIELDS = [
    "product_key",
    "stable_star_id",
    "partition_role",
    "mission",
    "quarter",
    "author",
    "cadence_seconds",
    "product_filename",
    "data_uri",
    "size_bytes",
    "mast_obs_id",
    "mast_obsid",
    "mast_parent_obsid",
    "mast_product_objid",
    "metadata_sha256",
    "payload_sha256",
    "query_id",
    "query_target_used",
    "query_date_utc",
    "acquisition_status",
]


def _text(value: Any) -> str:
    if value is None or getattr(value, "mask", False) is True:
        return ""
    return str(value)


def _digest(record: dict[str, str]) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _query(kic: str, role: str) -> list[dict[str, str]]:
    import lightkurve as lk

    query_target = f"KIC {kic}"
    result = lk.search_lightcurve(
        query_target, mission="Kepler", author="Kepler", cadence="short"
    )
    if len(result) == 0:
        # MAST's resolver currently returns no rows for the two 16 Cyg KIC-prefixed names,
        # while an exact numeric target query returns their known products.
        query_target = kic
        result = lk.search_lightcurve(
            query_target, mission="Kepler", author="Kepler", cadence="short"
        )
    rows: list[dict[str, str]] = []
    for source in result.table:
        mission = _text(source["mission"])
        quarter = mission.rsplit(" ", maxsplit=1)[-1]
        filename = _text(source["productFilename"])
        record = {
            "product_key": f"LEGACY-{kic}-{hashlib.sha256(filename.encode()).hexdigest()[:12]}",
            "stable_star_id": f"KIC {kic}",
            "partition_role": role,
            "mission": "Kepler",
            "quarter": quarter,
            "author": _text(source["author"]),
            "cadence_seconds": _text(source["exptime"]),
            "product_filename": filename,
            "data_uri": _text(source["dataURI"]),
            "size_bytes": _text(source["size"]),
            "mast_obs_id": _text(source["obs_id"]),
            "mast_obsid": _text(source["obsid"]),
            "mast_parent_obsid": _text(source["parent_obsid"]),
            "mast_product_objid": _text(source["objID"]),
            "payload_sha256": "",
            "query_id": f"MAST-QRY-LEGACY-{kic}-20260920",
            "query_target_used": query_target,
            "query_date_utc": QUERY_DATE,
            "acquisition_status": "candidate_inventory_only_not_an_analysis_input",
        }
        record["metadata_sha256"] = _digest(record)
        rows.append(record)
    return sorted(rows, key=lambda row: (int(row["quarter"]), row["product_filename"]))


def _write(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output-dir", default="data/manifests/stage2")
    args = parser.parse_args()
    with (ROOT / "evidence/benchmarks/legacy_population.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        population = list(csv.DictReader(handle))
    with (ROOT / "registries/population_partitions.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        roles = {row["kic"]: row["role"] for row in csv.DictReader(handle)}
    products_by_kic: dict[str, list[dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_query, row["kic"], roles[row["kic"]]): row["kic"]
            for row in population
        }
        for future in as_completed(futures):
            kic = futures[future]
            products_by_kic[kic] = future.result()
    if set(products_by_kic) != {row["kic"] for row in population}:
        raise RuntimeError("one or more LEGACY queries did not complete")
    products = [
        product
        for row in sorted(population, key=lambda item: int(item["kic"]))
        for product in products_by_kic[row["kic"]]
    ]
    summaries: list[dict[str, str]] = []
    for row in sorted(population, key=lambda item: int(item["kic"])):
        kic = row["kic"]
        star_products = products_by_kic[kic]
        metadata_digest = hashlib.sha256(
            "\n".join(product["metadata_sha256"] for product in star_products).encode()
        ).hexdigest()
        summaries.append(
            {
                "stable_star_id": row["object_id"],
                "kic": kic,
                "partition_role": roles[kic],
                "query_id": f"MAST-QRY-LEGACY-{kic}-20260920",
                "query_expression": (
                    f"search_lightcurve('{star_products[0]['query_target_used']}', "
                    "mission='Kepler', author='Kepler', cadence='short')"
                    if star_products
                    else "no successful exact target query"
                ),
                "query_date_utc": QUERY_DATE,
                "product_count": str(len(star_products)),
                "quarters": ";".join(
                    sorted({product["quarter"] for product in star_products}, key=int)
                ),
                "authors": "Kepler" if star_products else "",
                "cadence_seconds": ";".join(
                    sorted({product["cadence_seconds"] for product in star_products})
                ),
                "metadata_snapshot_sha256": metadata_digest,
                "status": (
                    "candidate_inventory_frozen" if star_products else "no_short_cadence_product_found"
                ),
            }
        )
    output = ROOT / args.output_dir
    _write(output / "legacy_kepler_product_index.csv", PRODUCT_FIELDS, products)
    _write(output / "legacy_kepler_star_inventory.csv", list(summaries[0]), summaries)


if __name__ == "__main__":
    main()
