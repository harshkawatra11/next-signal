"""Evidence Strength: Strong / Moderate / Weak, computed deterministically, with its reasoning shown.

This is the brief's eighth required output element: "Evidence Strength: Strong, Moderate or Weak, with the
reasoning shown." The scoring rule and its thresholds are documented in the research deliverable and on the
deck's formula callout (S5); this module is the single source of truth both read from.
"""
from __future__ import annotations

from ..schemas import StrengthBreakdown


def strength(
    independent_origins: int,
    grades: list[str],
    corroborated_numbers: int,
    total_numbers: int,
    tests_passed: int,
    tests_applicable: int,
    persistent_periods: int,
    unresolved_contradictions: int,
    sector_partial: bool,
    single_document: bool,
) -> StrengthBreakdown:
    ind = {0: 0, 1: 0, 2: 1, 3: 2}.get(independent_origins, 3)  # 0..3
    gmap = {"A": 2, "B": 1.5, "C": 1, "D": 0.5, "E": 0, "F": 0}
    rel = round(sum(gmap.get(g, 0) for g in grades) / max(1, len(grades)), 2) if grades else 0.0  # 0..2
    cor = round(2 * corroborated_numbers / max(1, total_numbers), 2)  # 0..2
    sur = round(2 * tests_passed / max(1, tests_applicable), 2) if tests_applicable else 0.0  # 0..2
    per = 1.0 if persistent_periods >= 3 else (0.5 if persistent_periods == 2 else 0.0)  # 0..1
    pen = -2.0 * unresolved_contradictions - (1.0 if sector_partial else 0.0)
    total = max(0.0, ind + rel + cor + sur + per + pen)
    label: str
    if total >= 7:
        label = "Strong"
    elif total >= 4:
        label = "Moderate"
    else:
        label = "Weak"
    if single_document:
        label = "Weak"

    reasons = [
        f"{independent_origins} independent origins (+{ind})",
        f"average source grade {rel}/2",
        f"{corroborated_numbers}/{total_numbers} key numbers reproduced in a second source (+{cor})",
        f"{tests_passed}/{tests_applicable} falsification tests passed (+{sur})" if tests_applicable else "no falsification tests applicable",
        f"persists for {persistent_periods} periods (+{per})",
    ]
    if pen:
        reasons.append(
            f"penalties {pen} (unresolved contradictions {unresolved_contradictions}, sector-wide component {sector_partial})"
        )
    if single_document:
        reasons.append("downgraded to Weak: the finding rests on a single document")

    return StrengthBreakdown(
        independence=ind,
        reliability=rel,
        corroboration=cor,
        survival=sur,
        persistence=per,
        penalties=pen,
        total=round(total, 2),
        label=label,  # type: ignore[arg-type]
        reasoning=reasons,
    )
