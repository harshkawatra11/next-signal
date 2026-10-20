"""Angle definitions: each playbook (pharma, hospital, diagnostics, generic) carries a fixed set of
research angles the Discover stage can choose among (PLAN.md §5.7). An angle is data, not a hypothesis:
it names a question, the metrics that would answer it, and the doc kinds / external sources needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Angle:
    angle_id: str
    question: str
    metrics: tuple[str, ...]
    doc_kinds: tuple[str, ...]
    external_sources: tuple[str, ...]
    rival_tests: tuple[str, ...] = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9")


PHARMA: tuple[Angle, ...] = (
    Angle("P1", "Has the business model quietly shifted (specialty/innovative, CDMO, India branded, consumer health), and when?",
          ("specialty_share", "cdmo_share", "geo_share_change_5y"), ("presentation", "annual_report"), ("openfda", "peers")),
    Angle("P2", "Did a regulatory or compliance development hit the financials in filings before mainstream coverage?",
          ("fda_wl_24m", "us_rev_usd_yoy"), ("regulatory_usfda", "results"), ("fda_warning_letters", "fda_import_alert", "openfda_recalls", "gdelt")),
    Angle("P3", "How has geographic revenue exposure shifted over five years, and what drove it?",
          ("geo_share", "geo_share_change_5y", "fx_effect_us"), ("presentation", "annual_report"), ("peers",)),
    Angle("P4", "Is a single product or exclusivity window carrying a segment, and when does it end?",
          ("us_rev_usd_yoy",), ("transcript",), ("orange_book", "openfda_approvals")),
    Angle("P5", "Are new launches masking price erosion in the base business?",
          ("anda_approvals_ttm", "us_rev_usd_yoy", "gross_margin"), ("transcript",), ("openfda_drugsfda",)),
    Angle("P6", "Do receivables or inventory tell a different story from revenue?",
          ("receivable_days", "inventory_days", "rec_growth_minus_rev_growth", "cfo_to_ebitda"), ("annual_report",), ("screener",)),
    Angle("P7", "Is R&D intensity or capitalisation changing the earnings quality?",
          ("rd_pct",), ("annual_report",), ()),
    Angle("P8", "Is profit quality changing (other income, forex, one-offs, tax)?",
          ("other_income_share_pbt", "exceptional_share_pbt", "etr"), ("results",), ()),
    Angle("P9", "Is there a hidden dependence on a partner, supplier, licensor or customer?",
          (), ("annual_report", "transcript"), ("fda_warning_letters",)),
    Angle("P10", "Do different disclosure channels tell different stories (SEC vs NSE, press vs filing, guidance vs actual)?",
          (), ("results", "transcript"), ("sec",)),
)

HOSPITAL: tuple[Angle, ...] = (
    Angle("H1", "Are announced bed additions matching what is actually commissioned?",
          ("beds_gap",), ("presentation", "capacity"), ()),
    Angle("H2", "What is driving ARPOB growth: price, payor mix, case mix, or international patients?",
          ("arpob_yoy", "intl_share"), ("presentation",), ()),
    Angle("H3", "Is new capacity diluting occupancy at mature units?",
          ("revenue_per_bed", "ebitda_per_bed"), ("presentation",), ()),
    Angle("H4", "Is a non-hospital segment (pharmacy, digital, insurance) dragging or subsidising the core?",
          (), ("results", "transcript"), ()),
    Angle("H5", "How exposed is the chain to regulatory price caps (CGHS, PMJAY, NPPA implant caps)?",
          (), ("annual_report",), ("regulator_in",)),
    Angle("H6", "Is growth organic or acquired?",
          (), ("presentation", "acquisition"), ()),
)

DIAGNOSTICS: tuple[Angle, ...] = (
    Angle("D1", "Is growth driven by test volume or realisation per test?",
          (), ("presentation",), ()),
    Angle("D2", "Is patient growth outpacing test growth, and what does that say about the B2B/B2C mix?",
          (), ("presentation",), ()),
    Angle("D3", "Is network expansion translating into revenue per centre?",
          (), ("presentation",), ()),
)

GENERIC: tuple[Angle, ...] = (
    Angle("G1", "Is reported growth price-led or volume-led?",
          ("price_vs_volume_growth",), ("presentation", "results"), ("peers",)),
    Angle("G2", "Do working-capital trends diverge from revenue growth?",
          ("rec_growth_minus_rev_growth", "receivable_days"), ("annual_report",), ()),
    Angle("G3", "Has the segment mix shifted, and is the shift showing up before it is announced?",
          ("geo_share_change_5y",), ("presentation",), ()),
    Angle("G4", "Is profit quality changing (one-offs, other income, tax)?",
          ("other_income_share_pbt", "exceptional_share_pbt", "etr"), ("results",), ()),
    Angle("G5", "Does guidance match the actual outcome?",
          (), ("transcript", "results"), ()),
    Angle("G6", "Do different disclosure channels disagree?",
          (), ("results",), ("sec",)),
)

PLAYBOOKS: dict[str, tuple[Angle, ...]] = {
    "pharma": PHARMA,
    "hospital": HOSPITAL,
    "diagnostics": DIAGNOSTICS,
    "generic": GENERIC,
}
