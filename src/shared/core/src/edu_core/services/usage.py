"""Service for tracking and enforcing user usage limits."""

from contextlib import contextmanager
from datetime import UTC, datetime, time
from typing import Literal
from uuid import uuid4

from edu_db.models import (
    AgentRun,
    AgentToolCall,
    Chat,
    ChatMessage,
    ChatMessagePart,
    UserUsage,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import UsageLimitExceededError
from edu_core.schemas.usage import ToolUsageDto, UsageDto, UsageLimitDto
from edu_core.services.quota import QuotaService


class UsageService:
    """Service for tracking and enforcing user usage limits."""

    def __init__(
        self,
        max_chat_messages_per_day: int = 50,
        max_flashcard_generations_per_day: int = 10,
        max_quiz_generations_per_day: int = 10,
        max_mindmap_generations_per_day: int = 10,
        max_document_uploads_per_day: int = 5,
    ) -> None:
        """Initialize the usage service.

        Args:
            max_chat_messages_per_day: Maximum chat messages per day
            max_flashcard_generations_per_day: Maximum flashcard generations per day
            max_quiz_generations_per_day: Maximum quiz generations per day
            max_mindmap_generations_per_day: Maximum mind map generations per day
            max_document_uploads_per_day: Maximum document uploads per day
        """
        self.max_chat_messages_per_day = max_chat_messages_per_day
        self.max_flashcard_generations_per_day = max_flashcard_generations_per_day
        self.max_quiz_generations_per_day = max_quiz_generations_per_day
        self.max_mindmap_generations_per_day = max_mindmap_generations_per_day
        self.max_document_uploads_per_day = max_document_uploads_per_day

    def check_and_increment(
        self,
        user_id: str,
        usage_type: Literal[
            "chat_message",
            "flashcard_generation",
            "quiz_generation",
            "mindmap_generation",
            "document_upload",
        ],
    ) -> None:
        """Check if user has exceeded limit and increment counter.

        Args:
            user_id: The user's unique identifier
            usage_type: Type of usage to check and increment

        Raises:
            UsageLimitExceeded: If the user has exceeded their usage limit
        """
        quota_service = QuotaService()
        if quota_service.has_active_entitlement(user_id):
            operation_id = str(uuid4())
            quota_service.consume(
                user_id=user_id,
                resource_type=usage_type,
                idempotency_key=f"usage:{usage_type}:{operation_id}",
                business_type="legacy_usage",
                business_id=operation_id,
            )
            return
        with self._get_db_session() as db:
            try:
                usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
                if not usage:
                    usage = UserUsage(
                        user_id=user_id,
                        chat_messages_today=0,
                        flashcard_generations_today=0,
                        quiz_generations_today=0,
                        mindmap_generations_today=0,
                        document_uploads_today=0,
                        last_reset_date=datetime.now(UTC),
                    )
                    db.add(usage)
                    db.commit()
                    db.refresh(usage)

                usage = self._reset_daily_counters_if_needed(usage)

                # Get current count and limit
                count_map = {
                    "chat_message": usage.chat_messages_today,
                    "flashcard_generation": usage.flashcard_generations_today,
                    "quiz_generation": usage.quiz_generations_today,
                    "mindmap_generation": usage.mindmap_generations_today,
                    "document_upload": usage.document_uploads_today,
                }

                limit_map = {
                    "chat_message": self.max_chat_messages_per_day,
                    "flashcard_generation": self.max_flashcard_generations_per_day,
                    "quiz_generation": self.max_quiz_generations_per_day,
                    "mindmap_generation": self.max_mindmap_generations_per_day,
                    "document_upload": self.max_document_uploads_per_day,
                }

                current_count = count_map[usage_type]
                limit = limit_map[usage_type]

                # Check limit
                if current_count >= limit:
                    raise UsageLimitExceededError(
                        usage_type=usage_type,
                        current_count=current_count,
                        limit=limit,
                    )

                # Increment counter
                if usage_type == "chat_message":
                    usage.chat_messages_today += 1
                elif usage_type == "flashcard_generation":
                    usage.flashcard_generations_today += 1
                elif usage_type == "quiz_generation":
                    usage.quiz_generations_today += 1
                elif usage_type == "mindmap_generation":
                    usage.mindmap_generations_today += 1
                elif usage_type == "document_upload":
                    usage.document_uploads_today += 1

                db.commit()
                db.refresh(usage)
            except UsageLimitExceededError:
                raise
            except Exception:
                db.rollback()
                raise

    def get_usage(self, user_id: str) -> UsageDto:
        """Get current usage statistics for a user.

        Args:
            user_id: The user's unique identifier

        Returns:
            UsageDto containing usage statistics for all usage types
        """
        with self._get_db_session() as db:
            try:
                usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
                if not usage:
                    usage = UserUsage(
                        user_id=user_id,
                        chat_messages_today=0,
                        flashcard_generations_today=0,
                        quiz_generations_today=0,
                        mindmap_generations_today=0,
                        document_uploads_today=0,
                        last_reset_date=datetime.now(UTC),
                    )
                    db.add(usage)
                    db.commit()
                    db.refresh(usage)

                usage = self._reset_daily_counters_if_needed(usage)

                return UsageDto(
                    chat_messages=UsageLimitDto(
                        used=usage.chat_messages_today,
                        limit=self.max_chat_messages_per_day,
                    ),
                    flashcard_generations=UsageLimitDto(
                        used=usage.flashcard_generations_today,
                        limit=self.max_flashcard_generations_per_day,
                    ),
                    quiz_generations=UsageLimitDto(
                        used=usage.quiz_generations_today,
                        limit=self.max_quiz_generations_per_day,
                    ),
                    mindmap_generations=UsageLimitDto(
                        used=usage.mindmap_generations_today,
                        limit=self.max_mindmap_generations_per_day,
                    ),
                    document_uploads=UsageLimitDto(
                        used=usage.document_uploads_today,
                        limit=self.max_document_uploads_per_day,
                    ),
                    tool_usage=self._get_daily_tool_usage(db, user_id),
                )
            except Exception:
                raise

    def _get_daily_tool_usage(self, db, user_id: str) -> list[ToolUsageDto]:
        """Aggregate all persisted tool calls for the current UTC day.

        Tool calls can originate from the conversational tutor or from the
        multi-agent orchestration runtime. Both stores are included so the
        settings page reflects the user's complete tool activity.
        """
        now = datetime.now(UTC)
        day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)

        agent_rows = (
            db.query(
                AgentToolCall.tool_name,
                AgentToolCall.status,
                AgentToolCall.started_at,
            )
            .join(AgentRun, AgentRun.id == AgentToolCall.run_id)
            .filter(
                AgentRun.user_id == user_id,
                AgentToolCall.started_at >= day_start,
            )
            .all()
        )
        chat_rows = (
            db.query(
                ChatMessagePart.tool_name,
                ChatMessagePart.tool_state,
                ChatMessagePart.created_at,
            )
            .join(ChatMessage, ChatMessage.id == ChatMessagePart.message_id)
            .join(Chat, Chat.id == ChatMessage.chat_id)
            .filter(
                Chat.user_id == user_id,
                ChatMessagePart.part_type == "tool_call",
                ChatMessagePart.tool_name.isnot(None),
                ChatMessagePart.created_at >= day_start,
            )
            .all()
        )

        totals: dict[str, dict[str, int | datetime | None]] = {}

        def add_call(
            tool_name: str | None,
            status: str | None,
            used_at: datetime | None,
            successful_status: str,
            failed_status: str,
        ) -> None:
            if not tool_name:
                return
            summary = totals.setdefault(
                tool_name,
                {"total": 0, "successful": 0, "failed": 0, "last_used_at": None},
            )
            summary["total"] = int(summary["total"] or 0) + 1
            if status == successful_status:
                summary["successful"] = int(summary["successful"] or 0) + 1
            elif status == failed_status:
                summary["failed"] = int(summary["failed"] or 0) + 1

            last_used_at = summary["last_used_at"]
            if used_at and (last_used_at is None or used_at > last_used_at):
                summary["last_used_at"] = used_at

        for tool_name, status, used_at in agent_rows:
            add_call(tool_name, status, used_at, "completed", "failed")
        for tool_name, status, used_at in chat_rows:
            add_call(tool_name, status, used_at, "output-available", "output-error")

        return [
            ToolUsageDto(tool_name=tool_name, **summary)
            for tool_name, summary in sorted(
                totals.items(),
                key=lambda item: (-int(item[1]["total"] or 0), item[0]),
            )
        ]

    def _reset_daily_counters_if_needed(self, usage: UserUsage) -> UserUsage:
        """Reset daily counters if it's a new day.

        Args:
            db: Database session
            usage: UserUsage model instance

        Returns:
            Updated UserUsage model instance
        """
        now = datetime.now(UTC)
        last_reset = usage.last_reset_date

        # Check if it's a new day (compare dates, not times)
        if now.date() > last_reset.date():
            usage.chat_messages_today = 0
            usage.flashcard_generations_today = 0
            usage.quiz_generations_today = 0
            usage.mindmap_generations_today = 0
            usage.document_uploads_today = 0
            usage.last_reset_date = now

        return usage

    @contextmanager
    def _get_db_session(self):
        """Context manager for database sessions."""
        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
