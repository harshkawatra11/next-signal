"""Market-model event study: CAR and t-stat around an event date.

Estimation window [-250, -30] trading days before the event, event windows [-1,+1] and [-5,+5].
Market proxy: NIFTY 50 by default; sector index used as a robustness check.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class EventStudyResult:
    car: float
    t_stat: float
    n_est: int
    window: tuple[int, int]


def _log_returns(prices: list[float]) -> np.ndarray:
    p = np.asarray(prices, dtype=float)
    return np.diff(np.log(p))


def event_study(
    stock_prices: list[float],
    market_prices: list[float],
    event_index: int,
    window: tuple[int, int] = (-1, 1),
    est_window: tuple[int, int] = (-250, -30),
) -> EventStudyResult | None:
    """All price series must be aligned by trading day and cover at least est_window[0] before
    event_index and window[1] after it. event_index is the index of the event day in the price arrays.
    """
    r_i = _log_returns(stock_prices)
    r_m = _log_returns(market_prices)
    if len(r_i) != len(r_m):
        return None
    # returns array index j corresponds to price index j+1, so event day return is at r[event_index - 1]
    ev_ret_idx = event_index - 1
    est_start = ev_ret_idx + est_window[0]
    est_end = ev_ret_idx + est_window[1]
    if est_start < 0 or est_end >= len(r_i) or est_end <= est_start + 10:
        return None
    x = r_m[est_start:est_end]
    y = r_i[est_start:est_end]
    if np.allclose(x.var(), 0):
        return None
    beta, alpha = np.polyfit(x, y, 1)
    resid = y - (alpha + beta * x)
    sigma_eps = float(resid.std(ddof=2)) or 1e-9

    w0, w1 = ev_ret_idx + window[0], ev_ret_idx + window[1]
    if w0 < 0 or w1 >= len(r_i):
        return None
    ar = r_i[w0 : w1 + 1] - (alpha + beta * r_m[w0 : w1 + 1])
    car = float(ar.sum())
    length = w1 - w0 + 1
    t_stat = car / (sigma_eps * np.sqrt(length))
    return EventStudyResult(car=car, t_stat=float(t_stat), n_est=est_end - est_start, window=window)
