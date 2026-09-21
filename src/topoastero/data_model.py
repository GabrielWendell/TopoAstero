"""Canonical Stage 2 data records and invariant checks.

The classes deliberately use only the Python standard library.  Mission readers may depend on
larger astronomy packages, but the durable interchange contract and its validation stay usable
offline and in minimal CI environments.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Self

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class Mission(StrEnum):
    """Mission names admitted by the canonical observational schemas."""

    KEPLER = "Kepler"
    TESS = "TESS"
    SIMULATION = "simulation"


MISSION_CADENCES: dict[Mission, frozenset[str]] = {
    Mission.KEPLER: frozenset({"short", "long"}),
    Mission.TESS: frozenset({"target_20s", "target_2min", "ffi"}),
    Mission.SIMULATION: frozenset({"synthetic"}),
}


def _finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _nonempty(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _nonnegative(value: float, name: str) -> None:
    _finite(value, name)
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _mission_cadence(mission: Mission, cadence_class: str) -> None:
    if cadence_class not in MISSION_CADENCES[mission]:
        raise ValueError(f"invalid mission/cadence pair: {mission.value}/{cadence_class}")


@dataclass(frozen=True, slots=True)
class DerivedProvenance:
    """Minimum lineage carried by every derived canonical row."""

    raw_product_ids: tuple[str, ...]
    config_sha256: str
    software_version: str
    source_row_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.raw_product_ids or any(not value.strip() for value in self.raw_product_ids):
            raise ValueError("raw_product_ids must contain at least one non-empty ID")
        if SHA256_PATTERN.fullmatch(self.config_sha256) is None:
            raise ValueError("config_sha256 must be a lowercase SHA-256 digest")
        _nonempty(self.software_version, "software_version")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        return cls(
            raw_product_ids=tuple(str(item) for item in value["raw_product_ids"]),
            config_sha256=str(value["config_sha256"]),
            software_version=str(value["software_version"]),
            source_row_ids=tuple(str(item) for item in value.get("source_row_ids", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LightCurveRow:
    """One canonical light-curve sample after a named preprocessing state."""

    row_id: str
    stable_star_id: str
    time_bjd: float
    flux: float
    flux_uncertainty: float
    quality: int
    cadence_seconds: float
    cadence_class: str
    mission: Mission
    segment_id: str
    aperture_or_product: str
    mask_reason: str
    preprocessing_state: str
    provenance: DerivedProvenance

    def __post_init__(self) -> None:
        for name in (
            "row_id",
            "stable_star_id",
            "segment_id",
            "aperture_or_product",
            "mask_reason",
            "preprocessing_state",
        ):
            _nonempty(str(getattr(self, name)), name)
        _finite(self.time_bjd, "time_bjd")
        _finite(self.flux, "flux")
        _nonnegative(self.flux_uncertainty, "flux_uncertainty")
        if self.quality < 0:
            raise ValueError("quality must be nonnegative")
        if not math.isfinite(self.cadence_seconds) or self.cadence_seconds <= 0:
            raise ValueError("cadence_seconds must be finite and positive")
        _mission_cadence(self.mission, self.cadence_class)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        return cls(
            row_id=str(value["row_id"]),
            stable_star_id=str(value["stable_star_id"]),
            time_bjd=float(value["time_bjd"]),
            flux=float(value["flux"]),
            flux_uncertainty=float(value["flux_uncertainty"]),
            quality=int(value["quality"]),
            cadence_seconds=float(value["cadence_seconds"]),
            cadence_class=str(value["cadence_class"]),
            mission=Mission(str(value["mission"])),
            segment_id=str(value["segment_id"]),
            aperture_or_product=str(value["aperture_or_product"]),
            mask_reason=str(value["mask_reason"]),
            preprocessing_state=str(value["preprocessing_state"]),
            provenance=DerivedProvenance.from_dict(value["provenance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["mission"] = self.mission.value
        return result


@dataclass(frozen=True, slots=True)
class SpectrumRow:
    """One frequency bin with an explicit spectral convention and lineage."""

    row_id: str
    stable_star_id: str
    frequency_uHz: float
    power: float
    power_unit: str
    normalization: str
    nyquist_uHz: float
    window_id: str
    background_components: tuple[str, ...]
    provenance: DerivedProvenance

    def __post_init__(self) -> None:
        for name in ("row_id", "stable_star_id", "power_unit", "window_id"):
            _nonempty(str(getattr(self, name)), name)
        _nonnegative(self.frequency_uHz, "frequency_uHz")
        _nonnegative(self.power, "power")
        if not math.isfinite(self.nyquist_uHz) or self.nyquist_uHz <= 0:
            raise ValueError("nyquist_uHz must be finite and positive")
        if self.frequency_uHz > self.nyquist_uHz:
            raise ValueError("frequency_uHz cannot exceed nyquist_uHz")
        allowed = {"one_sided_psd", "two_sided_psd", "amplitude_spectrum"}
        if self.normalization not in allowed:
            raise ValueError(f"normalization must be one of {sorted(allowed)}")
        if not self.background_components:
            raise ValueError("background_components cannot be empty")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        return cls(
            row_id=str(value["row_id"]),
            stable_star_id=str(value["stable_star_id"]),
            frequency_uHz=float(value["frequency_uHz"]),
            power=float(value["power"]),
            power_unit=str(value["power_unit"]),
            normalization=str(value["normalization"]),
            nyquist_uHz=float(value["nyquist_uHz"]),
            window_id=str(value["window_id"]),
            background_components=tuple(str(item) for item in value["background_components"]),
            provenance=DerivedProvenance.from_dict(value["provenance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModeFrequencyRow:
    """Canonical published or derived oscillation-mode reference."""

    row_id: str
    stable_star_id: str
    radial_order_n: int
    angular_degree_l: int
    frequency_uHz: float
    uncertainty_minus_uHz: float
    uncertainty_plus_uHz: float
    source_id: str
    source_version: str
    provenance: DerivedProvenance

    def __post_init__(self) -> None:
        for name in ("row_id", "stable_star_id", "source_id", "source_version"):
            _nonempty(str(getattr(self, name)), name)
        if self.radial_order_n < 0 or self.angular_degree_l < 0:
            raise ValueError("mode indices must be nonnegative")
        if not math.isfinite(self.frequency_uHz) or self.frequency_uHz <= 0:
            raise ValueError("frequency_uHz must be finite and positive")
        _nonnegative(self.uncertainty_minus_uHz, "uncertainty_minus_uHz")
        _nonnegative(self.uncertainty_plus_uHz, "uncertainty_plus_uHz")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        return cls(
            row_id=str(value["row_id"]),
            stable_star_id=str(value["stable_star_id"]),
            radial_order_n=int(value["radial_order_n"]),
            angular_degree_l=int(value["angular_degree_l"]),
            frequency_uHz=float(value["frequency_uHz"]),
            uncertainty_minus_uHz=float(value["uncertainty_minus_uHz"]),
            uncertainty_plus_uHz=float(value["uncertainty_plus_uHz"]),
            source_id=str(value["source_id"]),
            source_version=str(value["source_version"]),
            provenance=DerivedProvenance.from_dict(value["provenance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StellarReferenceRow:
    """Canonical stellar/global reference value with asymmetric uncertainty."""

    row_id: str
    stable_star_id: str
    quantity: str
    value: float
    unit: str
    uncertainty_minus: float
    uncertainty_plus: float
    source_id: str
    source_version: str
    provenance: DerivedProvenance

    def __post_init__(self) -> None:
        for name in (
            "row_id",
            "stable_star_id",
            "quantity",
            "unit",
            "source_id",
            "source_version",
        ):
            _nonempty(str(getattr(self, name)), name)
        _finite(self.value, "value")
        _nonnegative(self.uncertainty_minus, "uncertainty_minus")
        _nonnegative(self.uncertainty_plus, "uncertainty_plus")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Self:
        return cls(
            row_id=str(value["row_id"]),
            stable_star_id=str(value["stable_star_id"]),
            quantity=str(value["quantity"]),
            value=float(value["value"]),
            unit=str(value["unit"]),
            uncertainty_minus=float(value["uncertainty_minus"]),
            uncertainty_plus=float(value["uncertainty_plus"]),
            source_id=str(value["source_id"]),
            source_version=str(value["source_version"]),
            provenance=DerivedProvenance.from_dict(value["provenance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_monotonic_segments(rows: Sequence[LightCurveRow]) -> list[str]:
    """Return ordering/duplication errors without reordering the caller's rows."""
    errors: list[str] = []
    seen_rows: set[str] = set()
    previous: dict[tuple[str, Mission, str], float] = {}
    for row in rows:
        if row.row_id in seen_rows:
            errors.append(f"duplicate light-curve row_id: {row.row_id}")
        seen_rows.add(row.row_id)
        key = (row.stable_star_id, row.mission, row.segment_id)
        if key in previous and row.time_bjd <= previous[key]:
            errors.append(
                f"non-monotonic time in {row.stable_star_id}/{row.mission.value}/{row.segment_id}"
            )
        previous[key] = row.time_bjd
    return errors


def duplicate_values(records: Iterable[Mapping[str, str]], field: str) -> set[str]:
    """Return duplicate non-empty values from a sequence of flat records."""
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        value = record.get(field, "")
        if value:
            counts[value] += 1
    return {value for value, count in counts.items() if count > 1}


def validate_mission_product(record: Mapping[str, str]) -> list[str]:
    """Validate one frozen MAST product record independently of network access."""
    errors: list[str] = []
    key = record.get("product_key", "<missing>")
    try:
        mission = Mission(record["mission"])
        cadence = record["cadence_class"]
        _mission_cadence(mission, cadence)
        if float(record["cadence_seconds"]) <= 0:
            errors.append(f"{key}: cadence_seconds must be positive")
        if float(record["exposure_seconds"]) <= 0:
            errors.append(f"{key}: exposure_seconds must be positive")
        if int(record["size_bytes"]) <= 0:
            errors.append(f"{key}: size_bytes must be positive")
        row_count = int(record["row_count"])
        finite_rows = int(record["finite_flux_rows"])
        if row_count <= 0 or not 0 <= finite_rows <= row_count:
            errors.append(f"{key}: invalid row counts")
        finite_uncertainty = int(record["finite_uncertainty_rows"])
        if not 0 <= finite_uncertainty <= row_count:
            errors.append(f"{key}: invalid uncertainty row counts")
        if int(record["nonphysical_uncertainty_rows"]) != 0:
            errors.append(f"{key}: nonphysical uncertainties detected")
        if int(record["duplicate_time_rows"]) != 0:
            errors.append(f"{key}: duplicate timestamps detected")
        if int(record["time_order_violations"]) != 0:
            errors.append(f"{key}: time-order violations detected")
        if float(record["time_start"]) >= float(record["time_stop"]):
            errors.append(f"{key}: time coverage is not increasing")
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"{key}: malformed mission product ({exc})")
    if SHA256_PATTERN.fullmatch(record.get("sha256", "")) is None:
        errors.append(f"{key}: invalid SHA-256")
    for required in (
        "stable_star_id",
        "segment",
        "author",
        "flux_column",
        "flux_unit",
        "uncertainty_column",
        "uncertainty_unit",
        "quality_column",
        "time_system",
        "data_uri",
        "query_id",
        "unit_status",
        "aperture_provenance",
    ):
        if not record.get(required, "").strip():
            errors.append(f"{key}: blank {required}")
    return errors


def validate_population_partitions(records: Sequence[Mapping[str, str]]) -> list[str]:
    """Reject cross-role leakage and malformed star-grouped assignments."""
    errors: list[str] = []
    roles_by_star: dict[str, set[str]] = defaultdict(set)
    allowed = {"development", "internal_validation", "final_holdout", "descriptive_benchmark"}
    for record in records:
        star = record.get("stable_star_id", "").strip()
        role = record.get("role", "").strip()
        if not star:
            errors.append("partition row has a blank stable_star_id")
            continue
        if role not in allowed:
            errors.append(f"{star}: invalid partition role {role!r}")
        roles_by_star[star].add(role)
    for star, roles in roles_by_star.items():
        if len(roles) != 1:
            errors.append(f"{star} appears in multiple roles: {sorted(roles)}")
    if roles_by_star.get("KIC 10963065") != {"descriptive_benchmark"}:
        errors.append("Rudy must be descriptive_benchmark only")
    return errors
