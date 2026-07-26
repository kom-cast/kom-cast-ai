from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TYPECAST_", env_file=".env")

    api_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
