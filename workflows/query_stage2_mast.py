"""Freeze the Stage 2 Rudy MAST query and inspect downloaded FITS products.

This is an acquisition workflow, not an offline contract check.  Run it in an isolated
environment with ``lightkurve`` and ``astropy`` installed.  The checked-in manifest is the
dated result; routine validation never contacts MAST.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import time
import urllib.parse
import urllib.request
from collections.abc import Iterable, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

from topoastero.portability import write_csv_lf, write_json_lf

QUERY_DATE = "2026-09-20"
RUDY_KIC = "10963065"
RUDY_TIC = "48450369"
TESS_AUTHORS = {"SPOC", "TESS-SPOC", "QLP"}
FIELDS = [
    "product_key",
    "stable_star_id",
    "mission",
    "segment",
    "segment_number",
    "author",
    "product_type",
    "cadence_class",
    "cadence_seconds",
    "exposure_seconds",
    "flux_column",
    "flux_unit",
    "uncertainty_column",
    "uncertainty_unit",
    "quality_column",
    "time_column",
    "time_system",
    "time_unit",
    "bjd_reference",
    "time_start",
    "time_stop",
    "row_count",
    "finite_flux_rows",
    "finite_uncertainty_rows",
    "nonphysical_uncertainty_rows",
    "quality_zero_rows",
    "duplicate_time_rows",
    "time_order_violations",
    "missing_cadence_gaps",
    "crowding_metric",
    "flux_fraction",
    "spectral_window_status",
    "unit_status",
    "aperture_provenance",
    "mast_obs_id",
    "mast_obsid",
    "mast_parent_obsid",
    "mast_product_objid",
    "product_filename",
    "data_uri",
    "size_bytes",
    "sha256",
    "query_id",
    "query_date_utc",
    "acquisition_status",
    "notes",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    if value is None or getattr(value, "mask", False) is True:
        return ""
    return str(value)


def _download(data_uri: str, destination: Path, expected_size: int) -> None:
    if destination.is_file() and destination.stat().st_size == expected_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    endpoint = "https://mast.stsci.edu/api/v0.1/Download/file?uri="
    url = endpoint + urllib.parse.quote(data_uri, safe="")
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if temporary.stat().st_size != expected_size:
                raise OSError(
                    f"size mismatch for {destination.name}: "
                    f"{temporary.stat().st_size} != {expected_size}"
                )
            temporary.replace(destination)
            return
        except (OSError, urllib.error.URLError):
            temporary.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep(float(attempt))


def _header_value(headers: Iterable[Any], key: str) -> Any:
    for header in headers:
        if key in header:
            return header[key]
    return ""


def _float_text(value: Any, digits: int = 12) -> str:
    if value in (None, ""):
        return ""
    numeric = float(value)
    if not math.isfinite(numeric):
        return ""
    return f"{numeric:.{digits}g}"


def _inspect_fits(path: Path, author: str) -> dict[str, str]:
    import numpy as np
    from astropy.io import fits

    with fits.open(path, memmap=True) as hdus:
        table_hdu = next(hdu for hdu in hdus if getattr(hdu, "columns", None) is not None)
        headers = [table_hdu.header, hdus[0].header]
        names = list(table_hdu.columns.names)
        data = table_hdu.data
        flux_column = next(
            (
                name
                for name in ("PDCSAP_FLUX", "KSPSAP_FLUX", "SAP_FLUX", "DET_FLUX")
                if name in names
            ),
            "",
        )
        uncertainty_column = next(
            (
                name
                for name in (
                    f"{flux_column}_ERR",
                    "PDCSAP_FLUX_ERR",
                    "KSPSAP_FLUX_ERR",
                    "SAP_FLUX_ERR",
                )
                if name in names
            ),
            "",
        )
        quality_column = next(
            (name for name in ("SAP_QUALITY", "QUALITY", "DQUALITY") if name in names), ""
        )
        time_column = next((name for name in ("TIME", "TMID_BJD") if name in names), "")
        times = np.asarray(data[time_column], dtype=float) if time_column else np.array([])
        finite_times = np.sort(times[np.isfinite(times)])
        flux = np.asarray(data[flux_column], dtype=float) if flux_column else np.array([])
        uncertainty = (
            np.asarray(data[uncertainty_column], dtype=float)
            if uncertainty_column
            else np.array([])
        )
        original_finite_times = times[np.isfinite(times)]
        deltas_seconds = np.diff(finite_times) * 86400.0
        original_deltas = np.diff(original_finite_times)
        positive = deltas_seconds[deltas_seconds > 0]
        median_cadence = float(np.median(positive)) if len(positive) else math.nan
        missing_gaps = (
            int(np.count_nonzero(positive > 1.5 * median_cadence))
            if math.isfinite(median_cadence)
            else 0
        )
        if quality_column:
            quality = np.asarray(data[quality_column])
            quality_zero_rows = int(np.count_nonzero(quality == 0))
        else:
            quality_zero_rows = 0
        bjdrefi = float(_header_value(headers, "BJDREFI") or 0)
        bjdreff = float(_header_value(headers, "BJDREFF") or 0)
        cadence_header = _header_value(headers, "TIMEDEL")
        cadence_seconds = (
            float(cadence_header) * 86400.0 if cadence_header not in (None, "") else median_cadence
        )
        exposure = _header_value(headers, "EXPOSURE")
        if exposure in (None, ""):
            exposure = _header_value(headers, "INT_TIME")
        if exposure in (None, ""):
            exposure = cadence_seconds
        if author == "SPOC":
            aperture_note = "SPOC pipeline optimal aperture"
        elif author == "TESS-SPOC":
            aperture_note = "TESS-SPOC FFI pipeline aperture"
        elif author == "QLP":
            aperture_note = "QLP FFI aperture"
        else:
            aperture_note = "Kepler pipeline optimal aperture"
        return {
            "cadence_seconds": _float_text(cadence_seconds, 10),
            "exposure_seconds": _float_text(exposure, 10),
            "flux_column": flux_column,
            "flux_unit": (
                _text(table_hdu.columns[flux_column].unit) if flux_column else "not_provided"
            )
            or "dimensionless_or_header_unspecified",
            "uncertainty_column": uncertainty_column or "not_provided",
            "uncertainty_unit": (
                _text(table_hdu.columns[uncertainty_column].unit)
                if uncertainty_column
                else "not_provided"
            )
            or "dimensionless_or_header_unspecified",
            "quality_column": quality_column,
            "time_column": time_column,
            "time_system": _text(_header_value(headers, "TIMESYS")),
            "time_unit": _text(_header_value(headers, "TIMEUNIT")) or "d",
            "bjd_reference": _float_text(bjdrefi + bjdreff, 12),
            "time_start": _float_text(finite_times[0] if len(finite_times) else "", 14),
            "time_stop": _float_text(finite_times[-1] if len(finite_times) else "", 14),
            "row_count": str(len(data)),
            "finite_flux_rows": str(int(np.count_nonzero(np.isfinite(flux)))),
            "finite_uncertainty_rows": str(
                int(np.count_nonzero(np.isfinite(uncertainty))) if uncertainty_column else 0
            ),
            "nonphysical_uncertainty_rows": str(
                int(np.count_nonzero(np.isfinite(uncertainty) & (uncertainty < 0)))
                if uncertainty_column
                else 0
            ),
            "quality_zero_rows": str(quality_zero_rows),
            "duplicate_time_rows": str(int(np.count_nonzero(original_deltas == 0))),
            "time_order_violations": str(int(np.count_nonzero(original_deltas < 0))),
            "missing_cadence_gaps": str(missing_gaps),
            "crowding_metric": (
                _float_text(_header_value(headers, "CROWDSAP"), 10) or "not_provided"
            ),
            "flux_fraction": (
                _float_text(_header_value(headers, "FLFRCSAP"), 10) or "not_provided"
            ),
            "spectral_window_status": "cadence_gaps_counted_from_finite_time_axis",
            "unit_status": "FITS_column_units_and_time_reference_recorded",
            "aperture_provenance": aperture_note,
            "notes": (
                "source has no per-cadence uncertainty column"
                if not uncertainty_column
                else "source uncertainty column recorded"
            ),
        }


def _segment_number(mission: str) -> int:
    return int(mission.rsplit(" ", maxsplit=1)[-1])


def _cadence_class(mission: str, seconds: float) -> str:
    if mission.startswith("Kepler"):
        return "short"
    if seconds <= 120:
        return "target_2min"
    return "ffi"


def _product_key(prefix: str, row: Any) -> str:
    segment = _segment_number(_text(row["mission"]))
    author = _text(row["author"]).upper().replace("-", "_")
    objid = _text(row["objID"])
    filename_token = hashlib.sha256(_text(row["productFilename"]).encode()).hexdigest()[:12]
    return f"{prefix}-{segment:02d}-{author}-{objid}-{filename_token}"


def _manifest_row(row: Any, cache: Path, prefix: str, query_id: str) -> dict[str, str]:
    filename = _text(row["productFilename"])
    data_uri = _text(row["dataURI"])
    expected_size = int(row["size"])
    path = cache / filename
    _download(data_uri, path, expected_size)
    inspected = _inspect_fits(path, _text(row["author"]))
    mission = _text(row["mission"])
    cadence_seconds = float(inspected["cadence_seconds"])
    result = {
        "product_key": _product_key(prefix, row),
        "stable_star_id": f"KIC {RUDY_KIC}",
        "mission": "Kepler" if mission.startswith("Kepler") else "TESS",
        "segment": "quarter" if mission.startswith("Kepler") else "sector",
        "segment_number": str(_segment_number(mission)),
        "author": _text(row["author"]),
        "product_type": "pipeline_light_curve",
        "cadence_class": _cadence_class(mission, cadence_seconds),
        **inspected,
        "mast_obs_id": _text(row["obs_id"]),
        "mast_obsid": _text(row["obsid"]),
        "mast_parent_obsid": _text(row["parent_obsid"]),
        "mast_product_objid": _text(row["objID"]),
        "product_filename": filename,
        "data_uri": data_uri,
        "size_bytes": str(expected_size),
        "sha256": _sha256(path),
        "query_id": query_id,
        "query_date_utc": QUERY_DATE,
        "acquisition_status": "verified_payload_not_redistributed",
    }
    return {field: result.get(field, "") for field in FIELDS}


def _write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    write_csv_lf(path, rows, fieldnames=FIELDS)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/manifests/stage2")
    parser.add_argument("--cache-dir", required=True)
    args = parser.parse_args(argv)

    import lightkurve as lk

    output = Path(args.output_dir)
    cache = Path(args.cache_dir)
    kepler_result = lk.search_lightcurve(
        f"KIC {RUDY_KIC}", cadence="short", author="Kepler", quarter=(2, 5, 6, 7)
    )
    tess_result = lk.search_lightcurve(f"TIC {RUDY_TIC}", mission="TESS")
    tess_rows = [row for row in tess_result.table if _text(row["author"]) in TESS_AUTHORS]
    kepler_rows = [
        _manifest_row(row, cache / "kepler", "KPLR-RUDY-Q", "MAST-QRY-RUDY-KEPLER-20260920")
        for row in kepler_result.table
    ]
    tess_manifest = [
        _manifest_row(row, cache / "tess", "TESS-RUDY-S", "MAST-QRY-RUDY-TESS-20260920")
        for row in tess_rows
    ]
    _write_csv(output / "rudy_kepler_products.csv", kepler_rows)
    _write_csv(output / "rudy_tess_products.csv", tess_manifest)
    snapshot = {
        "schema_version": 1,
        "query_date_utc": QUERY_DATE,
        "target": {"kic": RUDY_KIC, "tic": RUDY_TIC},
        "software": {
            "lightkurve": version("lightkurve"),
            "astropy": version("astropy"),
        },
        "queries": [
            {
                "query_id": "MAST-QRY-RUDY-KEPLER-20260920",
                "expression": (
                    "search_lightcurve('KIC 10963065', cadence='short', "
                    "author='Kepler', quarter=(2,5,6,7))"
                ),
                "returned_products": len(kepler_rows),
                "selection": "all returned products",
            },
            {
                "query_id": "MAST-QRY-RUDY-TESS-20260920",
                "expression": "search_lightcurve('TIC 48450369', mission='TESS')",
                "returned_products_all_authors": len(tess_result),
                "selected_products": len(tess_manifest),
                "selection": "author in {SPOC,TESS-SPOC,QLP}",
            },
        ],
        "payload_policy": (
            "FITS payloads were downloaded to an external cache for checksum/header/QC "
            "inspection and are not redistributed in this repository."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json_lf(output / "mast_query_snapshot.json", snapshot)


if __name__ == "__main__":
    main()
