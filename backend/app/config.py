from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "X Circle Operator"
    database_url: str = "sqlite:///./usergrowth.db"
    frontend_origin: str = "http://localhost:3000"
    x_bearer_token: str = ""
    discovery_mode: str = "sample"
    max_public_tasks_per_day: int = 20
    max_dm_tasks_per_day: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

