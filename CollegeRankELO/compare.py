"""
compare.py
----------
Weighted comparison used to decide the *winner* of an Elo match.

We deliberately do NOT use the current Elo rating to decide who wins,
because that would make the ranking self-reinforcing. Instead we compute a
weighted score from real-world attributes and treat that as ground truth.

Weights (must sum to 100):
    ROI                 40
    Placement %         25
    Average Package     20
    Fees (inverted)     10
    NAAC grade           5

If the absolute weighted-score difference is smaller than DRAW_THRESHOLD,
the match is declared a draw.
"""

from dataclasses import dataclass, asdict
from typing import Dict


NAAC_MAP: Dict[str, int] = {
    "A++": 100, "A+": 90, "A": 80,
    "B++": 70, "B+": 60, "B": 50, "C": 40,
}

WEIGHTS = {
    "roi": 0.40,
    "placement": 0.25,
    "package": 0.20,
    "fees": 0.10,
    "naac": 0.05,
}

DRAW_THRESHOLD = 2.0  # weighted-score points


@dataclass
class ScoreBreakdown:
    roi: float
    placement: float
    package: float
    fees: float
    naac: float
    total: float

    def as_dict(self) -> dict:
        return asdict(self)


def _normalise(value: float, best: float) -> float:
    """Return value / best on a 0-100 scale, guarded against divide-by-zero."""
    if best <= 0:
        return 0.0
    return max(0.0, min(100.0, (value / best) * 100.0))


class CompareService:
    """Computes weighted scores and decides winners."""

    def score(self, college: dict, peers_max: dict) -> ScoreBreakdown:
        """
        college    : dict with keys annual_fee, average_package,
                     placement_percentage, naac_grade
        peers_max  : dict with the max values across the compared pair,
                     used to normalise attributes onto a common scale.
        """
        roi_val = college["average_package"] / max(1, college["annual_fee"])
        roi = _normalise(roi_val, peers_max["roi"])
        placement = _normalise(college["placement_percentage"], peers_max["placement"])
        package = _normalise(college["average_package"], peers_max["package"])
        # Lower fee is better -> invert.
        fees = _normalise(peers_max["fees"] - college["annual_fee"] + 1,
                          peers_max["fees"])
        naac = NAAC_MAP.get(college["naac_grade"], 50)

        total = (
            roi * WEIGHTS["roi"] +
            placement * WEIGHTS["placement"] +
            package * WEIGHTS["package"] +
            fees * WEIGHTS["fees"] +
            naac * WEIGHTS["naac"]
        )
        return ScoreBreakdown(round(roi, 2), round(placement, 2),
                              round(package, 2), round(fees, 2),
                              round(naac, 2), round(total, 2))

    def peers_max(self, a: dict, b: dict) -> dict:
        return {
            "roi": max(a["average_package"] / max(1, a["annual_fee"]),
                       b["average_package"] / max(1, b["annual_fee"])),
            "placement": max(a["placement_percentage"], b["placement_percentage"]),
            "package": max(a["average_package"], b["average_package"]),
            "fees": max(a["annual_fee"], b["annual_fee"]),
        }

    def decide(self, score_a: ScoreBreakdown, score_b: ScoreBreakdown) -> str:
        """Return 'A', 'B' or 'DRAW'."""
        diff = score_a.total - score_b.total
        if abs(diff) < DRAW_THRESHOLD:
            return "DRAW"
        return "A" if diff > 0 else "B"
