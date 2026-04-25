import os


def load_dotenv(path: str) -> None:
    """
    Minimal .env loader (no external dependency).
    - Only sets keys that are not already present in the environment.
    - Supports simple KEY=VALUE pairs (optionally quoted).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f.readlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                if key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        return

