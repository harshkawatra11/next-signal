"""Analysis of Competing Hypotheses (Heuer, 1999, ch. 8): the matrix that produces the Counterargument.

The main hypothesis has to hold its own in this matrix (lowest, or near-lowest, inconsistency); the rival with
the next-lowest inconsistency becomes the discovery's stated Counterargument (brief requirement R12).
"""
from __future__ import annotations

from typing import Callable

SCORE = {"CC": 2, "C": 1, "N": 0, "I": -1, "II": -2}
CellFn = Callable[[str, str], str]


def ach_matrix(hyp_ids: list[str], ev_ids: list[str], cell: CellFn) -> dict:
    """cell(ev_id, hyp_id) -> one of 'CC', 'C', 'N', 'I', 'II'."""
    cells = [[cell(e, h) for h in hyp_ids] for e in ev_ids]
    incons = [
        sum(min(0, SCORE[cells[i][j]]) for i in range(len(ev_ids)))
        for j in range(len(hyp_ids))
    ]
    ranked = sorted(range(len(hyp_ids)), key=lambda j: incons[j], reverse=True)  # least inconsistent (highest score) first
    return {
        "hypotheses": hyp_ids,
        "evidence": ev_ids,
        "cells": cells,
        "inconsistency": incons,
        "ranked": [hyp_ids[j] for j in ranked],
    }


def main_holds(m: dict, main_id: str) -> bool:
    if not m["hypotheses"]:
        return False
    best = max(m["inconsistency"])
    j = m["hypotheses"].index(main_id)
    return m["inconsistency"][j] >= best - 1


def counterargument(m: dict, main_id: str) -> str | None:
    rivals = [h for h in m["ranked"] if h != main_id]
    return rivals[0] if rivals else None
