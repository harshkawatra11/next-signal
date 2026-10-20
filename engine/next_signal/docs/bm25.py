"""BM25 ranking over a document's pages, used to pick candidate pages for quote-anchored LLM extraction
(PLAN.md §5.8 step 2) instead of feeding an entire PDF to the model.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class PageIndex:
    """pages: list of page text, 0-indexed internally but reported 1-indexed (PDF page convention)."""

    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self._corpus = [tokenize(p) for p in pages]
        self._bm25 = BM25Okapi(self._corpus) if self._corpus and any(self._corpus) else None

    def top_pages(self, query_terms: list[str], k: int = 4) -> list[tuple[int, float]]:
        """Returns [(page_number_1_indexed, score), ...] sorted by descending score."""
        if self._bm25 is None:
            return []
        query_tokens: list[str] = []
        for term in query_terms:
            query_tokens.extend(tokenize(term))
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda t: t[1], reverse=True)
        return [(idx + 1, float(score)) for idx, score in ranked[:k] if score > 0]


def candidate_pages_for_metric(pages: list[str], synonyms: list[str], k: int = 4) -> list[int]:
    """Convenience wrapper: returns just the 1-indexed page numbers for a metric's synonym list."""
    idx = PageIndex(pages)
    return [p for p, _ in idx.top_pages(synonyms, k=k)]
