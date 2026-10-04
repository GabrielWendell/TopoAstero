"""Additive Stage 11 CLI; the byte-sealed Stage 10 CLI remains intact."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from topoastero.config import content_hash
from topoastero.population_acquisition import acquire_population, load_config
from topoastero.population_freeze import freeze_release, open_confirmation
from topoastero.population_pipeline import cohort, run_role, source_fingerprint
from topoastero.population_references import import_references
from topoastero.population_reporting import build_report
from topoastero.population_store import append_event, contained, read_json, write_table
from topoastero.stage11_validation import validate_stage11


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="topoastero-stage11", description=__doc__)
    result.add_argument("--root", type=Path, default=Path.cwd())
    commands = result.add_subparsers(dest="command", required=True)
    refs = commands.add_parser("references", help="import corrected CDS reference tables")
    refs.add_argument("--cache-dir", required=True, type=Path)
    refs.add_argument("--download", action="store_true")
    acquire = commands.add_parser("acquire", help="checksum existing/download public mission payloads")
    acquire.add_argument("--cache-dir", required=True, type=Path)
    acquire.add_argument("--download", action="store_true")
    acquire.add_argument("--role", choices=("all", "development", "internal_validation", "descriptive_benchmark", "final_holdout"), default="all")
    acquire.add_argument("--timeout", type=float, default=240.0, help="per-read network timeout in seconds (default: 240)")
    acquire.add_argument("--retries", type=int, default=4, help="download attempts per payload (default: 4)")
    acquire.add_argument("--retry-backoff", type=float, default=2.0, help="linear retry backoff base in seconds (default: 2)")
    commands.add_parser("cohort", help="reconcile all 66 metadata/partition/reference records")
    run = commands.add_parser("run-development", help="run development/internal/Rudy; holdout is unavailable")
    run.add_argument("--cache-dir", required=True, type=Path)
    run.add_argument("--role", choices=("all", "development", "internal_validation", "descriptive_benchmark"), default="all")
    run.add_argument("--output-dir", help="new repository-relative development output after a logged change")
    change = commands.add_parser("log-change", help="record a pre-confirmation software/configuration change")
    change.add_argument("--note", required=True)
    change.add_argument("--affected-roles", default="development;internal_validation")
    freeze = commands.add_parser("freeze", help="sign exact release after acquisition/development QA")
    freeze.add_argument("--cache-dir", required=True, type=Path)
    freeze.add_argument("--supervisor", required=True)
    freeze.add_argument("--data-steward", required=True)
    freeze.add_argument("--container-digest", required=True)
    freeze.add_argument("--signing-key", required=True, type=Path)
    freeze.add_argument("--development-dir", type=Path)
    confirmation = commands.add_parser("open-confirmation", help="execute the signed holdout once")
    confirmation.add_argument("--cache-dir", required=True, type=Path)
    confirmation.add_argument("--resume", action="store_true", help="resume identical interrupted attempt, retaining completed star checkpoints")
    report = commands.add_parser("report", help="regenerate machine-readable gate, audits and Paper II draft")
    report.add_argument("--development-dir", type=Path, help="active non-holdout run directory; signed release takes precedence")
    validate = commands.add_parser("validate", help="validate implementation/evidence without opening holdout")
    validate.add_argument("--without-prior-stages", action="store_true")
    validate.add_argument("--require-confirmation", action="store_true")
    return result


def main(argv: Sequence[str] | None = None) -> None:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    cfg = load_config(root)
    try:
        if args.command == "references":
            if contained(root, cfg["release"]).exists():
                raise ValueError("reference edition is frozen for confirmation")
            result = import_references(root, args.cache_dir.resolve(), download=args.download)
            print(f"Corrected LEGACY references: {result['stars']} stars, {result['mode_rows']} modes, {result['ratio_rows']} ratios")
        elif args.command == "acquire":
            result = acquire_population(
                root,
                args.cache_dir.resolve(),
                cfg,
                download=args.download,
                role=args.role,
                timeout=args.timeout,
                retries=args.retries,
                retry_backoff=args.retry_backoff,
            )
            print(f"Verified mission products: {result['verified_products']}/{result['expected_products']}; no holdout representations computed")
        elif args.command == "cohort":
            rows = cohort(root, cfg)
            write_table(contained(root, cfg["reports"]) / "cohort_ledger.csv", rows)
            print(f"Reconciled {len(rows)} unique star groups; original split preserved")
        elif args.command == "run-development":
            if contained(root, cfg["release"]).exists():
                raise ValueError("development is locked by the confirmation release")
            roles = ("development", "internal_validation", "descriptive_benchmark") if args.role == "all" else (args.role,)
            base = contained(root, args.output_dir or cfg["output"])
            for role in roles:
                result = run_role(root, args.cache_dir.resolve(), cfg, role, base / role)
                print(f"{role}: {result['stars_with_estimates']}/{result['stars']} stars with estimates; missing/failures retained")
        elif args.command == "log-change":
            if contained(root, cfg["release"]).exists():
                raise ValueError("post-freeze changes require a disclosed new exploratory study, not confirmation retuning")
            if "holdout" in args.affected_roles or not args.note.strip():
                raise ValueError("development QA may not tune holdout stars")
            append_event(contained(root, cfg["qa_log"]), {"event": "software_or_configuration_change", "note": args.note,
                                                        "affected_roles": args.affected_roles, "configuration_sha256": content_hash(cfg),
                                                        "code_sha256": source_fingerprint(root), "holdout_used": False})
        elif args.command == "freeze":
            result = freeze_release(root, args.cache_dir.resolve(), cfg, supervisor=args.supervisor, data_steward=args.data_steward,
                                    container_digest=args.container_digest, signing_key=args.signing_key.resolve(),
                                    development_dir=args.development_dir.resolve() if args.development_dir else None)
            print(f"Signed confirmation release: {result['payload_sha256']}; holdout remains unopened")
        elif args.command == "open-confirmation":
            result = open_confirmation(root, args.cache_dir.resolve(), cfg, resume=args.resume)
            print(f"First confirmation preserved: {result['stars_with_estimates']}/{result['stars']} stars with estimates")
        elif args.command == "report":
            result = build_report(root, cfg, development_dir=args.development_dir.resolve() if args.development_dir else None)
            print(f"Stage 11 implementation: PASS; scientific G11: {result['status']}")
        elif args.command == "validate":
            issues = validate_stage11(root, require_prior_stages=not args.without_prior_stages, require_confirmation=args.require_confirmation)
            if issues:
                raise ValueError("\n".join(issues))
            gate = read_json(root / "reports/stage11/G11_ACCEPTANCE.json")
            print(f"Stage 11 implementation: PASS; scientific G11: {gate['status']}")
        else:
            raise RuntimeError("unhandled Stage 11 command")
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
