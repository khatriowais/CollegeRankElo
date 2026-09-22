"""
config.py
---------
Central, environment-driven settings for CollegeRankELO.

All tunables live here and are read from environment variables (optionally
loaded from a local ``.env`` file — see ``.env.example``). Nothing secret is
hard-coded; the defaults below are safe development placeholders.

Other modules (``app.py``, ``elo.py``, ``compare.py``, ``database.py``,
``seed_database.py``) import ``settings`` from here. The attribute names below
are load-bearing — they match what those modules expect.
"""

from __future__ import annotations

import os
import warnings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# --- .env loading -----------------------------------------------------------
# Prefer python-dotenv when installed; otherwise fall back to a tiny built-in
# parser so the app still runs without the extra dependency.
def _load_env_file(path: str) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(path)
        return
    except Exception:
        pass
    # Minimal fallback parser: KEY=VALUE lines, '#' comments, optional quotes.
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                # Do not clobber variables already set in the real environment.
                os.environ.setdefault(key, val)
    except OSError:
        pass


_load_env_file(os.path.join(BASE_DIR, ".env"))


# --- typed getters -----------------------------------------------------------
def _get(key: str, default: str) -> str:
    val = os.environ.get(key)
    return default if val is None or val == "" else val


def _get_int(key: str, default: int) -> int:
    try:
        return int(_get(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(_get(key, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    """Application settings resolved from the environment (immutable at import)."""

    def __init__(self) -> None:
        # Flask / server
        self.secret_key: str = _get("SECRET_KEY", "dev-secret-change-me")
        self.flask_env: str = _get("FLASK_ENV", "development")
        self.is_production: bool = self.flask_env.lower() == "production"
        self.port: int = _get_int("PORT", 5000)

        # Admin credentials (admin panel login)
        self.admin_username: str = _get("ADMIN_USERNAME", "admin")
        self.admin_password: str = _get("ADMIN_PASSWORD", "changeme")

        # Database (empty -> database.py falls back to bundled SQLite file)
        self.database_url: str = _get("DATABASE_URL", "")

        # Elo tunables
        self.elo_k_factor: int = _get_int("ELO_K_FACTOR", 32)
        self.elo_start_rating: float = _get_float("ELO_START_RATING", 1500.0)
        self.draw_threshold: float = _get_float("DRAW_THRESHOLD", 2.0)

        # Data files / directories
        self.data_dir: str = os.path.join(BASE_DIR, "data")
        self.snapshots_dir: str = os.path.join(self.data_dir, "snapshots")
        self.data_file: str = _get(
            "DATA_FILE",
            os.path.join(self.data_dir, "mumbai_university_colleges.json"),
        )

        # Multi-cohort ingestion (used from Phase 1 onward; harmless before then)
        self.scorecard_api_key: str = _get("SCORECARD_API_KEY", "DEMO_KEY")
        self.default_cohort: str = _get("DEFAULT_COHORT", "mumbai")

        self._validate()

    @property
    def weights(self) -> dict:
        """Comparison weights (should sum to ~1.0)."""
        return {
            "roi": _get_float("WEIGHT_ROI", 0.40),
            "placement": _get_float("WEIGHT_PLACEMENT", 0.25),
            "package": _get_float("WEIGHT_PACKAGE", 0.20),
            "fees": _get_float("WEIGHT_FEES", 0.10),
            "naac": _get_float("WEIGHT_NAAC", 0.05),
        }

    def _validate(self) -> None:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            warnings.warn(
                f"Comparison weights sum to {total:.3f}, expected 1.0. "
                "Check WEIGHT_* values in your environment/.env."
            )
        if self.is_production and self.secret_key.startswith("dev-"):
            warnings.warn(
                "SECRET_KEY is still the dev default while FLASK_ENV=production. "
                "Set a strong SECRET_KEY in .env."
            )


settings = Settings()
