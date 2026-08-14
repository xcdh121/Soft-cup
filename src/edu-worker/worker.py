from pathlib import Path
from urllib.parse import urlparse
import sys

from arq.connections import RedisSettings
from arq.worker import func
from config import get_settings
from edu_core.services import AgentOrchestrationService, SearchService
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
