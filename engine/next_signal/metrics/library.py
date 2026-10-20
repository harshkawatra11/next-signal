"""The metric registry: every formula the Calculate stage can apply. The LLM never computes a number
shown to the user; every number traces back to one of these functions and the Fact objects (with their
quote anchors) that feed it.

Each entry is a Metric(id, name, formula_text, fn, inputs, unit, applies_to, higher_is). `fn` takes a dict of
named float inputs (the same names listed in `inputs`) and returns a float, or None if the computation is not
defined for the given inputs (e.g. division by zero, missing a required input - the caller is responsible for
not calling fn when a required input is missing; this module never imputes a missing figure).

`applies_to` is one of "pharma", "hospital", "diagnostics", "generic", or "all" (works for any playbook).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

Playbook = Literal["pharma", "hospital", "diagnostics", "generic", "all"]


@dataclass
class Metric:
    metric_id: str
    name: str
    formula_text: str
    fn: Callable[[dict[str, float]], float | None]
    inputs: list[str]
    unit: str
    applies_to: Playbook = "all"
    higher_is: Literal["better", "worse", "neutral"] = "neutral"


def _safe_div(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return a / b


REGISTRY: dict[str, Metric] = {}


def register(m: Metric) -> Metric:
    REGISTRY[m.metric_id] = m
    return m


# ---- Growth ----------------------------------------------------------------

register(Metric(
    "rev_yoy", "Revenue growth, year on year",
    "(revenue_t - revenue_t_minus_4q) / revenue_t_minus_4q",
    lambda i: _safe_div(i["revenue_t"] - i["revenue_t_minus_4q"], i["revenue_t_minus_4q"]),
    ["revenue_t", "revenue_t_minus_4q"], "pct",
))

register(Metric(
    "rev_qoq", "Revenue growth, quarter on quarter",
    "(revenue_t - revenue_t_minus_1q) / revenue_t_minus_1q",
    lambda i: _safe_div(i["revenue_t"] - i["revenue_t_minus_1q"], i["revenue_t_minus_1q"]),
    ["revenue_t", "revenue_t_minus_1q"], "pct",
))

register(Metric(
    "rev_cagr_5y", "Revenue CAGR, 5 years",
    "(revenue_fy_end / revenue_fy_start) ** (1 / 5) - 1",
    lambda i: (i["revenue_fy_end"] / i["revenue_fy_start"]) ** (1 / 5) - 1 if i.get("revenue_fy_start", 0) > 0 else None,
    ["revenue_fy_end", "revenue_fy_start"], "pct",
))

register(Metric(
    "us_rev_usd_yoy", "US revenue growth, year on year, in USD",
    "(us_rev_usd_t - us_rev_usd_t_minus_4q) / us_rev_usd_t_minus_4q",
    lambda i: _safe_div(i["us_rev_usd_t"] - i["us_rev_usd_t_minus_4q"], i["us_rev_usd_t_minus_4q"]),
    ["us_rev_usd_t", "us_rev_usd_t_minus_4q"], "pct", applies_to="pharma",
))

register(Metric(
    "us_rev_inr_yoy", "US revenue growth, year on year, in INR",
    "(us_rev_inr_t - us_rev_inr_t_minus_4q) / us_rev_inr_t_minus_4q",
    lambda i: _safe_div(i["us_rev_inr_t"] - i["us_rev_inr_t_minus_4q"], i["us_rev_inr_t_minus_4q"]),
    ["us_rev_inr_t", "us_rev_inr_t_minus_4q"], "pct", applies_to="pharma",
))

register(Metric(
    "fx_effect_us", "FX effect on reported US growth",
    "us_rev_inr_yoy - us_rev_usd_yoy",
    lambda i: i["us_rev_inr_yoy"] - i["us_rev_usd_yoy"],
    ["us_rev_inr_yoy", "us_rev_usd_yoy"], "pct_pts", applies_to="pharma",
))

register(Metric(
    "india_vs_ipm_gap", "India formulations growth minus IPM growth",
    "india_rev_yoy - ipm_growth_yoy",
    lambda i: i["india_rev_yoy"] - i["ipm_growth_yoy"],
    ["india_rev_yoy", "ipm_growth_yoy"], "pct_pts", applies_to="pharma",
))

# ---- Mix --------------------------------------------------------------------

register(Metric(
    "geo_share", "Geography's share of total revenue",
    "geo_revenue / total_revenue",
    lambda i: _safe_div(i["geo_revenue"], i["total_revenue"]),
    ["geo_revenue", "total_revenue"], "pct", applies_to="pharma",
))

register(Metric(
    "geo_share_change_5y", "Change in a geography's revenue share over 5 years",
    "geo_share_now - geo_share_5y_ago",
    lambda i: i["geo_share_now"] - i["geo_share_5y_ago"],
    ["geo_share_now", "geo_share_5y_ago"], "pct_pts", applies_to="pharma",
))

register(Metric(
    "specialty_share", "Global specialty/innovative medicines share of total revenue",
    "specialty_revenue / total_revenue",
    lambda i: _safe_div(i["specialty_revenue"], i["total_revenue"]),
    ["specialty_revenue", "total_revenue"], "pct", applies_to="pharma",
))

# ---- Profitability ------------------------------------------------------------

register(Metric(
    "gross_margin", "Gross margin",
    "(revenue - cogs) / revenue",
    lambda i: _safe_div(i["revenue"] - i["cogs"], i["revenue"]),
    ["revenue", "cogs"], "pct",
))

register(Metric(
    "ebitda_margin", "EBITDA margin",
    "ebitda / revenue",
    lambda i: _safe_div(i["ebitda"], i["revenue"]),
    ["ebitda", "revenue"], "pct",
))

register(Metric(
    "pat_margin", "PAT margin",
    "pat / revenue",
    lambda i: _safe_div(i["pat"], i["revenue"]),
    ["pat", "revenue"], "pct",
))

register(Metric(
    "rd_pct", "R&D spend as a share of revenue",
    "rd_spend / revenue",
    lambda i: _safe_div(i["rd_spend"], i["revenue"]),
    ["rd_spend", "revenue"], "pct", applies_to="pharma",
))

register(Metric(
    "other_income_share_pbt", "Other income as a share of profit before tax",
    "other_income / pbt",
    lambda i: _safe_div(i["other_income"], i["pbt"]),
    ["other_income", "pbt"], "pct",
))

register(Metric(
    "exceptional_share_pbt", "Exceptional items as a share of profit before tax",
    "exceptional_items / pbt",
    lambda i: _safe_div(i["exceptional_items"], i["pbt"]),
    ["exceptional_items", "pbt"], "pct",
))

register(Metric(
    "etr", "Effective tax rate",
    "tax_expense / pbt",
    lambda i: _safe_div(i["tax_expense"], i["pbt"]),
    ["tax_expense", "pbt"], "pct",
))

# ---- Working capital ----------------------------------------------------------

register(Metric(
    "receivable_days", "Trade receivable days",
    "trade_receivables / revenue * days_in_period",
    lambda i: _safe_div(i["trade_receivables"], i["revenue"]) and (i["trade_receivables"] / i["revenue"]) * i["days_in_period"],
    ["trade_receivables", "revenue", "days_in_period"], "days",
))

register(Metric(
    "inventory_days", "Inventory days",
    "inventory / cogs * days_in_period",
    lambda i: _safe_div(i["inventory"], i["cogs"]) and (i["inventory"] / i["cogs"]) * i["days_in_period"],
    ["inventory", "cogs", "days_in_period"], "days",
))

register(Metric(
    "payable_days", "Trade payable days",
    "trade_payables / cogs * days_in_period",
    lambda i: _safe_div(i["trade_payables"], i["cogs"]) and (i["trade_payables"] / i["cogs"]) * i["days_in_period"],
    ["trade_payables", "cogs", "days_in_period"], "days",
))

register(Metric(
    "ccc", "Cash conversion cycle",
    "receivable_days + inventory_days - payable_days",
    lambda i: i["receivable_days"] + i["inventory_days"] - i["payable_days"],
    ["receivable_days", "inventory_days", "payable_days"], "days",
))

register(Metric(
    "rec_growth_minus_rev_growth", "Receivables growth minus revenue growth",
    "receivables_yoy - revenue_yoy",
    lambda i: i["receivables_yoy"] - i["revenue_yoy"],
    ["receivables_yoy", "revenue_yoy"], "pct_pts",
))

# ---- Cash and capital ----------------------------------------------------------

register(Metric(
    "cfo_to_ebitda", "Cash flow from operations to EBITDA",
    "cfo / ebitda",
    lambda i: _safe_div(i["cfo"], i["ebitda"]),
    ["cfo", "ebitda"], "ratio",
))

register(Metric(
    "capex_to_sales", "Capex as a share of revenue",
    "capex / revenue",
    lambda i: _safe_div(i["capex"], i["revenue"]),
    ["capex", "revenue"], "pct",
))

register(Metric(
    "fcf_margin", "Free cash flow margin",
    "(cfo - capex) / revenue",
    lambda i: _safe_div(i["cfo"] - i["capex"], i["revenue"]),
    ["cfo", "capex", "revenue"], "pct",
))

register(Metric(
    "net_debt_to_ebitda", "Net debt to EBITDA",
    "net_debt / ebitda_ttm",
    lambda i: _safe_div(i["net_debt"], i["ebitda_ttm"]),
    ["net_debt", "ebitda_ttm"], "ratio",
))

# ---- Quality --------------------------------------------------------------------

register(Metric(
    "sloan_accruals", "Sloan accruals ratio",
    "(pat - cfo) / avg_total_assets",
    lambda i: _safe_div(i["pat"] - i["cfo"], i["avg_total_assets"]),
    ["pat", "cfo", "avg_total_assets"], "ratio",
))

# ---- Regulatory (pharma) ---------------------------------------------------------

register(Metric(
    "fda_wl_24m", "USFDA warning letters in the last 24 months",
    "count of warning letters to owned or partner sites, trailing 24 months",
    lambda i: i["count"],
    ["count"], "count", applies_to="pharma",
))

register(Metric(
    "anda_approvals_ttm", "ANDA approvals, trailing 12 months",
    "count of ANDA final approvals in openFDA drugsfda, trailing 12 months",
    lambda i: i["count"],
    ["count"], "count", applies_to="pharma",
))

# ---- Hospital -----------------------------------------------------------------

register(Metric(
    "arpob", "Average revenue per occupied bed per day",
    "hospital_revenue / (operational_beds * occupancy * days_in_period)",
    lambda i: _safe_div(i["hospital_revenue"], i["operational_beds"] * i["occupancy"] * i["days_in_period"]),
    ["hospital_revenue", "operational_beds", "occupancy", "days_in_period"], "INR_per_bed_day", applies_to="hospital",
))

register(Metric(
    "arpob_yoy", "ARPOB growth, year on year",
    "(arpob_t - arpob_t_minus_4q) / arpob_t_minus_4q",
    lambda i: _safe_div(i["arpob_t"] - i["arpob_t_minus_4q"], i["arpob_t_minus_4q"]),
    ["arpob_t", "arpob_t_minus_4q"], "pct", applies_to="hospital",
))

register(Metric(
    "beds_gap", "Beds announced for the period minus beds actually operational",
    "beds_announced - beds_operational",
    lambda i: i["beds_announced"] - i["beds_operational"],
    ["beds_announced", "beds_operational"], "beds", applies_to="hospital",
))

register(Metric(
    "revenue_per_bed", "Annualised revenue per operational bed",
    "hospital_revenue_annualised / operational_beds",
    lambda i: _safe_div(i["hospital_revenue_annualised"], i["operational_beds"]),
    ["hospital_revenue_annualised", "operational_beds"], "INR_per_bed", applies_to="hospital",
))

register(Metric(
    "ebitda_per_bed", "Annualised EBITDA per operational bed",
    "hospital_ebitda_annualised / operational_beds",
    lambda i: _safe_div(i["hospital_ebitda_annualised"], i["operational_beds"]),
    ["hospital_ebitda_annualised", "operational_beds"], "INR_per_bed", applies_to="hospital",
))

register(Metric(
    "intl_share", "International patients' share of hospital revenue",
    "intl_revenue / hospital_revenue",
    lambda i: _safe_div(i["intl_revenue"], i["hospital_revenue"]),
    ["intl_revenue", "hospital_revenue"], "pct", applies_to="hospital",
))

# ---- Generic (works for any company) ----------------------------------------------

register(Metric(
    "price_vs_volume_growth", "Price-led share of revenue growth",
    "(rev_yoy - volume_yoy) when both disclosed",
    lambda i: i["rev_yoy"] - i["volume_yoy"],
    ["rev_yoy", "volume_yoy"], "pct_pts", applies_to="generic",
))


def metrics_for(playbook: Playbook) -> list[Metric]:
    return [m for m in REGISTRY.values() if m.applies_to in (playbook, "all")]


def compute(metric_id: str, inputs: dict[str, float]) -> float | None:
    m = REGISTRY[metric_id]
    missing = [k for k in m.inputs if k not in inputs]
    if missing:
        return None
    return m.fn(inputs)
