"""Shared, minimal chart style for all figures."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # fixed categorical order
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.labelsize": 10.5,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
        "lines.linewidth": 2.0,
        "lines.markersize": 7,
        "font.size": 10.5,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "svg.fonttype": "none",      # keep text as text: smaller, searchable SVGs
        "svg.hashsalt": "ammsim",    # deterministic SVG ids
    })


def subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=TEXT_2,
            fontsize=9.5, va="bottom")


def label_end(ax, x, y, text, color_idx=None, dy=0):
    """Direct label at the end of a line, in text ink (not series colour)."""
    ax.annotate(text, (x, y), xytext=(6, dy), textcoords="offset points",
                color=TEXT, fontsize=9.5, va="center")
