"""Additive Stage 12 CLI: no edits to the frozen earlier CLI or estimator files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from topoastero.hybrid.features import load_config
from topoastero.hybrid.pipeline import run_development, run_transfer
from topoastero.hybrid.release import evaluate_confirmation, freeze
from topoastero.hybrid.reporting import build_report
from topoastero.hybrid.transfer import calibration_layer
from topoastero.hybrid.validation import validate
from topoastero.population_store import contained, read_json, read_table, write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fit")
    transfer = commands.add_parser("transfer")
    transfer.add_argument("--cache-dir", type=Path, required=True)
    commands.add_parser("report")
    check = commands.add_parser("validate")
    check.add_argument("--without-prior-stages", action="store_true")
    sign = commands.add_parser("freeze")
    sign.add_argument("--signing-key", type=Path, required=True)
    sign.add_argument("--supervisor", required=True)
    sign.add_argument("--data-steward", required=True)
    sign.add_argument("--container-digest", required=True)
    commands.add_parser("evaluate-confirmation")
    calibration = commands.add_parser("recalibrate")
    calibration.add_argument("--simulations", type=Path, required=True)
    calibration.add_argument("--authorization", required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        cfg = load_config(root)
        if args.command == "fit":
            run = run_development(root, cfg)
            print(f"Stage 12 grouped development: {run['status']}; {run['usable_stars']} unique stars")
        elif args.command == "transfer":
            run = run_transfer(root, args.cache_dir.resolve(), cfg)
            print(f"Stage 12 transfer: {run['cells']} cells; {run['actual_sectors']} actual sectors; {run['parent_stars']} parent star")
        elif args.command == "report":
            print("Stage 12 scientific G12: " + build_report(root, cfg)["status"])
        elif args.command == "validate":
            issues = validate(root, prior=not args.without_prior_stages)
            if issues:
                print("\n".join(issues))
                return 1
            print("Stage 12 implementation: PASS; scientific G12: " + read_json(contained(root, cfg["reports"]) / "G12_ACCEPTANCE.json")["status"])
        elif args.command == "freeze":
            freeze(root, cfg, signing_key=args.signing_key.resolve(), supervisor=args.supervisor,
                   data_steward=args.data_steward, container_digest=args.container_digest)
            print("Exact Stage 12 model release signed; no holdout opened")
        elif args.command == "evaluate-confirmation":
            print("Stage 12 first confirmation archive: " + evaluate_confirmation(root, cfg)["status"])
        elif args.command == "recalibrate":
            if contained(root, cfg["release"]).exists() or contained(root, cfg["confirmation_state"]).exists():
                raise ValueError("signed/opened release cannot be recalibrated")
            rows = json.loads(args.simulations.read_text())["rows"] if args.simulations.suffix == ".json" else read_table(args.simulations)
            allowed = {r["stable_star_id"] for r in read_table(root / "registries/population_partitions.csv") if r["role"] == "development"}
            if any(row["stable_star_id"] not in allowed for row in rows):
                raise ValueError("calibration star IDs must belong to the original development partition")
            numeric_rows = [{**row, "estimate": float(row["estimate"]), "reference": float(row["reference"])} for row in rows]
            layer = calibration_layer(numeric_rows, cfg, args.authorization)
            write_json(contained(root, cfg["output"]) / "authorized_calibration_layer.json", layer, exclusive=True)
            print("Authorized simulation-only calibration layer archived; application requires a new frozen release and disjoint validation")
    except (ValueError, OSError, KeyError) as exc:
        print("Stage 12 error: " + str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
