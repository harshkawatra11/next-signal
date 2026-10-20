"""Ind AS XBRL instance document parsing (PLAN.md §5.8 step 4): maps the P&L line-item tags the metric
library needs to their reported values and reporting-period context, from a company's NSE-filed XBRL
instance document. An XBRL fact is machine-readable at the source, so its anchor is `verified=True` by
construction once extracted; no quote-matching against page text is needed, unlike a PDF-sourced fact.

Tag names and the context shape below are confirmed against a live NSE XBRL instance (verified 16 Oct
2026, see build-log.md), not assumed from documentation. The probe caught two things a naive reader would
miss. First, the real tag for total expenses is "Expenses", not "TotalExpenses" (no "TotalExpenses" tag
exists in the instance at all). Second, and more consequential: a single quarter's broadcast can carry
two (or more) non-dimensional contexts whose period dates, entity and scenario are all byte-for-byte
identical, differing only in their context id (observed as "OneD" and "FourD" in one real filing), with
genuinely different reported values for the same tag (a roughly 3x ratio on revenue). This is NSE's
convention for bundling standalone and consolidated figures inside one XBRL instance, but the instance
itself gives no machine-readable attribute that says which context is which: no dimension, no footnote
reference, nothing beyond the id string. Resolving this definitively would need either the taxonomy's own
label linkbase (not fetched here) or the human-readable rendered statement published alongside the XBRL.
Lacking either, quarter_facts() below takes the first occurrence in document order for each (item,
period) pair, which is deterministic and matches what the filer listed first, and is honestly documented
as an unresolved ambiguity rather than a verified choice. A consumer that needs certainty about which
basis (standalone or consolidated) a number uses should cross-check it against the
`results-comparision` endpoint's own figures for the same period, which carries an explicit basis.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from lxml import etree

# Element local-names (namespace prefix stripped) mapped to our own raw line-item vocabulary. Ind AS
# taxonomy filings on NSE commonly use these standard element names regardless of which namespace prefix
# (in-capmkt, in-bse-fin, etc.) a given filer's instance document declares.
TAG_TO_ITEM = {
    "RevenueFromOperations": "revenue",
    "OtherIncome": "other_income",
    "CostOfMaterialsConsumed": "materials",
    "PurchasesOfStockInTrade": "purchases",
    "ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade": "inventory_change",
    "EmployeeBenefitExpense": "employee",
    "FinanceCosts": "finance_costs",
    "DepreciationDepletionAndAmortisationExpense": "dna",
    "OtherExpenses": "other_expenses",
    "Expenses": "total_expenses",
    "ProfitBeforeExceptionalItemsAndTax": "pbt_before_exceptional",
    "ExceptionalItemsBeforeTax": "exceptional_items",
    "ProfitBeforeTax": "pbt",
    "TaxExpense": "tax_expense",
    "ProfitLossForPeriod": "pat",
    "ProfitOrLossAttributableToOwnersOfParent": "pat_owners",
}

_CRORE = 1e7


def local_name(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_xbrl_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_contexts(root) -> dict[str, dict]:
    """Returns {context_id: {"start": date_or_None, "end": date_or_None, "instant": date_or_None,
    "has_dimension": bool}}. has_dimension is True when the context carries a segment or scenario child
    (a member of a reporting dimension, such as a business segment or a prior-period comparative axis),
    which marks it as not the plain whole-company figure for its period."""
    contexts: dict[str, dict] = {}
    for ctx in root.iter():
        if local_name(ctx.tag) != "context":
            continue
        ctx_id = ctx.get("id")
        if ctx_id is None:
            continue
        period = next((c for c in ctx.iter() if local_name(c.tag) == "period"), None)
        start = end = instant = None
        if period is not None:
            for p in period:
                ln = local_name(p.tag)
                if ln == "startDate":
                    start = _parse_xbrl_date(p.text)
                elif ln == "endDate":
                    end = _parse_xbrl_date(p.text)
                elif ln == "instant":
                    instant = _parse_xbrl_date(p.text)
        has_dimension = any(local_name(c.tag) in ("segment", "scenario") for c in ctx.iter())
        contexts[ctx_id] = {"start": start, "end": end, "instant": instant, "has_dimension": has_dimension}
    return contexts


def _all_facts(root, contexts: dict[str, dict]) -> list[dict]:
    rows = []
    for el in root.iter():
        tag = local_name(el.tag)
        item = TAG_TO_ITEM.get(tag)
        if item is None or el.text is None:
            continue
        ctx_id = el.get("contextRef")
        if ctx_id is None:
            continue
        ctx = contexts.get(ctx_id)
        if ctx is None:
            continue
        raw = el.text.strip()
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        sign = -1.0 if el.get("sign") == "-" else 1.0
        rows.append({
            "item": item, "tag": tag, "value_inr": value * sign, "context_id": ctx_id,
            "period_start": ctx["start"], "period_end": ctx["end"], "has_dimension": ctx["has_dimension"],
            "raw_text": raw,
        })
    return rows


def quarter_facts(xbrl_bytes: bytes, from_date: date, to_date: date) -> list[dict]:
    """Returns one row per recognised line item for the single quarter running from_date to to_date:
    {item, tag, value, unit, period_start, period_end, context_id, anchor_quote}. Keeps only
    non-dimensional contexts whose start and end match the filing's own period exactly, which excludes
    any segment-level breakdown (a dimensioned context). Values are converted from rupees to INR crore. A
    context with no startDate (an "instant" balance-sheet context, not used by the P&L items this
    function extracts) is skipped, since none of TAG_TO_ITEM's mapped tags are balance-sheet items.

    When more than one matching context reports the same item (NSE's standalone-plus-consolidated
    bundling, see the module docstring), only the first one encountered in document order is kept: this
    is a deterministic tie-break, not a verified choice of which basis is which."""
    root = etree.fromstring(xbrl_bytes)
    contexts = parse_contexts(root)
    rows = []
    seen_items: set[str] = set()
    for fact in _all_facts(root, contexts):
        if fact["has_dimension"]:
            continue
        if fact["period_start"] != from_date or fact["period_end"] != to_date:
            continue
        if fact["item"] in seen_items:
            continue
        seen_items.add(fact["item"])
        value_crore = fact["value_inr"] / _CRORE
        rows.append({
            "item": fact["item"], "tag": fact["tag"], "value": value_crore, "unit": "INR_cr",
            "period_start": fact["period_start"].isoformat(), "period_end": fact["period_end"].isoformat(),
            "context_id": fact["context_id"],
            "anchor_quote": "%s=%s (context %s, %s to %s)" % (
                fact["tag"], fact["raw_text"], fact["context_id"],
                fact["period_start"].isoformat(), fact["period_end"].isoformat(),
            ),
        })
    return rows


def quarter_items(rows: list[dict]) -> dict[str, float]:
    """{raw_item: value} from quarter_facts' output, for feeding directly into the series adapter."""
    return {r["item"]: r["value"] for r in rows}
