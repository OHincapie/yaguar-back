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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
