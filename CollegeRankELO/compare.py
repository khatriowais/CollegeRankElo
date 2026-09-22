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

# Weights / threshold are env-overridable via config.settings
# (see .env.example: WEIGHT_ROI, WEIGHT_PLACEMENT, ... DRAW_THRESHOLD).
# Hard-coded values below are fallbacks only.
try:
    from config import settings as _settings  # type: ignore

    WEIGHTS = dict(_settings.weights)
    DRAW_THRESHOLD = _settings.draw_threshold
except Exception:
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

    def common_metrics(self, a: dict, b: dict) -> set:
        """
        Metrics that BOTH colleges have real data for.

        A head-to-head must be judged only on ground the two colleges share.
        If we scored each college on whatever it happens to have, a college
        would be *penalised for publishing its data*: an expensive-but-honest
        college that reports a high fee would score badly on ``fees`` while its
        opponent -- which published nothing -- would be judged on NAAC alone
        and win by default. Restricting both sides to the intersection removes
        that perverse incentive.

        NAAC is always in the set: it is populated for every ranked college and
        falls back to a neutral 50 when the grade is unknown.
        """
        def num(c: dict, key: str) -> bool:
            return c.get(key) is not None

        keys = {"naac"}
        # ROI needs a package AND a non-zero fee on both sides.
        if (num(a, "average_package") and a.get("annual_fee")
                and num(b, "average_package") and b.get("annual_fee")):
            keys.add("roi")
        if num(a, "placement_percentage") and num(b, "placement_percentage"):
            keys.add("placement")
        if num(a, "average_package") and num(b, "average_package"):
            keys.add("package")
        if num(a, "annual_fee") and num(b, "annual_fee"):
            keys.add("fees")
        return keys

    def score(self, college: dict, peers_max: dict, only: set = None) -> ScoreBreakdown:
        """
        college    : dict with keys annual_fee, average_package,
                     placement_percentage, naac_grade (any of the numeric
                     metrics may be None when we don't have credible data).
        peers_max  : dict with the max values across the compared pair,
                     used to normalise attributes onto a common scale.
        only       : optional set of metric keys to score on -- normally the
                     output of :meth:`common_metrics` so both sides of a match
                     are judged on identical criteria. ``None`` scores on every
                     metric this college has.

        Missing (None) metrics are skipped and their weight is redistributed
        across the metrics that ARE scored, so a college is never penalised for
        data we simply do not have. NAAC is always scored (an unknown grade
        defaults to a neutral 50).
        """
        fee = college.get("annual_fee")
        pkg = college.get("average_package")
        plc = college.get("placement_percentage")

        def wanted(key: str) -> bool:
            return only is None or key in only

        components: Dict[str, float] = {}
        if wanted("roi") and pkg is not None and fee:
            components["roi"] = _normalise(pkg / fee, peers_max.get("roi", 0))
        if wanted("placement") and plc is not None:
            components["placement"] = _normalise(plc, peers_max.get("placement", 0))
        if wanted("package") and pkg is not None:
            components["package"] = _normalise(pkg, peers_max.get("package", 0))
        if wanted("fees") and fee is not None:
            best_fee = peers_max.get("fees", 0)
            # Lower fee is better -> invert.
            components["fees"] = _normalise(best_fee - fee + 1, best_fee)
        components["naac"] = float(NAAC_MAP.get(college.get("naac_grade"), 50))

        active_weight = sum(WEIGHTS[k] for k in components) or 1.0
        total = sum(components[k] * WEIGHTS[k] for k in components) / active_weight

        def g(k: str) -> float:
            return round(components.get(k, 0.0), 2)

        return ScoreBreakdown(g("roi"), g("placement"), g("package"),
                              g("fees"), g("naac"), round(total, 2))

    def peers_max(self, a: dict, b: dict) -> dict:
        def _max(key: str) -> float:
            vals = [c[key] for c in (a, b) if c.get(key) is not None]
            return max(vals) if vals else 0.0

        roi_vals = [c["average_package"] / c["annual_fee"] for c in (a, b)
                    if c.get("average_package") is not None and c.get("annual_fee")]
        return {
            "roi": max(roi_vals) if roi_vals else 0.0,
            "placement": _max("placement_percentage"),
            "package": _max("average_package"),
            "fees": _max("annual_fee"),
        }

    def decide(self, score_a: ScoreBreakdown, score_b: ScoreBreakdown) -> str:
        """Return 'A', 'B' or 'DRAW'."""
        diff = score_a.total - score_b.total
        if abs(diff) < DRAW_THRESHOLD:
            return "DRAW"
        return "A" if diff > 0 else "B"
