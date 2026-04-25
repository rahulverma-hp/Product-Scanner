from __future__ import annotations

import os

from Backend.env_loader import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Backend/
DB_PATH = os.path.join(BASE_DIR, "profiles.db")


def load_env() -> None:
    # Allow putting keys into Backend/.env
    load_dotenv(os.path.join(BASE_DIR, ".env"))

