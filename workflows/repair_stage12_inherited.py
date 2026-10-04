"""Re-execute inherited Stage 11 derived spectra without rewriting earlier runs.

This is an ARCHIVED-SPECTRA replay, not a raw-product population reproduction.
Completed missing/pipeline-failed records are carried forward unchanged in
scientific status. The original default/population_dev trees remain untouched.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np

from topoastero.config import content_hash
from topoastero.population import analyze_spectra
from topoastero.population_acquisition import load_config
from topoastero.population_pipeline import (
    catalog_rows,
    cohort,
    ratio_benchmark,
    source_fingerprint,
    star_input_id,
)
from topoastero.population_reporting import build_report
from topoastero.population_statistics import build_performance, operating_domain
from topoastero.population_store import (
    append_event,
    contained,
    read_json,
    seal,
    seal_issues,
    star_slug,
    write_json,
    write_table,
)


def replay(root: Path, directory: str = "results/stage11/stage12_compatibility_replay") -> None:
    cfg = load_config(root)
    active = read_json(root / "reports/stage11/evidence_manifest.json")["role_directories"]
    source = contained(root, directory)
    source.mkdir(parents=True, exist_ok=True)
    members = cohort(root, cfg)
    for role in ("development", "internal_validation", "descriptive_benchmark"):
        old = root / active[role]
        new = source / role
        if (new / "run_manifest.json").exists():
            summary = read_json(new / "summary.json")
            issues = seal_issues(root, read_json(new / "run_manifest.json")["files"])
            if issues or summary["code_sha256"] != source_fingerprint(root) or summary["configuration_sha256"] != content_hash(cfg):
                raise ValueError("stale archived-spectrum replay; choose a new --output-dir")
            continue
        catalog, ratios, statuses = [], [], []
        for member in (m for m in members if m["role"] == role):
            original = old / "stars" / star_slug(member["stable_star_id"])
            target = new / "stars" / original.name
            target.mkdir(parents=True, exist_ok=True)
            result = read_json(original / "analysis.json")
            original_seal = seal(root, original / "analysis.json")
            if (original / "monthly_spectra.npz").exists() and result["status"] in {"ok", "limited"}:
                archived = np.load(original / "monthly_spectra.npz")
                frequency, spectra, weights = archived["frequency_uHz"], archived["spectra"], archived["exposure_cadences"]
                science, mean, background, bootstrap = analyze_spectra(frequency, spectra, weights, cfg,
                    seed=cfg["master_seed"] + int(member["kic"]), duty_cycle=result["duty_cycle"])
                result.update(science)
                if result["available_products"] < result["expected_products"]:
                    result["quality_flags"].append("incomplete_products")
                    result["status"] = "limited"
                shutil.copyfile(original / "monthly_spectra.npz", target / "monthly_spectra.npz")
                write_table(target / "mean_spectrum.csv", [{"frequency_uHz": float(f), "power_ppm2_per_uHz": float(p), "background_ppm2_per_uHz": float(b)} for f, p, b in zip(frequency, mean, background, strict=True)])
                write_table(target / "segment_bootstrap.csv", bootstrap)
                print("Replayed archived monthly spectrum: " + member["stable_star_id"], flush=True)
            result.update({"input_id": star_input_id(root, cfg, member["stable_star_id"]), "reproduction_scope": "archived_monthly_spectra_only_no_raw_payload_reproduction",
                           "archived_analysis_source": original_seal, "completed_failed_records_retried": False})
            write_json(target / "analysis.json", result)
            write_json(target / "star_manifest.json", {"schema_version": 1, "stable_star_id": member["stable_star_id"], "role": role,
                        "input_id": result["input_id"], "files": [seal(root, p) for p in sorted(target.iterdir()) if p.is_file() and p.name != "star_manifest.json"]})
            catalog.extend(catalog_rows(member, result))
            ratios.extend(ratio_benchmark(root, cfg, member, result, target))
            statuses.append({"stable_star_id": member["stable_star_id"], "status": result["status"], "flags": result["quality_flags"], "input_id": result["input_id"]})
        performance, comparison = build_performance(catalog, cfg, role=role)
        for name, rows in (("catalog.csv", catalog), ("performance.csv", performance), ("paired_comparisons.csv", comparison),
                           ("ratio_benchmark.csv", ratios), ("operating_domain.csv", operating_domain(catalog, cfg))):
            write_table(new / name, rows)
        write_json(new / "catalog.json", {"schema_version": 1, "role": role, "rows": catalog})
        summary = read_json(old / "summary.json")
        summary.update({"statuses": statuses, "code_sha256": source_fingerprint(root), "configuration_sha256": content_hash(cfg),
                        "stars_with_estimates": len({r["stable_star_id"] for r in catalog if r["estimate"] is not None}),
                        "reproduction_scope": "archived_monthly_spectra_only_no_raw_payload_reproduction", "raw_payloads_reprocessed": False})
        write_json(new / "summary.json", summary)
        write_json(new / "run_manifest.json", {"schema_version": 1, "role": role, "files": [seal(root, p) for p in sorted(new.rglob("*")) if p.is_file() and p.name != "run_manifest.json"]})
    append_event(root / cfg["qa_log"], {"event": "stage12_compatibility_derived_replay", "holdout_used": False,
                 "reproduction_scope": "archived_monthly_spectra_only", "code_sha256": source_fingerprint(root), "original_runs_preserved": True})
    build_report(root, cfg, development_dir=source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output-dir", default="results/stage11/stage12_compatibility_replay")
    args = parser.parse_args()
    replay(args.root.resolve(), args.output_dir)
