"""Deterministic fallback paragraphs, one function per section of the research paper. Used when the
Sarvam (or Gemini) prose fails the content guard twice. Every sentence here is built only from
PaperSpec facts already computed by spec.py: no number is invented.
"""
from __future__ import annotations

from .spec import PaperSpec


def _fact(spec: PaperSpec, section: str, key: str) -> str:
    for f in spec.facts.get(section, []):
        if f.key == key:
            return f.text
    return ""


def _join(texts: list[str]) -> str:
    out = []
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if not t.endswith("."):
            t += "."
        out.append(t)
    return " ".join(out)


def title(spec: PaperSpec) -> str:
    if spec.has_finding and spec.focus_metric_name and spec.changepoint_quarter:
        return f"{spec.company}: {spec.focus_metric_name.lower()} has moved away from its peers since {spec.changepoint_quarter}"
    return f"{spec.company}: what {spec.n_quarters} quarters of filed results show"


def abstract(spec: PaperSpec) -> str:
    company_texts = [f.text for f in spec.facts.get("company", [])]
    outlook_texts = [f.text for f in spec.facts.get("outlook", [])]
    if spec.has_finding:
        finding_texts = [f.text for f in spec.facts.get("findings", [])]
        explanations_summary = f"We tested {spec.n_explanations} competing explanations for the change, set out in Table 3."
        return _join(
            finding_texts
            + [f"We examine {spec.n_quarters} quarters of {spec.company}'s filed results against {spec.n_peers} listed peers and test the change against {spec.n_explanations} alternative explanations."]
            + company_texts
            + [explanations_summary]
            + outlook_texts
        )
    return _join(
        [f"We examined {spec.n_quarters} quarters of {spec.company}'s filed results and compared them with {spec.n_peers} listed peers."]
        + company_texts
        + ["Every explanation we considered for the largest change in the data was rejected or weakened by the checks set out in Section 4, so this note reports no finding."]
        + outlook_texts
    )


def introduction(spec: PaperSpec) -> list[str]:
    intro_facts = _join([f.text for f in spec.facts.get("intro", [])])
    para = _join([
        f"This note examines {spec.company}, a {spec.sector_phrase} listed on the National Stock Exchange of India, using its quarterly financial results up to {spec.as_of}.",
        intro_facts,
        "Section 2 describes the company and the data, Section 3 sets out what changed, Section 4 tests the competing explanations, Section 5 states what would change our view, and Section 6 concludes.",
    ])
    return [para]


def company_and_data(spec: PaperSpec) -> list[str]:
    facts_text = _join([f.text for f in spec.facts.get("company", [])])
    return [_join([facts_text, "Table 1 reports the quarterly results and Figure 1 plots revenue and EBITDA."])]


def findings(spec: PaperSpec) -> list[str]:
    facts_text = _join([f.text for f in spec.facts.get("findings", [])])
    has_table4 = any(t.number == 4 for t in spec.tables)
    closer = "Figure 2 compares the measure with its peers"
    if has_table4:
        closer += " and Table 4 sets out the latest quarter for each company."
    else:
        closer += "."
    return [_join([facts_text, closer])]


def explanations(spec: PaperSpec) -> list[str]:
    table3 = next((t for t in spec.tables if t.number == 3), None)
    lead = f"We considered {spec.n_explanations} explanations, set out in Table 3."
    rows_text = []
    if table3:
        for row in table3.rows:
            statement, _checked, result, reason = row
            reason_lc = reason[0].lower() + reason[1:] if reason else ""
            rows_text.append(f"{statement} {result.lower()}, because {reason_lc}".strip())
    return [_join([lead] + rows_text)]


def outlook(spec: PaperSpec) -> list[str]:
    facts_text = _join([f.text for f in spec.facts.get("outlook", [])])
    return [facts_text] if facts_text else ["No further check has been identified at this time."]


def conclusion(spec: PaperSpec) -> list[str]:
    if spec.has_finding:
        first = spec.facts.get("findings", [None])
        first_text = first[0].text if first else ""
        return [_join([
            first_text,
            f"The change survives the checks in Section 4, and it will be tested again when {spec.company} reports its next quarterly results.",
        ])]
    watch = spec.focus_metric_name.lower() if spec.focus_metric_name else "the company's key metrics"
    return [_join([
        f"No explanation for the largest change in {spec.company}'s results survived the checks in Section 4.",
        f"The measure to watch is {watch} in the next quarterly results.",
    ])]
