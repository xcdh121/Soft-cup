"""Queue service for synchronously dispatching local tasks."""

import logging
from collections.abc import Callable

from edu_queue.schemas import QueueTaskMessage

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

    def send_message(self, message: QueueTaskMessage) -> None:
        """
        Dispatch a QueueTaskMessage immediately in-process.

        Args:
            message: The queue task message to send

        Raises:
            Exception: If dispatching the message fails
        """
        try:
            if self.task_handler is None:
                raise RuntimeError("Queue service is not configured with a task handler.")
            self.task_handler(message)
            logger.info("Task dispatched via local queue: %s", self.queue_name)

        except Exception as e:
            logger.error(f"Error sending message: {e!s}")
            raise e
