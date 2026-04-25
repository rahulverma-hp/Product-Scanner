from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Any

from flask import request


def hash_password(password: str) -> str:
    """
    PBKDF2-HMAC-SHA256 hash.
    Stored as: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    password = password or ""
    salt = secrets.token_bytes(16)
    iterations = 210_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, it_s, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(it_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        dk = hashlib.pbkdf2_hmac(
            "sha256", (password or "").encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_session(conn, profile_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, profile_id, created_at) VALUES (?, ?, ?)",
        (token, int(profile_id), int(time.time())),
    )
    return token


def get_profile_by_token(conn, token: str):
    if not token:
        return None
    row = conn.execute(
        """
        SELECT p.id, p.username, p.display_name, p.age, p.gender, p.height_cm, p.weight_kg
        FROM sessions s
        JOIN profiles p ON p.id = s.profile_id
        WHERE s.token = ?
        """,
        (token,),
    ).fetchone()
    return dict(row) if row else None


def auth_token_from_request() -> str:
    h = request.headers.get("Authorization") or ""
    if h.lower().startswith("bearer "):
        return h.split(" ", 1)[1].strip()
    data: dict[str, Any] = request.get_json(silent=True) or {}
    return (data.get("auth_token") or "").strip()

