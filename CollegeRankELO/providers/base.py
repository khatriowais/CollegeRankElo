"""
providers/base.py
-----------------
Canonical record + provider interface shared by every data source.

``RawCollege`` maps 1:1 onto the writable columns of ``models.College`` (it
deliberately omits ``id``, ``elo_rating`` and ``last_updated``, which the
database owns), so ``College(**record.column_values())`` just works.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class RawCollege:
    # Identity / location
    college_name: str
    country: str
    cohort: str
    data_source: str
    is_ranked: bool = False
    currency: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None

    # Descriptive
    type: Optional[str] = None
    university: Optional[str] = None
    naac_grade: Optional[str] = None
    nirf_rank: Optional[int] = None
    website: Optional[str] = None
    logo: Optional[str] = None
    source_url: Optional[str] = None

    # Courses / Programs & Fee Structure
    courses: Optional[List[dict]] = None

    # Metrics (None where a source has no verified figure — never fabricate)
    annual_fee: Optional[int] = None
    average_package: Optional[int] = None
    highest_package: Optional[int] = None
    placement_percentage: Optional[float] = None
    student_rating: Optional[float] = None

    def column_values(self) -> dict:
        """Return a dict of column -> value for constructing a ``College``."""
        import json
        d = asdict(self)
        if isinstance(d.get("courses"), list):
            d["courses"] = json.dumps(d["courses"], ensure_ascii=False)
        return d


class BaseProvider(abc.ABC):
    """A single data source. Subclasses yield canonical ``RawCollege`` rows."""

    #: short, stable identifier stored on each row (e.g. 'hipolabs')
    data_source: str = "base"
    #: cohort these rows belong to (e.g. 'mumbai', 'india')
    cohort: str = ""

    @abc.abstractmethod
    def rows(self, offline: bool = True) -> List[RawCollege]:
        """Return the source's colleges as canonical records.

        ``offline=True`` must read only committed local files (snapshots /
        curated JSON) so ingestion works with no network — important for a
        reproducible demo/viva.
        """
        raise NotImplementedError
