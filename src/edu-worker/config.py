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
    redis_url: str = "redis://localhost:6379/0"
    task_job_timeout_seconds: int = 900
    task_job_max_tries: int = 3
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_api_secret: str = ""
    embedding_app_id: str = ""
    embedding_base_url: str | None = None
    embedding_domain: str = "query"
    embedding_dimensions: int = 3072

    # Database
    database_url: str = ""

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
