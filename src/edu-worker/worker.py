import sys
from pathlib import Path
from urllib.parse import urlparse

from arq.connections import RedisSettings
from arq.worker import func
from config import get_settings
from edu_core.services import AgentOrchestrationService, SearchService
from edu_core.services.baidu_search import BaiduSearchClient, BaiduSearchConfig
from edu_core.services.xfyun_image_generation import (
    XfyunImageGenerationClient,
    XfyunImageGenerationConfig,
)
from edu_core.services.xfyun_ppt import XfyunPptClient, XfyunPptConfig
from edu_db.session import init_db
from edu_queue.schemas import QueueTaskMessage

API_SRC = Path(__file__).resolve().parents[1] / "edu-api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from task_runner import TaskRunnerService  # noqa: E402


def redis_settings_from_url(redis_url: str) -> RedisSettings:
    parsed = urlparse(redis_url)
    database = int((parsed.path or "/0").lstrip("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


async def run_task(ctx, message: QueueTaskMessage) -> None:
    settings = get_settings()
    init_db(settings.database_url)

    search_service = SearchService(
        database_url=settings.database_url,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_api_key=settings.embedding_api_key,
        embedding_api_secret=settings.embedding_api_secret,
        embedding_app_id=settings.embedding_app_id,
        embedding_base_url=settings.embedding_base_url,
        embedding_domain=settings.embedding_domain,
        embedding_dimensions=settings.embedding_dimensions,
    )
    baidu_search_client = BaiduSearchClient(
        BaiduSearchConfig(
            api_key=settings.baidu_search_api_key,
            base_url=settings.baidu_search_base_url,
            video_top_k=settings.baidu_search_video_top_k,
            web_top_k=settings.baidu_search_web_top_k,
            sites=tuple(
                site.strip()
                for site in settings.baidu_search_sites.split(",")
                if site.strip()
            ),
            safe_search=settings.baidu_search_safe_search,
            timeout_seconds=settings.baidu_search_timeout_seconds,
        )
    )
    xfyun_image_client = XfyunImageGenerationClient(
        XfyunImageGenerationConfig(
            enabled=settings.xfyun_image_generation_enabled,
            app_id=settings.xfyun_image_generation_app_id,
            api_key=settings.xfyun_image_generation_api_key,
            api_secret=settings.xfyun_image_generation_api_secret,
            base_url=settings.xfyun_image_generation_base_url,
            timeout_seconds=settings.xfyun_image_generation_timeout_seconds,
            default_width=settings.xfyun_image_generation_default_width,
            default_height=settings.xfyun_image_generation_default_height,
        )
    )
    xfyun_ppt_client = XfyunPptClient(
        XfyunPptConfig(
            enabled=settings.xfyun_ppt_enabled,
            app_id=settings.xfyun_ppt_app_id,
            secret=settings.xfyun_ppt_secret,
            base_url=settings.xfyun_ppt_base_url,
            business_id=settings.xfyun_ppt_business_id,
            default_author=settings.xfyun_ppt_default_author,
            default_language=settings.xfyun_ppt_default_language,
            default_search=settings.xfyun_ppt_default_search,
            default_is_card_note=settings.xfyun_ppt_default_is_card_note,
            default_is_figure=settings.xfyun_ppt_default_is_figure,
            default_ai_image=settings.xfyun_ppt_default_ai_image,
            poll_interval_seconds=settings.xfyun_ppt_poll_interval_seconds,
            poll_timeout_seconds=settings.xfyun_ppt_poll_timeout_seconds,
        )
    )
    runner = TaskRunnerService(
        storage_root=settings.storage_root,
        llm_model=settings.llm_model,
        llm_api_key=settings.llm_api_key,
        llm_base_url=settings.llm_base_url,
        llm_input_cost_per_million_cny=settings.llm_input_cost_per_million_cny,
        llm_output_cost_per_million_cny=settings.llm_output_cost_per_million_cny,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        embedding_api_key=settings.embedding_api_key,
        embedding_api_secret=settings.embedding_api_secret,
        embedding_app_id=settings.embedding_app_id,
        embedding_base_url=settings.embedding_base_url,
        embedding_domain=settings.embedding_domain,
        embedding_dimensions=settings.embedding_dimensions,
        search_service=search_service,
        xfyun_image_generation_client=xfyun_image_client,
        xfyun_ppt_client=xfyun_ppt_client,
        baidu_search_client=baidu_search_client,
    )
    await runner._dispatch_async(message)


async def recover_agent_runs(ctx) -> None:
    """Requeue durable runs left behind by a terminated worker."""

    settings = get_settings()
    init_db(settings.database_url)
    service = AgentOrchestrationService()
    for run in service.list_recoverable_runs(stale_after_seconds=30):
        await ctx["redis"].enqueue_job(
            "run_task",
            {
                "type": "agent_run",
                "data": {"run_id": run["run_id"], "user_id": run["user_id"]},
            },
            _queue_name=settings.task_queue_name,
        )


settings = get_settings()


class WorkerSettings:
    functions = [
        func(
            run_task,
            timeout=settings.task_job_timeout_seconds,
            max_tries=settings.task_job_max_tries,
        )
    ]
    redis_settings = redis_settings_from_url(settings.redis_url)
    queue_name = settings.task_queue_name
    job_timeout = settings.task_job_timeout_seconds
    # Document parsing and embedding can be memory intensive. Keep production
    # concurrency explicit instead of inheriting arq's default of 10 jobs.
    max_jobs = settings.worker_max_jobs
    on_startup = recover_agent_runs
