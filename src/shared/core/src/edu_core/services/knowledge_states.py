"""Service for project-scoped student knowledge states."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import (
    KnowledgePoint,
    KnowledgePointRelation,
    KnowledgeStateEvent,
    PracticeRecord,
    Project,
    StudentKnowledgeState,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.knowledge_states import (
    KnowledgeGraphDto,
    KnowledgeGraphEdgeDto,
    KnowledgeGraphNodeDto,
    KnowledgeStateDto,
    KnowledgeStateRefreshDto,
)


class KnowledgeStateService:
    """Manage the current user's state for course knowledge points."""

    def list_states(
        self, project_id: str, user_id: str
    ) -> list[KnowledgeStateDto]:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(
                db, project_id, user_id
            )
            rows = (
                db.query(KnowledgePoint, StudentKnowledgeState)
                .outerjoin(
                    StudentKnowledgeState,
                    (StudentKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                    & (StudentKnowledgeState.user_id == user_id),
                )
                .filter(KnowledgePoint.course_id == project.course_id)
                .order_by(KnowledgePoint.position, KnowledgePoint.created_at)
                .all()
            )
            return [
                self._to_dto(project_id, user_id, point, state)
                for point, state in rows
            ]

    def get_state(
        self, project_id: str, knowledge_point_id: str, user_id: str
    ) -> KnowledgeStateDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(
                db, project_id, user_id
            )
            point = self._get_course_knowledge_point(
                db, project.course_id, knowledge_point_id
            )
            state = (
                db.query(StudentKnowledgeState)
                .filter(
                    StudentKnowledgeState.user_id == user_id,
                    StudentKnowledgeState.knowledge_point_id
                    == knowledge_point_id,
                )
                .first()
            )
            return self._to_dto(project_id, user_id, point, state)

    def get_knowledge_graph(
        self, project_id: str, user_id: str
    ) -> KnowledgeGraphDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(
                db, project_id, user_id
            )
            rows = (
                db.query(KnowledgePoint, StudentKnowledgeState)
                .outerjoin(
                    StudentKnowledgeState,
                    (StudentKnowledgeState.knowledge_point_id == KnowledgePoint.id)
                    & (StudentKnowledgeState.user_id == user_id),
                )
                .filter(KnowledgePoint.course_id == project.course_id)
                .order_by(KnowledgePoint.position, KnowledgePoint.created_at)
                .all()
            )
            relations = (
                db.query(KnowledgePointRelation)
                .filter(KnowledgePointRelation.course_id == project.course_id)
                .order_by(KnowledgePointRelation.created_at)
                .all()
            )

            return KnowledgeGraphDto(
                project_id=project_id,
                course_id=project.course_id,
                nodes=[
                    KnowledgeGraphNodeDto(
                        id=point.id,
                        label=point.name,
                        chapter_id=point.chapter_id,
                        difficulty_level=point.difficulty_level,
                        position=point.position,
                        tags=point.tags or [],
                        mastery_score=state.mastery_score if state else 0,
                        confidence=state.confidence if state else 0,
                        trend=state.trend if state else "stable",
                        status=state.status if state else "not_started",
                    )
                    for point, state in rows
                ],
                edges=[
                    KnowledgeGraphEdgeDto(
                        id=relation.id,
                        source=relation.source_knowledge_point_id,
                        target=relation.target_knowledge_point_id,
                        relation_type=relation.relation_type,
                        strength=relation.strength,
                        description=relation.description,
                    )
                    for relation in relations
                ],
            )

    def upsert_state(
        self,
        project_id: str,
        knowledge_point_id: str,
        user_id: str,
        *,
        mastery_score: float,
        confidence: float,
        trend: str,
        status: str,
        attempt_count: int,
        correct_count: int,
        evidence: list[dict],
        last_practiced_at,
    ) -> KnowledgeStateDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(
                db, project_id, user_id
            )
            point = self._get_course_knowledge_point(
                db, project.course_id, knowledge_point_id
            )
            state = (
                db.query(StudentKnowledgeState)
                .filter(
                    StudentKnowledgeState.user_id == user_id,
                    StudentKnowledgeState.knowledge_point_id
                    == knowledge_point_id,
                )
                .first()
            )
            if state is None:
                state = StudentKnowledgeState(
                    id=str(uuid4()),
                    user_id=user_id,
                    knowledge_point_id=knowledge_point_id,
                )
                db.add(state)

            score_before = float(state.mastery_score or 0)
            state.mastery_score = mastery_score
            state.confidence = confidence
            state.trend = trend
            state.status = status
            state.attempt_count = attempt_count
            state.correct_count = correct_count
            state.evidence = evidence
            state.last_practiced_at = last_practiced_at
            db.add(
                KnowledgeStateEvent(
                    id=str(uuid4()),
                    knowledge_state_id=state.id,
                    project_id=project_id,
                    user_id=user_id,
                    knowledge_point_id=knowledge_point_id,
                    event_type="manual_update",
                    source_type="manual",
                    source_id=str(uuid4()),
                    score_before=score_before,
                    score_after=mastery_score,
                    impact=mastery_score - score_before,
                    evidence={"reason": "manual API update"},
                )
            )
            db.commit()
            db.refresh(state)
            return self._to_dto(project_id, user_id, point, state)

    def refresh_states(
        self, project_id: str, user_id: str
    ) -> KnowledgeStateRefreshDto:
        """Apply unprocessed practice records to knowledge states."""
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(
                db, project_id, user_id
            )
            points = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.course_id == project.course_id)
                .all()
            )
            points_by_id = {point.id: point for point in points}
            records = (
                db.query(PracticeRecord)
                .filter(
                    PracticeRecord.project_id == project_id,
                    PracticeRecord.user_id == user_id,
                )
                .order_by(PracticeRecord.created_at, PracticeRecord.id)
                .all()
            )

            processed_count = 0
            already_processed_count = 0
            unmatched_count = 0
            updated: dict[str, tuple[KnowledgePoint, StudentKnowledgeState]] = {}

            for record in records:
                point = self._resolve_practice_knowledge_point(
                    record, points_by_id
                )
                if point is None:
                    unmatched_count += 1
                    continue

                existing_event = (
                    db.query(KnowledgeStateEvent)
                    .filter(
                        KnowledgeStateEvent.user_id == user_id,
                        KnowledgeStateEvent.knowledge_point_id == point.id,
                        KnowledgeStateEvent.source_type == "practice_record",
                        KnowledgeStateEvent.source_id == record.id,
                    )
                    .first()
                )
                if existing_event:
                    already_processed_count += 1
                    continue

                state = (
                    db.query(StudentKnowledgeState)
                    .filter(
                        StudentKnowledgeState.user_id == user_id,
                        StudentKnowledgeState.knowledge_point_id == point.id,
                    )
                    .first()
                )
                if state is None:
                    state = StudentKnowledgeState(
                        id=str(uuid4()),
                        user_id=user_id,
                        knowledge_point_id=point.id,
                        mastery_score=0,
                        confidence=0,
                        trend="stable",
                        status="not_started",
                        attempt_count=0,
                        correct_count=0,
                        evidence=[],
                    )
                    db.add(state)

                score_before = float(state.mastery_score or 0)
                target_score = 100.0 if record.was_correct else 0.0
                score_after = round(
                    score_before * 0.7 + target_score * 0.3, 2
                )
                impact = round(score_after - score_before, 2)

                state.mastery_score = score_after
                state.attempt_count = int(state.attempt_count or 0) + 1
                if record.was_correct:
                    state.correct_count = int(state.correct_count or 0) + 1
                else:
                    state.correct_count = int(state.correct_count or 0)
                state.confidence = min(
                    1.0, round(0.2 + state.attempt_count * 0.1, 2)
                )
                state.trend = (
                    "up" if impact > 2 else "down" if impact < -2 else "stable"
                )
                state.status = (
                    "mastered" if score_after >= 80 else "learning"
                )
                state.last_practiced_at = record.created_at

                evidence_item = {
                    "event_type": "practice_record",
                    "source_id": record.id,
                    "item_type": record.item_type,
                    "item_id": record.item_id,
                    "topic": record.topic,
                    "was_correct": record.was_correct,
                    "impact": impact,
                }
                state.evidence = [
                    *(state.evidence or []),
                    evidence_item,
                ][-100:]
                db.add(
                    KnowledgeStateEvent(
                        id=str(uuid4()),
                        knowledge_state_id=state.id,
                        project_id=project_id,
                        user_id=user_id,
                        knowledge_point_id=point.id,
                        event_type="practice_result",
                        source_type="practice_record",
                        source_id=record.id,
                        score_before=score_before,
                        score_after=score_after,
                        impact=impact,
                        was_correct=record.was_correct,
                        evidence=evidence_item,
                    )
                )
                processed_count += 1
                updated[point.id] = (point, state)

            db.commit()
            for _, state in updated.values():
                db.refresh(state)

            return KnowledgeStateRefreshDto(
                processed_count=processed_count,
                already_processed_count=already_processed_count,
                unmatched_count=unmatched_count,
                updated_states=[
                    self._to_dto(project_id, user_id, point, state)
                    for point, state in updated.values()
                ],
            )

    @staticmethod
    def _resolve_practice_knowledge_point(
        record: PracticeRecord,
        points_by_id: dict[str, KnowledgePoint],
    ) -> KnowledgePoint | None:
        if record.knowledge_point_id:
            return points_by_id.get(record.knowledge_point_id)

        normalized_topic = (record.topic or "").strip().casefold()
        if not normalized_topic:
            return None
        matches = [
            point
            for point in points_by_id.values()
            if point.name.strip().casefold() == normalized_topic
            or normalized_topic
            in {
                str(tag).strip().casefold()
                for tag in (point.tags or [])
            }
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _get_owned_project_with_course(
        db, project_id: str, user_id: str
    ) -> Project:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == user_id)
            .first()
        )
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        if not project.course_id:
            raise ValueError(
                f"Project {project_id} is not associated with a course"
            )
        return project

    @staticmethod
    def _get_course_knowledge_point(
        db, course_id: str, knowledge_point_id: str
    ) -> KnowledgePoint:
        point = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.id == knowledge_point_id,
                KnowledgePoint.course_id == course_id,
            )
            .first()
        )
        if not point:
            raise NotFoundError(
                f"Knowledge point {knowledge_point_id} not found in project course"
            )
        return point

    @staticmethod
    def _to_dto(
        project_id: str,
        user_id: str,
        point: KnowledgePoint,
        state: StudentKnowledgeState | None,
    ) -> KnowledgeStateDto:
        return KnowledgeStateDto(
            id=state.id if state else None,
            user_id=user_id,
            project_id=project_id,
            knowledge_point_id=point.id,
            knowledge_point_name=point.name,
            chapter_id=point.chapter_id,
            mastery_score=state.mastery_score if state else 0,
            confidence=state.confidence if state else 0,
            trend=state.trend if state else "stable",
            status=state.status if state else "not_started",
            attempt_count=state.attempt_count if state else 0,
            correct_count=state.correct_count if state else 0,
            evidence=state.evidence if state else [],
            last_practiced_at=state.last_practiced_at if state else None,
            created_at=state.created_at if state else None,
            updated_at=state.updated_at if state else None,
        )

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
