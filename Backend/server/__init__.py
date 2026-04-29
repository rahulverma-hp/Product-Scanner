from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .config import load_env
from .db import init_db
from .routes import register_routes


def create_app() -> Flask:
    load_env()
    app = Flask(__name__, template_folder="templates")
    CORS(app)
    # Ensure tables exist even when running under gunicorn (Render).
    init_db()
    register_routes(app)
    return app

