from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "X Circle Operator"
    database_url: str = "sqlite:///./usergrowth.db"
    frontend_origin: str = "http://localhost:3000"
    allowed_login_email: str = "wanhongbo137@gmail.com"
    auth_secret: str = "change-me-in-production"
    auth_token_ttl_seconds: int = 604800
    x_bearer_token: str = ""
    discovery_mode: str = "sample"
    outbound_proxy: str = ""
    max_public_tasks_per_day: int = 20
    max_dm_tasks_per_day: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
