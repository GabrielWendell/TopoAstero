"""Command-line interface for TopoAstero repository contracts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from topoastero.acquisition import verify_cached_products
from topoastero.config import configuration_hash
from topoastero.provenance import sha256_file
from topoastero.resources import write_resource_audit
from topoastero.smoke import run_smoke
from topoastero.stage1_validation import validate_stage1
from topoastero.stage2_validation import validate_stage2
from topoastero.stage3_validation import validate_stage3
from topoastero.validation import validate_stage0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="topoastero")
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke = subparsers.add_parser("smoke", help="run the deterministic Stage 0 workflow")
    smoke.add_argument("--config", default="configs/smoke.yaml")
    smoke.add_argument("--output-dir", default="results/smoke")

    validate = subparsers.add_parser("validate-stage0", help="validate governance artifacts")
    validate.add_argument("--root", default=".")
    validate.add_argument("--without-smoke", action="store_true")

    stage1 = subparsers.add_parser(
        "validate-stage1", help="validate literature evidence, benchmarks, and G1"
    )
    stage1.add_argument("--root", default=".")
    stage1.add_argument("--without-stage0", action="store_true")

    stage2 = subparsers.add_parser(
        "validate-stage2", help="validate data manifests, schemas, partitions, QC, and G2"
    )
    stage2.add_argument("--root", default=".")
    stage2.add_argument("--without-prior-stages", action="store_true")

    stage3 = subparsers.add_parser(
        "validate-stage3", help="validate classical baselines, observation model, and G3"
    )
    stage3.add_argument("--root", default=".")
    stage3.add_argument("--without-prior-stages", action="store_true")

    cache = subparsers.add_parser(
        "verify-stage2-cache", help="verify cached mission payloads against frozen manifests"
    )
    cache.add_argument("--manifest", action="append", required=True)
    cache.add_argument("--cache-dir", required=True)

    hash_parser = subparsers.add_parser("hash-config", help="print a canonical config hash")
    hash_parser.add_argument("path")

    checksum = subparsers.add_parser("checksum", help="print a file SHA-256 checksum")
    checksum.add_argument("path")

    resources = subparsers.add_parser("audit-resources", help="inventory compute and software")
    resources.add_argument("--root", default=".")
    resources.add_argument("--output", default="reports/stage0/resource_audit.json")
    resources.add_argument("--check-network", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "smoke":
        result = run_smoke(args.config, args.output_dir)
        print(json.dumps(result["summary"], indent=2, sort_keys=True))
        return
    if args.command == "validate-stage0":
        errors = validate_stage0(args.root, require_smoke=not args.without_smoke)
        if errors:
            print("Stage 0 validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Stage 0 governance contract: PASS")
        return
    if args.command == "validate-stage1":
        errors = validate_stage1(args.root, require_stage0=not args.without_stage0)
        if errors:
            print("Stage 1 evidence contract failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Stage 1 literature and benchmark contract: PASS")
        return
    if args.command == "validate-stage2":
        errors = validate_stage2(args.root, require_prior_stages=not args.without_prior_stages)
        if errors:
            print("Stage 2 data contract failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Stage 2 data, provenance, and canonical-model contract: PASS")
        return
    if args.command == "validate-stage3":
        errors = validate_stage3(args.root, require_prior_stages=not args.without_prior_stages)
        if errors:
            print("Stage 3 classical-baseline contract failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Stage 3 classical baseline and observation-model contract: PASS")
        return
    if args.command == "verify-stage2-cache":
        errors = verify_cached_products(args.manifest, args.cache_dir)
        if errors:
            print("Stage 2 cached payload verification failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            raise SystemExit(1)
        print("Stage 2 cached payload verification: PASS")
        return
    if args.command == "hash-config":
        print(configuration_hash(args.path))
        return
    if args.command == "checksum":
        print(sha256_file(args.path))
        return
    if args.command == "audit-resources":
        record = write_resource_audit(args.root, args.output, check_network=args.check_network)
        print(json.dumps(record, indent=2, sort_keys=True))
        return
    raise RuntimeError(f"Unhandled command: {args.command}")
