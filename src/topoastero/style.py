"""Publication-quality Matplotlib styling for TopoAstero.

This module is the visual contract for Stage 3 and every later project stage.
It centralizes journal-scale typography, colorblind-accessible semantic colors,
axis finishing, annotations, and deterministic figure export. Plotting workflows
must use :func:`topoastero_style` (or :func:`set_style`) rather than modifying
``matplotlib.rcParams`` locally.

Examples
--------
>>> import matplotlib.pyplot as plt
>>> from topoastero.style import FIGSIZE, data_color, save_figure, style_axes, topoastero_style
>>> with topoastero_style(context="paper"):
...     fig, ax = plt.subplots(figsize=FIGSIZE["single"])
...     ax.plot([0, 1], [0, 1], color=data_color("spectrum"), label="PSD")
...     _ = style_axes(ax, xlabel="Frequency", ylabel="Power", legend=True)
...     _ = save_figure(fig, "example.svg", source="results/example.csv", close=True)
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import matplotlib as mpl
import matplotlib.pyplot as plt
from cycler import cycler
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.text import Text

from topoastero.portability import normalize_text_file_lf

__all__ = [
    "BACKGROUND_COLORS",
    "BACKGROUND_LABELS",
    "DATA_COLORS",
    "FIGSIZE",
    "MISSION_COLORS",
    "MISSION_LABELS",
    "MODE_DEGREE_COLORS",
    "MODE_DEGREE_LABELS",
    "STYLE_ID",
    "STYLE_VERSION",
    "WINDOW_COLORS",
    "WINDOW_LINESTYLES",
    "add_identity_line",
    "add_zero_line",
    "annotate_textbox",
    "background_color",
    "background_label",
    "build_rcparams",
    "data_color",
    "figure_metadata",
    "get_palette",
    "list_palettes",
    "mission_color",
    "mission_label",
    "mode_degree_color",
    "mode_degree_label",
    "panel_label",
    "save_figure",
    "set_style",
    "style_axes",
    "style_legend",
    "topoastero_style",
]

GridAxis = Literal["x", "y", "both"]
StyleContext = Literal["paper", "notebook", "talk", "poster"]

STYLE_VERSION = "1.0"
STYLE_ID = f"TA-PLOT-{STYLE_VERSION}"

# Stable, colorblind-accessible meanings for astronomy products.
MISSION_LABELS: dict[str, str] = {
    "KEPLER": "Kepler",
    "K2": "K2",
    "TESS": "TESS",
}
MISSION_COLORS: dict[str, str] = {
    "KEPLER": "#2F5C85",
    "K2": "#2A6F55",
    "TESS": "#DD6B20",
}

MODE_DEGREE_LABELS: dict[int, str] = {
    0: r"$\ell=0$",
    1: r"$\ell=1$",
    2: r"$\ell=2$",
    3: r"$\ell=3$",
}
MODE_DEGREE_COLORS: dict[int, str] = {
    0: "#0072B2",
    1: "#D55E00",
    2: "#009E73",
    3: "#CC79A7",
}

BACKGROUND_LABELS: dict[str, str] = {
    "H0": r"$H_0$",
    "H1": r"$H_1$",
    "H2": r"$H_2$",
}
BACKGROUND_COLORS: dict[str, str] = {
    "H0": "#8C8C8C",
    "H1": "#DD6B20",
    "H2": "#2F5C85",
}

DATA_COLORS: dict[str, str] = {
    "raw": "#77838F",
    "spectrum": "#5C6F82",
    "background": "#2F5C85",
    "envelope": "#C44E52",
    "reference": "#2A6F55",
    "residual": "#8172B2",
    "threshold": "#C44E52",
    "exclusion": "#E69F00",
    "marginal": "#E69F00",
    "not_detected": "#6C7A89",
}

WINDOW_COLORS: dict[str, str] = {
    "Q2": "#0072B2",
    "Q5": "#D55E00",
    "Q6": "#009E73",
    "Q7": "#CC79A7",
    "combined_absolute": "#1F1F1F",
    "combined_compressed": "#E69F00",
}
WINDOW_LINESTYLES: dict[str, str] = {
    "Q2": "-",
    "Q5": "-",
    "Q6": "-",
    "Q7": "-",
    "combined_absolute": "-",
    "combined_compressed": "--",
}

_PALETTES: dict[str, tuple[str, ...]] = {
    "topoastero": (
        "#2F5C85",
        "#C44E52",
        "#55A868",
        "#8172B2",
        "#DD6B20",
        "#64B5CD",
        "#8C8C8C",
        "#937860",
    ),
    "missions": tuple(MISSION_COLORS.values()),
    "degrees": tuple(MODE_DEGREE_COLORS.values()),
    "backgrounds": tuple(BACKGROUND_COLORS.values()),
    "colorblind": (
        "#0072B2",
        "#D55E00",
        "#009E73",
        "#CC79A7",
        "#56B4E9",
        "#E69F00",
        "#000000",
    ),
    "mono": ("#1F1F1F", "#4C4C4C", "#6E6E6E", "#8A8A8A", "#A6A6A6"),
}

# Common journal widths plus the multi-panel layouts used by TopoAstero.
FIGSIZE: dict[str, tuple[float, float]] = {
    "single": (3.45, 2.35),
    "single_square": (3.45, 3.30),
    "double": (7.10, 4.40),
    "double_short": (7.10, 3.20),
    "triple": (7.10, 2.85),
    "gallery": (9.50, 8.20),
}


def list_palettes() -> list[str]:
    """Return the names of the built-in TopoAstero palettes."""

    return sorted(_PALETTES)


def get_palette(palette: str | Iterable[str] | None = None) -> tuple[str, ...]:
    """Resolve a named or user-provided color palette."""

    if palette is None:
        return _PALETTES["topoastero"]
    if isinstance(palette, str):
        if palette not in _PALETTES:
            valid = ", ".join(list_palettes())
            raise ValueError(f"Unknown palette {palette!r}. Available palettes: {valid}.")
        return _PALETTES[palette]
    colors = tuple(str(color) for color in palette)
    if not colors:
        raise ValueError("Custom palette must contain at least one color.")
    return colors


def _resolve_usetex(use_tex: bool | Literal["auto"]) -> bool:
    if use_tex == "auto":
        return shutil.which("latex") is not None
    if isinstance(use_tex, bool):
        return use_tex
    raise ValueError("use_tex must be True, False, or 'auto'.")


def build_rcparams(
    *,
    context: StyleContext = "paper",
    use_tex: bool | Literal["auto"] = False,
    base_fontsize: float | None = None,
    dpi: int = 160,
    save_dpi: int = 300,
    transparent: bool = False,
    palette: str | Iterable[str] | None = None,
    grid: bool = False,
    constrained_layout: bool = False,
) -> dict[str, object]:
    """Build deterministic Matplotlib parameters for a publication context.

    ``use_tex=False`` is the reproducible default: STIX math rendering closely
    matches journal typography without requiring a system LaTeX installation.
    """

    presets: dict[str, dict[str, float]] = {
        "paper": {"fontsize": 9.6, "linewidth": 1.25, "markersize": 4.5},
        "notebook": {"fontsize": 11.5, "linewidth": 1.45, "markersize": 5.2},
        "talk": {"fontsize": 14.0, "linewidth": 1.85, "markersize": 6.2},
        "poster": {"fontsize": 18.0, "linewidth": 2.20, "markersize": 7.2},
    }
    if context not in presets:
        valid = ", ".join(presets)
        raise ValueError(f"Unsupported context {context!r}. Choose one of: {valid}.")

    preset = presets[context]
    fontsize = float(base_fontsize if base_fontsize is not None else preset["fontsize"])
    linewidth = preset["linewidth"]
    markersize = preset["markersize"]
    usetex = _resolve_usetex(use_tex)

    return {
        "figure.dpi": dpi,
        "savefig.dpi": save_dpi,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.04,
        "savefig.transparent": transparent,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "figure.constrained_layout.use": constrained_layout,
        "font.size": fontsize,
        "font.family": "serif",
        "font.serif": ["STIX Two Text", "STIXGeneral", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "text.usetex": usetex,
        "axes.formatter.use_mathtext": not usetex,
        "axes.unicode_minus": True,
        "axes.prop_cycle": cycler(color=get_palette(palette)),
        "axes.grid": grid,
        "axes.axisbelow": True,
        "axes.linewidth": 0.9,
        "axes.edgecolor": "0.18",
        "axes.titlesize": fontsize + 0.5,
        "axes.titleweight": "semibold",
        "axes.labelsize": fontsize,
        "axes.labelpad": 4.5,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "xtick.minor.visible": True,
        "ytick.minor.visible": True,
        "xtick.major.size": 5.0,
        "ytick.major.size": 5.0,
        "xtick.minor.size": 2.5,
        "ytick.minor.size": 2.5,
        "xtick.major.width": 0.9,
        "ytick.major.width": 0.9,
        "xtick.minor.width": 0.7,
        "ytick.minor.width": 0.7,
        "xtick.labelsize": fontsize - 0.3,
        "ytick.labelsize": fontsize - 0.3,
        "lines.linewidth": linewidth,
        "lines.markersize": markersize,
        "lines.markeredgewidth": 0.75,
        "patch.linewidth": 0.75,
        "errorbar.capsize": 2.5,
        "grid.color": "0.84",
        "grid.linestyle": ":",
        "grid.linewidth": 0.7,
        "legend.frameon": True,
        "legend.framealpha": 0.94,
        "legend.facecolor": "white",
        "legend.edgecolor": "0.82",
        "legend.fancybox": False,
        "legend.fontsize": fontsize - 0.8,
        "legend.title_fontsize": fontsize - 0.4,
        "image.cmap": "magma",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "svg.hashsalt": STYLE_ID,
    }


def set_style(
    *,
    context: StyleContext = "paper",
    use_tex: bool | Literal["auto"] = False,
    base_fontsize: float | None = None,
    dpi: int = 160,
    save_dpi: int = 300,
    transparent: bool = False,
    palette: str | Iterable[str] | None = None,
    grid: bool = False,
    constrained_layout: bool = False,
) -> None:
    """Apply the TopoAstero visual contract globally."""

    mpl.rcParams.update(
        build_rcparams(
            context=context,
            use_tex=use_tex,
            base_fontsize=base_fontsize,
            dpi=dpi,
            save_dpi=save_dpi,
            transparent=transparent,
            palette=palette,
            grid=grid,
            constrained_layout=constrained_layout,
        )
    )


@contextmanager
def topoastero_style(
    *,
    context: StyleContext = "paper",
    use_tex: bool | Literal["auto"] = False,
    base_fontsize: float | None = None,
    dpi: int = 160,
    save_dpi: int = 300,
    transparent: bool = False,
    palette: str | Iterable[str] | None = None,
    grid: bool = False,
    constrained_layout: bool = False,
) -> Iterator[None]:
    """Temporarily apply the TopoAstero visual contract inside a ``with`` block."""

    with mpl.rc_context(
        build_rcparams(
            context=context,
            use_tex=use_tex,
            base_fontsize=base_fontsize,
            dpi=dpi,
            save_dpi=save_dpi,
            transparent=transparent,
            palette=palette,
            grid=grid,
            constrained_layout=constrained_layout,
        )
    ):
        yield


def _background_key(value: str | int) -> str:
    return f"H{str(value).replace('_', '').upper().removeprefix('H')}"


def _degree_key(value: str | int) -> int | None:
    text = str(value).lower().replace("ell", "").replace("l", "").replace("=", "").strip()
    try:
        return int(text)
    except ValueError:
        return None


def mission_color(mission: str, fallback: str = "#5C677D") -> str:
    """Return a stable mission color, or ``fallback`` for an unknown mission."""

    return MISSION_COLORS.get(str(mission).upper(), fallback)


def mission_label(mission: str) -> str:
    """Return a display label for a mission."""

    key = str(mission).upper()
    return MISSION_LABELS.get(key, str(mission))


def mode_degree_color(degree: str | int, fallback: str = "#5C677D") -> str:
    """Return the stable color for spherical-harmonic degree ``degree``."""

    key = _degree_key(degree)
    return MODE_DEGREE_COLORS.get(key, fallback) if key is not None else fallback


def mode_degree_label(degree: str | int) -> str:
    """Return the mathematical label for spherical-harmonic degree ``degree``."""

    key = _degree_key(degree)
    return MODE_DEGREE_LABELS.get(key, str(degree)) if key is not None else str(degree)


def background_color(model: str | int, fallback: str = "#5C677D") -> str:
    """Return the stable color for a Harvey model family member."""

    return BACKGROUND_COLORS.get(_background_key(model), fallback)


def background_label(model: str | int) -> str:
    """Return the mathematical label for a Harvey model family member."""

    key = _background_key(model)
    return BACKGROUND_LABELS.get(key, str(model))


def data_color(role: str, fallback: str = "#5C677D") -> str:
    """Return the color assigned to a semantic data role."""

    return DATA_COLORS.get(str(role).lower(), fallback)


def style_axes(
    ax: Axes,
    *,
    xlabel: str | None = None,
    ylabel: str | None = None,
    title: str | None = None,
    xscale: str | None = None,
    yscale: str | None = None,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    grid: bool = True,
    grid_axis: GridAxis = "y",
    minor: bool = True,
    legend: bool = False,
    legend_loc: str = "best",
    legend_title: str | None = None,
    legend_ncols: int = 1,
    zero_line: bool = False,
    identity_line: bool = False,
) -> Axes:
    """Apply consistent labels, scales, ticks, spines, grid, and legend."""

    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if title is not None:
        ax.set_title(title, pad=6.0)
    if xscale is not None:
        ax.set_xscale(xscale)
    if yscale is not None:
        ax.set_yscale(yscale)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)

    ax.minorticks_on() if minor else ax.minorticks_off()
    ax.grid(grid, axis=grid_axis, which="major")
    for spine in ax.spines.values():
        spine.set_linewidth(0.9)
        spine.set_color("0.18")
    ax.tick_params(which="major", direction="in", top=True, right=True, length=5.0, width=0.9)
    ax.tick_params(which="minor", direction="in", top=True, right=True, length=2.5, width=0.7)
    if zero_line:
        add_zero_line(ax)
    if identity_line:
        add_identity_line(ax)
    if legend:
        style_legend(
            ax,
            loc=legend_loc,
            title=legend_title,
            ncols=legend_ncols,
        )
    return ax


def style_legend(
    ax: Axes,
    *,
    loc: str = "best",
    title: str | None = None,
    ncols: int = 1,
    frameon: bool = True,
    outside: bool = False,
) -> Legend | None:
    """Create a compact legend when the axis has labeled artists."""

    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return None
    kwargs: dict[str, object] = {}
    if outside:
        kwargs["bbox_to_anchor"] = (1.02, 1.0)
        kwargs["borderaxespad"] = 0.0
        loc = "upper left"
    legend = ax.legend(
        handles,
        labels,
        loc=loc,
        title=title,
        ncols=ncols,
        frameon=frameon,
        borderpad=0.35,
        handlelength=1.8,
        handletextpad=0.5,
        columnspacing=0.9,
        **kwargs,
    )
    frame = legend.get_frame()
    frame.set_alpha(0.94)
    frame.set_edgecolor("0.82")
    frame.set_linewidth(0.75)
    return legend


def panel_label(
    ax: Axes,
    label: str,
    *,
    x: float = 0.02,
    y: float = 0.98,
    fontsize: float | None = None,
    boxed: bool = True,
) -> Text:
    """Add a journal-style panel label such as ``(a)``."""

    bbox = None
    if boxed:
        bbox = {
            "boxstyle": "round,pad=0.16",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.88,
        }
    return ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontweight="bold",
        fontsize=fontsize,
        bbox=bbox,
        zorder=10,
    )


def annotate_textbox(
    ax: Axes,
    text: str,
    *,
    x: float = 0.98,
    y: float = 0.97,
    ha: Literal["left", "center", "right"] = "right",
    va: Literal["top", "center", "bottom"] = "top",
    fontsize: float | None = None,
) -> Text:
    """Add a restrained annotation in axis coordinates."""

    return ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontsize=fontsize,
        bbox={
            "boxstyle": "round,pad=0.24",
            "facecolor": "white",
            "edgecolor": "0.84",
            "linewidth": 0.7,
            "alpha": 0.94,
        },
        zorder=9,
    )


def add_zero_line(ax: Axes, *, axis: Literal["x", "y"] = "y") -> Axes:
    """Add a subtle zero reference along one axis."""

    if axis == "y":
        ax.axhline(0.0, color="0.38", linewidth=0.8, alpha=0.75, zorder=0)
    elif axis == "x":
        ax.axvline(0.0, color="0.38", linewidth=0.8, alpha=0.75, zorder=0)
    else:
        raise ValueError("axis must be 'x' or 'y'.")
    return ax


def add_identity_line(ax: Axes, *, color: str = "0.38", linestyle: str = "--") -> Axes:
    """Add ``y=x`` over the shared range of the current axis limits."""

    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    lo = max(xmin, ymin)
    hi = min(xmax, ymax)
    ax.plot([lo, hi], [lo, hi], color=color, linestyle=linestyle, linewidth=0.8, zorder=0)
    return ax


def figure_metadata(
    *,
    source: str | Sequence[str] | None = None,
    description: str | None = None,
    software_version: str = "TopoAstero",
) -> dict[str, str | None]:
    """Build deterministic, source-aware metadata for a released figure."""

    if source is None:
        sources: list[str] = []
    elif isinstance(source, str):
        sources = [source]
    else:
        sources = [str(item) for item in source]
    details = [f"Visual contract: {STYLE_ID}"]
    if sources:
        details.append(f"Machine-readable source: {', '.join(sources)}")
    if description:
        details.append(description)
    return {
        "Creator": f"{software_version}; {STYLE_ID}",
        "Date": None,
        "Description": "; ".join(details),
    }


def _metadata_for_suffix(
    suffix: str, metadata: Mapping[str, str | None]
) -> dict[str, str | None] | None:
    if suffix == ".svg":
        return dict(metadata)
    if suffix == ".pdf":
        return {
            "Creator": metadata.get("Creator"),
            "Subject": metadata.get("Description"),
        }
    if suffix == ".png":
        return {
            "Software": metadata.get("Creator"),
            "Description": metadata.get("Description"),
        }
    return None


def save_figure(
    fig: Figure,
    path: str | Path,
    *,
    close: bool = False,
    dpi: int | None = None,
    facecolor: str = "white",
    pad_inches: float = 0.1,
    formats: Sequence[str] | None = None,
    source: str | Sequence[str] | None = None,
    description: str | None = None,
    software_version: str = "TopoAstero",
    metadata: Mapping[str, str | None] | None = None,
) -> Path:
    """Save a figure reproducibly and optionally export sibling formats."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    export_metadata = figure_metadata(
        source=source,
        description=description,
        software_version=software_version,
    )
    if metadata:
        export_metadata.update(metadata)

    destinations = [destination]
    destinations.extend(
        destination.with_suffix(f".{str(file_format).lstrip('.')}")
        for file_format in formats or ()
    )
    for output in dict.fromkeys(destinations):
        suffix_metadata = _metadata_for_suffix(output.suffix.lower(), export_metadata)
        if suffix_metadata is None:
            fig.savefig(
                output,
                dpi=dpi,
                facecolor=facecolor,
                bbox_inches="tight",
                pad_inches=pad_inches,
            )
        else:
            fig.savefig(
                output,
                dpi=dpi,
                facecolor=facecolor,
                bbox_inches="tight",
                pad_inches=pad_inches,
                metadata=suffix_metadata,
            )
        if output.suffix.lower() == ".svg":
            normalize_text_file_lf(output)
    if close:
        plt.close(fig)
    return destination
