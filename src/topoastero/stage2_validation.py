"""Offline validation of the complete Stage 2 data/provenance contract."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from topoastero.config import configuration_hash, load_yaml
from topoastero.data_model import (
    SHA256_PATTERN,
    duplicate_values,
    validate_mission_product,
    validate_population_partitions,
)
from topoastero.provenance import sha256_file
from topoastero.stage1_validation import validate_stage1

REQUIRED_SCHEMAS = {
    "derived_provenance.schema.json",
    "identifier_record.schema.json",
    "mission_product_manifest.schema.json",
    "light_curve.schema.json",
    "spectrum.schema.json",
    "mode_frequency.schema.json",
    "stellar_reference.schema.json",
    "population_split.schema.json",
}
REQUIRED_FILES = [
    "configs/stage2_data.yaml",
    "data/manifests/stage2/rudy_aliases.yaml",
    "data/manifests/stage2/rudy_kepler_products.csv",
    "data/manifests/stage2/rudy_tess_products.csv",
    "data/manifests/stage2/mast_query_snapshot.json",
    "data/manifests/stage2/legacy_kepler_product_index.csv",
    "data/manifests/stage2/legacy_kepler_star_inventory.csv",
    "data/manifests/stage2/reference_manifest.csv",
    "data/manifests/stage2/reference_sources.csv",
    "data/reference/mode_frequencies.csv",
    "data/reference/frequency_ratios.csv",
    "data/reference/stellar_references.csv",
    "data/canonical/examples/light_curve.jsonl",
    "data/canonical/examples/spectrum.jsonl",
    "data/canonical/examples/mode_frequency.jsonl",
    "data/canonical/examples/stellar_reference.jsonl",
    "registries/population_partitions.csv",
    "registries/split_attestation.json",
    "registries/split_policy.yaml",
    "registries/exclusion_ledger.csv",
    "docs/data/CANONICAL_DATA_MODEL.md",
    "docs/data/DATA_ACQUISITION_AND_PROVENANCE.md",
    "docs/protocols/STAGE2_QC_AND_EXCLUSION_PROTOCOL.md",
    "reports/stage2/qc_report.json",
    "reports/stage2/QC_REPORT.md",
    "reports/stage2/partition_balance.json",
    "reports/stage2/G2_ACCEPTANCE.json",
    "reports/stage2/STAGE2_REPORT.md",
    "reports/stage2/TRACEABILITY_MATRIX.md",
    "reports/stage2/deliverable_manifest.csv",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _canonical_metadata_hash(row: dict[str, str]) -> str:
    record = {key: value for key, value in row.items() if key != "metadata_sha256"}
    payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def validate_schemas(root: Path, errors: list[str]) -> None:
    for name in sorted(REQUIRED_SCHEMAS):
        path = root / "schemas" / name
        if not path.is_file():
            errors.append(f"required Stage 2 schema missing: {name}")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON schema {name}: {exc}")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{name} must declare JSON Schema draft 2020-12")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            errors.append(f"{name} must be a closed object schema")


def validate_identity(root: Path, errors: list[str]) -> None:
    record = load_yaml(root / "data/manifests/stage2/rudy_aliases.yaml")
    expected = {
        "kic": "10963065",
        "tic": "48450369",
        "gaia_dr3": "2131593785132997632",
        "hd": "176693",
    }
    if record.get("stable_star_id") != "KIC 10963065":
        errors.append("Rudy alias record must use KIC 10963065 as the stable star ID")
    if record.get("identifiers") != expected:
        errors.append("Rudy KIC/TIC/Gaia/HD identifiers differ from the resolved record")
    aliases = set(record.get("aliases", []))
    required = {"KIC 10963065", "HD 176693", "Kepler-408", "TIC 48450369"}
    if not required <= aliases:
        errors.append("Rudy alias record is missing a required name")
    coordinates = record.get("coordinates", {})
    try:
        ra, dec = float(coordinates["ra_deg"]), float(coordinates["dec_deg"])
    except (KeyError, TypeError, ValueError):
        errors.append("Rudy alias record has malformed coordinates")
    else:
        if abs(ra - 284.78618530976996) > 1e-10 or abs(dec - 48.42322232216) > 1e-10:
            errors.append("Rudy coordinates differ from the frozen SIMBAD resolution")
    if record.get("resolution", {}).get("status") != "resolved":
        errors.append("Rudy identity resolution is not complete")


def validate_rudy_products(root: Path, errors: list[str]) -> None:
    directory = root / "data/manifests/stage2"
    kepler = _read_csv(directory / "rudy_kepler_products.csv")
    tess = _read_csv(directory / "rudy_tess_products.csv")
    if len(kepler) != 10:
        errors.append(f"Rudy Kepler manifest must contain 10 products; found {len(kepler)}")
    if len(tess) != 33:
        errors.append(f"Rudy TESS manifest must contain 33 products; found {len(tess)}")
    all_rows = [*kepler, *tess]
    duplicates = duplicate_values(all_rows, "product_key")
    if duplicates:
        errors.append(f"mission manifests contain duplicate product keys: {sorted(duplicates)}")
    filenames = duplicate_values(all_rows, "product_filename")
    if filenames:
        errors.append(f"mission manifests contain duplicate filenames: {sorted(filenames)}")
    for row in all_rows:
        errors.extend(validate_mission_product(row))
    if {int(row["segment_number"]) for row in kepler} != {2, 5, 6, 7}:
        errors.append("Rudy Kepler manifest must cover tutorial quarters 2, 5, 6, and 7")
    if {row["author"] for row in kepler} != {"Kepler"}:
        errors.append("Rudy Kepler products must have author Kepler")
    expected_sectors = {14, 15, 40, 41, 53, 55, 74, 75, 80, 81, 82}
    if {int(row["segment_number"]) for row in tess} != expected_sectors:
        errors.append("Rudy TESS manifest sector coverage differs from the frozen query")
    author_counts = Counter(row["author"] for row in tess)
    if author_counts != {"SPOC": 11, "TESS-SPOC": 11, "QLP": 11}:
        errors.append(f"Rudy TESS author counts differ: {dict(author_counts)}")
    if any(row["time_system"] != "TDB" or row["time_unit"] != "d" for row in all_rows):
        errors.append("all Rudy mission products must record TDB day-valued time axes")
    snapshot = json.loads((directory / "mast_query_snapshot.json").read_text(encoding="utf-8"))
    queries = {item["query_id"]: item for item in snapshot.get("queries", [])}
    if queries.get("MAST-QRY-RUDY-KEPLER-20260920", {}).get("returned_products") != 10:
        errors.append("Kepler query snapshot does not agree with its manifest")
    if queries.get("MAST-QRY-RUDY-TESS-20260920", {}).get("selected_products") != 33:
        errors.append("TESS query snapshot does not agree with its manifest")


def validate_legacy_inventory(root: Path, errors: list[str]) -> None:
    directory = root / "data/manifests/stage2"
    stars = _read_csv(directory / "legacy_kepler_star_inventory.csv")
    products = _read_csv(directory / "legacy_kepler_product_index.csv")
    if len(stars) != 66 or len({row["stable_star_id"] for row in stars}) != 66:
        errors.append("LEGACY Kepler star inventory must contain 66 unique stars")
    if any(row["status"] != "candidate_inventory_frozen" for row in stars):
        errors.append("every LEGACY star must have at least one frozen short-cadence candidate")
    if {row["stable_star_id"] for row in products} != {row["stable_star_id"] for row in stars}:
        errors.append("LEGACY product index and star inventory cover different stars")
    duplicates = duplicate_values(products, "product_key")
    if duplicates:
        errors.append(f"LEGACY product index has duplicate keys: {sorted(duplicates)[:3]}")
    for row in products:
        if row["metadata_sha256"] != _canonical_metadata_hash(row):
            errors.append(f"LEGACY metadata checksum mismatch: {row['product_key']}")
        if row["payload_sha256"]:
            errors.append(f"inventory-only candidate falsely has a payload hash: {row['product_key']}")
        if row["acquisition_status"] != "candidate_inventory_only_not_an_analysis_input":
            errors.append(f"LEGACY candidate has a wrong acquisition state: {row['product_key']}")
    counts = Counter(row["stable_star_id"] for row in products)
    for row in stars:
        if counts[row["stable_star_id"]] != int(row["product_count"]):
            errors.append(f"LEGACY product count mismatch for {row['stable_star_id']}")


def validate_references(root: Path, errors: list[str]) -> None:
    directory = root / "data/reference"
    expected_counts = {
        "mode_frequencies.csv": 42,
        "frequency_ratios.csv": 38,
        "stellar_references.csv": 264,
    }
    config_hash = configuration_hash(root / "configs/stage2_data.yaml")
    for name, count in expected_counts.items():
        rows = _read_csv(directory / name)
        if len(rows) != count:
            errors.append(f"{name} must contain {count} rows; found {len(rows)}")
        duplicates = duplicate_values(rows, "row_id")
        if duplicates:
            errors.append(f"{name} has duplicate row IDs")
        for row in rows:
            if row.get("config_sha256") != config_hash:
                errors.append(f"{name} row {row.get('row_id')} has the wrong config hash")
            if not row.get("raw_product_ids") or not row.get("source_row_ids"):
                errors.append(f"{name} row {row.get('row_id')} lacks source provenance")
            if row.get("software_version") != "TopoAstero-0.3.0":
                errors.append(f"{name} row {row.get('row_id')} has the wrong software version")
    manifest = _read_csv(root / "data/manifests/stage2/reference_manifest.csv")
    if len(manifest) != 3:
        errors.append("reference manifest must contain the three canonical reference tables")
    for row in manifest:
        path = root / row["path"]
        if not path.is_file() or row["sha256"] != sha256_file(path):
            errors.append(f"reference manifest checksum mismatch: {row['path']}")
    sources = _read_csv(root / "data/manifests/stage2/reference_sources.csv")
    if len(sources) != 3 or any(SHA256_PATTERN.fullmatch(row["sha256"]) is None for row in sources):
        errors.append("reference source ledger is incomplete or has an invalid checksum")


def validate_partitions(root: Path, errors: list[str]) -> None:
    path = root / "registries/population_partitions.csv"
    rows = _read_csv(path)
    if len(rows) != 66 or len({row["stable_star_id"] for row in rows}) != 66:
        errors.append("population partition must contain 66 unique star groups")
    errors.extend(validate_population_partitions(rows))
    counts = Counter(row["role"] for row in rows)
    expected = {
        "development": 39,
        "internal_validation": 13,
        "final_holdout": 13,
        "descriptive_benchmark": 1,
    }
    if counts != expected:
        errors.append(f"population partition counts differ: {dict(counts)}")
    if any(row["group_key"] != "stable_star_id" for row in rows):
        errors.append("population split is not grouped by stable_star_id")
    attestation = json.loads((root / "registries/split_attestation.json").read_text())
    if attestation.get("sha256") != sha256_file(path):
        errors.append("population split content seal does not match")
    source = root / str(attestation.get("source", ""))
    if not source.is_file() or attestation.get("source_sha256") != sha256_file(source):
        errors.append("population split source seal does not match")
    policy = load_yaml(root / "registries/split_policy.yaml")
    if policy.get("assignment_status") != "frozen_T2.8":
        errors.append("split policy does not declare the T2.8 assignment frozen")
    if policy.get("actual_assignments") != "registries/population_partitions.csv":
        errors.append("split policy does not point to the frozen assignment file")
    if _read_csv(root / "registries/holdout_access_log.csv"):
        errors.append("holdout access log must remain empty at G2")


def validate_examples(root: Path, errors: list[str]) -> None:
    expected = {
        "light_curve.jsonl": {"time_bjd", "flux", "flux_uncertainty", "provenance"},
        "spectrum.jsonl": {"frequency_uHz", "power", "normalization", "provenance"},
        "mode_frequency.jsonl": {"frequency_uHz", "radial_order_n", "provenance"},
        "stellar_reference.jsonl": {"quantity", "value", "unit", "provenance"},
    }
    for name, required in expected.items():
        path = root / "data/canonical/examples" / name
        records: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"{name} line {number} is invalid JSON: {exc}")
        if not records:
            errors.append(f"{name} must contain at least one canonical example")
            continue
        for record in records:
            if not required <= set(record):
                errors.append(f"{name} example lacks required canonical fields")
            provenance = record.get("provenance", {})
            if not provenance.get("raw_product_ids"):
                errors.append(f"{name} example lacks raw product IDs")
            if SHA256_PATTERN.fullmatch(str(provenance.get("config_sha256", ""))) is None:
                errors.append(f"{name} example has an invalid config hash")
            if not provenance.get("software_version"):
                errors.append(f"{name} example lacks a software version")


def validate_qc_and_gate(root: Path, errors: list[str]) -> None:
    qc = json.loads((root / "reports/stage2/qc_report.json").read_text(encoding="utf-8"))
    if qc.get("overall_status") != "pass":
        errors.append("Stage 2 QC report must pass")
    checks = qc.get("checks", [])
    if not isinstance(checks, list) or len(checks) < 8:
        errors.append("Stage 2 QC report does not cover the required integrity checks")
    elif any(check.get("status") != "pass" for check in checks):
        errors.append("every Stage 2 QC check must pass")
    gate = json.loads((root / "reports/stage2/G2_ACCEPTANCE.json").read_text(encoding="utf-8"))
    if gate.get("gate") != "G2" or gate.get("decision") != "PASS":
        errors.append("G2 acceptance record must declare PASS")
    clauses = gate.get("clauses", [])
    if not isinstance(clauses, list) or len(clauses) < 4:
        errors.append("G2 acceptance record lacks the agenda clauses")
    elif any(clause.get("status") != "pass" for clause in clauses):
        errors.append("every G2 acceptance clause must pass")
    manifest = _read_csv(root / "reports/stage2/deliverable_manifest.csv")
    if duplicate_values(manifest, "path"):
        errors.append("Stage 2 deliverable manifest has duplicate paths")
    for row in manifest:
        path = root / row["path"]
        if not path.is_file():
            errors.append(f"Stage 2 manifest path missing: {row['path']}")
        elif row["sha256"] != sha256_file(path):
            errors.append(f"Stage 2 manifest checksum mismatch: {row['path']}")


def validate_stage2(root: str | Path, *, require_prior_stages: bool = True) -> list[str]:
    """Validate tasks T2.1-T2.8, deliverables D2.1-D2.4, and Gate G2."""
    repository = Path(root).resolve()
    errors = [
        f"Required Stage 2 file missing: {relative}"
        for relative in REQUIRED_FILES
        if not (repository / relative).is_file()
    ]
    if errors:
        return errors
    validate_schemas(repository, errors)
    validate_identity(repository, errors)
    validate_rudy_products(repository, errors)
    validate_legacy_inventory(repository, errors)
    validate_references(repository, errors)
    validate_partitions(repository, errors)
    validate_examples(repository, errors)
    validate_qc_and_gate(repository, errors)
    if require_prior_stages:
        errors.extend(
            f"Stage 0/1 regression: {error}"
            for error in validate_stage1(repository, require_stage0=True)
        )
    return errors
