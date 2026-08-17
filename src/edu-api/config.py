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
    resource_package_generation_concurrency: int = 4

    # Database
    database_url: str = ""

    # Self-hosted authentication
    auth_jwt_secret: str = ""
    auth_access_token_expire_minutes: int = 10080
    auth_allow_registration: bool = True
    auth_admin_usernames: str = ""
    allow_dev_auth_bypass: bool = False

    # Billing and payment callbacks. Provider secrets never leave the API process.
    billing_environment: str = "development"
    billing_manual_payment_enabled: bool = True
    billing_order_expiry_minutes: int = 30
    billing_manual_payment_recipient: str = ""
    billing_manual_wechat_qr_url: str = ""
    billing_manual_qq_qr_url: str = ""
    payment_webhook_secret: str = ""
    payment_callback_base_url: str = ""

    # LLM / embedding providers (OpenAI-compatible endpoints or local servers)
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    # Provider price in CNY per one million tokens. Keep zero when unknown;
    # token usage is still recorded while estimated cost is shown as unconfigured.
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

    # XFYun Spark text-to-image generation
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

    # XFYun Chinese speech recognition (IAT)
    xfyun_iat_enabled: bool = False
    xfyun_iat_app_id: str = ""
    xfyun_iat_api_key: str = ""
    xfyun_iat_api_secret: str = ""
    xfyun_iat_host: str = "iat.xf-yun.com"
    xfyun_iat_path: str = "/v1"

    # XFYun handwriting recognition
    xfyun_handwriting_enabled: bool = False
    xfyun_handwriting_app_id: str = ""
    xfyun_handwriting_api_key: str = ""
    xfyun_handwriting_base_url: str = (
        "https://webapi.xfyun.cn/v1/service/v1/ocr/handwriting"
    )
    xfyun_handwriting_timeout_seconds: float = 30.0

    # XFYun Spark image understanding
    xfyun_image_understanding_enabled: bool = False
    xfyun_image_understanding_app_id: str = ""
    xfyun_image_understanding_api_key: str = ""
    xfyun_image_understanding_api_secret: str = ""
    xfyun_image_understanding_base_url: str = (
        "wss://spark-api.cn-huabei-1.xf-yun.com/v2.1/image"
    )
    xfyun_image_understanding_domain: str = "imagev3"
    xfyun_image_understanding_timeout_seconds: float = 60.0
    xfyun_image_understanding_max_tokens: int = 2048

    # XFYun PDF document OCR
    xfyun_pdf_ocr_enabled: bool = False
    xfyun_pdf_ocr_app_id: str = ""
    xfyun_pdf_ocr_secret: str = ""
    xfyun_pdf_ocr_base_url: str = "https://iocr.xfyun.cn/ocrzdq/v1/pdfOcr"
    xfyun_pdf_ocr_timeout_seconds: float = 120.0

    # XFYun Machine Translation (New)
    xfyun_translation_enabled: bool = False
    xfyun_translation_app_id: str = ""
    xfyun_translation_api_key: str = ""
    xfyun_translation_api_secret: str = ""
    xfyun_translation_base_url: str = "https://itrans.xf-yun.com/v1/its"
    xfyun_translation_timeout_seconds: float = 30.0

    # Baidu AI Search
    baidu_search_api_key: str = ""
    baidu_search_base_url: str = "https://qianfan.baidubce.com"
    baidu_search_video_top_k: int = 6
    baidu_search_web_top_k: int = 5
    baidu_search_sites: str = "bilibili.com"
    baidu_search_safe_search: bool = True
    baidu_search_timeout_seconds: float = 15.0

    # Sandboxed code execution (Piston-compatible POST /api/v2/execute endpoint)
    code_execution_api_url: str = ""
    code_execution_api_token: str = ""
    code_execution_timeout_seconds: float = 15.0

    # Usage Limits (per day per user)
    max_chat_messages_per_day: int = 50
    max_flashcard_generations_per_day: int = 10
    max_quiz_generations_per_day: int = 10
    max_document_uploads_per_day: int = 5


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
