"""Peer-relative z-scores, robust (median/MAD) and classical (mean/std)."""
from __future__ import annotations

from statistics import mean, median, pstdev


def mad(xs: list[float]) -> float:
    m = median(xs)
    return median([abs(x - m) for x in xs]) or 1e-9


def robust_z(subject: float, peers: list[float]) -> float | None:
    if len(peers) < 3:
        return None
    return (subject - median(peers)) / (1.4826 * mad(peers))


def classical_z(subject: float, peers: list[float]) -> float | None:
    if len(peers) < 3:
        return None
    sd = pstdev(peers) or 1e-9
    return (subject - mean(peers)) / sd
