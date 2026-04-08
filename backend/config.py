import os
from pathlib import Path

class Config:
    DATABASE        = os.environ.get("DATABASE", str(Path(__file__).parent / "lectures.db"))
    SECRET_KEY      = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    # Comma-separated list of allowed CORS origins, e.g. "https://awesome-lectures.com"
    ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")]

    # GitHub OAuth (create at github.com/settings/developers)
    GITHUB_CLIENT_ID     = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
    GITHUB_REPO          = os.environ.get("GITHUB_REPO", "")    # "owner/repo"
    GITHUB_BRANCH        = os.environ.get("GITHUB_BRANCH", "main")
    # Comma-separated GitHub usernames allowed to access /admin
    ALLOWED_MODERATORS   = [u.strip() for u in os.environ.get("ALLOWED_MODERATORS", "").split(",") if u.strip()]

    SESSION_COOKIE_SAMESITE = "Lax"
