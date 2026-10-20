"""Series adapter: turns per-period raw P&L line items (from docs.xbrl.quarter_items, one dict per
period) into the derived items and lag-resolved inputs the metric registry expects, using calendar-correct
period arithmetic (metrics/periods.py) rather than list position. This is what makes metrics like rev_yoy
computable at all: the registry's own input names (revenue_t, revenue_t_minus_4q) are period-relative, and
a single period's raw facts can never satisfy them without this resolution step. (PLAN.md Wave 1 E5.)
"""
from __future__ import annotations

from typing import Callable, Optional

from .periods import quarter_before, same_quarter_prior_year


def with_derived_items(raw_by_period: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """raw_by_period: {period: {raw_item: value}}, typically built from docs.xbrl.quarter_items() across
    several quarters. Returns a new dict with the same periods, each period's values extended with
    `cogs` and `ebitda` wherever every one of their own inputs exists for that period; a period missing
    one of those inputs (an older quarter from a different taxonomy version, for instance) simply does
    not get the derived item, rather than an imputed or partial value."""
    out: dict[str, dict[str, float]] = {}
    for period, values in raw_by_period.items():
        row = dict(values)
        if all(k in values for k in ("materials", "purchases", "inventory_change")):
            row["cogs"] = values["materials"] + values["purchases"] + values["inventory_change"]
        if all(k in values for k in ("pbt_before_exceptional", "finance_costs", "dna", "other_income")):
            row["ebitda"] = (
                values["pbt_before_exceptional"] + values["finance_costs"] + values["dna"] - values["other_income"]
            )
        out[period] = row
    return out


# Suffix conventions the metric registry uses for a period-relative input name (see
# metrics/library.py's rev_yoy, rev_qoq, us_rev_usd_yoy, us_rev_inr_yoy), and how to resolve the actual
# period that suffix refers to, given the period the metric is being computed for.
_LAG_SUFFIXES: dict[str, Callable[[str], Optional[str]]] = {
    "_t_minus_1q": quarter_before,
    "_t_minus_4q": same_quarter_prior_year,
    "_t": lambda period: period,
}


def resolve_inputs(
    raw_by_period: dict[str, dict[str, float]], period: str, input_names: list[str]
) -> Optional[dict[str, float]]:
    """Builds the flat {input_name: value} dict a metric needs to be computed for `period`, resolving any
    period-relative name (ending in _t, _t_minus_1q or _t_minus_4q) by calendar arithmetic rather than by
    list position, and looking up any other name directly in `period`'s own values. Returns None if any
    referenced period is unresolvable (an unrecognised period string) or its base item is missing from
    raw_by_period for that period: a metric is never computed from a lag that silently shifted to the
    wrong quarter because the correct one had no data. Longer suffixes are checked first so "_t_minus_4q"
    is never mistaken for a bare "_t" match."""
    out: dict[str, float] = {}
    for name in input_names:
        matched = False
        for suffix in ("_t_minus_1q", "_t_minus_4q", "_t"):
            if not name.endswith(suffix):
                continue
            base_item = name[: -len(suffix)]
            target_period = _LAG_SUFFIXES[suffix](period)
            if target_period is None:
                return None
            values = raw_by_period.get(target_period)
            if values is None or base_item not in values:
                return None
            out[name] = values[base_item]
            matched = True
            break
        if matched:
            continue
        values = raw_by_period.get(period)
        if values is None or name not in values:
            return None
        out[name] = values[name]
    return out
