import os

from dotenv import load_dotenv


load_dotenv()


def _env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return val


DATABASE_URL = _env("DATABASE_URL")
SESSION_SECRET = _env("SESSION_SECRET")

# Keep cookies local-demo friendly; still secure enough for the assignment.
SESSION_COOKIE = os.getenv("SESSION_COOKIE", "snickr_session")

