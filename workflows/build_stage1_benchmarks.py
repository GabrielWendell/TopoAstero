"""Build the checked-in Stage 1 LEGACY and Rudy benchmark tables.

The publisher machine-readable inputs are not redistributed. Download the three files recorded
in ``evidence/benchmarks/source_provenance.csv``, verify their SHA-256 digests, and pass their
paths to this script. The generated CSV files are deterministic and are committed for offline
validation.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from pathlib import Path

from topoastero.portability import write_csv_lf

RUDY_KIC = "10963065"
GLOBAL_SOURCE = "SilvaAguirre2017"
POPULATION_SOURCES = "Lund2017;SilvaAguirre2017"
MODE_SOURCE = "Lund2017"
GLOBAL_LOCATION = "publisher machine-readable Table 3"
STELLAR_LOCATION = "publisher machine-readable Table 4"
MODE_LOCATION = "publisher machine-readable Table 6"


def _data_rows(path: Path, columns: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == columns and fields and re.fullmatch(r"\d{7,8}", fields[0]) is not None:
            rows.append(fields)
    return rows


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> None:
    write_csv_lf(path, rows, fieldnames=fieldnames)


def _fixed_field(record: str, start: int, stop: int) -> str:
    return record[start:stop].strip()


def build_population(global_table: Path, output: Path) -> list[list[str]]:
    source_rows = _data_rows(global_table, 12)
    if len(source_rows) != 66:
        raise ValueError(f"expected 66 LEGACY rows; found {len(source_rows)}")
    rows: list[dict[str, str]] = []
    for fields in source_rows:
        kic, numax, numax_plus, numax_minus, dnu, dnu_plus, dnu_minus = fields[:7]
        teff, teff_error, feh, feh_error, atmosphere_ref = fields[7:]
        rows.append(
            {
                "object_id": f"KIC {kic}",
                "kic": kic,
                "popular_name": "Rudy" if kic == RUDY_KIC else "",
                "population": "Kepler LEGACY dwarf sample",
                "selection": "high-SNR solar-like oscillator selected by Lund et al. (2017)",
                "evolutionary_scope": "main-sequence or slightly evolved subgiant",
                "numax_uHz": numax,
                "numax_error_minus_uHz": numax_minus,
                "numax_error_plus_uHz": numax_plus,
                "dnu_uHz": dnu,
                "dnu_error_minus_uHz": dnu_minus,
                "dnu_error_plus_uHz": dnu_plus,
                "teff_K": teff,
                "teff_error_K": teff_error,
                "feh_dex": feh,
                "feh_error_dex": feh_error,
                "atmosphere_reference_code": atmosphere_ref,
                "source_key": POPULATION_SOURCES,
                "source_location": (
                    "Lund et al. Paper I sample definition; publisher machine-readable "
                    "Paper II Table 3"
                ),
            }
        )
    _write_csv(output, list(rows[0]), rows)
    return source_rows


def build_targets(global_rows: Sequence[Sequence[str]], stellar_table: Path, output: Path) -> None:
    rows: list[dict[str, str]] = []

    def add(
        *,
        kic: str,
        quantity: str,
        value: str,
        unit: str,
        minus: str,
        plus: str,
        uncertainty: str,
        method: str,
        source: str,
        location: str,
        reconciliation: str,
        status: str = "benchmark",
    ) -> None:
        rows.append(
            {
                "benchmark_id": f"BT-{len(rows) + 1:04d}",
                "object_id": f"KIC {kic}",
                "object_label": "Rudy" if kic == RUDY_KIC else "",
                "sample": "Rudy" if kic == RUDY_KIC else "LEGACY",
                "quantity": quantity,
                "value": value,
                "unit": unit,
                "uncertainty_minus": minus,
                "uncertainty_plus": plus,
                "uncertainty_type": uncertainty,
                "method": method,
                "source_key": source,
                "source_location": location,
                "reconciliation": reconciliation,
                "status": status,
            }
        )

    for fields in global_rows:
        kic, numax, numax_plus, numax_minus, dnu, dnu_plus, dnu_minus = fields[:7]
        teff, teff_error, feh, feh_error, atmosphere_ref = fields[7:]
        shared = "Authoritative LEGACY population value; retain asymmetric bounds as published."
        add(
            kic=kic,
            quantity="numax",
            value=numax,
            unit="uHz",
            minus=numax_minus,
            plus=numax_plus,
            uncertainty="published confidence interval",
            method="LEGACY global seismic analysis",
            source=GLOBAL_SOURCE,
            location=GLOBAL_LOCATION,
            reconciliation=shared,
        )
        add(
            kic=kic,
            quantity="dnu",
            value=dnu,
            unit="uHz",
            minus=dnu_minus,
            plus=dnu_plus,
            uncertainty="published confidence interval",
            method="LEGACY global seismic analysis",
            source=GLOBAL_SOURCE,
            location=GLOBAL_LOCATION,
            reconciliation=shared,
        )
        add(
            kic=kic,
            quantity="teff",
            value=teff,
            unit="K",
            minus=teff_error,
            plus=teff_error,
            uncertainty="published symmetric uncertainty",
            method=f"atmospheric source code {atmosphere_ref} in Paper II Table 3",
            source=GLOBAL_SOURCE,
            location=GLOBAL_LOCATION,
            reconciliation="Use as model input, not as an output of a topological estimator.",
        )
        add(
            kic=kic,
            quantity="feh",
            value=feh,
            unit="dex",
            minus=feh_error,
            plus=feh_error,
            uncertainty="published symmetric uncertainty",
            method=f"atmospheric source code {atmosphere_ref} in Paper II Table 3",
            source=GLOBAL_SOURCE,
            location=GLOBAL_LOCATION,
            reconciliation="Use as model input, not as an output of a topological estimator.",
        )

    # The official Lightkurve worked example is deliberately recorded as a separate method.
    # It reports point estimates but no uncertainties and therefore cannot replace Table 3.
    tutorial = [
        ("numax", "2145", "uHz"),
        ("dnu", "103.11", "uHz"),
        ("mass", "1.08", "Msun"),
        ("radius", "1.23", "Rsun"),
        ("logg", "4.29", "dex(cgs)"),
    ]
    for quantity, value, unit in tutorial:
        add(
            kic=RUDY_KIC,
            quantity=quantity,
            value=value,
            unit=unit,
            minus="",
            plus="",
            uncertainty="not reported",
            method="Lightkurve first-look tutorial using Kepler Q2,Q5,Q6,Q7",
            source="LightkurveTutorial",
            location="worked-example output",
            reconciliation=(
                "Context-only first-look value; compare with the full LEGACY value and do not "
                "use as the authoritative acceptance target."
            ),
            status="context_only",
        )

    stellar_rows = _data_rows(stellar_table, 50)
    if len(stellar_rows) != 66:
        raise ValueError(f"expected 66 stellar-catalog rows; found {len(stellar_rows)}")
    rudy = next(row for row in stellar_rows if row[0] == RUDY_KIC)
    # Table 4's downloaded flat file does not encode which of the seven modelling pipelines
    # produced it. Keep the values for reconciliation, but never label them a consensus target.
    catalog_quantities = [
        ("mass", 1, 3, 2, "Msun"),
        ("radius", 4, 6, 5, "Rsun"),
        ("logg", 7, 9, 8, "dex(cgs)"),
        ("age", 10, 12, 11, "Gyr"),
        ("luminosity", 13, 15, 14, "Lsun"),
        ("density", 16, 18, 17, "g/cm3"),
        ("distance", 19, 21, 20, "pc"),
    ]
    for quantity, value_index, minus_index, plus_index, unit in catalog_quantities:
        add(
            kic=RUDY_KIC,
            quantity=quantity,
            value=rudy[value_index],
            unit=unit,
            minus=rudy[minus_index].lstrip("-"),
            plus=rudy[plus_index],
            uncertainty="published catalog interval",
            method="LEGACY Paper II online stellar-properties catalog",
            source=GLOBAL_SOURCE,
            location=STELLAR_LOCATION,
            reconciliation=(
                "Context-only: the flat file omits pipeline identity; do not interpret as the "
                "seven-pipeline consensus without publisher-side attribution."
            ),
            status="context_only",
        )

    _write_csv(output, list(rows[0]), rows)


def build_rudy_modes(mode_table: Path, output: Path) -> None:
    rows: list[dict[str, str]] = []
    for line in mode_table.read_text(encoding="utf-8").splitlines():
        if line[:8].strip() != RUDY_KIC:
            continue

        rows.append(
            {
                "object_id": f"KIC {RUDY_KIC}",
                "radial_order_n": _fixed_field(line, 9, 11),
                "angular_degree_l": _fixed_field(line, 12, 13),
                "frequency_uHz": _fixed_field(line, 14, 21),
                "frequency_error_minus_uHz": _fixed_field(line, 22, 26),
                "frequency_error_plus_uHz": _fixed_field(line, 27, 31),
                "amplitude_ppm": _fixed_field(line, 32, 36),
                "amplitude_error_minus_ppm": _fixed_field(line, 37, 41),
                "amplitude_error_plus_ppm": _fixed_field(line, 42, 46),
                "linewidth_uHz": _fixed_field(line, 47, 52),
                "linewidth_error_minus_uHz": _fixed_field(line, 53, 57),
                "linewidth_error_plus_uHz": _fixed_field(line, 58, 62),
                "ln_k_limit": _fixed_field(line, 63, 64),
                "ln_k": _fixed_field(line, 64, 70),
                "source_key": MODE_SOURCE,
                "source_location": MODE_LOCATION,
            }
        )
    if len(rows) != 42:
        raise ValueError(f"expected 42 Rudy modes; found {len(rows)}")
    _write_csv(output, list(rows[0]), rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-table", type=Path, required=True)
    parser.add_argument("--stellar-table", type=Path, required=True)
    parser.add_argument("--mode-table", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/benchmarks"))
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    global_rows = build_population(args.global_table, args.output_dir / "legacy_population.csv")
    build_targets(global_rows, args.stellar_table, args.output_dir / "benchmark_targets.csv")
    build_rudy_modes(args.mode_table, args.output_dir / "rudy_mode_frequencies.csv")


if __name__ == "__main__":
    main()
