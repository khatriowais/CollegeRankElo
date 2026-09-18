"""
providers/hipolabs.py
---------------------
Indian colleges & universities from the open Hipolabs
``university-domains-list`` dataset (the directory cohort).

This is an open, freely-licensed dataset of institution *names, domains and
websites* — it has no fees / placement / earnings, so every row is
``is_ranked=False`` (directory only, never Elo-ranked). We ship a committed
India snapshot (``data/snapshots/hipolabs_india.json``) so ingestion is fully
offline and reproducible; ``offline=False`` refreshes it from source.
"""

from __future__ import annotations

import json
import os
from typing import List

from .base import BaseProvider, RawCollege

SOURCE_URL = "https://github.com/Hipo/university-domains-list"
WORLD_URL = ("https://raw.githubusercontent.com/Hipo/university-domains-list/"
             "master/world_universities_and_domains.json")


class HipolabsIndiaProvider(BaseProvider):
    data_source = "hipolabs"
    cohort = "india"

    def __init__(self, snapshots_dir: str):
        self.snapshot = os.path.join(snapshots_dir, "hipolabs_india.json")

    # -- loading ------------------------------------------------------------
    def _load(self, offline: bool) -> list:
        if os.path.exists(self.snapshot):
            with open(self.snapshot, "r", encoding="utf-8") as fh:
                return json.load(fh)
        if offline:
            # No snapshot and no network allowed: nothing to ingest.
            return []
        return self._refresh()

    def _refresh(self) -> list:
        """Fetch the world dataset, keep India, and cache the snapshot."""
        from urllib.request import urlopen
        with urlopen(WORLD_URL, timeout=30) as resp:
            world = json.loads(resp.read().decode("utf-8"))
        india = [x for x in world if x.get("country") == "India"]
        india.sort(key=lambda x: (x.get("name") or "").lower())
        os.makedirs(os.path.dirname(self.snapshot), exist_ok=True)
        with open(self.snapshot, "w", encoding="utf-8") as fh:
            json.dump(india, fh, ensure_ascii=False, indent=2)
        return india

    # -- provider API -------------------------------------------------------
    def rows(self, offline: bool = True) -> List[RawCollege]:
        data = self._load(offline)
        out: List[RawCollege] = []
        seen = set()
        for row in data:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            pages = row.get("web_pages") or []
            website = pages[0].strip() if pages and pages[0] else None
            region = (row.get("state-province") or "").strip() or None
            out.append(RawCollege(
                college_name=name,
                country="India",
                cohort=self.cohort,
                data_source=self.data_source,
                is_ranked=False,          # directory only — no verified metrics
                currency="INR",
                region=region,
                website=website,
                source_url=SOURCE_URL,
            ))
        return out
