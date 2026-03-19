"""Sage Cloud runtime configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Default data directory: ~/.sage-cloud/
# Each Sage Cloud installation gets its own storage here, auto-created on first run.
_DATA_DIR = Path.home() / ".sage-cloud"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SAGE_CLOUD_API_KEYS: str = "sage_sk_dev_key_01"
    SAGE_CLOUD_DB_PATH: str = str(_DATA_DIR / "sage-cloud.db")
    SAGE_CLOUD_ARTIFACT_DIR: str = str(_DATA_DIR / "artifacts")
    SAGE_CLOUD_APPS: str = ""
    SAGE_CLOUD_HOST: str = "0.0.0.0"
    SAGE_CLOUD_PORT: int = 8000
    SAGE_CLOUD_ENV: str = "development"

    def api_keys_list(self) -> list[str]:
        """Return API keys as a list, stripping whitespace."""
        return [k.strip() for k in self.SAGE_CLOUD_API_KEYS.split(",") if k.strip()]

    def apps_list(self) -> list[str]:
        """Return enabled app names as a list."""
        return [a.strip() for a in self.SAGE_CLOUD_APPS.split(",") if a.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
