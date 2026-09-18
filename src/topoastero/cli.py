"""Command-line interface for the Stage 0 repository contract."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from topoastero.config import configuration_hash
from topoastero.provenance import sha256_file
from topoastero.resources import write_resource_audit
from topoastero.smoke import run_smoke
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

