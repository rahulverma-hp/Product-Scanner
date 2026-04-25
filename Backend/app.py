from Backend.server import create_app
from Backend.server.db import init_db

app = create_app()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)