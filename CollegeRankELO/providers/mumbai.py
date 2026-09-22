"""
providers/mumbai.py
-------------------
Curated, cited Mumbai University colleges (the ranked cohort).

Reads ``data/mumbai_university_colleges.json``. These rows carry real,
verifiable identity fields (name, type, affiliating university, NAAC grade,
website, source URL). Economic metrics (fees / package / placement) are left
as ``None`` unless a cited figure is present — we never invent them.
"""

from __future__ import annotations

import json
import os
from typing import List

from .base import BaseProvider, RawCollege


def _clean(v):
    """Normalise blanks to None; keep real zeros/values intact."""
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    return v


class MumbaiProvider(BaseProvider):
    data_source = "mumbai_curated"
    cohort = "mumbai"

    def __init__(self, data_file: str):
        self.data_file = data_file

    def rows(self, offline: bool = True) -> List[RawCollege]:
        if not os.path.exists(self.data_file):
            return []
        with open(self.data_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        out: List[RawCollege] = []
        seen = set()
        for row in data:
            name = _clean(row.get("college_name"))
            if not name or name in seen:
                continue
            seen.add(name)
            out.append(RawCollege(
                college_name=name,
                country="India",
                cohort=self.cohort,
                data_source=self.data_source,
                is_ranked=True,           # curated cohort competes on Elo
                currency="INR",
                city=_clean(row.get("city")) or "Mumbai",
                region=_clean(row.get("region")) or "Maharashtra",
                type=_clean(row.get("type")),
                university=_clean(row.get("university")),
                naac_grade=_clean(row.get("naac_grade")),
                nirf_rank=_clean(row.get("nirf_rank")),
                website=_clean(row.get("website")),
                logo=_clean(row.get("logo")),
                source_url=_clean(row.get("source_url")),
                courses=row.get("courses") or [],
                annual_fee=_clean(row.get("annual_fee")),
                average_package=_clean(row.get("average_package")),
                highest_package=_clean(row.get("highest_package")),
                placement_percentage=_clean(row.get("placement_percentage")),
                student_rating=_clean(row.get("student_rating")),
            ))
        return out
