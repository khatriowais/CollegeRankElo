"""
ingest.py
---------
Build / refresh the CollegeRankELO database from all data providers.

Design goals:
  * **Idempotent** — re-running never duplicates rows or double-counts Elo.
  * **Priority merge** — a curated source always wins over a directory source,
    so directory rows (which have no metrics) can never overwrite real data
    with nulls. Priority: mumbai_curated > us_scorecard > hipolabs.
  * **Offline by default** — reads committed snapshots so a demo/viva needs
    no network.

CLI:
    python ingest.py                 # upsert into the existing DB (offline)
    python ingest.py --rebuild       # drop & recreate, then ingest (offline)
    python ingest.py --rebuild --online   # also refresh snapshots from source
"""

from __future__ import annotations

import argparse
from typing import List

from database import SessionLocal, init_db, reset_db
from models import College, EloHistory
from providers import MumbaiProvider, HipolabsIndiaProvider, RawCollege

try:
    from config import settings
    _DATA_FILE = settings.data_file
    _SNAPSHOTS = settings.snapshots_dir
    _START = settings.elo_start_rating
except Exception:                     # pragma: no cover - config always present
    import os
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _DATA_FILE = os.path.join(_BASE, "data", "mumbai_university_colleges.json")
    _SNAPSHOTS = os.path.join(_BASE, "data", "snapshots")
    _START = 1500.0

# Higher number wins a collision on the same (college_name, country).
PRIORITY = {"mumbai_curated": 3, "us_scorecard": 2, "hipolabs": 1}

# Fields a higher-priority source may overwrite (identity/metrics, not id/elo).
_MERGE_FIELDS = (
    "city", "region", "type", "university", "naac_grade", "nirf_rank",
    "website", "logo", "annual_fee", "average_package", "highest_package",
    "placement_percentage", "student_rating",
)
_PROVENANCE_FIELDS = ("cohort", "currency", "data_source", "source_url",
                      "is_ranked")


def _providers() -> List:
    """Providers ordered highest-priority first (so merges resolve correctly)."""
    provs = [
        MumbaiProvider(_DATA_FILE),
        HipolabsIndiaProvider(_SNAPSHOTS),
    ]
    return sorted(provs, key=lambda p: PRIORITY.get(p.data_source, 0),
                  reverse=True)


def ingest(offline: bool = True, rebuild: bool = False,
           verbose: bool = True) -> int:
    """Upsert every provider's rows into the DB. Returns rows inserted."""
    if rebuild:
        reset_db()
    else:
        init_db()

    session = SessionLocal()
    inserted = updated = skipped = 0

    for prov in _providers():
        rows = prov.rows(offline=offline)
        if verbose:
            print(f"  {prov.data_source}: {len(rows)} rows")
        for rc in rows:
            existing = (session.query(College)
                        .filter_by(college_name=rc.college_name,
                                   country=rc.country).first())
            if existing is None:
                _insert(session, rc)
                inserted += 1
            elif PRIORITY.get(rc.data_source, 0) > PRIORITY.get(
                    existing.data_source, 0):
                _merge(session, existing, rc)
                updated += 1
            else:
                skipped += 1
        session.commit()

    session.close()
    if verbose:
        print(f"Ingest complete: {inserted} inserted, {updated} updated, "
              f"{skipped} unchanged.")
    return inserted


def _insert(session, rc: RawCollege) -> None:
    college = College(**rc.column_values())
    if rc.is_ranked:
        college.elo_rating = _START
    session.add(college)
    session.flush()
    if rc.is_ranked:
        session.add(EloHistory(college_id=college.id, rating=_START))


def _merge(session, existing: College, rc: RawCollege) -> None:
    """A higher-priority source updates an existing row (never with nulls)."""
    for f in _MERGE_FIELDS:
        val = getattr(rc, f)
        if val is not None:
            setattr(existing, f, val)
    for f in _PROVENANCE_FIELDS:
        setattr(existing, f, getattr(rc, f))
    # A row promoted into a ranked cohort needs a starting Elo + history.
    if rc.is_ranked and not existing.history:
        existing.elo_rating = _START
        session.add(EloHistory(college_id=existing.id, rating=_START))


def main() -> None:
    ap = argparse.ArgumentParser(description="Build/refresh the college DB.")
    ap.add_argument("--rebuild", action="store_true",
                    help="drop and recreate all tables before ingesting")
    ap.add_argument("--online", action="store_true",
                    help="allow network fetch to refresh snapshots")
    args = ap.parse_args()

    print(f"Ingesting (rebuild={args.rebuild}, offline={not args.online})…")
    n = ingest(offline=not args.online, rebuild=args.rebuild)
    print(f"Done. {n} new colleges.")


if __name__ == "__main__":
    main()
