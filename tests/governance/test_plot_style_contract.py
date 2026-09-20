from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_every_plotting_workflow_uses_the_topoastero_visual_contract() -> None:
    plotting_workflows: list[Path] = []
    for path in sorted((ROOT / "workflows").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in ("plt.subplots", ".savefig(", "save_figure(")):
            plotting_workflows.append(path)
            assert "from topoastero.style import" in source, path.name
            assert ".savefig(" not in source, path.name
            assert "plt.rcParams" not in source, path.name
    assert "run_stage3_classical.py" in {path.name for path in plotting_workflows}


def test_style_policy_explicitly_applies_to_future_stages() -> None:
    guide = (ROOT / "docs/reproducibility/PLOTTING_STYLE_GUIDE.md").read_text(encoding="utf-8")
    assert "TA-PLOT-1.0" in guide
    assert "Stage 3 and every later" in guide or "Stage 3 or later" in guide
    assert "machine-readable source" in guide
