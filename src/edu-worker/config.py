from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    storage_root: str = "./.localdata"
    task_queue_name: str = "local-sync"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_base_url: str | None = None

    # Database
    database_url: str = ""

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
