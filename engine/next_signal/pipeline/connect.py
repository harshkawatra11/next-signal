"""Connect stage: turn the source plan into documents, quote-anchored Facts and graded EvidenceItems
(PLAN.md §5.8). Live document fetch (sources/bse.py, sources/screener.py, regulator clients) and LLM-based
quote extraction are not wired yet; this module implements the deterministic parts that do not depend on
them, so Calculate and the other later stages stay testable against this stage's real output shape.
"""
from __future__ import annotations

from datetime import date, datetime

from .. import universe as universe_module
from ..docs.anchors import verify
from ..docs.bm25 import PageIndex
from ..docs.xbrl import quarter_facts
from ..grading.admiralty import classify
from ..http import cached_bytes
from ..metrics.periods import fiscal_label
from ..schemas import Anchor, Document, Fact, FinancialRow, EvidenceItem
from ..sources.nse import classify_kind
from ..sources.nse_financials import fetch_filings
from .context import RunContext

_NSE_DATE_FORMATS = ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y")
_XBRL_HEADERS = {"Referer": "https://www.nseindia.com/"}


def classify_document(
    url: str, title: str, kind: str, publisher: str, published_at: datetime | None, is_peer: bool = False
) -> Document:
    origin_class, reliability = classify(url, is_peer=is_peer)
    doc_id = __import__("hashlib").sha1(url.encode()).hexdigest()[:12]
    return Document(
        doc_id=doc_id, kind=kind, title=title, url=url, publisher=publisher, origin_class=origin_class,
        published_at=published_at, fetched_at=datetime.now(), reliability=reliability,
    )


def point_in_time_filter(documents: list[Document], as_of: date) -> list[Document]:
    """Drops documents published after as_of so a time-travel run never sees the future. A document with
    no published_at is dropped too: an unstamped document cannot be placed in time, so including it would
    silently leak look-ahead information into a point-in-time replay."""
    kept = []
    for d in documents:
        if d.published_at is None:
            continue
        if d.published_at.date() > as_of:
            continue
        kept.append(d)
    return kept


def build_page_index(pages: list[str]) -> PageIndex:
    return PageIndex(pages)


def anchor_fact(
    fact_id: str, metric: str, period: str, value: float, unit: str, entity: str,
    doc: Document, page: int, page_text: str, quote: str,
) -> Fact | None:
    """Returns a Fact with a verified Anchor, or None (anchor_fail) if the quote does not appear verbatim
    in the page text. This is the anti-hallucination gate: callers must drop the fact on None, never
    relax the check or substitute an unverified anchor."""
    if not verify(quote, page_text):
        return None
    return Fact(
        fact_id=fact_id, metric=metric, period=period, value=value, unit=unit, entity=entity,
        anchor=Anchor(doc_id=doc.doc_id, page=page, quote=quote, verified=True),
    )


def evidence_item_from_fact(ev_id: str, fact: Fact, doc: Document, supports: list[str]) -> EvidenceItem:
    return EvidenceItem(
        ev_id=ev_id, doc_id=doc.doc_id, title=doc.title, url=doc.url, publisher=doc.publisher,
        origin_class=doc.origin_class, reliability=doc.reliability, published_at=doc.published_at,
        supports=supports, contradicts=[], anchor=fact.anchor,
    )


def _parse_nse_datetime(raw) -> datetime | None:
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in _NSE_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def document_from_nse_item(item: dict, is_peer: bool = False) -> Document | None:
    """item: one row from NSE's corporate-announcements API response (PLAN.md §5.5.1: `desc` the
    subject, `attchmntText` extra text, `attchmntFile` the PDF URL on nsearchives, `an_dt`/`sort_date`
    the publish timestamp). Returns None for an item with no attachment URL: a bare text announcement
    carries nothing Connect can later quote-anchor a fact against, so it is not worth a Document record."""
    url = item.get("attchmntFile")
    if not url:
        return None
    subject = item.get("desc", "") or ""
    attachment_text = item.get("attchmntText", "") or ""
    kind = classify_kind(subject, attachment_text)
    published_at = _parse_nse_datetime(item.get("an_dt") or item.get("sort_date"))
    return classify_document(url, subject or kind, kind, "NSE", published_at, is_peer=is_peer)


def documents_from_nse_announcements(items: list[dict], is_peer: bool = False) -> list[Document]:
    docs = [document_from_nse_item(item, is_peer=is_peer) for item in items]
    return [d for d in docs if d is not None]


def _nse_response_items(raw) -> list[dict]:
    """NSE's announcement endpoint has been observed to return either a bare JSON array or an object
    wrapping the array under a 'data' key; both shapes are accepted rather than assuming one."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("data") or []
    return []


async def fetch_documents(ctx: RunContext, nse_client=None) -> list[Document]:
    """Live document fetch. `nse_client` is an injected `sources.nse.NSE`-shaped object (duck-typed on
    `.announcements(symbol, frm, to)`); passing None (the default) degrades to an empty list rather than
    making a network call, the same honest-stub pattern as discover.py::quickpass_metrics. BSE fallback,
    screener and the regulator clients are real parsers now (sources/bse.py, screener.py, openfda.py,
    orangebook.py, fda_web.py, ratings.py) but are not yet wired into this fetch step; each needs its own
    source-plan-driven call (PLAN.md §5.7 step 6), not a blanket always-call-everything approach."""
    if nse_client is None:
        return []
    frm = date(ctx.as_of.year - 1, ctx.as_of.month, ctx.as_of.day).strftime("%d-%m-%Y")
    to = ctx.as_of.strftime("%d-%m-%Y")
    try:
        raw = await nse_client.announcements(ctx.symbol, frm, to)
    except Exception:
        return []
    return documents_from_nse_announcements(_nse_response_items(raw))


async def fetch_financials(
    nse_client, symbol: str, as_of: date, limit: int = 12, is_peer: bool = False
) -> tuple[list[Document], list[Fact], list[FinancialRow]]:
    """Fetches up to `limit` quarterly filings for `symbol`, then each one's XBRL instance, returning the
    Documents, the verified Facts extracted from them, and the same data regrouped into FinancialRow
    (one row per quarter, for the Report contract's own P&L table). Degrades to ([], [], []) when
    nse_client is None (the honest-stub pattern fetch_documents already uses), and skips, rather than
    aborts on, a filing whose XBRL fetch fails or whose instance has no quarter-matching facts: one bad
    filing must not cost the other eleven. FinancialRow is built here, not from the flattened Facts list
    afterward, because only here is the filing's own exact `to_date` still at hand; a Fact carries only
    the fiscal label (e.g. "Q3FY25"), which is not reversible back to a calendar date."""
    if nse_client is None:
        return [], [], []
    filings = await fetch_filings(nse_client, symbol, as_of=as_of, limit=limit)
    documents: list[Document] = []
    facts: list[Fact] = []
    financial_rows: list[FinancialRow] = []
    for filing in filings:
        doc = classify_document(
            filing.xbrl_url, f"{symbol} {filing.financial_year} results XBRL", "results_xbrl", "NSE",
            filing.broadcast_at, is_peer=is_peer,
        )
        try:
            xbrl_bytes, _ = await cached_bytes(filing.xbrl_url, kind="xbrl", headers=_XBRL_HEADERS)
            rows = quarter_facts(xbrl_bytes, filing.from_date, filing.to_date)
        except Exception:
            # A network failure, a 403/404 served as an HTML page with a 200 status, or a malformed
            # instance document are all equally "this filing is unusable": skip it and move on to the
            # next one, rather than letting one bad XBRL URL (observed live against a peer company)
            # abort every remaining filing and peer in the run.
            continue
        if not rows:
            continue
        documents.append(doc)
        period_label = fiscal_label(filing.to_date)
        values: dict[str, float] = {}
        for row in rows:
            facts.append(Fact(
                fact_id=f"{symbol}-{period_label}-{row['item']}", metric=row["item"], period=period_label,
                value=row["value"], unit=row["unit"], entity=symbol,
                anchor=Anchor(doc_id=doc.doc_id, page=None, quote=row["anchor_quote"], verified=True),
            ))
            values[row["item"]] = row["value"]
        financial_rows.append(FinancialRow(
            period=period_label, period_end=filing.to_date, values=values, doc_id=doc.doc_id,
        ))
    return documents, facts, financial_rows


async def select_peers(ctx: RunContext, k: int = 5) -> list[str]:
    """Picks up to k same-playbook companies from the live Track D universe, excluding the subject, in
    the index CSV's own order. This is a generic, deterministic fallback used when no market-cap data is
    available to rank by (NSE's quote-equity endpoint, the only source for that, returns 403 under this
    engine's current access pattern): index order is not company-specific and applies to any symbol, so
    it satisfies the no-hard-coding rule the same way universe.peers()'s market-cap ranking does."""
    uni = await universe_module.load_universe()
    all_rows: dict[str, universe_module.UniverseRow] = {}
    for rows in uni.values():
        for r in rows:
            all_rows.setdefault(r.symbol, r)
    subject = all_rows.get(ctx.symbol)
    if subject is None:
        return []
    subject_pb = universe_module.playbook_for_row(subject, uni)
    peers = [
        s for s, r in all_rows.items()
        if s != ctx.symbol and universe_module.playbook_for_row(r, uni) == subject_pb
    ]
    return peers[:k]


async def run(ctx: RunContext, nse_client=None, select_peers_fn=None) -> None:
    """`select_peers_fn` lets a caller inject an alternative to the real select_peers() (which reads the
    live universe), defaulting to the real one; a test that injects an `nse_client` but does not want a
    live universe fetch should pass `select_peers_fn=lambda ctx: []` rather than relying on a disk-cache
    hit to make the real one fast, the same injectable-seam pattern used throughout this pipeline's other
    stages for a not-yet-fully-wired or network-touching dependency."""
    fetched = await fetch_documents(ctx, nse_client=nse_client)

    financial_docs, financial_facts, financial_rows = await fetch_financials(
        nse_client, ctx.symbol, ctx.as_of, limit=12
    )
    ctx.facts.extend(financial_facts)
    ctx.financials = sorted(financial_rows, key=lambda r: r.period_end, reverse=True)

    if not ctx.peers and nse_client is not None:
        ctx.peers = await (select_peers_fn or select_peers)(ctx)

    peer_docs: list[Document] = []
    peer_facts: list[Fact] = []
    for peer_symbol in ctx.peers:
        p_docs, p_facts, _ = await fetch_financials(nse_client, peer_symbol, ctx.as_of, limit=6, is_peer=True)
        peer_docs.extend(p_docs)
        peer_facts.extend(p_facts)
    ctx.facts.extend(peer_facts)

    documents = point_in_time_filter(fetched + financial_docs + peer_docs, ctx.as_of)
    ctx.documents.extend(documents)
    ctx.trace.append({
        "stage": "connect",
        "documents_fetched": len(fetched) + len(financial_docs) + len(peer_docs),
        "documents_in_window": len(documents),
        "facts": len(ctx.facts),
    })
