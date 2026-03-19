"""Groot runtime configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default data directory: ~/.groot/
# Each Groot installation gets its own storage here, auto-created on first run.
_DATA_DIR = Path.home() / ".groot"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GROOT_API_KEYS: str = "groot_sk_dev_key_01"
    GROOT_DB_PATH: str = str(_DATA_DIR / "groot.db")
    GROOT_ARTIFACT_DIR: str = str(_DATA_DIR / "artifacts")
    GROOT_APPS: str = "_example"
    GROOT_HOST: str = "0.0.0.0"
    GROOT_PORT: int = 8000
    GROOT_ENV: str = "development"

    def api_keys_list(self) -> list[str]:
        """Return API keys as a list, stripping whitespace."""
        return [k.strip() for k in self.GROOT_API_KEYS.split(",") if k.strip()]

    def apps_list(self) -> list[str]:
        """Return enabled app names as a list."""
        return [a.strip() for a in self.GROOT_APPS.split(",") if a.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
