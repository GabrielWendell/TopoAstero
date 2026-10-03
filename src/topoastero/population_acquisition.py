"""Checksum acquisition and an optional Lightkurve adapter for monthly LEGACY PSDs."""

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from topoastero.classical import spectral_window
from topoastero.config import load_yaml
from topoastero.population_store import contained, read_json, read_table, utc_now, write_json
from topoastero.provenance import sha256_file
from topoastero.rudy_benchmark import rebin_spectrum


def _download_payload(
    url: str,
    path: Path,
    *,
    expected_size: int,
    timeout: float,
    retries: int,
    retry_backoff: float,
) -> None:
    """Download one MAST payload with bounded retries and atomic replacement.

    A timed-out or truncated transfer never becomes a verified cache entry. Existing
    completed payloads are handled by ``acquire_population`` and are not downloaded again.
    """
    if timeout <= 0 or retries < 1 or retry_backoff < 0:
        raise ValueError("download timeout/retries/backoff must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "TopoAstero/Stage11"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as handle:
                while block := response.read(1024 * 1024):
                    handle.write(block)
            if temporary.stat().st_size != expected_size:
                raise OSError(
                    f"mission payload size mismatch after download: {path.name}; "
                    f"expected {expected_size}, got {temporary.stat().st_size}"
                )
            temporary.replace(path)
            return
        except (TimeoutError, socket.timeout, urllib.error.URLError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            if attempt == retries:
                raise OSError(
                    f"mission payload download failed after {retries} attempts: {path.name}: {exc}"
                ) from exc
            time.sleep(retry_backoff * attempt)


def acquire_population(
    root: Path,
    cache: Path,
    cfg: dict[str, Any],
    *,
    download: bool = False,
    role: str = "all",
    timeout: float = 240.0,
    retries: int = 4,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    """Verify the frozen candidate inventory; first payload hashes are acquired honestly.

    Candidate metadata hashes are NOT payload checksums. Existing Stage 11 payload
    hashes, once recorded, must agree on all subsequent reads. Missing files are
    represented explicitly. Acquisition alone computes no holdout representations.
    """
    if contained(root, cfg["release"]).exists():
        raise ValueError("acquisition manifest is frozen by the confirmation release")
    target = contained(root, cfg["acquisition"])
    prior = {r["product_key"]: r for r in read_json(target).get("products", [])} if target.exists() else {}
    products = []
    rows = read_table(contained(root, cfg["products"]))
    for row in rows:
        name = row["product_filename"]
        if Path(name).name != name or "\\" in name:
            raise ValueError("unsafe mission filename")
        relative = "kepler/" + name
        path = contained(cache, relative)
        active = role == "all" or row["partition_role"] == role
        if download and active and not path.exists():
            url = "https://mast.stsci.edu/api/v0.1/Download/file?uri=" + urllib.parse.quote(row["data_uri"], safe="")
            _download_payload(
                url,
                path,
                expected_size=int(row["size_bytes"]),
                timeout=timeout,
                retries=retries,
                retry_backoff=retry_backoff,
            )
        sha = None
        if path.is_file():
            if path.stat().st_size != int(row["size_bytes"]):
                raise ValueError(f"mission payload size mismatch: {name}")
            sha = sha256_file(path)
            expected = prior.get(row["product_key"], {}).get("sha256") or row.get("payload_sha256")
            if expected and sha != expected:
                raise ValueError(f"mission payload checksum mismatch: {name}")
        # Do not silently discard an acquired hash if a cache moved or lost a file.
        if sha is None and row["product_key"] in prior:
            old = prior[row["product_key"]]
            sha = old.get("sha256")
        products.append({"product_key": row["product_key"], "stable_star_id": row["stable_star_id"],
                         "role": row["partition_role"], "cache_relative_path": relative, "data_uri": row["data_uri"],
                         "size_bytes": int(row["size_bytes"]), "sha256": sha,
                         "status": "payload_verified" if path.is_file() else "missing_payload",
                         "checksum_origin": "Stage11_payload_acquisition" if sha else "not_acquired"})
    manifest = {"schema_version": 1, "inventory_sha256": sha256_file(contained(root, cfg["products"])),
                "recorded_at_utc": utc_now(), "holdout_representations_computed": False,
                "products": products, "verified_products": sum(r["status"] == "payload_verified" for r in products),
                "expected_products": len(products)}
    write_json(target, manifest)
    return manifest


def verified_star_products(root: Path, cache: Path, cfg: dict[str, Any], star: str) -> tuple[list[Path], int]:
    manifest = read_json(contained(root, cfg["acquisition"]))
    if manifest["inventory_sha256"] != sha256_file(contained(root, cfg["products"])):
        raise ValueError("candidate inventory changed since acquisition")
    records = [r for r in manifest["products"] if r["stable_star_id"] == star]
    paths = []
    for row in records:
        path = contained(cache, row["cache_relative_path"])
        if row.get("sha256") is None or not path.exists():
            continue
        if path.stat().st_size != row["size_bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError(f"payload changed for {star}: {path.name}")
        paths.append(path)
    return paths, len(records)


def monthly_spectra(paths: list[Path], cfg: dict[str, Any]) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any], np.ndarray[Any, Any], dict[str, Any]]:
    """PP-01 per-month PSD, uniform rebinning, exposure weights and cadence-mask audit.

    Normalize each month independently, then average PSDs; never bridge gaps by
    filling flux. Optional astronomy imports stay outside the dependency-light core.
    """
    import lightkurve as lk  # type: ignore[import-untyped]

    lo, hi, step = cfg["observation"]["frequency_grid_uHz"]
    grid = np.arange(lo, hi + step / 2, step, dtype=np.float64)
    spectra, weights, times = [], [], []
    cadence = cfg["observation"]["cadence_seconds"]
    expected_kic: int | None = None
    for path in paths:
        curve = lk.KeplerLightCurve.read(path, flux_column="pdcsap_flux", quality_bitmask="default").remove_nans().normalize()
        header_kic = int(curve.meta["KEPLERID"])
        if expected_kic is None:
            expected_kic = header_kic
        if header_kic != expected_kic or not path.name.startswith(f"kplr{header_kic:09d}-"):
            raise ValueError("mission_header_star_identifier_mismatch")
        time = np.asarray(curve.time.value, dtype=np.float64)
        if time.size < 64 or np.any(np.diff(time) <= 0):
            raise ValueError("invalid_monthly_light_curve")
        pg = curve.to_periodogram(normalization="psd", minimum_frequency=max(1.0, lo - 2 * step), maximum_frequency=hi + 2 * step)
        native_frequency = np.asarray(pg.frequency.value, dtype=np.float64)
        native_power = np.asarray(pg.power.value, dtype=np.float64) * 1e12
        spectra.append(rebin_spectrum(native_frequency, native_power, grid))
        weights.append(time.size)
        times.append(time)
    concatenated = np.concatenate(times)
    if np.unique(concatenated).size != concatenated.size:
        raise ValueError("overlapping_month_products")
    time = np.sort(concatenated)
    window = spectral_window(time, cadence)
    meta = {"segments": len(paths), "cadence_count": int(time.size),
            "duration_days": float(time[-1] - time[0]), "duty_cycle": window.duty_cycle,
            "native_window_resolution_uHz": window.resolution_uHz,
            "window_frequency_uHz": window.frequency_uHz.tolist(), "window_power": window.power.tolist(),
            "segment_products": [p.name for p in paths],
            "estimator": "exposure_weighted_monthly_mean_psd", "preprocessing": "PP-01"}
    return grid, np.asarray(spectra, dtype=np.float64), np.asarray(weights, dtype=np.float64), meta


def load_config(root: Path, path: Path | None = None) -> dict[str, Any]:
    cfg = load_yaml(path or root / "configs/stage11_legacy.yaml")
    if cfg.get("schema_version") != 1 or cfg.get("cohort_size") != 66:
        raise ValueError("Stage 11 requires the registered 66-star cohort and schema v1")
    if cfg["topology"]["normalization"] != "log_ratio" or cfg["topology"]["ridge_inference"] != "geometry_only" or cfg["topology"]["delay_topology"] != "dropped_at_G7":
        raise ValueError("Stage 11 cannot override the frozen Stage 6/7/8 inference scope")
    if cfg["observation"]["preprocessing_branch"] != "PP-01" or cfg["observation"]["quality_bitmask"] != "default" or cfg["observation"]["estimator"] != "exposure_weighted_monthly_mean_psd":
        raise ValueError("unsupported population observation operator")
    if cfg["statistics"]["primary_quantities"] != ["numax", "dnu"] or cfg["statistics"]["pooled_roles_allowed"]:
        raise ValueError("registered primary endpoints and separate roles are required")
    if not cfg["uncertainty"]["segment_bootstrap_replicates"] >= 8 or cfg["statistics"]["minimum_stars_for_interval"] < 3:
        raise ValueError("invalid uncertainty sample size")
    if not 0 < cfg["uncertainty"]["interval_level"] < 1 or not 0 < cfg["statistics"]["alpha"] < 0.5:
        raise ValueError("invalid interval level or alpha")
    if cfg["classical"]["background_components"] != 2 or cfg["observation"]["minimum_months"] < 3:
        raise ValueError("registered H2 background and at least three monthly segments are required")
    return cfg
