"""Loads the Track D universe from NSE/NIFTY Indices CSVs at run time (never hard-coded), maps a
resolved company to a sub-industry playbook, and selects peers. This is the mechanism behind brief
requirement R19 ("works for every NIFTY 50 company in the track without company-specific tuning") and
R20 (tie-break universe beyond the NIFTY 50).
"""
from __future__ import annotations

import csv
import io
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from rapidfuzz import fuzz, process

from .config import settings
from .http import cached_text

Playbook = Literal["pharma", "hospital", "diagnostics", "generic"]

NIFTY_URLS = {
    "nifty50": [
        "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
        "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    ],
    "niftypharma": [
        "https://niftyindices.com/IndexConstituent/ind_niftypharmalist.csv",
        "https://archives.nseindia.com/content/indices/ind_niftypharmalist.csv",
    ],
    "niftyhealthcare": [
        "https://niftyindices.com/IndexConstituent/ind_niftyhealthcarelist.csv",
        "https://archives.nseindia.com/content/indices/ind_niftyhealthcarelist.csv",
    ],
}


@dataclass
class UniverseRow:
    company_name: str
    industry: str
    symbol: str
    isin: str
    source_index: str


def _parse_csv(text: str, source_index: str) -> list[UniverseRow]:
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        name_key = next((k for k in r if k.strip().lower().startswith("company")), None)
        industry_key = next((k for k in r if k.strip().lower().startswith("industry")), None)
        symbol_key = next((k for k in r if k.strip().lower() == "symbol"), None)
        isin_key = next((k for k in r if "isin" in k.strip().lower()), None)
        if not (name_key and symbol_key):
            continue
        rows.append(UniverseRow(
            company_name=(r.get(name_key) or "").strip(),
            industry=(r.get(industry_key) or "").strip() if industry_key else "",
            symbol=(r.get(symbol_key) or "").strip(),
            isin=(r.get(isin_key) or "").strip() if isin_key else "",
            source_index=source_index,
        ))
    return rows


async def _fetch_index(name: str) -> list[UniverseRow]:
    cache_file = settings.universe_cache_dir / f"{name}.csv"
    for url in NIFTY_URLS[name]:
        try:
            text, _ = await cached_text(url, kind="listing")
            if text and "," in text:
                rows = _parse_csv(text, name)
                if rows:
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(text, encoding="utf-8")
                    return rows
        except Exception:
            continue
    if cache_file.exists():
        return _parse_csv(cache_file.read_text(encoding="utf-8"), name + "_cached")
    return []


_universe_cache: dict[str, list[UniverseRow]] | None = None
_universe_cache_ts: float = 0.0


async def load_universe(force: bool = False) -> dict[str, list[UniverseRow]]:
    global _universe_cache, _universe_cache_ts
    if _universe_cache is not None and not force and (time.time() - _universe_cache_ts) < 6 * 3600:
        return _universe_cache
    out = {}
    for name in NIFTY_URLS:
        out[name] = await _fetch_index(name)
    _universe_cache = out
    _universe_cache_ts = time.time()
    return out


def track_d_n50(universe: dict[str, list[UniverseRow]]) -> list[UniverseRow]:
    return [r for r in universe.get("nifty50", []) if "healthcare" in r.industry.lower()]


def track_d_tiebreak(universe: dict[str, list[UniverseRow]], limit: int = 10) -> list[UniverseRow]:
    n50_symbols = {r.symbol for r in universe.get("nifty50", [])}
    seen: set[str] = set()
    out = []
    for key in ("niftypharma", "niftyhealthcare"):
        for r in universe.get(key, []):
            if r.symbol in n50_symbols or r.symbol in seen:
                continue
            seen.add(r.symbol)
            out.append(r)
    return out[:limit]


# ---- Sub-industry -> playbook mapping (generic text match, no company names) --------------------

def playbook_for(basic_industry: str, industry: str = "") -> Playbook:
    text = f"{basic_industry} {industry}".lower()
    if "hospital" in text or "healthcare service" in text:
        return "hospital"
    if "diagnostic" in text or "laborator" in text and "pharmaceutical" not in text:
        return "diagnostics"
    if "pharmaceutical" in text or "biotech" in text or "drug" in text:
        return "pharma"
    return "generic"


_DIAGNOSTICS_NAME = re.compile(r"\b(lab|laborator|diagnostic|path)", re.I)
_HOSPITAL_NAME = re.compile(r"\b(hospital|healthcare|medical|medic)", re.I)


def playbook_for_row(row: UniverseRow, universe: dict[str, list[UniverseRow]]) -> Playbook:
    """Routes a company to a sub-industry playbook using its index membership and its own name, not the
    coarse `Industry` column the NIFTY 50 index CSV gives: every Track D row in that file reads
    "Healthcare" regardless of whether the company is a pharmaceutical maker or a hospital chain, which
    `playbook_for`'s industry-text rule cannot split further on that column alone. Membership in the
    Nifty Pharma or Nifty Healthcare index, plus a generic keyword match on the company's own name (never
    a specific company name, only sector words), resolves the split. A company in neither index falls
    back to `playbook_for`'s industry-text rule, then "generic", which is the brief's own "works for any
    listed company" robustness requirement (R20)."""
    pharma_symbols = {r.symbol for r in universe.get("niftypharma", [])}
    healthcare_symbols = {r.symbol for r in universe.get("niftyhealthcare", [])}
    if row.symbol in pharma_symbols:
        return "pharma"
    if row.symbol in healthcare_symbols:
        if _HOSPITAL_NAME.search(row.company_name):
            return "hospital"
        if _DIAGNOSTICS_NAME.search(row.company_name):
            return "diagnostics"
    return playbook_for(row.industry)


# ---- Resolve a free-text query against the universe --------------------------------------------

@dataclass
class ResolvedIdentity:
    symbol: str
    company_name: str
    industry: str
    playbook: Playbook
    in_nifty50: bool
    isin: str


_NAME_NOISE = re.compile(
    r"\b(LTD|LIMITED|LIMITED COMPANY|PVT|PRIVATE|LLC|INC|CORP|CORPORATION|COMPANY|CO)\b"
)


def _normalise_name(s: str) -> str:
    """Strip punctuation (periods, apostrophes), legal-entity suffixes and casing before fuzzy matching.
    Real company names carry these inconsistently (apostrophes, periods, "Ltd." suffixes versus a user
    typing the bare name), and WRatio alone can score such a pair at under 20/100 unnormalised, which
    would silently fail to resolve almost any real free-text company query (verified directly against a
    real NIFTY 50 name during development; see DECISIONS.md and the build log for the specific case and
    scores, kept out of this docstring so no company name appears in engine source, per the no-hard-
    coding rule). token_sort_ratio on normalised text resolves the same kind of pair reliably.
    """
    s = s.upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _NAME_NOISE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def resolve_offline(query: str, universe: dict[str, list[UniverseRow]]) -> Optional[ResolvedIdentity]:
    """Resolve against the loaded universe only (no network). Used by pipeline/resolve.py as the first
    attempt before falling back to a live NSE lookup for a name/symbol outside the Track D universe."""
    all_rows: list[UniverseRow] = []
    seen_symbols: set[str] = set()
    for rows in universe.values():
        for r in rows:
            if r.symbol not in seen_symbols:
                seen_symbols.add(r.symbol)
                all_rows.append(r)

    q = query.strip().upper()
    for r in all_rows:
        if r.symbol.upper() == q:
            return _to_identity(r, universe)

    if not all_rows:
        return None
    norm_query = _normalise_name(query)
    norm_candidates = [_normalise_name(r.company_name) for r in all_rows]
    match = process.extractOne(norm_query, norm_candidates, scorer=fuzz.token_sort_ratio, score_cutoff=85)
    if match is None:
        return None
    return _to_identity(all_rows[match[2]], universe)


def _to_identity(r: UniverseRow, universe: dict[str, list[UniverseRow]]) -> ResolvedIdentity:
    in_n50 = any(x.symbol == r.symbol for x in universe.get("nifty50", []))
    return ResolvedIdentity(
        symbol=r.symbol,
        company_name=r.company_name,
        industry=r.industry,
        playbook=playbook_for_row(r, universe),
        in_nifty50=in_n50,
        isin=r.isin,
    )


def peers(symbol: str, universe: dict[str, list[UniverseRow]], market_caps: dict[str, float], k: int = 5) -> list[str]:
    """Rank by absolute log-difference of market cap among same-playbook companies, excluding the subject.
    market_caps: {symbol: market_cap}. Generic, no hand-picked lists."""
    import math

    all_rows: dict[str, UniverseRow] = {}
    for rows in universe.values():
        for r in rows:
            all_rows[r.symbol] = r
    subject = all_rows.get(symbol)
    if subject is None:
        return []
    subject_pb = playbook_for_row(subject, universe)
    subject_cap = market_caps.get(symbol)
    candidates = [
        (s, r) for s, r in all_rows.items()
        if s != symbol and playbook_for_row(r, universe) == subject_pb and s in market_caps
    ]
    if subject_cap is None or not candidates:
        return [s for s, _ in candidates[:k]]
    scored = sorted(candidates, key=lambda sr: abs(math.log(market_caps[sr[0]] + 1) - math.log(subject_cap + 1)))
    return [s for s, _ in scored[:k]]
