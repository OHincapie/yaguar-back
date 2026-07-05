from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://localhost/yaguar"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24h
    debug: bool = False

    # Comma-separated list of exact allowed origins, plus a regex for Vercel
    # preview deployments of the frontend (which get a unique URL per deploy).
    cors_allowed_origins: str = "http://localhost:3000"
    cors_allowed_origin_regex: str = r"https://yaguar-front.*\.vercel\.app"

    # AI agents. Swapping providers (e.g. to Gemini) is meant to be just
    # changing llm_provider/llm_model — no agent code should import a
    # provider SDK directly. See src/domains/agents/llm.py.
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    openai_api_key: str = ""
    google_api_key: str = ""

    # Vercel automatically sends this as `Authorization: Bearer <value>`
    # on every cron invocation when a CRON_SECRET env var is set on the
    # project — the name is fixed by Vercel's convention, not ours.
    cron_secret: str = "change-me-in-production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
