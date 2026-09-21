"""
config.py
---------
Centralised, environment-based configuration for CollegeRankELO.

All secrets and tunables are read from environment variables (optionally
loaded from a local `.env` file via python-dotenv). Nothing sensitive is
hard-coded, which is required for a clean final-year-project submission
and for safe deployment.

Copy `.env.example` -> `.env` and fill in your own values::

    cp .env.example .env

Environment variables
---------------------
SECRET_KEY            Flask session secret (required in production)
ADMIN_USERNAME        Admin login username (default: admin)
ADMIN_PASSWORD        Admin login password (default: changeme — change it!)
DATABASE_URL          SQLAlchemy URL (default: sqlite:///database/colleges.db)
FLASK_ENV             development | production (default: development)
PORT                  Port to run on (default: 5000)
ELO_K_FACTOR          Elo sensitivity K (default: 32)
ELO_START_RATING      Starting Elo (default: 1500)
DRAW_THRESHOLD        Weighted-score gap below which a match is a draw (default: 2.0)
WEIGHT_ROI / WEIGHT_PLACEMENT / WEIGHT_PACKAGE / WEIGHT_FEES / WEIGHT_NAAC
                      Comparison weights, must sum to 1.0
DATA_FILE             Path to seed JSON (default: data/mumbai_university_colleges.json)
"""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    # python-dotenv is optional — env vars still work without it.
    pass


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except (ValueError, TypeError):
        return default


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class Settings:
    # --- Flask / auth ---
    secret_key: str = field(
        default_factory=lambda: _get("SECRET_KEY", "dev-only-change-me"))
    admin_username: str = field(
        default_factory=lambda: _get("ADMIN_USERNAME", "admin"))
    admin_password: str = field(
        default_factory=lambda: _get("ADMIN_PASSWORD", "changeme"))
    flask_env: str = field(
        default_factory=lambda: _get("FLASK_ENV", "development"))
    port: int = field(
        default_factory=lambda: _get_int("PORT", 5000))

    # --- Database / data ---
    database_url: str = field(default_factory=lambda: _get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "database", "colleges.db"),
    ))
    data_file: str = field(default_factory=lambda: _get(
        "DATA_FILE",
        os.path.join(BASE_DIR, "data", "mumbai_university_colleges.json"),
    ))

    # --- Elo tunables ---
    elo_k_factor: int = field(
        default_factory=lambda: _get_int("ELO_K_FACTOR", 32))
    elo_start_rating: float = field(
        default_factory=lambda: _get_float("ELO_START_RATING", 1500))
    draw_threshold: float = field(
        default_factory=lambda: _get_float("DRAW_THRESHOLD", 2.0))

    # --- Comparison weights (must sum to 1.0) ---
    weight_roi: float = field(
        default_factory=lambda: _get_float("WEIGHT_ROI", 0.40))
    weight_placement: float = field(
        default_factory=lambda: _get_float("WEIGHT_PLACEMENT", 0.25))
    weight_package: float = field(
        default_factory=lambda: _get_float("WEIGHT_PACKAGE", 0.20))
    weight_fees: float = field(
        default_factory=lambda: _get_float("WEIGHT_FEES", 0.10))
    weight_naac: float = field(
        default_factory=lambda: _get_float("WEIGHT_NAAC", 0.05))

    @property
    def is_production(self) -> bool:
        return self.flask_env.lower() == "production"

    @property
    def weights(self) -> dict:
        return {
            "roi": self.weight_roi,
            "placement": self.weight_placement,
            "package": self.weight_package,
            "fees": self.weight_fees,
            "naac": self.weight_naac,
        }


settings = Settings()
