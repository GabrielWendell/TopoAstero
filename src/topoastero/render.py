"""Machine-readable and dependency-free SVG outputs for the smoke workflow."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from topoastero.persistence import PersistencePair


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_rows(path: str | Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _scale(value: float, lower: float, upper: float, start: float, span: float) -> float:
    if upper == lower:
        return start + span / 2.0
    return start + span * (value - lower) / (upper - lower)


def write_smoke_svg(
    path: str | Path,
    time: Sequence[float],
    signal: Sequence[float],
    pairs: Sequence[PersistencePair],
) -> None:
    """Render a compact reference figure without a plotting dependency."""

    width, height = 960, 520
    margin = 64
    panel_height = 160
    x0, plot_width = margin, width - 2 * margin
    y_min, y_max = min(signal), max(signal)
    points = []
    for x_value, y_value in zip(time, signal, strict=True):
        x = _scale(x_value, min(time), max(time), x0, plot_width)
        y = margin + panel_height - _scale(y_value, y_min, y_max, 0, panel_height)
        points.append(f"{x:.2f},{y:.2f}")

    finite_pairs = [pair for pair in pairs if pair.death is not None]
    persistence_max = max((pair.persistence or 0.0 for pair in finite_pairs), default=1.0)
    bars: list[str] = []
    base_y = 330
    for order, pair in enumerate(sorted(finite_pairs, key=lambda item: -(item.persistence or 0.0))[:12]):
        bar_width = _scale(pair.persistence or 0.0, 0.0, persistence_max, 0.0, plot_width)
        y = base_y + order * 11
        bars.append(
            f'<line x1="{x0}" y1="{y}" x2="{x0 + bar_width:.2f}" y2="{y}" '
            'stroke="#0d7f86" stroke-width="7" />'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#ffffff"/>
<text x="{margin}" y="32" font-family="sans-serif" font-size="22" fill="#17324d">TopoAstero Stage 0 smoke workflow</text>
<text x="{margin}" y="52" font-family="sans-serif" font-size="13" fill="#516170">Seeded multimode signal and finite H0 superlevel persistence</text>
<rect x="{margin}" y="{margin}" width="{plot_width}" height="{panel_height}" fill="#f6f9fb" stroke="#cbd5df"/>
<polyline points="{' '.join(points)}" fill="none" stroke="#17324d" stroke-width="1.6"/>
<text x="{margin}" y="260" font-family="sans-serif" font-size="16" fill="#17324d">Twelve longest finite bars</text>
{''.join(bars)}
<text x="{margin}" y="500" font-family="sans-serif" font-size="12" fill="#516170">Reference implementation: exact H0 on a path graph; essential class omitted from bar panel.</text>
</svg>\n"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(svg, encoding="utf-8")

