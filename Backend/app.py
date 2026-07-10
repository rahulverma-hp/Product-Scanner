from __future__ import annotations

# Allow running this file from either:
# - project root: `python -m Backend.app`
# - Backend folder: `python app.py`
try:
    from Backend.server import create_app
    from Backend.server.db import init_db
except ModuleNotFoundError:
    import os
    import sys

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from Backend.server import create_app
    from Backend.server.db import init_db

app = create_app()


if __name__ == "__main__":
    init_db()
    # Disable reloader — loading TinyLlama twice (parent + child) can OOM/crash the server.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)