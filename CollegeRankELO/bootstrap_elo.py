"""
bootstrap_elo.py
----------------
Seed the leaderboard by playing every ranked college against every other one.

Why this exists
    Elo only means something after matches have been played. A freshly ingested
    database has all 22 Mumbai colleges sitting on the same 1500, so the
    leaderboard is alphabetical noise. This runs the full round-robin -- all
    C(22,2) = 231 pairs -- through the *same* :func:`match.run_match` the web UI
    calls, so the resulting ratings are exactly what a user would have produced
    by clicking through every pairing.

Order sensitivity
    Elo is path-dependent: the order matches are played in changes the final
    numbers. Two defences are used. Pair order is shuffled with a fixed seed
    (``--seed``), so a run is reproducible but not alphabetically biased; and
    the round-robin is replayed for several passes, by which point ratings have
    settled and further passes barely move them. Only the final pass is written
    to the ``comparisons`` / ``elo_history`` tables -- earlier passes are
    convergence warm-up, so the saved match log stays readable at 231 rows
    instead of 1848.

Usage
    python bootstrap_elo.py                 # 6 passes, reset ratings first
    python bootstrap_elo.py --passes 10
    python bootstrap_elo.py --keep-history  # append instead of wiping
    python bootstrap_elo.py --dry-run       # compute and print, write nothing
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys

from database import SessionLocal, init_db
from models import College, Comparison, EloHistory
from compare import CompareService
from elo import EloService, EloConfig
from match import run_match
from config import settings


def ranked_colleges(session, cohort: str | None):
    q = session.query(College).filter(College.is_ranked == True)  # noqa: E712
    if cohort:
        q = q.filter(College.cohort == cohort)
    # Stable base order so --seed fully determines the shuffle.
    return q.order_by(College.id).all()


def play(session, colleges, compare_service, elo_service,
         passes: int, seed: int, persist_final: bool) -> dict:
    pairs = list(itertools.combinations(colleges, 2))
    rng = random.Random(seed)
    stats = {"pairs": len(pairs), "passes": passes, "A": 0, "B": 0, "DRAW": 0,
             "metrics_used": {}, "max_shift_final_pass": 0.0}

    for p in range(1, passes + 1):
        order = pairs[:]
        rng.shuffle(order)
        final = (p == passes)
        before = {c.id: c.elo_rating for c in colleges}

        for a, b in order:
            result = run_match(session, a, b, compare_service, elo_service,
                               persist=final and persist_final)
            if final:
                stats[result["winner"]] += 1
                key = "+".join(result["metrics_used"])
                stats["metrics_used"][key] = stats["metrics_used"].get(key, 0) + 1

        shift = max(abs(c.elo_rating - before[c.id]) for c in colleges)
        print(f"  pass {p}/{passes}: max rating shift {shift:8.2f}")
        if final:
            stats["max_shift_final_pass"] = round(shift, 2)

    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--passes", type=int, default=6,
                    help="round-robin repetitions (default 6)")
    ap.add_argument("--seed", type=int, default=2024,
                    help="shuffle seed; same seed = same leaderboard")
    ap.add_argument("--cohort", default="",
                    help="cohort to play (e.g. 'mumbai', 'us', or '' for all ranked cohorts)")
    ap.add_argument("--keep-history", action="store_true",
                    help="keep existing ratings/comparisons instead of resetting")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print the table, write nothing")
    args = ap.parse_args(argv)

    init_db()
    session = SessionLocal()
    try:
        cohorts_to_run = [args.cohort] if args.cohort else ["mumbai", "us"]
        for ch in cohorts_to_run:
            colleges = ranked_colleges(session, ch)
            if len(colleges) < 2:
                print(f"Skipping cohort '{ch}': need at least 2 ranked colleges, found {len(colleges)}.")
                continue

            print(f"\n=======================================================")
            print(f"Running Elo tournament for cohort '{ch}' ({len(colleges)} colleges)")
            print(f"=======================================================")

            if not args.keep_history:
                ids = [c.id for c in colleges]
                deleted_h = (session.query(EloHistory)
                             .filter(EloHistory.college_id.in_(ids))
                             .delete(synchronize_session=False))
                deleted_c = (session.query(Comparison)
                             .filter(Comparison.college_a_id.in_(ids))
                             .delete(synchronize_session=False))
                for c in colleges:
                    c.elo_rating = EloConfig.START_RATING
                print(f"Reset: {len(colleges)} ratings -> {EloConfig.START_RATING}, "
                      f"cleared {deleted_c} comparisons / {deleted_h} history rows")

            stats = play(session, colleges, CompareService(),
                         EloService(k=settings.elo_k_factor),
                         passes=args.passes, seed=args.seed,
                         persist_final=not args.dry_run)

            table = sorted(
                [(c.elo_rating, c.naac_grade, c.annual_fee, c.placement_percentage,
                  c.average_package, c.college_name, c.currency) for c in colleges],
                key=lambda r: r[0], reverse=True)

            if args.dry_run:
                session.rollback()
                print("\n[dry run] nothing written")
            else:
                session.commit()

            curr_sym = "$" if ch == "us" else "INR "
            print(f"\n{'#':>3}  {'Elo':>8}  {'NAAC':<4} {'Fee':>12} {'Plc%':>6} "
                  f"{'AvgPkg':>12}  College")
            print("-" * 96)
            for i, (elo, naac, fee_v, plc_v, pkg_v, cname, currency) in enumerate(table, 1):
                sym = "$" if currency == "USD" else "Rs."
                fee = f"{sym}{fee_v:,}" if fee_v else "-"
                plc = f"{plc_v:.1f}%" if plc_v else "-"
                pkg = f"{sym}{pkg_v:,}" if pkg_v else "-"
                print(f"{i:>3}  {elo:>8.2f}  {naac or '-':<4} "
                      f"{fee:>12} {plc:>6} {pkg:>12}  {cname[:40]}")

            spread = table[0][0] - table[-1][0]
            print(f"\nFinal pass ({ch}): {stats['A'] + stats['B']} decisive, "
                  f"{stats['DRAW']} drawn, of {stats['pairs']} pairs")
            print(f"Rating spread: {spread:.2f}  "
                  f"(max shift in final pass {stats['max_shift_final_pass']})")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
