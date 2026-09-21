"""Cross-platform repository serialization and portability helpers.

Repository artifacts are byte-addressed by SHA-256, so text serialization must not depend on
an operating system's newline or path-separator conventions.  This module provides the single
canonical implementation used by workflows that create governed TopoAstero artifacts.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = frozenset(
    {
        ".bib",
        ".cff",
        ".cfg",
        ".csv",
        ".gitignore",
        ".html",
        ".ini",
        ".ipynb",
        ".json",
        ".jsonl",
        ".lock",
        ".md",
        ".py",
        ".rst",
        ".sh",
        ".svg",
        ".toml",
        ".tsv",
        ".txt",
        ".yaml",
        ".yml",
    }
)
TEXT_FILENAMES = frozenset(
    {
        ".dockerignore",
        ".editorconfig",
        ".gitattributes",
        ".gitignore",
        ".python-version",
        "CODEOWNERS",
        "Dockerfile",
        "LICENSE",
        "Makefile",
    }
)
EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
)


def repository_relative_posix(path: str | Path, root: str | Path) -> str:
    """Return a repository-relative path using POSIX separators on every host OS."""

    repository = Path(root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repository / candidate
    try:
        relative = candidate.resolve().relative_to(repository)
    except ValueError as exc:
        raise ValueError(f"path is outside repository root: {candidate}") from exc
    return relative.as_posix()


def write_text_lf(path: str | Path, text: str) -> None:
    """Write UTF-8 text without platform-dependent newline translation."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json_lf(path: str | Path, value: Any, *, indent: int = 2, sort_keys: bool = True) -> None:
    """Write deterministic UTF-8 JSON terminated by one LF newline."""

    payload = json.dumps(value, indent=indent, sort_keys=sort_keys) + "\n"
    write_text_lf(path, payload)


def write_csv_lf(
    path: str | Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str],
) -> None:
    """Write CSV using RFC-compatible quoting and an explicit LF record terminator."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalized_lf_bytes(data: bytes) -> bytes:
    """Normalize CRLF and lone CR bytes to LF without otherwise changing bytes."""

    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def normalize_text_file_lf(path: str | Path) -> bool:
    """Normalize a text file in place; return ``True`` only when bytes changed."""

    target = Path(path)
    original = target.read_bytes()
    normalized = normalized_lf_bytes(original)
    if normalized == original:
        return False
    target.write_bytes(normalized)
    return True


def is_repository_text_path(path: str | Path) -> bool:
    """Return whether a tracked repository path is governed as portable text."""

    candidate = Path(path)
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in candidate.parts):
        return False
    return candidate.name in TEXT_FILENAMES or candidate.suffix.lower() in TEXT_SUFFIXES


def tracked_repository_files(root: str | Path) -> list[Path]:
    """Return Git-tracked files, with a deterministic filesystem fallback for source archives."""

    repository = Path(root).resolve()
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repository,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            path
            for path in repository.rglob("*")
            if path.is_file()
            and not any(
                part in EXCLUDED_DIRECTORY_NAMES for part in path.relative_to(repository).parts
            )
        )
    paths = [repository / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    return sorted(path for path in paths if path.is_file())


def tracked_text_files(root: str | Path) -> list[Path]:
    repository = Path(root).resolve()
    return [
        path
        for path in tracked_repository_files(repository)
        if is_repository_text_path(path.relative_to(repository))
    ]


def newline_portability_issues(root: str | Path) -> list[str]:
    """Report tracked text files containing CR bytes."""

    repository = Path(root).resolve()
    issues: list[str] = []
    for path in tracked_text_files(repository):
        if b"\r" in path.read_bytes():
            issues.append(f"non-LF tracked text: {repository_relative_posix(path, repository)}")
    return issues


def normalize_tracked_text_files(root: str | Path) -> list[str]:
    """Normalize all tracked repository text and return changed relative paths."""

    repository = Path(root).resolve()
    changed: list[str] = []
    for path in tracked_text_files(repository):
        if normalize_text_file_lf(path):
            changed.append(repository_relative_posix(path, repository))
    return changed


def serialized_posix_path(value: str) -> str:
    """Normalize a serialized repository path to forward slashes."""

    return value.replace("\\", "/")


def manifest_path_portability_issues(root: str | Path) -> list[str]:
    """Report governed manifests that contain host-specific path separators."""

    repository = Path(root).resolve()
    issues: list[str] = []

    def check_value(label: str, value: object) -> None:
        if isinstance(value, str) and "\\" in value:
            issues.append(f"non-POSIX serialized path in {label}: {value}")

    smoke = repository / "results/smoke/run_manifest.json"
    if smoke.is_file():
        payload = json.loads(smoke.read_text(encoding="utf-8"))
        configuration = payload.get("configuration", {})
        if isinstance(configuration, dict):
            check_value(
                "results/smoke/run_manifest.json:configuration.path", configuration.get("path")
            )

    stage3 = repository / "results/stage3/run_manifest.json"
    if stage3.is_file():
        payload = json.loads(stage3.read_text(encoding="utf-8"))
        check_value("results/stage3/run_manifest.json:config_path", payload.get("config_path"))
        outputs = payload.get("outputs", [])
        if isinstance(outputs, list):
            for index, record in enumerate(outputs):
                if isinstance(record, dict):
                    check_value(
                        f"results/stage3/run_manifest.json:outputs[{index}].path",
                        record.get("path"),
                    )

    stage4 = repository / "results/stage4/run_manifest.json"
    if stage4.is_file():
        payload = json.loads(stage4.read_text(encoding="utf-8"))
        check_value("results/stage4/run_manifest.json:config_path", payload.get("config_path"))
        for collection in ("inputs", "outputs"):
            records = payload.get(collection, [])
            if isinstance(records, list):
                for index, record in enumerate(records):
                    if isinstance(record, dict):
                        check_value(
                            f"results/stage4/run_manifest.json:{collection}[{index}].path",
                            record.get("path"),
                        )

    split = repository / "registries/split_attestation.json"
    if split.is_file():
        payload = json.loads(split.read_text(encoding="utf-8"))
        check_value("registries/split_attestation.json:file", payload.get("file"))
        check_value("registries/split_attestation.json:source", payload.get("source"))

    csv_manifests = [
        repository / "data/manifests/stage2/reference_manifest.csv",
        repository / "reports/stage0/deliverable_manifest.csv",
        repository / "reports/stage1/deliverable_manifest.csv",
        repository / "reports/stage2/deliverable_manifest.csv",
        repository / "reports/stage3/deliverable_manifest.csv",
        repository / "reports/stage4/deliverable_manifest.csv",
    ]
    for manifest in csv_manifests:
        if not manifest.is_file():
            continue
        with manifest.open(encoding="utf-8", newline="") as handle:
            for number, row in enumerate(csv.DictReader(handle), start=2):
                check_value(
                    f"{repository_relative_posix(manifest, repository)}:{number}:path",
                    row.get("path"),
                )
    return issues


def repository_portability_issues(root: str | Path) -> list[str]:
    """Return all currently detectable cross-platform repository portability defects."""

    return [*newline_portability_issues(root), *manifest_path_portability_issues(root)]
