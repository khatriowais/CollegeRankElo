"""
providers
---------
Data-source adapters for CollegeRankELO ingestion.

Each provider turns one raw source (curated JSON, an open dataset, an API)
into a list of canonical ``RawCollege`` records that ``ingest.py`` upserts
into the database. Adding a new source = adding one provider here; nothing
else needs to change.
"""

from .base import RawCollege, BaseProvider
from .mumbai import MumbaiProvider
from .hipolabs import HipolabsIndiaProvider
from .scorecard import USScorecardProvider

__all__ = [
    "RawCollege",
    "BaseProvider",
    "MumbaiProvider",
    "HipolabsIndiaProvider",
    "USScorecardProvider",
]
