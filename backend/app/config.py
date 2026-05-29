from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "X Circle Operator"
    database_url: str = "sqlite:///./usergrowth.db"
    frontend_origin: str = "http://localhost:3000"
    frontend_origins: str = ""
    allowed_login_email: str = "wanhongbo137@gmail.com"
    auth_secret: str = "change-me-in-production"
    auth_token_ttl_seconds: int = 604800
    x_bearer_token: str = ""
    discovery_mode: str = "x_api"
    outbound_proxy: str = ""
    max_public_tasks_per_day: int = 20
    max_dm_tasks_per_day: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins() -> list[str]:
    settings = get_settings()
    configured = settings.frontend_origins or settings.frontend_origin
    origins = {origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()}
    origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
    return sorted(origins)
