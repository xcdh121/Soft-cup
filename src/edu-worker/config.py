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
    task_queue_name: str = "edu-agent:tasks"
    redis_url: str = "redis://localhost:6379/0"
    task_job_timeout_seconds: int = 900
    task_job_max_tries: int = 3
    worker_max_jobs: int = 4
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_input_cost_per_million_cny: float = 0.0
    llm_output_cost_per_million_cny: float = 0.0
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_api_secret: str = ""
    embedding_app_id: str = ""
    embedding_base_url: str | None = None
    embedding_domain: str = "query"
    embedding_dimensions: int = 3072

    baidu_search_api_key: str = ""
    baidu_search_base_url: str = "https://qianfan.baidubce.com"
    baidu_search_video_top_k: int = 6
    baidu_search_web_top_k: int = 5
    baidu_search_sites: str = "bilibili.com"
    baidu_search_safe_search: bool = True
    baidu_search_timeout_seconds: float = 15.0

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

    xfyun_image_generation_enabled: bool = False
    xfyun_image_generation_app_id: str = ""
    xfyun_image_generation_api_key: str = ""
    xfyun_image_generation_api_secret: str = ""
    xfyun_image_generation_base_url: str = (
        "https://spark-api.cn-huabei-1.xf-yun.com/v2.1/tti"
    )
    xfyun_image_generation_timeout_seconds: float = 120.0
    xfyun_image_generation_default_width: int = 512
    xfyun_image_generation_default_height: int = 512

    # Database
    database_url: str = ""

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
