"""Change-point detection (PELT, l2 model) and effect-size scoring.

The change-point period labels the Timeline's "when the change emerged" marker (brief requirement R10).
"""
from __future__ import annotations

import numpy as np
import ruptures as rpt


def changepoints(y: list[float], min_size: int = 2) -> list[int]:
    a = np.asarray(y, dtype=float)
    if len(a) < 6 or np.allclose(a, a[0]):
        return []
    pen = float(np.log(len(a)) * np.var(a) * 2)  # BIC-style penalty
    try:
        # jump=1 is required: ruptures' Pelt defaults to jump=5, which only evaluates breakpoints at
        # multiples of 5 and silently skips nearly every candidate on a short quarterly/annual series
        # (6 to 20 points is typical here). Verified directly: with the default jump, a clean step at
        # index 4 in an 8-point series is missed entirely and index 5 is returned instead.
        breaks = rpt.Pelt(model="l2", min_size=min_size, jump=1).fit(a).predict(pen=pen)
    except Exception:
        return []
    return [i for i in breaks if i < len(a)]


def cp_strength(y: list[float], idx: int) -> float:
    """Effect size of the mean shift at index idx, scaled to [0, 1]."""
    a = np.asarray(y, dtype=float)
    left, right = a[:idx], a[idx:]
    if len(left) < 2 or len(right) < 2:
        return 0.0
    pooled = float(np.sqrt((left.var(ddof=1) + right.var(ddof=1)) / 2)) or 1e-9
    return float(min(1.0, abs(right.mean() - left.mean()) / pooled / 3))


def best_changepoint(y: list[float], min_size: int = 2) -> tuple[int | None, float]:
    """Return (index, strength) of the strongest change-point, or (None, 0.0) if none found."""
    idxs = changepoints(y, min_size)
    if not idxs:
        return None, 0.0
    scored = [(i, cp_strength(y, i)) for i in idxs]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[0]
