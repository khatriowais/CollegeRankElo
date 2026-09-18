"""
seed_database.py
----------------
Load Mumbai University colleges from data/mumbai_university_colleges.json
and populate the SQLite database. Safe to re-run: uses upsert-by-name.
"""

import json
import os
from datetime import datetime

from database import SessionLocal, init_db
from models import College, EloHistory
from elo import EloConfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data", "mumbai_university_colleges.json")


def run() -> int:
    init_db()
    session = SessionLocal()
    with open(DATA_FILE) as f:
        rows = json.load(f)

    inserted = 0
    for row in rows:
        existing = session.query(College).filter_by(
            college_name=row["college_name"]).first()
        if existing:
            continue
        college = College(
            college_name=row["college_name"],
            city=row["city"],
            type=row["type"],
            university=row["university"],
            naac_grade=row["naac_grade"],
            nirf_rank=row["nirf_rank"],
            annual_fee=row["annual_fee"],
            average_package=row["average_package"],
            highest_package=row["highest_package"],
            placement_percentage=row["placement_percentage"],
            student_rating=row["student_rating"],
            website=row["website"],
            logo=row.get("logo") or "",
            elo_rating=EloConfig.START_RATING,
            last_updated=datetime.utcnow(),
        )
        session.add(college)
        session.flush()
        session.add(EloHistory(college_id=college.id,
                               rating=EloConfig.START_RATING))
        inserted += 1

    session.commit()
    session.close()
    return inserted


if __name__ == "__main__":
    n = run()
    print(f"Seeded {n} new colleges.")
