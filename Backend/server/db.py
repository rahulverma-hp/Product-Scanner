from __future__ import annotations

import sqlite3

from .config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            height_cm REAL,
            weight_kg REAL
        )
        """
    )
    try:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_username_ci
            ON profiles(username COLLATE NOCASE)
            """
        )
    except (sqlite3.OperationalError, sqlite3.IntegrityError):
        pass

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES profiles(id)
        )
        """
    )

    conn.commit()
    conn.close()

