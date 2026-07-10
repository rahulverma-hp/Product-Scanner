from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .config import load_env
from .db import init_db
from .routes import register_routes


def _warm_optional_models() -> None:
    try:
        from Backend.lifeve.hf_ner import warm_hf_models

        warm_hf_models()
    except Exception:
        pass


def create_app() -> Flask:
    load_env()
    app = Flask(__name__, template_folder="templates")
    CORS(app)
    init_db()
    register_routes(app)
    _warm_optional_models()
    return app

