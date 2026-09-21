from __future__ import annotations

from dataclasses import replace

import pytest

from topoastero.data_model import (
    DerivedProvenance,
    LightCurveRow,
    Mission,
    ModeFrequencyRow,
    SpectrumRow,
    StellarReferenceRow,
    duplicate_values,
    validate_mission_product,
    validate_monotonic_segments,
    validate_population_partitions,
)

HASH = "a" * 64


def provenance() -> DerivedProvenance:
    return DerivedProvenance(("RAW-1",), HASH, "TopoAstero-0.3.0", ("SRC-1",))


def light_curve() -> LightCurveRow:
    return LightCurveRow(
        row_id="LC-1",
        stable_star_id="KIC 10963065",
        time_bjd=2455000.0,
        flux=1.0,
        flux_uncertainty=0.01,
        quality=0,
        cadence_seconds=58.85,
        cadence_class="short",
        mission=Mission.KEPLER,
        segment_id="quarter-02",
        aperture_or_product="pipeline aperture",
        mask_reason="retained_quality_zero",
        preprocessing_state="raw",
        provenance=provenance(),
    )


def test_all_canonical_records_round_trip() -> None:
    light = light_curve()
    spectrum = SpectrumRow(
        "SP-1",
        "KIC 10963065",
        1000.0,
        0.5,
        "ppm^2/uHz",
        "one_sided_psd",
        8496.0,
        "WIN-1",
        ("white_noise",),
        provenance(),
    )
    mode = ModeFrequencyRow(
        "M-1", "KIC 10963065", 14, 1, 1500.0, 0.1, 0.2, "paper", "v1", provenance()
    )
    stellar = StellarReferenceRow(
        "R-1", "KIC 10963065", "numax", 2203.7, "uHz", 10.0, 10.0, "paper", "v1", provenance()
    )
    assert LightCurveRow.from_dict(light.to_dict()) == light
    assert SpectrumRow.from_dict(spectrum.to_dict()) == spectrum
    assert ModeFrequencyRow.from_dict(mode.to_dict()) == mode
    assert StellarReferenceRow.from_dict(stellar.to_dict()) == stellar
    assert DerivedProvenance.from_dict(provenance().to_dict()) == provenance()


@pytest.mark.parametrize(
    "factory,match",
    [
        (lambda: DerivedProvenance((), HASH, "v1"), "raw_product_ids"),
        (lambda: DerivedProvenance(("RAW",), "bad", "v1"), "config_sha256"),
        (lambda: DerivedProvenance(("RAW",), HASH, ""), "software_version"),
        (lambda: replace(light_curve(), time_bjd=float("nan")), "time_bjd"),
        (lambda: replace(light_curve(), flux=float("inf")), "flux"),
        (lambda: replace(light_curve(), flux_uncertainty=-0.1), "nonnegative"),
        (lambda: replace(light_curve(), quality=-1), "quality"),
        (lambda: replace(light_curve(), cadence_seconds=0), "cadence_seconds"),
        (
            lambda: replace(light_curve(), cadence_class="ffi"),
            "invalid mission/cadence pair",
        ),
        (lambda: replace(light_curve(), row_id=""), "row_id"),
    ],
)
def test_light_curve_and_provenance_reject_invalid_values(factory: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        factory()  # type: ignore[operator]


def test_spectrum_mode_and_stellar_invariants() -> None:
    with pytest.raises(ValueError, match="nyquist_uHz"):
        SpectrumRow("S", "K", 1.0, 1.0, "u", "one_sided_psd", 0.0, "W", ("b",), provenance())
    with pytest.raises(ValueError, match="frequency_uHz cannot exceed"):
        SpectrumRow("S", "K", 2.0, 1.0, "u", "one_sided_psd", 1.0, "W", ("b",), provenance())
    with pytest.raises(ValueError, match="normalization"):
        SpectrumRow("S", "K", 1.0, 1.0, "u", "unknown", 2.0, "W", ("b",), provenance())
    with pytest.raises(ValueError, match="background_components"):
        SpectrumRow("S", "K", 1.0, 1.0, "u", "one_sided_psd", 2.0, "W", (), provenance())
    with pytest.raises(ValueError, match="mode indices"):
        ModeFrequencyRow("M", "K", -1, 0, 1.0, 0.1, 0.1, "p", "v", provenance())
    with pytest.raises(ValueError, match="frequency_uHz"):
        ModeFrequencyRow("M", "K", 1, 0, 0.0, 0.1, 0.1, "p", "v", provenance())
    with pytest.raises(ValueError, match="uncertainty_minus"):
        StellarReferenceRow("R", "K", "q", 1.0, "u", -1.0, 1.0, "p", "v", provenance())


def test_time_is_strictly_monotonic_within_each_segment() -> None:
    first = light_curve()
    second = replace(first, row_id="LC-2", time_bjd=first.time_bjd + 0.001)
    other = replace(first, row_id="LC-3", segment_id="quarter-05", time_bjd=1.0)
    assert validate_monotonic_segments([first, second, other]) == []
    errors = validate_monotonic_segments([first, replace(first, row_id="LC-2")])
    assert any("non-monotonic" in error for error in errors)
    assert validate_monotonic_segments([first, first])[0].startswith("duplicate")


def test_duplicate_and_partition_guards() -> None:
    assert duplicate_values([{"id": "x"}, {"id": "x"}, {"id": ""}], "id") == {"x"}
    valid = [
        {"stable_star_id": "KIC 1", "role": "development"},
        {"stable_star_id": "KIC 10963065", "role": "descriptive_benchmark"},
    ]
    assert validate_population_partitions(valid) == []
    invalid = [
        {"stable_star_id": "KIC 1", "role": "development"},
        {"stable_star_id": "KIC 1", "role": "final_holdout"},
        {"stable_star_id": "KIC 2", "role": "invalid_role"},
        {"stable_star_id": "", "role": "bad"},
        {"stable_star_id": "KIC 10963065", "role": "development"},
    ]
    errors = validate_population_partitions(invalid)
    assert any("multiple roles" in error for error in errors)
    assert any("blank" in error for error in errors)
    assert any("Rudy" in error for error in errors)


def valid_product() -> dict[str, str]:
    return {
        "product_key": "P-1",
        "stable_star_id": "KIC 1",
        "mission": "Kepler",
        "segment": "quarter",
        "author": "Kepler",
        "cadence_class": "short",
        "cadence_seconds": "58.8",
        "exposure_seconds": "50",
        "flux_column": "PDCSAP_FLUX",
        "flux_unit": "e-/s",
        "uncertainty_column": "PDCSAP_FLUX_ERR",
        "uncertainty_unit": "e-/s",
        "quality_column": "SAP_QUALITY",
        "time_system": "TDB",
        "row_count": "10",
        "finite_flux_rows": "9",
        "finite_uncertainty_rows": "9",
        "nonphysical_uncertainty_rows": "0",
        "duplicate_time_rows": "0",
        "time_order_violations": "0",
        "time_start": "1",
        "time_stop": "2",
        "size_bytes": "100",
        "sha256": HASH,
        "data_uri": "mast:x",
        "query_id": "Q-1",
        "unit_status": "recorded",
        "aperture_provenance": "pipeline",
    }


def test_mission_product_validation() -> None:
    assert validate_mission_product(valid_product()) == []
    for field, value, message in (
        ("cadence_class", "ffi", "mission/cadence"),
        ("cadence_seconds", "0", "cadence_seconds"),
        ("exposure_seconds", "0", "exposure_seconds"),
        ("size_bytes", "0", "size_bytes"),
        ("finite_flux_rows", "11", "row counts"),
        ("finite_uncertainty_rows", "11", "uncertainty row counts"),
        ("nonphysical_uncertainty_rows", "1", "nonphysical"),
        ("duplicate_time_rows", "1", "duplicate timestamps"),
        ("time_order_violations", "1", "time-order"),
        ("time_start", "2", "coverage"),
        ("sha256", "bad", "SHA-256"),
        ("flux_unit", "", "blank flux_unit"),
    ):
        record = valid_product()
        record[field] = value
        assert any(message in error for error in validate_mission_product(record))
    malformed = valid_product()
    malformed.pop("mission")
    assert "malformed" in validate_mission_product(malformed)[0]
