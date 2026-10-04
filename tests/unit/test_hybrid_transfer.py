"""Physical integration, matched realizations and mission adapter contracts."""
from __future__ import annotations

import copy
import math
import sys
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from topoastero.hybrid import transfer
from topoastero.population_store import write_json
from topoastero.provenance import sha256_file


def test_real_exposure_average_preserves_a_linear_flux_curve(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]["transfer"]
    source = np.arange(0., 3*86400, 30.)
    window = np.arange(0., 2*86400, 120.)
    time, flux, meta = transfer.degrade(source, source*.001, window, cfg, level="window", offset_days=0, seed=4, source_white=0, target_white=0)
    assert np.allclose(flux, time*86400*.001, atol=1e-8)
    assert time[0] > 0 and time[-1]*86400 < source[-1]
    assert meta["exposure_seconds"] == 120 and meta["inherited_noise_removed"] is False
    assert 0 < meta["supported_exposure_fraction"] < 1


def test_common_random_numbers_share_noise_across_matching_levels(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]["transfer"]
    source = np.arange(0., 3*86400, 30.)
    window = np.arange(0., 2*86400, 120.)
    curve = np.sin(source/500)
    args = dict(offset_days=0, seed=99, source_white=0., target_white=.1)
    ntime, noise, _ = transfer.degrade(source, curve, window, cfg, level="noise", **args)
    wtime, masked, _ = transfer.degrade(source, curve, window, cfg, level="window", **args)
    assert np.array_equal(ntime, wtime[:len(ntime)]) and np.array_equal(noise, masked[:len(ntime)])
    repeat = transfer.degrade(source, curve, window, cfg, level="window", **args)
    assert np.array_equal(masked, repeat[1])
    clean = transfer.degrade(source, curve, window, cfg, level="window", **{**args, "target_white": 0})
    dilute = transfer.degrade(source, curve, window, cfg, level="contamination", **{**args, "target_white": 0})
    retained = np.searchsorted(clean[0], dilute[0])
    assert np.allclose(dilute[1], clean[1][retained]/1.3)
    assert len(dilute[0]) < len(clean[0])
    short_cfg = {**cfg, "short_duration_days": .5}
    short = transfer.degrade(source, curve, window, short_cfg, level="short_duration", **args)
    assert short[2]["duration_days"] <= .5
    native = transfer.degrade(source, curve, window, cfg, level="native", **args)
    assert native[2]["cadence_seconds"] == 30 and native[2]["noise_sigma_ppm"] == 0


def test_gap_rejection_and_invalid_physical_parameters(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]["transfer"]
    source = np.arange(0., 86400, 30.)
    source = source[(source < 30000) | (source > 35000)]
    window = np.arange(0., 80000, 120.)
    args = dict(level="window", offset_days=0, seed=1, source_white=0, target_white=0)
    time, _, _ = transfer.degrade(source, np.zeros_like(source), window, cfg, **args)
    assert not np.any((time*86400 >= 30000) & (time*86400 <= 35000))
    for change in ({"cadence_seconds": 10}, {"exposure_seconds": 500}, {"additional_duty": 0},
                   {"contaminating_to_target_flux": -.5}, {"additional_signal_color_response": 0}):
        with pytest.raises(ValueError):
            transfer.degrade(source, np.zeros_like(source), window, {**cfg, **change}, **{**args, "level": "contamination"})
    for change in ({"level": "bogus"}, {"offset_days": -1}, {"offset_days": 1000}):
        with pytest.raises(ValueError):
            transfer.degrade(source, np.zeros_like(source), window, cfg, **{**args, **change})
    with pytest.raises(ValueError, match="source"):
        transfer.degrade(source[::-1], np.zeros_like(source), window, cfg, **args)
    with pytest.raises(ValueError, match="window"):
        transfer.degrade(source, np.zeros_like(source), window[::-1], cfg, **args)


def astronomy_stub(monkeypatch: pytest.MonkeyPatch) -> tuple[ModuleType, list[dict]]:
    lk, astropy, units = ModuleType("lightkurve"), ModuleType("astropy"), ModuleType("astropy.units")
    units.microhertz = 1.0
    calls = []

    class Curve:
        def __init__(self, **kwargs: dict) -> None:
            self.kwargs = kwargs
        def to_periodogram(self, **kwargs: dict) -> SimpleNamespace:
            calls.append(kwargs)
            freq = np.linspace(1., 4500., 9000)
            return SimpleNamespace(frequency=SimpleNamespace(value=freq), power=SimpleNamespace(value=np.full_like(freq, 2e-12)))
    lk.LightCurve = Curve
    astropy.units = units
    monkeypatch.setitem(sys.modules, "lightkurve", lk)
    monkeypatch.setitem(sys.modules, "astropy", astropy)
    monkeypatch.setitem(sys.modules, "astropy.units", units)
    return lk, calls


def test_adapter_explicit_microhertz_grid_and_endpoint_padding(hybrid_repository: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    root, cfg, _, _ = hybrid_repository
    _, calls = astronomy_stub(monkeypatch)
    monkeypatch.setattr(transfer, "fit_population_background", lambda grid, power, cfg: (np.ones_like(grid), {}))
    point = {"classical_numax": 2200., "classical_dnu": 100., "topology_numax": 2210., "envelope_ratio": 2.,
             "nominal_score": .5, "maximum_alias_score": .4, "envelope_half_width_uHz": 300., "nominal_winner_at_boundary": False}
    monkeypatch.setattr(transfer, "estimate_points", lambda *a: dict(point))
    monkeypatch.setattr(transfer, "make_echelle_field", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "score_echelle", lambda f: (SimpleNamespace(graph_only=.4, topology=.6), None, None))
    time = np.arange(0., 86400, 120)/86400
    analysis, grid, power = transfer.analyze_curve(time, np.sin(time), root, cfg, 120)
    assert grid[0] == 105 and grid[-1] < 1e6/(2*120) and np.isfinite(power).all()
    assert calls[0]["minimum_frequency"] < grid[0] and calls[0]["maximum_frequency"] > grid[-1]
    assert analysis["features"]["cylinder_score"] == .6
    assert transfer.white_floor(time, np.sin(time)) == pytest.approx(2/np.log(2))
    with pytest.raises(ValueError, match="Nyquist"):
        transfer.analyze_curve(time, np.sin(time), root, cfg, 300)
    with pytest.raises(ValueError, match="time series"):
        transfer.analyze_curve(time[:10], np.ones(10), root, cfg, 120)
    class Bad:
        def to_periodogram(self, **kwargs: dict) -> SimpleNamespace:
            return SimpleNamespace(power=SimpleNamespace(value=np.zeros(100)))
    lk = sys.modules["lightkurve"]
    monkeypatch.setattr(lk, "LightCurve", lambda **kw: Bad())
    with pytest.raises(ValueError, match="noise-floor"):
        transfer.white_floor(time, np.sin(time))


def test_mission_payloads_verify_identity_hash_months_and_unique_sectors(hybrid_repository: tuple, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    root = hybrid_repository[0]
    lk, _ = astronomy_stub(monkeypatch)
    cache = tmp_path / "cache"
    sectors = [14, 15, 40, 41, 54, 55, 74, 75, 80, 81, 82]
    products, curves = [], {}
    for mission, count in (("kepler", 10), ("tess", 11)):
        for i in range(count):
            path = cache / mission / f"{mission}{i}.fits"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"SYNTHETIC_NOT_OBSERVATIONS")
            products.append({"mission": mission, "product_filename": path.name, "sha256": sha256_file(path)})
            meta = {"KEPLERID": 10963065, "QUARTER": 5 if i < 3 else 2} if mission == "kepler" else {"TICID": 48450369, "SECTOR": sectors[i]}
            curve = SimpleNamespace(time=SimpleNamespace(value=np.linspace(i*2, i*2+1, 200)), flux=SimpleNamespace(value=np.ones(200)), meta=meta)
            curve.remove_nans = lambda c=curve: c
            curve.normalize = lambda c=curve: c
            curves[path.name] = curve
    monkeypatch.setattr(lk, "read", lambda path: curves[path.name], raising=False)
    write_json(root / "results/stage10/benchmark_capsule.json", {"products": products})
    time, flux, targets, files = transfer.read_mission_inputs(root, cache)
    assert len(time) == 600 and len(targets) == 11 and len(files) == 21 and np.all(flux == 0)
    curves["tess0.fits"].meta["TICID"] = 1
    with pytest.raises(ValueError, match="identifier"):
        transfer.read_mission_inputs(root, cache)
    curves["tess0.fits"].meta["TICID"] = 48450369
    curves["kepler0.fits"].meta["KEPLERID"] = 1
    with pytest.raises(ValueError, match="identifier"):
        transfer.read_mission_inputs(root, cache)
    curves["kepler0.fits"].meta["KEPLERID"] = 10963065
    curves["tess1.fits"].meta["SECTOR"] = 14
    with pytest.raises(ValueError, match="11 TESS"):
        transfer.read_mission_inputs(root, cache)
    curves["tess1.fits"].meta["SECTOR"] = 15
    curves["kepler1.fits"].time.value = curves["kepler0.fits"].time.value
    with pytest.raises(ValueError, match="overlapping"):
        transfer.read_mission_inputs(root, cache)
    (cache / "kepler/kepler0.fits").write_bytes(b"changed")
    with pytest.raises(ValueError, match="payload"):
        transfer.read_mission_inputs(root, cache)


def test_simulation_recalibration_collapses_draws_to_parent_stars(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]
    rows = [{"stable_star_id": f"S{i}", "role": "development", "origin": "degradation_simulation", "method": m, "quantity": q,
             "estimate": 100., "reference": 100*math.exp(.1 if i < 6 else .2)} for i in range(10) for m in ("baseline", "hybrid") for q in ("numax", "dnu")]
    layer = transfer.calibration_layer(rows, cfg, "SYNTHETIC authorization only")
    uneven = rows + [copy.deepcopy(r) for r in rows if r["stable_star_id"] == "S9"]*100
    assert transfer.calibration_layer(uneven, cfg, "SYNTHETIC")["offsets"] == layer["offsets"]
    assert layer["offsets"]["baseline_numax"] == pytest.approx(.1) and not layer["feature_redesign"]
    for change in ({"role": "final_holdout"}, {"role": "internal_validation"}, {"stable_star_id": transfer.RUDY}, {"origin": "actual_TESS"}, {"estimate": 0}, {"reference": np.nan}):
        bad = copy.deepcopy(rows)
        bad[0].update(change)
        with pytest.raises(ValueError):
            transfer.calibration_layer(bad, cfg, "SYNTHETIC")
    for data, authorization in [(rows[:4], "SYNTHETIC"), (rows[:-1], "SYNTHETIC"), (rows, "")]:
        with pytest.raises(ValueError):
            transfer.calibration_layer(data, cfg, authorization)
