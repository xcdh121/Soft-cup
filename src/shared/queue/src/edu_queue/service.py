"""Queue services for dispatching local or Redis-backed background tasks."""

import asyncio
import logging
from collections.abc import Callable
from threading import Thread
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

from .schemas import QueueTaskMessage, TaskType

logger = logging.getLogger(__name__)


class QueueService:
    """Service for dispatching tasks in-process."""

    def __init__(
        self,
        connection_string: str = "",
        queue_name: str = "local-sync",
        task_handler: Callable[[QueueTaskMessage], None] | None = None,
    ):
        """Initialize the queue service.

        Args:
            connection_string: Unused compatibility field
            queue_name: Logical queue name for logging
            task_handler: Synchronous task handler
        """
        self.queue_name = queue_name
        self.task_handler = task_handler

    def send_message(self, message: QueueTaskMessage) -> str:
        """
        Dispatch a QueueTaskMessage immediately in-process.

        Args:
            message: The queue task message to send

        Raises:
            Exception: If dispatching the message fails
        """
        try:
            if self.task_handler is None:
                raise RuntimeError(
                    "Queue service is not configured with a task handler."
                )
            self.task_handler(message)
            logger.info("Task dispatched via local queue: %s", self.queue_name)
            return "local-sync"

        except Exception as e:
            logger.error("Error sending message: %s", e)
            raise

    @property
    def is_remote(self) -> bool:
        return False


class ArqQueueService:
    """Service for enqueueing tasks into Redis for arq workers."""

    def __init__(
        self,
        redis_url: str,
        queue_name: str = "edu-agent:tasks",
        job_timeout_seconds: int = 900,
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self.job_timeout_seconds = job_timeout_seconds

    def send_message(self, message: QueueTaskMessage) -> str:
        """
        Enqueue a QueueTaskMessage into Redis.

        This method intentionally keeps the same synchronous API as the local
        implementation so existing service methods can enqueue background work
        without being converted to async in the first migration pass.
        """
        try:
            job_id = self._run_async(self._enqueue(message))
            logger.info("Task enqueued via arq queue %s: %s", self.queue_name, job_id)
            return job_id
        except Exception as e:
            logger.error("Error enqueueing message: %s", e)
            raise

    @property
    def is_remote(self) -> bool:
        return True

    async def _enqueue(self, message: QueueTaskMessage) -> str:
        redis = await create_pool(_redis_settings_from_url(self.redis_url))
        try:
            normalized = _normalize_message(message)
            desired_job_id = _job_id_for_message(normalized)
            job = await redis.enqueue_job(
                "run_task",
                normalized,
                _queue_name=self.queue_name,
                _expires=self.job_timeout_seconds * 2,
                _job_id=desired_job_id,
            )
            if job is None:
                if desired_job_id:
                    return desired_job_id
                raise RuntimeError("arq did not return a job handle")
            return job.job_id
        finally:
            await redis.close()

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result = None
        error: Exception | None = None

        def run() -> None:
            nonlocal result, error
            try:
                result = asyncio.run(coro)
            except Exception as exc:  # pragma: no cover
                error = exc

        thread = Thread(target=run, daemon=False)
        thread.start()
        thread.join()
        if error:
            raise error
        return result


def _normalize_message(message: QueueTaskMessage) -> dict:
    task_type = message["type"]
    normalized_type = task_type.value if isinstance(task_type, TaskType) else task_type
    return {
        "type": normalized_type,
        "data": dict(message["data"]),
    }


def _job_id_for_message(message: dict) -> str | None:
    """Use a stable ID for package items so Redis redelivery cannot duplicate work."""
    if message.get("type") != TaskType.RESOURCE_PACKAGE_ITEM.value:
        return None
    data = message.get("data") or {}
    package_id = str(data.get("package_id") or "")
    resource_id = str(data.get("resource_id") or "")
    if not package_id or not resource_id:
        return None
    return f"resource-package:{package_id}:{resource_id}"


def _redis_settings_from_url(redis_url: str) -> RedisSettings:
    parsed = urlparse(redis_url)
    database = int((parsed.path or "/0").lstrip("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )
