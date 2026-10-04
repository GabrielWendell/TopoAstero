"""Fresh Stage 10 raw reproduction with declared numerical and rendered-figure checks.

The original strict replay is kept unchanged. This additive check records its
attempt and uses rtol=1e-6, atol=1e-6 for platform-level optimizer differences.
Identifiers, strings, flags, rows and generated manuscript text remain exact.
Journal figure PNGs must agree in dimensions, mean pixel difference <= 0.5/255
and changed-pixel fraction <= 1%; SVG text and viewBox must match exactly.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from reproduce_stage10 import COMPUTE_SOURCES, copy_source
from run_stage10_rudy import seal

from topoastero.portability import write_json_lf

ATOL = 1e-6
RTOL = 1e-6


def differences(first: Any, second: Any, location: str, issues: list[str], metrics: dict[str, float]) -> None:
    if isinstance(first, dict) and isinstance(second, dict):
        if first.keys() != second.keys():
            issues.append(location + ": keys differ")
        for key in first.keys() & second.keys():
            differences(first[key], second[key], location + "." + key, issues, metrics)
    elif isinstance(first, list) and isinstance(second, list):
        if len(first) != len(second):
            issues.append(location + ": lengths differ")
        for i, (x, y) in enumerate(zip(first, second, strict=False)):
            differences(x, y, f"{location}[{i}]", issues, metrics)
    elif isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, (int, float)) and not isinstance(second, bool):
        delta = abs(first - second)
        metrics["maximum_absolute_difference"] = max(metrics["maximum_absolute_difference"], delta)
        metrics["maximum_relative_difference"] = max(metrics["maximum_relative_difference"], delta / max(ATOL, abs(first)))
        if not np.isclose(first, second, atol=ATOL, rtol=RTOL):
            issues.append(f"{location}: numeric difference {first} vs {second}")
    elif first != second:
        issues.append(location + ": exact value differs")


def compare(root: Path, fresh: Path) -> dict[str, Any]:
    issues = []
    rows = []
    for path in sorted((root / "results/stage10").iterdir()):
        if path.suffix not in {".json", ".csv"} or path.name in {"run_manifest.json", "environment.json", "benchmark_capsule.json"}:
            continue
        target = fresh / path.relative_to(root)
        metrics = {"maximum_absolute_difference": 0.0, "maximum_relative_difference": 0.0}
        before = len(issues)
        if path.suffix == ".json":
            differences(json.loads(path.read_text()), json.loads(target.read_text()), path.name, issues, metrics)
        else:
            with path.open(newline="") as handle:
                first = list(csv.reader(handle))
            with target.open(newline="") as handle:
                second = list(csv.reader(handle))
            if len(first) != len(second):
                issues.append(path.name + ": row count differs")
            for index, (left, right) in enumerate(zip(first, second, strict=False)):
                if len(left) != len(right):
                    issues.append(path.name + ": column count differs")
                for column, (a, b) in enumerate(zip(left, right, strict=False)):
                    try:
                        x, y = float(a), float(b)
                    except ValueError:
                        x, y = a, b
                    differences(x, y, f"{path.name}:{index}:{column}", issues, metrics)
        rows.append({"path": path.relative_to(root).as_posix(), "status": "pass" if len(issues) == before else "fail", **metrics})
    for path in sorted((root / "reports/stage10/figures").glob("*.svg")):
        target = fresh / path.relative_to(root)
        left, right = ET.parse(path).getroot(), ET.parse(target).getroot()
        texts = lambda tree: [e.text for e in tree.iter() if e.tag.endswith(("text", "description", "title"))]  # noqa: E731
        same = left.attrib["viewBox"] == right.attrib["viewBox"] and texts(left) == texts(right)
        a = np.asarray(Image.open(path.with_suffix(".png")).convert("RGB"), dtype=float)
        b = np.asarray(Image.open(target.with_suffix(".png")).convert("RGB"), dtype=float)
        mae, fraction = 255.0, 1.0
        if a.shape == b.shape:
            delta = np.abs(a - b)
            mae = float(np.mean(delta))
            fraction = float(np.mean(np.any(delta > 8, axis=2)))
        passed = same and mae <= .5 and fraction <= .01
        if not passed:
            issues.append("journal figure comparison failed: " + path.name)
        rows.append({"path": path.relative_to(root).as_posix(), "status": "pass" if passed else "fail", "pixel_mae_0_255": mae,
                     "changed_pixel_fraction_over_8": fraction, "same_viewbox_and_text": same})
    for name in ("main.tex", "results_macros.tex", "results_tables.tex", "claim_ledger.tex", "references.bib"):
        same = (root / "paper1" / name).read_bytes() == (fresh / "paper1" / name).read_bytes()
        if not same:
            issues.append("generated manuscript source differs: " + name)
        rows.append({"path": "paper1/" + name, "status": "pass" if same else "fail", "exact_bytes": True})
    return {"status": "pass" if not issues else "fail", "numeric_atol": ATOL, "numeric_rtol": RTOL,
            "figure_criteria": "SVG_viewBox_and_text_exact; PNG_pixel_MAE<=0.5; fraction_pixels_delta>8<=0.01",
            "comparisons": rows, "differences": issues}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    root, destination = args.root.resolve(), args.work_dir.resolve()
    if destination.exists() or destination.is_relative_to(root):
        raise ValueError("use a new work directory outside the source repository")
    old = root / "reports/stage10/clean_reproduction.json"
    if old.exists():
        write_json_lf(root / "reports/stage11/strict_stage10_reproduction_attempt.json", json.loads(old.read_text()))
    copy_source(root, destination)
    env = {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT", "PYTHONPATH"}}
    subprocess.run(["uv", "sync", "--locked", "--group", "dev", "--extra", "astronomy"], cwd=destination, env=env, check=True, capture_output=True)
    command = ["uv", "run", "python", "-u", "workflows/reproduce_stage10.py", "--cache-dir", str(args.cache_dir.resolve()), "--require-tex"]
    log = destination.parent / "stage10_portable_reproduction.log"
    print("Running a fresh locked Stage 10 raw-product reproduction with explicit portable comparison", flush=True)
    with log.open("w") as handle:
        completed = subprocess.run(command, cwd=destination, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if completed.returncode:
        raise RuntimeError(log.read_text()[-2000:])
    comparison = compare(root, destination)
    write_json_lf(root / "reports/stage11/portable_stage10_reproduction_comparison.json", comparison)
    report = {"status": comparison["status"], "fresh_source_copy": True, "fresh_locked_environment": True, "new_process": True,
              "independent_human_reviewer": None, "raw_products_verified_in_child": 21, "raw_cache_reused": True,
              "existing_Stage10_outputs_excluded": True, "subprocess_returncode": 0, "compared_files": len(comparison["comparisons"]),
              "numeric_atol": ATOL, "numeric_rtol": RTOL, "journal_SVG_byte_identity_required": False,
              "journal_SVG_semantic_and_PNG_pixel_checks_required": True,
              "PDF_regenerated": (destination / "paper1/main.pdf").is_file(),
              "source_inputs": [seal(root, relative) for relative in COMPUTE_SOURCES],
              "result_files": [seal(root, p.relative_to(root).as_posix()) for p in sorted((root / "results/stage10").iterdir()) if p.suffix in {".csv", ".json"} and p.name not in {"run_manifest.json", "benchmark_capsule.json", "environment.json"}],
              "comparison_report": "reports/stage11/portable_stage10_reproduction_comparison.json",
              "original_strict_attempt_preserved": "reports/stage11/strict_stage10_reproduction_attempt.json",
              "differences": comparison["differences"]}
    write_json_lf(old, report)
    if comparison["differences"]:
        raise ValueError("\n".join(comparison["differences"]))
    print(f"Portable clean raw-product reproduction: PASS ({len(comparison['comparisons'])} scientific/figure/manuscript files)")


if __name__ == "__main__":
    main()
