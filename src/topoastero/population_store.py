"""Portable, contained file operations for the additive Stage 11 workflows."""

from __future__ import annotations

import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from topoastero.portability import write_csv_lf, write_json_lf
from topoastero.provenance import sha256_file

Row = dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def contained(root: Path, relative: str) -> Path:
    """Reject absolute paths, traversal, symlinks outside root and Windows drive names."""
    if not relative or relative.startswith("/") or "\\" in relative or ":" in relative or ".." in Path(relative).parts:
        raise ValueError(f"unsafe repository path: {relative}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes repository: {relative}")
    return path


def star_slug(star_id: str) -> str:
    if re.fullmatch(r"KIC [1-9][0-9]{5,8}", star_id) is None:
        raise ValueError(f"invalid canonical star identifier: {star_id}")
    return star_id.replace(" ", "")


def read_json(path: Path) -> Row:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def read_table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_table(path: Path, rows: list[Row], fields: list[str] | None = None) -> None:
    names = fields if fields is not None else list(dict.fromkeys(key for row in rows for key in row))
    if not names:
        names = ["status"]
    write_csv_lf(path, rows, fieldnames=names)


def write_json(path: Path, value: Row, *, exclusive: bool = False) -> None:
    # Validate before opening a file; no NaN/Infinity in machine-readable evidence.
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    else:
        temporary = path.with_name(path.name + ".tmp")
        write_json_lf(temporary, value)
        temporary.replace(path)


def seal(root: Path, path: Path) -> Row:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    return {"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def seal_issues(root: Path, records: list[Row]) -> list[str]:
    issues = []
    for record in records:
        try:
            path = contained(root, str(record["path"]))
            if not path.is_file() or path.stat().st_size != record["size_bytes"] or sha256_file(path) != record["sha256"]:
                issues.append(f"stale seal: {record['path']}")
        except (KeyError, ValueError, TypeError):
            issues.append("invalid or unsafe seal")
    return issues


def append_event(path: Path, event: Row) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"recorded_at_utc": utc_now(), **event}, sort_keys=True, allow_nan=False)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
