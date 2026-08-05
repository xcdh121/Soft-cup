"""Offline, privacy-safe aggregation of learning evidence."""

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from edu_db.models import CollectiveInsight, KnowledgePoint, LearningEvidenceEvent
from edu_db.session import get_session_factory


class CollectiveInsightService:
    """Publish course patterns only after a minimum distinct-learner threshold."""

    VERSION = "collective-v1"
    DEFAULT_MIN_SAMPLE_SIZE = 10

    @staticmethod
    def aggregate_events(
        rows: list[tuple[str, str, bool | None]],
        *,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    ) -> dict[str, dict]:
        """Return de-identified aggregates keyed by knowledge point.

        Each row is ``(knowledge_point_id, user_id, was_correct)``. User IDs are
        used only for thresholding and are never copied into the result.
        """

        grouped: dict[str, dict] = defaultdict(
            lambda: {"learners": set(), "attempt_count": 0, "correct_count": 0}
        )
        for knowledge_point_id, user_id, was_correct in rows:
            bucket = grouped[knowledge_point_id]
            bucket["learners"].add(user_id)
            bucket["attempt_count"] += 1
            bucket["correct_count"] += int(was_correct is True)

        published: dict[str, dict] = {}
        for knowledge_point_id, bucket in grouped.items():
            sample_size = len(bucket["learners"])
            if sample_size < max(2, min_sample_size):
                continue
            attempts = bucket["attempt_count"]
            correct = bucket["correct_count"]
            published[knowledge_point_id] = {
                "sample_size": sample_size,
                "attempt_count": attempts,
                "correct_rate": round(correct / attempts, 4) if attempts else 0.0,
                "difficulty_rate": round(1 - (correct / attempts), 4)
                if attempts
                else 0.0,
            }
        return published

    def aggregate_course(
        self,
        course_id: str,
        *,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
        window_days: int = 30,
        ttl_days: int = 7,
    ) -> list[dict]:
        """Materialize a bounded-window course aggregate for offline jobs."""

        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=max(1, window_days))
        with self._get_db_session() as db:
            rows = (
                db.query(
                    LearningEvidenceEvent.knowledge_point_id,
                    LearningEvidenceEvent.user_id,
                    LearningEvidenceEvent.payload,
                )
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == LearningEvidenceEvent.knowledge_point_id,
                )
                .filter(
                    KnowledgePoint.course_id == course_id,
                    LearningEvidenceEvent.event_type == "practice_result",
                    LearningEvidenceEvent.occurred_at >= window_start,
                    LearningEvidenceEvent.occurred_at <= window_end,
                )
                .all()
            )
            aggregates = self.aggregate_events(
                [
                    (point_id, user_id, (payload or {}).get("was_correct"))
                    for point_id, user_id, payload in rows
                    if point_id
                ],
                min_sample_size=min_sample_size,
            )
            created = []
            for point_id, aggregate in aggregates.items():
                row = CollectiveInsight(
                    id=str(uuid4()),
                    course_id=course_id,
                    knowledge_point_id=point_id,
                    pattern_type="difficulty",
                    sample_size=aggregate["sample_size"],
                    aggregate=aggregate,
                    window_start=window_start,
                    window_end=window_end,
                    version=self.VERSION,
                    expires_at=window_end + timedelta(days=max(1, ttl_days)),
                )
                db.add(row)
                created.append(
                    {
                        "id": row.id,
                        "knowledge_point_id": point_id,
                        "pattern_type": row.pattern_type,
                        **aggregate,
                    }
                )
            db.commit()
            return created

    def list_current(
        self,
        course_id: str,
        *,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    ) -> list[dict]:
        now = datetime.now(timezone.utc)
        with self._get_db_session() as db:
            rows = (
                db.query(CollectiveInsight)
                .filter(
                    CollectiveInsight.course_id == course_id,
                    CollectiveInsight.sample_size >= max(2, min_sample_size),
                    CollectiveInsight.expires_at > now,
                )
                .order_by(CollectiveInsight.created_at.desc())
                .all()
            )
            seen: set[tuple[str, str]] = set()
            result = []
            for row in rows:
                key = (row.knowledge_point_id, row.pattern_type)
                if key in seen:
                    continue
                seen.add(key)
                result.append(
                    {
                        "id": row.id,
                        "knowledge_point_id": row.knowledge_point_id,
                        "pattern_type": row.pattern_type,
                        "sample_size": row.sample_size,
                        "aggregate": row.aggregate or {},
                        "window_start": row.window_start.isoformat(),
                        "window_end": row.window_end.isoformat(),
                        "version": row.version,
                    }
                )
            return result

    @contextmanager
    def _get_db_session(self):
        session_local = get_session_factory()
        db = session_local()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
