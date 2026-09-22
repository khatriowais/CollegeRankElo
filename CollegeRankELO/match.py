"""
match.py
--------
One head-to-head Elo match, in one place.

Both the interactive ``POST /api/compare`` endpoint and the offline tournament
bootstrap (``bootstrap_elo.py``) call :func:`run_match`, so a rating produced by
a script is arrived at by exactly the same arithmetic as one produced by a click.
Keeping this in a single function is what makes the leaderboard reproducible.
"""

from __future__ import annotations

import json
from typing import Tuple

from models import College, Comparison, EloHistory
from compare import CompareService
from elo import EloService

OUTCOME = {"A": 1.0, "B": 0.0, "DRAW": 0.5}


def eligibility_error(a: College, b: College) -> str | None:
    """Return a human-readable reason the pair can't be compared, else None."""
    if a.id == b.id:
        return "select two different colleges"
    if not (a.is_ranked and b.is_ranked):
        return ("Both colleges must be Elo-ranked. Directory listings have no "
                "verified metrics to compare.")
    if a.cohort != b.cohort:
        return ("Colleges are in different cohorts and can't be compared "
                "head-to-head.")
    return None


def run_match(session, a: College, b: College,
              compare_service: CompareService,
              elo_service: EloService,
              persist: bool = True) -> dict:
    """
    Score A against B, update both Elo ratings and record the match.

    The pair is judged only on ``common_metrics`` -- the metrics both colleges
    actually have data for -- so nobody is rewarded for withholding figures.
    The set that decided the match is returned as ``metrics_used`` so the UI can
    say *why* a college won instead of leaving the user to guess.

    Caller is responsible for ``session.commit()`` when ``persist`` is True.
    """
    a_dict, b_dict = a.to_dict(), b.to_dict()
    common = compare_service.common_metrics(a_dict, b_dict)
    peers = compare_service.peers_max(a_dict, b_dict)
    score_a = compare_service.score(a_dict, peers, only=common)
    score_b = compare_service.score(b_dict, peers, only=common)
    winner = compare_service.decide(score_a, score_b)

    old_a, old_b = a.elo_rating, b.elo_rating
    res = elo_service.update(old_a, old_b, OUTCOME[winner])
    a.elo_rating, b.elo_rating = res.new_a, res.new_b

    if persist:
        session.add(EloHistory(college_id=a.id, rating=res.new_a))
        session.add(EloHistory(college_id=b.id, rating=res.new_b))
        session.add(Comparison(
            college_a_id=a.id, college_b_id=b.id, winner=winner,
            score_a=score_a.total, score_b=score_b.total,
            breakdown_a=json.dumps(score_a.as_dict()),
            breakdown_b=json.dumps(score_b.as_dict()),
            old_elo_a=old_a, old_elo_b=old_b,
            new_elo_a=res.new_a, new_elo_b=res.new_b,
        ))

    return {
        "winner": winner,
        "score_a": score_a,
        "score_b": score_b,
        "old_elo": {"a": old_a, "b": old_b},
        "new_elo": {"a": res.new_a, "b": res.new_b},
        "expected": {"a": res.expected_a, "b": res.expected_b},
        # Sorted for a stable UI / stable test assertions.
        "metrics_used": sorted(common),
    }
