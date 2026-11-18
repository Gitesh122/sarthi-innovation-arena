"""Application configuration.

Database
--------
* Local / laptop:  SQLite file in ./data (default, zero setup)
* Streamlit Cloud: set DATABASE_URL in Secrets (free Postgres from Neon / Supabase),
  because Streamlit Cloud's disk is wiped on every restart.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Sarthi Innovation Arena 2027"
APP_ORG = "Sarthi Immortal AI"
APP_VERSION = "4.1.0 (Python)"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# First-run administrator (password must be changed at first login)
DEFAULT_ADMIN_NAME = "Event Administrator"
DEFAULT_ADMIN_EMAIL = "admin@sarthiarena.in"
DEFAULT_ADMIN_PASSWORD = "Sarthi@2027"

LIVE_REFRESH_SECONDS = 4
TIMEZONE = "Asia/Kolkata"

# Brand palette (from the provided gradient)
C_LAV, C_OLIVE, C_SAGE, C_TEAL = "#8a86a0", "#9e9230", "#86a04e", "#3bb5a8"
C_TEAL_D = "#2a9186"
PALETTE = [C_LAV, C_OLIVE, C_SAGE, C_TEAL, "#6c6886"]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("DATABASE_URL", "")  # type: ignore[attr-defined]
        except Exception:
            url = ""
    if not url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DATA_DIR / 'arena.sqlite'}"
    if url.startswith("postgres://"):  # Heroku/Neon style → SQLAlchemy style
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url
