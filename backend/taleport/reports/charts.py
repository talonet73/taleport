"""Vector charts for the PDF: matplotlib → SVG → ReportLab Drawing, text kept as text.

Colors are the validated chart palette of the app (`--tp-chart-1`, `--tp-series-1…5` in
`frontend/src/index.css`), so a PDF reads like the dashboards. One axis per chart, legend
only with two or more series, values written next to bars.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("svg")  # no GUI backend: reports are built in a worker thread

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
from reportlab.graphics.shapes import Drawing  # noqa: E402
from svglib.fonts import register_font  # noqa: E402
from svglib.svglib import svg2rlg  # noqa: E402

# Real text in the SVG, drawn by ReportLab with the same DejaVu font as the report body:
# selectable in the PDF and sharper than glyph outlines.
plt.rcParams.update({"svg.fonttype": "none", "font.family": "DejaVu Sans", "font.size": 9})
register_font(
    "DejaVu Sans", str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf")
)


@dataclass(frozen=True)
class ChartColors:
    surface: str
    text: str
    muted: str
    grid: str
    series: tuple[str, ...]


def _figure(width_pt: float, height_pt: float, colors: ChartColors) -> tuple[Any, Any]:
    fig, ax = plt.subplots(figsize=(width_pt / 72, height_pt / 72), dpi=72)
    fig.patch.set_facecolor(colors.surface)
    ax.set_facecolor(colors.surface)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(colors.grid)
    ax.tick_params(colors=colors.muted, length=0)
    return fig, ax


def _to_drawing(fig: Any) -> Drawing:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", facecolor=fig.get_facecolor())
    plt.close(fig)
    buffer.seek(0)
    drawing = svg2rlg(buffer)
    if drawing is None:  # pragma: no cover - svglib returns None only on unreadable input
        raise ValueError("chart conversion failed")
    return drawing


def bars(
    labels: list[str], values: list[int], notes: list[str], width: float, colors: ChartColors
) -> Drawing:
    """Horizontal bars, biggest on top, with the count and its share written at the end."""
    height = 26 + 17 * len(labels)
    fig, ax = _figure(width, height, colors)
    positions = range(len(labels))[::-1]
    ax.barh(list(positions), values, color=colors.series[0], height=0.62)
    ax.set_yticks(list(positions), labels, color=colors.text)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    top = max(values) if values else 1
    for y, value, note in zip(positions, values, notes, strict=True):
        ax.text(
            value + top * 0.01, y, f" {value} · {note}", va="center", color=colors.text, fontsize=8
        )
    ax.set_xlim(0, top * 1.22)
    fig.tight_layout(pad=0.4)
    return _to_drawing(fig)


def lines(
    days: list[str], series: list[dict[str, Any]], width: float, colors: ChartColors
) -> Drawing:
    fig, ax = _figure(width, 190, colors)
    x = range(len(days))
    for i, s in enumerate(series):
        ax.plot(
            list(x),
            s["values"],
            color=colors.series[i % len(colors.series)],
            linewidth=1.8,
            marker="o",
            markersize=3.5,
            label=s["name"],
        )
    _day_ticks(ax, days)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    ax.grid(axis="y", color=colors.grid, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    if len(series) > 1:
        # Above the plot, in the figure: the plot keeps the full width.
        legend = fig.legend(
            loc="upper left",
            ncol=min(len(series), 5),
            frameon=False,
            fontsize=8,
            handlelength=1.4,
        )
        for text in legend.get_texts():
            text.set_color(colors.text)
        fig.tight_layout(pad=0.4, rect=(0, 0, 1, 0.86))
    else:
        fig.tight_layout(pad=0.4)
    return _to_drawing(fig)


def daily(days: list[str], values: list[int], width: float, colors: ChartColors) -> Drawing:
    fig, ax = _figure(width, 150, colors)
    x = list(range(len(days)))
    ax.bar(x, values, color=colors.series[0], width=0.6)
    for xi, value in zip(x, values, strict=True):
        if value:
            ax.text(xi, value, str(value), ha="center", va="bottom", color=colors.text, fontsize=8)
    _day_ticks(ax, days)
    ax.yaxis.set_visible(False)
    ax.set_ylim(0, (max(values) or 1) * 1.18)
    fig.tight_layout(pad=0.4)
    return _to_drawing(fig)


def _day_ticks(ax: Any, days: list[str]) -> None:
    # At most ~8 labels ("2 nov"): readable at any period length.
    step = max(1, round(len(days) / 8))
    shown = list(range(0, len(days), step))
    ax.set_xticks(shown, [days[i] for i in shown])
