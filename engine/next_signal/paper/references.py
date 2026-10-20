"""Numbered references for the research paper. Built from the report's own Document and Event
records so every citation points at a document the engine actually retrieved; nothing here is
invented. Peer company filings are not individually tracked in schemas.Document (no entity link),
so the peer bundle entry below cites the peer's public NSE quote page, a stable and genuine URL,
rather than fabricating a specific filing URL.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import plain


@dataclass
class Reference:
    number: int
    text: str     # full formatted entry, no number prefix
    url: str
    doc_ids: list[str]


def _filing_entry(company: str, doc) -> str:
    published = plain.date_long(doc.published_at) if doc.published_at else ""
    return (
        f"{company}. Financial results for the quarter ended {published}. "
        f"Filed with the National Stock Exchange of India. {doc.url}"
    )


def _evidence_entry(doc) -> str:
    published = plain.date_long(doc.published_at) if doc.published_at else ""
    return f"{doc.publisher}. {doc.title}. {published}. {doc.url}"


def _peer_bundle_entry(peer_symbol: str, peer_names: dict[str, str]) -> str:
    name = peer_names.get(peer_symbol, peer_symbol)
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={peer_symbol}"
    return f"{name}. Quarterly financial results. National Stock Exchange of India. {url}"


def build_references(report) -> tuple[list["Reference"], dict[str, int]]:
    company = report.meta.company
    by_doc = {d.doc_id: d for d in report.documents}

    refs: list[Reference] = []
    doc_to_num: dict[str, int] = {}
    seen_doc_ids: set[str] = set()

    def _add(doc_id: str, text: str) -> None:
        if doc_id in seen_doc_ids:
            return
        seen_doc_ids.add(doc_id)
        n = len(refs) + 1
        refs.append(Reference(number=n, text=text, url=by_doc[doc_id].url if doc_id in by_doc else "", doc_ids=[doc_id]))
        doc_to_num[doc_id] = n

    # (1) subject quarterly filings behind Table 1, newest first.
    for row in report.financials[:8]:
        if row.doc_id in by_doc and row.doc_id not in seen_doc_ids:
            _add(row.doc_id, _filing_entry(company, by_doc[row.doc_id]))

    # (2) evidence documents of the discovery not already listed.
    if report.discovery:
        for ev in report.discovery.evidence:
            if ev.doc_id in by_doc and ev.doc_id not in seen_doc_ids:
                _add(ev.doc_id, _evidence_entry(by_doc[ev.doc_id]))
            elif ev.doc_id not in seen_doc_ids:
                # Evidence item carries its own citation fields even when the full Document is absent.
                seen_doc_ids.add(ev.doc_id)
                n = len(refs) + 1
                published = plain.date_long(ev.published_at) if ev.published_at else ""
                refs.append(Reference(
                    number=n, url=ev.url, doc_ids=[ev.doc_id],
                    text=f"{ev.publisher}. {ev.title}. {published}. {ev.url}",
                ))
                doc_to_num[ev.doc_id] = n

    # (3) one entry per peer company covering its filings.
    peer_names = getattr(report, "peer_names", {}) or {}
    for peer in report.peers:
        key = f"peer:{peer}"
        if key in seen_doc_ids:
            continue
        seen_doc_ids.add(key)
        n = len(refs) + 1
        refs.append(Reference(number=n, text=_peer_bundle_entry(peer, peer_names),
                               url=f"https://www.nseindia.com/get-quotes/equity?symbol={peer}", doc_ids=[key]))
        doc_to_num[key] = n

    # (4) regulator or rating events cited in the timeline.
    if report.discovery:
        for pt in report.discovery.timeline:
            if pt.event_id:
                ev = next((e for e in report.events if e.event_id == pt.event_id), None)
                if ev and ev.url and ev.event_id not in seen_doc_ids:
                    seen_doc_ids.add(ev.event_id)
                    n = len(refs) + 1
                    refs.append(Reference(
                        number=n, url=ev.url, doc_ids=[ev.event_id],
                        text=f"{ev.origin_class.replace('_', ' ').title()}. {ev.title}. {plain.date_long(ev.date)}. {ev.url}",
                    ))
                    doc_to_num[ev.event_id] = n

    return refs, doc_to_num
