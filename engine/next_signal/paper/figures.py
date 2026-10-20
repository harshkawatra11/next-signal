"""Grayscale research-paper figures. Series are told apart by line style and marker, never colour.
Text is converted to paths (svg.fonttype 'path') so the figure renders identically everywhere; the
typeface is matplotlib's bundled STIX, which matches the paper's STIX Two body text."""
from __future__ import annotations

import io
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 8.5,
    "axes.linewidth": 0.6, "axes.edgecolor": "black", "axes.labelcolor": "black",
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": "black", "ytick.color": "black", "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.direction": "out", "ytick.direction": "out", "legend.frameon": False, "legend.fontsize": 8,
    "lines.linewidth": 1.1, "lines.markersize": 3.5, "svg.fonttype": "path", "figure.dpi": 100,
})
WIDTH_IN = 6.0
STYLES = [dict(color="black", linestyle="-", marker="o"),
          dict(color="black", linestyle="--", marker="s", markerfacecolor="white"),
          dict(color="black", linestyle=":", marker="^", markerfacecolor="white")]


def _svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    s = buf.getvalue()
    return s[s.find("<svg"):]


def revenue_ebitda(labels: list[str], revenue: list[Optional[float]], ebitda: list[Optional[float]]) -> str:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.4))
    x = range(len(labels))
    ax.plot(x, revenue, label="Revenue from operations", **STYLES[0])
    if any(v is not None for v in ebitda):
        ax.plot(x, ebitda, label="EBITDA", **STYLES[1])
    ax.set_xticks(list(x), labels)
    ax.set_ylabel("Rs crore")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(loc="upper left")
    return _svg(fig)


def metric_vs_peers(labels: list[str], subject: list[Optional[float]], peer_median: list[Optional[float]],
                    peer_low: list[Optional[float]], peer_high: list[Optional[float]], subject_label: str,
                    ylabel: str, changepoint_index: Optional[int], changepoint_label: str, pct: bool) -> str:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.6))
    x = list(range(len(labels)))
    scale = 100.0 if pct else 1.0
    f = lambda vs: [None if v is None else v * scale for v in vs]  # noqa: E731
    if any(v is not None for v in peer_low):
        lo, hi = f(peer_low), f(peer_high)
        xs = [i for i in x if lo[i] is not None and hi[i] is not None]
        ax.fill_between(xs, [lo[i] for i in xs], [hi[i] for i in xs], color="0.85", linewidth=0, label="Peer range")
    ax.plot(x, f(peer_median), label="Peer median", **STYLES[1])
    ax.plot(x, f(subject), label=subject_label, **STYLES[0])
    if changepoint_index is not None:
        ax.axvline(changepoint_index, color="black", linestyle=":", linewidth=0.8)
        ax.annotate(changepoint_label, xy=(changepoint_index, ax.get_ylim()[1]), xytext=(4, -10),
                    textcoords="offset points", fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylabel(ylabel)
    ax.legend(loc="best")
    return _svg(fig)


def peer_bars(names: list[str], values: list[float], subject_index: int, xlabel: str, pct: bool) -> str:
    order = sorted(range(len(values)), key=lambda i: values[i])
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 0.35 * len(values) + 0.6))
    scale = 100.0 if pct else 1.0
    for row, i in enumerate(order):
        is_subject = i == subject_index
        ax.barh(row, values[i] * scale, color="black" if is_subject else "white", edgecolor="black",
                linewidth=0.6, hatch=None if is_subject else "////", height=0.6)
    ax.set_yticks(range(len(order)), [names[i] for i in order])
    ax.set_xlabel(xlabel)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return _svg(fig)


def event_timeline(dates: list, labels: list[str], changepoint_date=None) -> str:
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 1.6))
    ax.axhline(0, color="black", linewidth=0.6)
    for i, (d, lab) in enumerate(zip(dates, labels)):
        y = 0.6 if i % 2 == 0 else -0.6
        ax.vlines(d, 0, y, color="black", linewidth=0.5)
        ax.plot([d], [0], marker="o", color="black", markersize=3)
        ax.text(d, y, lab[:48], fontsize=7.5, ha="center", va="bottom" if y > 0 else "top")
    if changepoint_date is not None:
        ax.axvline(changepoint_date, color="black", linestyle=":", linewidth=0.8)
    ax.set_ylim(-1.2, 1.2)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    fig.autofmt_xdate()
    return _svg(fig)
