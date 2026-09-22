"""
seed_database.py
----------------
Thin wrapper kept for backwards compatibility (``app.py`` auto-seeds via
``run()`` on an empty DB, and README/docs reference this script).

The real work now lives in ``ingest.py``, which pulls every data provider
(curated Mumbai + India directory) idempotently and offline. Run that
directly for a full rebuild:  ``python ingest.py --rebuild``.
"""

from ingest import ingest


def run() -> int:
    """Populate the database from all providers (offline). Returns inserted."""
    return ingest(offline=True, rebuild=False, verbose=True)


if __name__ == "__main__":
    n = run()
    print(f"Seeded {n} new colleges.")
