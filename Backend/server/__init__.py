from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .config import load_env
from .routes import register_routes


def create_app() -> Flask:
    load_env()
    app = Flask(__name__, template_folder="templates")
    CORS(app)
    register_routes(app)
    return app

