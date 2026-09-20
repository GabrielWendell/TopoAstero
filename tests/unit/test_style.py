from __future__ import annotations

from pathlib import Path
from typing import cast

import matplotlib
import pytest

matplotlib.use("Agg")

import matplotlib as mpl
import matplotlib.pyplot as plt

from topoastero.style import (
    BACKGROUND_COLORS,
    FIGSIZE,
    MISSION_COLORS,
    MODE_DEGREE_COLORS,
    STYLE_ID,
    WINDOW_COLORS,
    WINDOW_LINESTYLES,
    add_zero_line,
    annotate_textbox,
    background_color,
    background_label,
    build_rcparams,
    data_color,
    figure_metadata,
    get_palette,
    list_palettes,
    mission_color,
    mission_label,
    mode_degree_color,
    mode_degree_label,
    panel_label,
    save_figure,
    set_style,
    style_axes,
    style_legend,
    topoastero_style,
)


def test_semantic_palettes_and_accessors_are_stable() -> None:
    assert STYLE_ID == "TA-PLOT-1.0"
    assert set(list_palettes()) == {
        "backgrounds",
        "colorblind",
        "degrees",
        "missions",
        "mono",
        "topoastero",
    }
    assert get_palette() == get_palette("topoastero")
    assert get_palette(["red", "blue"]) == ("red", "blue")
    assert mission_color("kepler") == MISSION_COLORS["KEPLER"]
    assert mission_color("unknown") == "#5C677D"
    assert mission_label("tess") == "TESS"
    assert mission_label("Roman") == "Roman"
    assert mode_degree_color("ell=2") == MODE_DEGREE_COLORS[2]
    assert mode_degree_color("bad") == "#5C677D"
    assert mode_degree_label("l=1") == r"$\ell=1$"
    assert mode_degree_label("bad") == "bad"
    assert background_color("h_2") == BACKGROUND_COLORS["H2"]
    assert background_color(1) == BACKGROUND_COLORS["H1"]
    assert background_color("H9") == "#5C677D"
    assert background_label("H0") == r"$H_0$"
    assert background_label("H9") == "H9"
    assert data_color("ENVELOPE") == "#C44E52"
    assert data_color("unknown") == "#5C677D"
    assert FIGSIZE["double"] == (7.10, 4.40)
    assert WINDOW_COLORS["combined_compressed"] == "#E69F00"
    assert WINDOW_LINESTYLES["combined_compressed"] == "--"


def test_palette_and_parameter_validation() -> None:
    with pytest.raises(ValueError, match="Unknown palette"):
        get_palette("not-a-palette")
    with pytest.raises(ValueError, match="at least one"):
        get_palette([])
    with pytest.raises(ValueError, match="Unsupported context"):
        build_rcparams(context=cast("object", "print"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="use_tex"):
        build_rcparams(use_tex=cast("object", "sometimes"))  # type: ignore[arg-type]


def test_rcparams_cover_all_contexts_and_reproducible_defaults() -> None:
    font_sizes: list[float] = []
    for context in ("paper", "notebook", "talk", "poster"):
        params = build_rcparams(context=context)  # type: ignore[arg-type]
        font_sizes.append(float(params["font.size"]))
        assert params["svg.hashsalt"] == STYLE_ID
        assert params["svg.fonttype"] == "none"
        assert params["text.usetex"] is False
    assert font_sizes == sorted(font_sizes)

    custom = build_rcparams(
        use_tex="auto",
        base_fontsize=12.25,
        dpi=111,
        save_dpi=222,
        transparent=True,
        palette=("#000000",),
        grid=True,
        constrained_layout=True,
    )
    assert custom["font.size"] == 12.25
    assert custom["figure.dpi"] == 111
    assert custom["savefig.dpi"] == 222
    assert custom["savefig.transparent"] is True
    assert custom["axes.grid"] is True
    assert custom["figure.constrained_layout.use"] is True


def test_global_and_context_styles_apply_and_restore() -> None:
    with mpl.rc_context():
        set_style(context="talk", base_fontsize=13.0, grid=True)
        assert mpl.rcParams["font.size"] == 13.0
        assert mpl.rcParams["axes.grid"] is True

    original = mpl.rcParams["font.size"]
    with topoastero_style(context="poster", base_fontsize=19.0):
        assert mpl.rcParams["font.size"] == 19.0
    assert mpl.rcParams["font.size"] == original


def test_axis_helpers_style_labels_lines_legends_and_annotations() -> None:
    with topoastero_style():
        figure, axis = plt.subplots()
        axis.plot([1, 2], [1, 2], label="series")
        styled = style_axes(
            axis,
            xlabel="x",
            ylabel="y",
            title="title",
            xscale="log",
            yscale="log",
            xlim=(1, 3),
            ylim=(1, 3),
            grid=True,
            grid_axis="both",
            minor=False,
            legend=True,
            legend_loc="upper left",
            legend_title="key",
            legend_ncols=2,
            zero_line=False,
            identity_line=True,
        )
        assert styled is axis
        assert axis.get_xlabel() == "x"
        assert axis.get_ylabel() == "y"
        assert axis.get_title() == "title"
        assert axis.get_xscale() == "log"
        assert axis.get_yscale() == "log"
        assert axis.get_legend() is not None
        assert len(axis.lines) == 2
        assert panel_label(axis, "(a)", boxed=True).get_text() == "(a)"
        assert panel_label(axis, "(b)", boxed=False).get_text() == "(b)"
        assert annotate_textbox(axis, "note", ha="left", va="bottom").get_text() == "note"
        plt.close(figure)

        empty_figure, empty_axis = plt.subplots()
        assert style_legend(empty_axis) is None
        empty_axis.plot([0, 1], [1, 0], label="line")
        legend = style_legend(empty_axis, outside=True, frameon=False)
        assert legend is not None
        style_axes(empty_axis, grid=False, minor=True, zero_line=True)
        assert len(empty_axis.lines) == 2
        add_zero_line(empty_axis, axis="x")
        assert len(empty_axis.lines) == 3
        with pytest.raises(ValueError, match="axis must"):
            add_zero_line(empty_axis, axis=cast("object", "z"))  # type: ignore[arg-type]
        plt.close(empty_figure)


def test_metadata_and_multiformat_export_are_source_aware(tmp_path: Path) -> None:
    bare = figure_metadata()
    assert bare["Date"] is None
    assert STYLE_ID in str(bare["Description"])

    metadata = figure_metadata(
        source=["results/a.csv", "results/b.csv"],
        description="Diagnostic panel.",
        software_version="TopoAstero-0.4.0",
    )
    assert metadata["Creator"] == "TopoAstero-0.4.0; TA-PLOT-1.0"
    assert "results/a.csv, results/b.csv" in str(metadata["Description"])
    assert "Diagnostic panel." in str(metadata["Description"])

    figure, axis = plt.subplots()
    axis.plot([0, 1], [0, 1])
    output = save_figure(
        figure,
        tmp_path / "figure.svg",
        formats=("svg", "png", "pdf", "jpg"),
        source="results/source.csv",
        description="Export test.",
        software_version="TopoAstero-0.4.0",
        metadata={"Title": "Style test"},
        close=True,
    )
    assert output == tmp_path / "figure.svg"
    assert not plt.fignum_exists(figure.number)
    for suffix in ("svg", "png", "pdf", "jpg"):
        assert (tmp_path / f"figure.{suffix}").stat().st_size > 100
    svg = output.read_text(encoding="utf-8")
    assert "TA-PLOT-1.0" in svg
    assert "results/source.csv" in svg
    assert "Style test" in svg
