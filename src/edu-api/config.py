from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local storage / task execution
    storage_root: str = "./.localdata"
    task_queue_name: str = "local-sync"

    # Database
    database_url: str = ""

    # Supabase Auth
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    allow_dev_auth_bypass: bool = False

    # LLM / embedding providers (OpenAI-compatible endpoints or local servers)
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_base_url: str | None = None

    # Usage Limits (per day per user)
    max_chat_messages_per_day: int = 50
    max_flashcard_generations_per_day: int = 10
    max_quiz_generations_per_day: int = 10
    max_document_uploads_per_day: int = 5

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
