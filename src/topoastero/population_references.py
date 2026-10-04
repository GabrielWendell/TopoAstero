"""Import the corrected LEGACY edition without altering Stage 2/Paper I references."""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.population_store import read_table, seal, write_json, write_table
from topoastero.provenance import sha256_file

EDITION = "Lund2017-erratum-ApJ850-110-CDS"


def import_references(root: Path, cache: Path, *, download: bool = False) -> dict[str, Any]:
    """Parse fixed-width CDS mode/ratio tables, preserving asymmetric errors and edition.

    Table 1 is also available as a pipe-separated ASCII representation. Sun rows
    are excluded by membership in the frozen 66-star cohort, never by inference.
    """
    names = ("ReadMe", "table1.dat", "table6.dat", "table7.dat")
    cache.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = cache / name
        if download and not path.exists():
            with urllib.request.urlopen("https://cdsarc.cds.unistra.fr/ftp/J/ApJ/835/172/" + name, timeout=60) as response:
                path.write_bytes(response.read())
        if not path.is_file():
            raise FileNotFoundError(f"missing corrected CDS reference: {path}")
    readme = (cache / "ReadMe").read_text(encoding="utf-8")
    if "850, 110" not in readme or "erratum" not in readme:
        raise ValueError("reference edition does not attest to the 2017 erratum")
    members = {row["stable_star_id"] for row in read_table(root / "registries/population_partitions.csv")}
    modes: list[dict[str, Any]] = []
    ratios: list[dict[str, Any]] = []
    covariates: list[dict[str, Any]] = []
    for number, line in enumerate((cache / "table6.dat").read_text().splitlines(), 1):
        star = "KIC " + line[:8].strip()
        if star not in members:
            continue
        modes.append({"stable_star_id": star, "radial_order_n": int(line[9:11]),
                      "angular_degree_l": int(line[12:13]), "frequency_uHz": float(line[14:24]),
                      "uncertainty_minus_uHz": float(line[25:32]), "uncertainty_plus_uHz": float(line[33:40]),
                      "linewidth_uHz": float(line[65:73]) if line[65:73].strip() else None,
                      "source_edition": EDITION, "source_row": number,
                      "source_sha256": sha256_file(cache / "table6.dat")})
    for number, line in enumerate((cache / "table7.dat").read_text().splitlines(), 1):
        fields = line.split()
        if len(fields) != 6 or "KIC " + fields[0] not in members:
            continue
        ratios.append({"stable_star_id": "KIC " + fields[0], "ratio_type": fields[1].strip("_").replace("_", ""),
                       "radial_order_n": int(fields[2]), "value": float(fields[3]),
                       "uncertainty_minus": float(fields[4]), "uncertainty_plus": float(fields[5]),
                       "source_edition": EDITION, "source_row": number,
                       "source_sha256": sha256_file(cache / "table7.dat")})
    for number, line in enumerate((cache / "table1.dat").read_text().splitlines(), 1):
        fields = [s.strip() for s in line.split("|")]
        star = "KIC " + (fields[0] if len(fields) > 1 else line[:8].strip())
        if star not in members:
            continue
        radial_widths = [m["linewidth_uHz"] for m in modes if m["stable_star_id"] == star and m["angular_degree_l"] == 0 and m["linewidth_uHz"] is not None]
        covariates.append({"stable_star_id": star, "kp_mag": float(fields[2] if len(fields) > 1 else line[19:24]),
                           "mode_category": fields[6] if len(fields) > 1 else line[39:45].strip(),
                           "linewidth_uHz": float(np.median(radial_widths)) if radial_widths else None,
                           "linewidth_definition": "median_of_published_radial_mode_widths",
                           "evolutionary_state": "not_individually_classified",
                           "source_edition": EDITION, "source_row": number})
    if {m["stable_star_id"] for m in modes} != members or {r["stable_star_id"] for r in ratios} != members or {c["stable_star_id"] for c in covariates} != members:
        raise ValueError("corrected reference tables do not cover exactly the frozen cohort")
    unique: dict[tuple[str, int, int], dict[str, Any]] = {}
    duplicates = []
    for mode in modes:
        key = (mode["stable_star_id"], mode["radial_order_n"], mode["angular_degree_l"])
        if key in unique:
            prior = unique[key]
            if any(prior[k] != v for k, v in mode.items() if k != "source_row"):
                raise ValueError(f"conflicting duplicate mode: {key}")
            duplicates.append({"stable_star_id": key[0], "n": key[1], "l": key[2],
                               "retained_source_row": prior["source_row"], "duplicate_source_row": mode["source_row"],
                               "resolution": "identical_numeric_payload_retained_once"})
        else:
            unique[key] = mode
    modes = list(unique.values())
    if any(min(m["uncertainty_minus_uHz"], m["uncertainty_plus_uHz"]) < 0 for m in modes) or any(min(r["uncertainty_minus"], r["uncertainty_plus"]) < 0 for r in ratios):
        raise ValueError("negative published uncertainty")
    output = root / "data/reference/stage11"
    write_table(output / "mode_frequencies.csv", modes)
    write_table(output / "frequency_ratios.csv", ratios)
    write_table(output / "covariates.csv", covariates)
    write_table(output / "duplicate_reference_rows.csv", duplicates)
    manifest = {"schema_version": 1, "edition": EDITION, "erratum_doi": "10.3847/1538-4357/aa9658",
                "mode_rows": len(modes), "ratio_rows": len(ratios), "stars": len(members),
                "identical_duplicate_mode_rows": len(duplicates),
                "covariance_available": False,
                "uncertainty_semantics": "published_asymmetric_intervals; no Gaussian conversion; no joint covariance inferred",
                "sources": [{"name": n, "url": "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/835/172/" + n,
                             "sha256": sha256_file(cache / n)} for n in names],
                "files": [seal(root, output / n) for n in ("mode_frequencies.csv", "frequency_ratios.csv", "covariates.csv", "duplicate_reference_rows.csv")]}
    write_json(output / "reference_manifest.json", manifest)
    return manifest
