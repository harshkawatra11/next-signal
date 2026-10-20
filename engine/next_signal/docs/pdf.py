"""PDF text extraction (PLAN.md §5.8 step 1, spike S15): per-page text via PyMuPDF for the BM25 index and
quote-anchor verification, with pdfplumber tables pulled on demand only for pages BM25 has already
selected (extracting tables from every page of every filing is too slow to run unconditionally).
"""
from __future__ import annotations

import io
import re

import pdfplumber
import pymupdf


def _normalise_whitespace(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Returns page texts, 0-indexed in the list but representing 1-based PDF pages (pages[0] is page 1,
    matching docs/bm25.py's and docs/anchors.py's page-number convention throughout the pipeline).
    Whitespace is normalised so BM25 tokenisation and anchor verification both see consistent text
    regardless of how the source PDF wrapped its lines internally."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [_normalise_whitespace(page.get_text("text")) for page in doc]
    finally:
        doc.close()


def page_count(pdf_bytes: bytes) -> int:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return doc.page_count
    finally:
        doc.close()


def extract_table(pdf_bytes: bytes, page_number: int) -> list[list[str | None]] | None:
    """page_number is 1-based, matching extract_pages' convention. Returns the first table pdfplumber
    finds on that page as a list of rows, or None if the page is out of range or has no table."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
        if page_number < 1 or page_number > len(doc.pages):
            return None
        tables = doc.pages[page_number - 1].extract_tables()
        return tables[0] if tables else None
