# TopoAstero plotting style guide

**Visual contract:** TA-PLOT-1.0  
**Applies from:** Stage 3 onward  
**Normative module:** `src/topoastero/style.py`

## Policy

Every released Stage 3 or later figure must be created inside `topoastero_style(...)`, finished
with `style_axes(...)`, and exported with `save_figure(...)`. Plotting workflows must not update
Matplotlib `rcParams` or call `Figure.savefig` directly. This keeps typography, semantic colors,
dimensions, metadata, and export behavior reviewable in one versioned module.

The reproducible default is the `paper` context with `use_tex=False`. STIX math text provides
journal-like typography without a system LaTeX dependency. TeX rendering may be used for a
submission only when the build environment explicitly supplies and records it. The primary
repository format is SVG with editable text and deterministic metadata; publication exports may
add PDF or 300-dpi PNG siblings.

```python
import matplotlib.pyplot as plt

from topoastero.style import (
    FIGSIZE,
    data_color,
    save_figure,
    style_axes,
    topoastero_style,
)

with topoastero_style(context="paper", constrained_layout=True):
    figure, axis = plt.subplots(figsize=FIGSIZE["double"])
    axis.plot(x, y, color=data_color("spectrum"), label="PSD")
    style_axes(
        axis,
        xlabel=r"Frequency [$\mu$Hz]",
        ylabel=r"PSD [ppm$^2\,\mu$Hz$^{-1}$]",
        legend=True,
    )
    save_figure(
        figure,
        "reports/stage4/figures/example.svg",
        source="results/stage4/example.csv",
        software_version="TopoAstero-0.5.0",
        close=True,
    )
```

## Semantic encodings

Colors encode meaning and must not be selected by palette index inside a workflow.

| API | Stable meanings |
| --- | --- |
| `mission_color` | Kepler, K2, TESS |
| `mode_degree_color` | spherical-harmonic degrees 0-3 |
| `background_color` | Harvey families H0-H2 |
| `data_color` | raw spectrum, background, envelope, reference, residual, threshold, exclusion, marginal, non-detection |
| `WINDOW_COLORS` | Q2/Q5/Q6/Q7 and absolute/compressed combinations |

The defaults are colorblind-accessible and retain distinctions through line style or marker shape
where a categorical comparison is central. Never use color as the only encoding for a threshold,
candidate class, rejected model, or reference line. Unknown categories receive a neutral fallback
rather than an arbitrary cycle color.

## Figure construction

- Use `FIGSIZE["single"]` for one-column figures, `FIGSIZE["double"]` for normal full-width
  diagnostics, and `FIGSIZE["triple"]` for three compact panels.
- Label physical quantities with units. Use `\mu`Hz, not the ASCII placeholder `uHz`, in display
  labels; retain canonical ASCII unit strings in machine-readable tables.
- Use `panel_label` for multi-panel labels and `annotate_textbox` only for concise interpretation.
- Use a light major grid when it aids numerical comparison; suppress it for image panels.
- Retain rejected models, negative results, thresholds, and uncertainty bands when they are part of
  the claim. Styling must never hide scientifically inconvenient evidence.
- Keep numerical claims in source tables. Figures visualize results but are not a data store.

## Provenance and validation

`save_figure` embeds the software version, `TA-PLOT-1.0`, and one or more machine-readable sources
in SVG metadata while suppressing wall-clock timestamps. Stage run manifests record the style ID,
context, TeX choice, and primary format. The Stage 3 validator rejects figures missing any of
those markers or a source reference.

`tests/governance/test_plot_style_contract.py` scans plotting workflows. Any future workflow that
uses Matplotlib or exports a figure must import `topoastero.style` and may not call `savefig`
directly. A visual-contract revision changes `STYLE_VERSION`, documents the migration here, and
regenerates every affected released figure and checksum manifest.
