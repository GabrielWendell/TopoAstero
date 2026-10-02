"""One-command public-ID Rudy/Paper I capsule and fresh-process reproduction check."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from build_stage10_evidence import build as build_evidence
from build_stage10_manifest import build as build_manifest
from build_stage10_paper import build as build_paper
from run_stage10_rudy import ROOT, run, seal

from topoastero.portability import write_json_lf
from topoastero.provenance import sha256_file

PAPER_OUTPUTS = {"main.tex", "main.pdf", "results_macros.tex", "results_tables.tex", "claim_ledger.tex", "references.bib", "README.md", "build_status.json", "compile.log"}
COMPUTE_SOURCES = (
    "configs/stage10_rudy.yaml", "uv.lock", "src/topoastero/rudy_benchmark.py",
    "src/topoastero/classical.py", "src/topoastero/spectral_topology.py", "src/topoastero/echelle_topology.py",
    "src/topoastero/tda.py", "src/topoastero/style.py", "workflows/acquire_stage3_inputs.py",
    "workflows/run_stage3_classical.py", "workflows/run_stage8_echelle.py", "workflows/run_stage10_rudy.py",
    "workflows/build_stage10_evidence.py", "workflows/plot_stage10.py", "workflows/build_stage10_paper.py",
    "paper1/manuscript_template.tex", "paper1/additional_references.bib",
)


def copy_source(source: Path, destination: Path) -> None:
    def ignored(directory: str, names: list[str]) -> set[str]:
        relative = Path(directory).relative_to(source)
        excluded = {name for name in names if name in {".venv", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "dist", "build", ".coverage"} or name.endswith(".pyc")}
        if relative.as_posix() in {"results", "reports"}:
            excluded.add("stage10")
        if relative.as_posix() == "paper1":
            excluded |= {name for name in names if name in PAPER_OUTPUTS or Path(name).suffix in {".aux", ".bbl", ".blg", ".out", ".toc", ".log"}}
        return excluded
    shutil.copytree(source, destination, ignore=ignored, dirs_exist_ok=True)


def compare_values(expected: Any, actual: Any, location: str, errors: list[str]) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            errors.append(f"{location}: JSON keys differ")
        for key in expected.keys() & actual.keys():
            compare_values(expected[key], actual[key], f"{location}.{key}", errors)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            errors.append(f"{location}: array length differs")
        for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
            compare_values(left, right, f"{location}[{index}]", errors)
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool) and isinstance(actual, (float, int)) and not isinstance(actual, bool):
        if not np.isclose(expected, actual, atol=1e-8, rtol=1e-9):
            errors.append(f"{location}: numeric difference {expected} vs {actual}")
    elif expected != actual:
        errors.append(f"{location}: value differs")


def compare_science(expected_root: Path, actual_root: Path) -> tuple[list[str], int]:
    errors, compared = [], 0
    for path in sorted((expected_root / "results/stage10").iterdir()):
        if path.suffix not in {".json", ".csv"} or path.name in {"run_manifest.json", "environment.json", "benchmark_capsule.json"}:
            continue
        relative = path.relative_to(expected_root)
        target = actual_root / relative
        if not target.is_file():
            errors.append(f"missing reproduced file: {relative.as_posix()}")
            continue
        if path.suffix == ".json":
            compare_values(json.loads(path.read_text()), json.loads(target.read_text()), relative.as_posix(), errors)
        else:
            with path.open(encoding="utf-8", newline="") as handle:
                first = list(csv.reader(handle))
            with target.open(encoding="utf-8", newline="") as handle:
                second = list(csv.reader(handle))
            if len(first) != len(second):
                errors.append(f"{relative.as_posix()}: CSV row count differs")
                continue
            for index, (left, right) in enumerate(zip(first, second, strict=True)):
                if len(left) != len(right):
                    errors.append(f"{relative.as_posix()}:{index}: CSV column count differs")
                    continue
                for column, (a, b) in enumerate(zip(left, right, strict=True)):
                    try:
                        av, bv = float(a), float(b)
                    except ValueError:
                        av, bv = a, b
                    compare_values(av, bv, f"{relative.as_posix()}:{index}:{column}", errors)
        compared += 1
    for path in sorted((expected_root / "reports/stage10/figures").glob("*.svg")):
        target = actual_root / path.relative_to(expected_root)
        if not target.is_file() or sha256_file(path) != sha256_file(target):
            errors.append(f"journal SVG differs: {path.name}")
        compared += 1
    for name in ("main.tex", "results_macros.tex", "results_tables.tex", "claim_ledger.tex", "references.bib"):
        first, second = expected_root / "paper1" / name, actual_root / "paper1" / name
        if not second.is_file() or first.read_bytes() != second.read_bytes():
            errors.append(f"generated manuscript source differs: {name}")
        compared += 1
    pdf = actual_root / "paper1/main.pdf"
    if not pdf.is_file() or pdf.stat().st_size < 1000:
        errors.append("Paper I PDF was not regenerated")
    return errors, compared


def clean_check(cache: Path) -> None:
    if not (ROOT / "reports/stage10/freeze_manifest.json").is_file():
        raise FileNotFoundError("generate the complete Stage 10 capsule before --clean-check")
    with tempfile.TemporaryDirectory(prefix="topoastero-stage10-") as temporary:
        clean = Path(temporary) / "TopoAstero"
        copy_source(ROOT, clean)
        env = {key: value for key, value in os.environ.items() if key not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}}
        sync = subprocess.run(["uv", "sync", "--locked", "--group", "dev", "--extra", "astronomy"], cwd=clean, env=env, capture_output=True, text=True, check=False)
        if sync.returncode:
            raise RuntimeError(f"fresh locked environment failed:\n{sync.stderr[-3000:]}")
        log_path = Path(temporary) / "reproduction.log"
        command = ["uv", "run", "python", "-u", "workflows/reproduce_stage10.py", "--cache-dir", str(cache.resolve()), "--require-tex"]
        print("Fresh source copy/environment created; running the full raw-product capsule in a new process", flush=True)
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, cwd=clean, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        if completed.returncode:
            raise RuntimeError(f"fresh-process reproduction failed:\n{log_path.read_text()[-4000:]}")
        errors, count = compare_science(ROOT, clean)
        report = {"status": "pass" if not errors else "fail", "fresh_source_copy": True, "fresh_locked_environment": True, "new_process": True, "independent_human_reviewer": None, "raw_products_verified_in_child": 21, "raw_cache_reused": True, "existing_Stage10_outputs_excluded": True, "subprocess_returncode": completed.returncode, "compared_files": count, "numeric_atol": 1e-8, "numeric_rtol": 1e-9, "journal_SVG_byte_identity_required": True, "PDF_regenerated": (clean / "paper1/main.pdf").is_file(), "source_inputs": [seal(ROOT, relative) for relative in COMPUTE_SOURCES], "result_files": [seal(ROOT, path.relative_to(ROOT).as_posix()) for path in sorted((ROOT / "results/stage10").iterdir()) if path.suffix in {".csv", ".json"} and path.name not in {"run_manifest.json", "benchmark_capsule.json", "environment.json"}], "differences": errors}
        write_json_lf(ROOT / "reports/stage10/clean_reproduction.json", report)
        if errors:
            raise ValueError("\n".join(errors[:30]))
    build_manifest(ROOT)
    print(f"Clean raw-product reproduction: PASS ({count} scientific/figure/manuscript files compared)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--require-tex", action="store_true")
    parser.add_argument("--clean-check", action="store_true")
    args = parser.parse_args()
    if args.clean_check:
        clean_check(args.cache_dir)
        return
    output = args.output_root.resolve()
    if output != ROOT:
        if ROOT in output.parents:
            raise ValueError("use an --output-root outside the source repository")
        copy_source(ROOT, output)
    run(ROOT / "configs/stage10_rudy.yaml", args.cache_dir.resolve(), output, download=args.download)
    build_evidence(output, args.cache_dir.resolve())
    build_paper(output, require_tex=args.require_tex)
    build_manifest(output)


if __name__ == "__main__":
    main()
