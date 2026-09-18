"""
elo.py
------
Pure Elo rating math used by CollegeRankELO.

Formulae:
    Expected(A) = 1 / (1 + 10 ** ((R_B - R_A) / 400))
    R_A_new    = R_A + K * (S_A - Expected(A))

Where:
    S_A = 1 (win), 0.5 (draw), 0 (loss)
    K   = update sensitivity (32 by convention)
"""

from dataclasses import dataclass


class EloConfig:
    """Global Elo configuration — overridable via environment (.env)."""
    try:
        from config import settings as _s  # type: ignore
        START_RATING: float = _s.elo_start_rating  # type: ignore
        K_FACTOR: int = _s.elo_k_factor  # type: ignore
    except Exception:
        START_RATING: float = 1500  # type: ignore
        K_FACTOR: int = 32  # type: ignore


# Backwards-compatible module constants.
START_RATING = EloConfig.START_RATING
K_FACTOR = EloConfig.K_FACTOR


@dataclass
class EloResult:
    new_a: float
    new_b: float
    expected_a: float
    expected_b: float


class EloService:
    """Stateless service that performs Elo calculations."""

    def __init__(self, k: int | None = None) -> None:
        if k is None:
            try:
                from config import settings as _s  # type: ignore
                k = _s.elo_k_factor
            except Exception:
                k = EloConfig.K_FACTOR
        self.k = k

    def expected(self, rating_a: float, rating_b: float) -> float:
        """Probability that A beats B given their ratings."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def update(self, rating_a: float, rating_b: float, score_a: float) -> EloResult:
        """
        Return updated Elo ratings.

        score_a is the actual outcome for A: 1 win, 0.5 draw, 0 loss.
        Elo is zero-sum so score_b = 1 - score_a.
        """
        exp_a = self.expected(rating_a, rating_b)
        exp_b = 1.0 - exp_a
        score_b = 1.0 - score_a
        new_a = rating_a + self.k * (score_a - exp_a)
        new_b = rating_b + self.k * (score_b - exp_b)
        return EloResult(new_a=round(new_a, 2), new_b=round(new_b, 2),
                         expected_a=round(exp_a, 4), expected_b=round(exp_b, 4))
