import os
from pathlib import Path

class Config:
    DATABASE        = os.environ.get("DATABASE", str(Path(__file__).parent / "lectures.db"))
    SECRET_KEY      = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    # Comma-separated list of allowed CORS origins, e.g. "https://awesome-lectures.com"
    ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]
