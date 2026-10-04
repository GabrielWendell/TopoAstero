"""Paired practical tests, withholding, calibration and conditional transfer metrics."""
from __future__ import annotations

import copy

import pytest

from topoastero.hybrid.statistics import (
    paired_increment,
    paired_quality,
    probability_report,
    transfer_contributions,
    transfer_summary,
)


def paired_rows(n: int, b: float, h: float) -> list[dict]:
    return [{"stable_star_id": f"S{i}", "quantity": q, "reference": 100., "baseline": 100*(1+b), "hybrid": 100*(1+h),
             "baseline_lower": 90., "baseline_upper": 130.} for q in ("numax", "dnu") for i in range(n)]


def test_practical_superiority_equivalence_and_sparse_withholding(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]
    better = paired_increment(paired_rows(30, .2, .02), cfg)
    assert all(r["positive_increment"] and r["p_superior_holm"] == 0 for r in better)
    assert better[0]["metrics"]["baseline"]["reference_center_coverage"] == 1
    equal = paired_increment(paired_rows(30, .02, .02), cfg)
    assert all(r["quantified_equivalence"] and not r["positive_increment"] for r in equal)
    sparse = paired_increment(paired_rows(9, .2, .02), cfg)
    assert all(not r["positive_increment"] for r in sparse)
    noisy = paired_rows(30, .2, .1)
    for i, r in enumerate(noisy):
        r["hybrid"] += (i % 3)*2
    assert paired_increment(noisy, cfg)[0]["bootstrap95_lower"] is not None
    assert paired_increment([], cfg)[0]["mean_fractional_loss_improvement"] is None
    with pytest.raises(ValueError, match="one row"):
        paired_increment([*noisy, noisy[0]], cfg)
    noisy[0]["reference"] = 0
    with pytest.raises(ValueError, match="positive"):
        paired_increment(noisy, cfg)


def quality_tasks(n: int = 40) -> list[dict]:
    return [{"task": "catastrophic_failure", "method": m,
             "predictions": [{"stable_star_id": f"S{i}", "outcome": i % 2,
                              "prediction": (.6 if i % 2 else .5) if m == "baseline" else (.9 if i % 2 else .1)} for i in range(n)]} for m in ("baseline", "hybrid")]


def test_paired_failure_utility_uses_same_stars_and_requires_action_gain(hybrid_repository: tuple) -> None:
    cfg = hybrid_repository[1]
    result = paired_quality(quality_tasks(), cfg)
    assert result["positive_quality_increment"] and result["net_benefit_bootstrap95_lower"] > 0
    assert not paired_quality(quality_tasks(9), cfg)["positive_quality_increment"]
    assert paired_quality([], cfg)["status"] == "withheld"
    one = quality_tasks()
    for task in one:
        for p in task["predictions"]:
            p["outcome"] = 0
    assert paired_quality(one, cfg)["status"] == "withheld_single_class"
    bad = quality_tasks()
    bad[1]["predictions"][0]["outcome"] = 1
    with pytest.raises(ValueError, match="outcomes"):
        paired_quality(bad, cfg)
    duplicate = quality_tasks()
    duplicate[0]["predictions"].append(copy.deepcopy(duplicate[0]["predictions"][0]))
    with pytest.raises(ValueError, match="one prediction"):
        paired_quality(duplicate, cfg)


def test_calibration_counts_empty_bins_and_false_confidence() -> None:
    result = probability_report([0, 1, 0, 1], [0., 1., .1, .2])
    assert result["Brier"] == pytest.approx(.1625)
    assert sum(b["n"] for b in result["calibration"]) == 4
    assert any(b["mean_predicted"] is None for b in result["calibration"])
    assert next(r for r in result["decision_curve"] if r["threshold"] == .25)["false_confidence"] == 1
    assert probability_report([1, 1], [.5, .9])["Brier"] is None
    for y, p in [([], []), ([0], [2]), ([2], [.5]), ([0, 1], [.5])]:
        with pytest.raises(ValueError):
            probability_report(y, p)
    with pytest.raises(ValueError):
        probability_report([0, 1], [.2, .8], thresholds=(1.,))


def test_transfer_diagnostics_keep_rejections_and_one_parent() -> None:
    rows = [{"stable_star_id": "same", "sector": 14, "offset_days": 0, "draw": i, "level": level,
             "method": "baseline", "quantity": "dnu", "reference": 100., "candidate_estimate": 100.+10*j,
             "estimate": 100. if j == 0 else None, "accepted": j == 0, "recoverable": j == 0}
            for i in range(5) for j, level in enumerate(("native", "noise"))]
    summary = transfer_summary(rows)
    assert all(r["parent_stars"] == 1 and r["cells"] == 5 for r in summary)
    rejected = next(r for r in summary if r["level"] == "noise")
    assert rejected["median"] is None and rejected["candidate_median"] == 110
    delta = transfer_contributions(rows, ("native", "noise"))
    assert len(delta) == 5 and all(r["candidate_fractional_loss_change"] == pytest.approx(.1) for r in delta)
    rows[1]["candidate_estimate"] = None
    assert transfer_contributions(rows, ("native", "noise"))[0]["candidate_fractional_loss_change"] is None
