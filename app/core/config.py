from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    PROJECT_NAME: str = "Work-visa (PERM) outcome prediction"
    API_V1_STR: str = "/api/v1"
    # Browser origins allowed to call the demo API (the portfolio + this repo's GitHub Pages UI).
    # CORS is a browser courtesy, not access control -- abuse limits live below and in infra/.
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://srikarbolleddu.com",
        "https://www.srikarbolleddu.com",
        "https://srikarbolleddu.github.io",
        "https://d25jb32a4giwex.cloudfront.net",  # the portfolio's dev site
    ]
    # Largest accepted request body; a full prediction request is well under 1KB.
    MAX_BODY_BYTES: int = 4096
    # Best-effort per-client limit within one warm Lambda instance. The hard ceiling is the
    # API Gateway stage throttle (infra/main.tf).
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()
