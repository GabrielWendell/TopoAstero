"""Build small canonical JSONL examples, including an exact verified FITS excerpt."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from topoastero.config import configuration_hash
from topoastero.data_model import (
    DerivedProvenance,
    LightCurveRow,
    Mission,
    ModeFrequencyRow,
    SpectrumRow,
    StellarReferenceRow,
)
from topoastero.portability import write_text_lf

ROOT = Path(__file__).parents[1]


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    write_text_lf(path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _first_manifest_row() -> dict[str, str]:
    path = ROOT / "data/manifests/stage2/rudy_kepler_products.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def build_light_curve(cache_dir: Path, config_hash: str) -> list[LightCurveRow]:
    import numpy as np
    from astropy.io import fits

    manifest = _first_manifest_row()
    candidates = list(cache_dir.rglob(manifest["product_filename"]))
    if len(candidates) != 1:
        raise ValueError(f"expected one cached {manifest['product_filename']}; found {len(candidates)}")
    with fits.open(candidates[0], memmap=True) as hdus:
        data = hdus[1].data
        time = np.asarray(data[manifest["time_column"]], dtype=float)
        flux = np.asarray(data[manifest["flux_column"]], dtype=float)
        uncertainty = np.asarray(data[manifest["uncertainty_column"]], dtype=float)
        quality = np.asarray(data[manifest["quality_column"]], dtype=int)
        finite = np.flatnonzero(np.isfinite(time) & np.isfinite(flux) & np.isfinite(uncertainty))[:3]
    provenance = DerivedProvenance(
        raw_product_ids=(manifest["product_key"],),
        config_sha256=config_hash,
        software_version="TopoAstero-0.3.0",
    )
    return [
        LightCurveRow(
            row_id=f"LC-RUDY-Q02-{number:04d}",
            stable_star_id="KIC 10963065",
            time_bjd=float(time[index]) + float(manifest["bjd_reference"]),
            flux=float(flux[index]),
            flux_uncertainty=float(uncertainty[index]),
            quality=int(quality[index]),
            cadence_seconds=float(manifest["cadence_seconds"]),
            cadence_class="short",
            mission=Mission.KEPLER,
            segment_id="quarter-02",
            aperture_or_product=manifest["aperture_provenance"],
            mask_reason="retained_quality_zero" if quality[index] == 0 else "retained_flagged_sample",
            preprocessing_state="archive_PDCSAP_FLUX_no_project_transform",
            provenance=provenance,
        )
        for number, index in enumerate(finite, start=1)
    ]


def build_spectrum(config_hash: str) -> list[SpectrumRow]:
    provenance = DerivedProvenance(
        raw_product_ids=("PROJECT-GENERATED-SPECTRUM-FIXTURE",),
        config_sha256=config_hash,
        software_version="TopoAstero-0.3.0",
        source_row_ids=("LC-SYNTHETIC-0001",),
    )
    values = ((1000.0, 0.025), (1050.0, 0.2), (1100.0, 0.04))
    return [
        SpectrumRow(
            row_id=f"SPEC-FIXTURE-{index:04d}",
            stable_star_id="SIM fixture-star-001",
            frequency_uHz=frequency,
            power=power,
            power_unit="ppm^2/uHz",
            normalization="one_sided_psd",
            nyquist_uHz=8496.2,
            window_id="continuous-58.84876286s-v1",
            background_components=("white_noise", "single_harvey"),
            provenance=provenance,
        )
        for index, (frequency, power) in enumerate(values, start=1)
    ]


def build_modes(config_hash: str) -> list[ModeFrequencyRow]:
    path = ROOT / "data/reference/mode_frequencies.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle))[:3]
    return [
        ModeFrequencyRow(
            row_id=row["row_id"],
            stable_star_id=row["stable_star_id"],
            radial_order_n=int(row["radial_order_n"]),
            angular_degree_l=int(row["angular_degree_l"]),
            frequency_uHz=float(row["frequency_uHz"]),
            uncertainty_minus_uHz=float(row["uncertainty_minus_uHz"]),
            uncertainty_plus_uHz=float(row["uncertainty_plus_uHz"]),
            source_id=row["source_id"],
            source_version=row["source_version"],
            provenance=DerivedProvenance(
                raw_product_ids=(row["raw_product_ids"],),
                config_sha256=config_hash,
                software_version=row["software_version"],
                source_row_ids=(row["source_row_ids"],),
            ),
        )
        for row in source
    ]


def build_stellar(config_hash: str) -> list[StellarReferenceRow]:
    path = ROOT / "data/reference/stellar_references.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        source = list(csv.DictReader(handle))[:3]
    return [
        StellarReferenceRow(
            row_id=row["row_id"],
            stable_star_id=row["stable_star_id"],
            quantity=row["quantity"],
            value=float(row["value"]),
            unit=row["unit"],
            uncertainty_minus=float(row["uncertainty_minus"]),
            uncertainty_plus=float(row["uncertainty_plus"]),
            source_id=row["source_id"],
            source_version=row["source_version"],
            provenance=DerivedProvenance(
                raw_product_ids=(row["raw_product_ids"],),
                config_sha256=config_hash,
                software_version=row["software_version"],
                source_row_ids=(row["source_row_ids"],),
            ),
        )
        for row in source
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True)
    args = parser.parse_args()
    config_hash = configuration_hash(ROOT / "configs/stage2_data.yaml")
    output = ROOT / "data/canonical/examples"
    _jsonl(
        output / "light_curve.jsonl",
        [row.to_dict() for row in build_light_curve(Path(args.cache_dir), config_hash)],
    )
    _jsonl(output / "spectrum.jsonl", [row.to_dict() for row in build_spectrum(config_hash)])
    _jsonl(output / "mode_frequency.jsonl", [row.to_dict() for row in build_modes(config_hash)])
    _jsonl(
        output / "stellar_reference.jsonl",
        [row.to_dict() for row in build_stellar(config_hash)],
    )


if __name__ == "__main__":
    main()
