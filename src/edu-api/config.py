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
    task_queue_backend: str = "local"
    redis_url: str = "redis://localhost:6379/0"
    task_job_timeout_seconds: int = 900
    task_job_max_tries: int = 3

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
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_api_secret: str = ""
    embedding_app_id: str = ""
    embedding_base_url: str | None = None
    embedding_domain: str = "query"
    embedding_dimensions: int = 3072

    # XFYun PPT
    xfyun_ppt_enabled: bool = False
    xfyun_ppt_base_url: str = "https://zwapi.xfyun.cn"
    xfyun_ppt_app_id: str = ""
    xfyun_ppt_secret: str = ""
    xfyun_ppt_business_id: str = ""
    xfyun_ppt_default_author: str = "EduAgent"
    xfyun_ppt_default_language: str = "cn"
    xfyun_ppt_default_search: bool = False
    xfyun_ppt_default_is_card_note: bool = False
    xfyun_ppt_default_is_figure: bool = False
    xfyun_ppt_default_ai_image: str = "normal"
    xfyun_ppt_poll_interval_seconds: float = 3.0
    xfyun_ppt_poll_timeout_seconds: float = 180.0

    # Baidu AI Search
    baidu_search_api_key: str = ""
    baidu_search_base_url: str = "https://qianfan.baidubce.com"
    baidu_search_video_top_k: int = 6
    baidu_search_sites: str = "bilibili.com"
    baidu_search_timeout_seconds: float = 15.0

    # Usage Limits (per day per user)
    max_chat_messages_per_day: int = 50
    max_flashcard_generations_per_day: int = 10
    max_quiz_generations_per_day: int = 10
    max_document_uploads_per_day: int = 5

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
