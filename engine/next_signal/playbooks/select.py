"""Angle scoring and selection (PLAN.md §5.7 step 5):

    angle_score = 0.35*data_availability + 0.40*anomaly_signal + 0.25*novelty_prior

Keeps the top N angles, always including a playbook's brief-anchored angle (P2 for pharma, H1 for
hospital) when its data_availability clears a floor, since those are the brief's own Track D questions.
"""
from __future__ import annotations

from dataclasses import dataclass

from .angles import Angle

ANCHOR_ANGLE = {"pharma": "P2", "hospital": "H1", "diagnostics": None, "generic": None}


@dataclass
class AngleScore:
    angle_id: str
    question: str
    data_availability: float
    anomaly_signal: float
    novelty_prior: float
    score: float
    reason: str


def score_angle(
    angle: Angle,
    data_availability: float,
    anomaly_signal: float,
    novelty_prior: float,
) -> AngleScore:
    data_availability = max(0.0, min(1.0, data_availability))
    anomaly_signal = max(0.0, min(1.0, anomaly_signal))
    novelty_prior = max(0.0, min(1.0, novelty_prior))
    score = 0.35 * data_availability + 0.40 * anomaly_signal + 0.25 * novelty_prior
    reason = (
        f"data availability {data_availability:.2f}, anomaly signal {anomaly_signal:.2f}, "
        f"novelty prior {novelty_prior:.2f}"
    )
    return AngleScore(angle.angle_id, angle.question, data_availability, anomaly_signal, novelty_prior, score, reason)


def select_angles(
    playbook: str,
    angles: list[Angle],
    scores: dict[str, AngleScore],
    top_n: int = 4,
    anchor_floor: float = 0.3,
) -> list[AngleScore]:
    """scores: angle_id -> AngleScore, already computed for every candidate angle."""
    ranked = sorted(scores.values(), key=lambda s: s.score, reverse=True)
    chosen = ranked[:top_n]
    anchor_id = ANCHOR_ANGLE.get(playbook)
    if anchor_id and anchor_id in scores:
        anchor = scores[anchor_id]
        if anchor.data_availability >= anchor_floor and anchor not in chosen:
            chosen = chosen[: top_n - 1] + [anchor]
    return chosen
