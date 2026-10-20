"""Quote-anchor verification: the anti-hallucination core. A fact is only kept if its quote appears
verbatim (after whitespace/digit-grouping normalisation) in the source page text.
"""
from __future__ import annotations

import re


def _normalise(s: str) -> str:
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"(?<=\d),(?=\d)", "", s)  # 1,51,836 -> 151836
    return re.sub(r"\s+", " ", s).strip().lower()


def verify(quote: str, page_text: str) -> bool:
    q = _normalise(quote)
    return len(q) >= 12 and q in _normalise(page_text)
