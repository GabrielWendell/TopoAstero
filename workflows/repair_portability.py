"""Repair cross-platform text serialization, path syntax, and dependent SHA-256 seals.

This workflow is intentionally *non-scientific*: it does not recompute any asteroseismic result.
It canonicalizes repository text to LF, converts serialized repository paths to POSIX syntax, and
refreshes only checksum/size fields whose byte identity necessarily changes as a consequence.

Usage
-----
Apply the repair in place::

    uv run python workflows/repair_portability.py --root .

Verify that no portability defects remain without modifying files::

    uv run python workflows/repair_portability.py --root . --check
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from topoastero.portability import (
    normalize_tracked_text_files,
    repository_portability_issues,
    serialized_posix_path,
    write_csv_lf,
    write_json_lf,
)
from topoastero.provenance import sha256_file


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _refresh_checksum_manifest(path: Path, root: Path) -> int:
    """Refresh a CSV manifest with path/size_bytes/sha256 columns."""

    if not path.is_file():
        return 0
    rows = _read_csv(path)
    if not rows:
        return 0
    fieldnames = list(rows[0])
    required = {"path", "size_bytes", "sha256"}
    if not required <= set(fieldnames):
        raise ValueError(f"not a checksum manifest: {path}")
    changed = 0
    for row in rows:
        portable = serialized_posix_path(row["path"])
        target = root / portable
        if not target.is_file():
            raise FileNotFoundError(target)
        updates = {
            "path": portable,
            "size_bytes": str(target.stat().st_size),
            "sha256": sha256_file(target),
        }
        for key, value in updates.items():
            if row.get(key) != value:
                row[key] = value
                changed += 1
    write_csv_lf(path, rows, fieldnames=fieldnames)
    return changed


def _repair_reference_sources(root: Path) -> int:
    path = root / "data/manifests/stage2/reference_sources.csv"
    if not path.is_file():
        return 0
    rows = _read_csv(path)
    if not rows:
        return 0
    changed = 0
    for row in rows:
        value = serialized_posix_path(row.get("url", ""))
        candidate = root / value
        if candidate.is_file():
            digest = sha256_file(candidate)
            if row.get("url") != value:
                row["url"] = value
                changed += 1
            if row.get("sha256") != digest:
                row["sha256"] = digest
                changed += 1
    write_csv_lf(path, rows, fieldnames=list(rows[0]))
    return changed


def _repair_split_attestation(root: Path) -> int:
    path = root / "registries/split_attestation.json"
    if not path.is_file():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for key in ("file", "source"):
        value = serialized_posix_path(str(payload.get(key, "")))
        if payload.get(key) != value:
            payload[key] = value
            changed += 1
    split_file = root / str(payload["file"])
    source_file = root / str(payload["source"])
    if not split_file.is_file() or not source_file.is_file():
        raise FileNotFoundError("split attestation points to a missing repository file")
    updates = {
        "sha256": sha256_file(split_file),
        "source_sha256": sha256_file(source_file),
    }
    for key, value in updates.items():
        if payload.get(key) != value:
            payload[key] = value
            changed += 1
    write_json_lf(path, payload)
    return changed


def _repair_smoke_manifest(root: Path) -> int:
    path = root / "results/smoke/run_manifest.json"
    if not path.is_file():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    configuration = payload.get("configuration")
    if isinstance(configuration, dict):
        value = serialized_posix_path(str(configuration.get("path", "")))
        if configuration.get("path") != value:
            configuration["path"] = value
            changed += 1
    outputs = payload.get("outputs")
    if isinstance(outputs, dict):
        for name, record in outputs.items():
            if not isinstance(record, dict):
                continue
            output_path = path.parent / name
            if not output_path.is_file():
                raise FileNotFoundError(output_path)
            digest = sha256_file(output_path)
            if record.get("sha256") != digest:
                record["sha256"] = digest
                changed += 1
    write_json_lf(path, payload)
    return changed


def _repair_stage3_manifest(root: Path) -> int:
    path = root / "results/stage3/run_manifest.json"
    if not path.is_file():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    config_path = serialized_posix_path(str(payload.get("config_path", "")))
    if payload.get("config_path") != config_path:
        payload["config_path"] = config_path
        changed += 1
    outputs = payload.get("outputs")
    if isinstance(outputs, list):
        for record in outputs:
            if not isinstance(record, dict):
                continue
            portable = serialized_posix_path(str(record.get("path", "")))
            target = root / portable
            if not target.is_file():
                raise FileNotFoundError(target)
            updates: dict[str, Any] = {
                "path": portable,
                "size_bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
            for key, value in updates.items():
                if record.get(key) != value:
                    record[key] = value
                    changed += 1
    write_json_lf(path, payload)
    return changed


def repair(root: Path) -> dict[str, Any]:
    repository = root.resolve()
    normalized = normalize_tracked_text_files(repository)

    refreshed: dict[str, int] = {}
    # Direct byte seals must be refreshed before the stage-level checksum indexes that include them.
    refreshed["reference_manifest"] = _refresh_checksum_manifest(
        repository / "data/manifests/stage2/reference_manifest.csv", repository
    )
    refreshed["reference_sources"] = _repair_reference_sources(repository)
    refreshed["split_attestation"] = _repair_split_attestation(repository)
    refreshed["smoke_manifest"] = _repair_smoke_manifest(repository)
    refreshed["stage3_run_manifest"] = _repair_stage3_manifest(repository)

    # Rebuild stage checksum indexes last, because they cover many of the files changed above.
    for stage in range(4):
        key = f"stage{stage}_deliverable_manifest"
        refreshed[key] = _refresh_checksum_manifest(
            repository / f"reports/stage{stage}/deliverable_manifest.csv", repository
        )

    issues = repository_portability_issues(repository)
    return {
        "normalized_text_files": normalized,
        "normalized_text_file_count": len(normalized),
        "refreshed_fields": refreshed,
        "remaining_issues": issues,
        "status": "pass" if not issues else "fail",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    if args.check:
        issues = repository_portability_issues(root)
        if issues:
            print("TopoAstero portability check: FAIL")
            for issue in issues:
                print(f"- {issue}")
            raise SystemExit(1)
        print("TopoAstero portability check: PASS")
        return

    report = repair(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["remaining_issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
