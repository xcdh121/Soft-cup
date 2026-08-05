"""Service for project-scoped student knowledge states."""

import math

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import (
    AgentArtifact,
    AgentRun,
    Flashcard,
    FlashcardGroup,
    KnowledgePoint,
    KnowledgePointRelation,
    KnowledgeStateEvent,
    LearningEvidenceEvent,
    PracticeRecord,
    Project,
    Quiz,
    QuizQuestion,
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
from edu_core.services.knowledge_point_matching import match_knowledge_point_id


class KnowledgeStateService:
    """Manage the current user's state for course knowledge points."""

    def list_states(self, project_id: str, user_id: str) -> list[KnowledgeStateDto]:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
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
                self._to_dto(project_id, user_id, point, state) for point, state in rows
            ]

    def get_state(
        self, project_id: str, knowledge_point_id: str, user_id: str
    ) -> KnowledgeStateDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
            point = self._get_course_knowledge_point(
                db, project.course_id, knowledge_point_id
            )
            state = (
                db.query(StudentKnowledgeState)
                .filter(
                    StudentKnowledgeState.user_id == user_id,
                    StudentKnowledgeState.knowledge_point_id == knowledge_point_id,
                )
                .first()
            )
            return self._to_dto(project_id, user_id, point, state)

    def get_knowledge_graph(self, project_id: str, user_id: str) -> KnowledgeGraphDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
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
            project = self._get_owned_project_with_course(db, project_id, user_id)
            point = self._get_course_knowledge_point(
                db, project.course_id, knowledge_point_id
            )
            state = (
                db.query(StudentKnowledgeState)
                .filter(
                    StudentKnowledgeState.user_id == user_id,
                    StudentKnowledgeState.knowledge_point_id == knowledge_point_id,
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
            self._mark_learning_paths_stale(db, project_id, user_id)
            db.commit()
            db.refresh(state)
            return self._to_dto(project_id, user_id, point, state)

    def refresh_states(self, project_id: str, user_id: str) -> KnowledgeStateRefreshDto:
        """Apply unprocessed practice records to knowledge states."""
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
            points = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.course_id == project.course_id)
                .all()
            )
            points_by_id = {point.id: point for point in points}
            states_by_point = {
                state.knowledge_point_id: state
                for state in (
                    db.query(StudentKnowledgeState)
                    .filter(
                        StudentKnowledgeState.user_id == user_id,
                        StudentKnowledgeState.knowledge_point_id.in_(
                            list(points_by_id)
                        ),
                    )
                    .all()
                )
            }
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
                    db,
                    record,
                    points_by_id,
                )
                if point is None:
                    unmatched_count += 1
                    continue
                if record.knowledge_point_id is None:
                    record.knowledge_point_id = point.id

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

                state = states_by_point.get(point.id)
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
                    states_by_point[point.id] = state

                score_before = float(state.mastery_score or 0)
                score_after = self._updated_mastery(
                    score_before=score_before,
                    was_correct=record.was_correct,
                    difficulty=point.difficulty_level,
                    occurred_at=record.created_at,
                    previous_at=state.last_practiced_at,
                )
                impact = round(score_after - score_before, 2)

                state.mastery_score = score_after
                state.attempt_count = int(state.attempt_count or 0) + 1
                if record.was_correct:
                    state.correct_count = int(state.correct_count or 0) + 1
                else:
                    state.correct_count = int(state.correct_count or 0)
                state.confidence = min(1.0, round(0.2 + state.attempt_count * 0.1, 2))
                state.trend = (
                    "up" if impact > 2 else "down" if impact < -2 else "stable"
                )
                state.status = "mastered" if score_after >= 80 else "learning"
                state.last_practiced_at = record.created_at

                evidence_item = {
                    "event_type": "practice_record",
                    "source_id": record.id,
                    "item_type": record.item_type,
                    "item_id": record.item_id,
                    "topic": record.topic,
                    "was_correct": record.was_correct,
                    "impact": impact,
                    "difficulty": point.difficulty_level,
                    "occurred_at": record.created_at.isoformat()
                    if record.created_at
                    else None,
                    "model_version": "deterministic-kt-v2",
                    "contributions": {
                        "time_decay": True,
                        "guess_probability": 0.2,
                        "slip_probability": 0.08,
                    },
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
                db.add(
                    LearningEvidenceEvent(
                        id=str(uuid4()),
                        project_id=project_id,
                        user_id=user_id,
                        knowledge_point_id=point.id,
                        event_type="practice_result",
                        source_type="practice_record",
                        source_id=record.id,
                        idempotency_key=f"practice_record:{record.id}",
                        occurred_at=record.created_at,
                        payload={
                            "was_correct": record.was_correct,
                            "item_type": record.item_type,
                            "model_version": "deterministic-kt-v2",
                        },
                    )
                )
                processed_count += 1
                updated[point.id] = (point, state)

            if processed_count:
                self._mark_learning_paths_stale(db, project_id, user_id)
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
    def _mark_learning_paths_stale(db, project_id: str, user_id: str) -> None:
        run_ids = db.query(AgentRun.id).filter(
            AgentRun.project_id == project_id,
            AgentRun.user_id == user_id,
        )
        db.query(AgentArtifact).filter(
            AgentArtifact.run_id.in_(run_ids),
            AgentArtifact.artifact_key == "learning_path",
            AgentArtifact.validation_status == "valid",
        ).update(
            {AgentArtifact.validation_status: "stale"},
            synchronize_session=False,
        )

    @staticmethod
    def _updated_mastery(
        *,
        score_before: float,
        was_correct: bool,
        difficulty: str,
        occurred_at,
        previous_at,
    ) -> float:
        """Deterministic, explainable KT update with decay, guess, and slip."""

        decayed = max(0.0, min(100.0, score_before))
        if occurred_at and previous_at:
            elapsed_days = max(0.0, (occurred_at - previous_at).total_seconds() / 86400)
            decayed *= math.exp(-elapsed_days / 120.0)
        difficulty_weight = {
            "beginner": 0.24,
            "easy": 0.24,
            "intermediate": 0.30,
            "medium": 0.30,
            "advanced": 0.36,
            "hard": 0.36,
        }.get(str(difficulty).lower(), 0.30)
        guess_probability = 0.20
        slip_probability = 0.08
        observed = 1.0 if was_correct else 0.0
        # De-bias the observed result by the configured guess/slip rates.  A
        # fully correct/incorrect observation stays compatible with the v1
        # 100/0 target while the parameters remain explicit and auditable.
        latent_evidence = (observed - guess_probability) / (
            1.0 - guess_probability - slip_probability
        )
        evidence_target = max(0.0, min(1.0, latent_evidence)) * 100.0
        return round(
            max(
                0.0,
                min(100.0, decayed * (1.0 - difficulty_weight) + evidence_target * difficulty_weight),
            ),
            2,
        )

    @staticmethod
    def _resolve_practice_knowledge_point(
        db,
        record: PracticeRecord,
        points_by_id: dict[str, KnowledgePoint],
    ) -> KnowledgePoint | None:
        if record.knowledge_point_id:
            return points_by_id.get(record.knowledge_point_id)

        item_texts: list[str | None] = [record.topic]
        parent_texts: list[str | None] = []
        stored_id = None
        if record.item_type == "quiz":
            row = (
                db.query(QuizQuestion, Quiz)
                .join(Quiz, Quiz.id == QuizQuestion.quiz_id)
                .filter(QuizQuestion.id == record.item_id)
                .first()
            )
            if row:
                question, quiz = row
                stored_id = question.knowledge_point_id
                item_texts.extend(
                    [
                        question.question_text,
                        question.explanation,
                    ]
                )
                parent_texts.extend([quiz.name, quiz.description])
        elif record.item_type == "flashcard":
            row = (
                db.query(Flashcard, FlashcardGroup)
                .join(FlashcardGroup, FlashcardGroup.id == Flashcard.group_id)
                .filter(Flashcard.id == record.item_id)
                .first()
            )
            if row:
                flashcard, group = row
                stored_id = flashcard.knowledge_point_id
                item_texts.extend([flashcard.question, flashcard.answer])
                parent_texts.extend([group.name, group.description])

        if stored_id:
            return points_by_id.get(stored_id)
        matched_id = match_knowledge_point_id(
            list(points_by_id.values()),
            item_texts,
        )
        if not matched_id:
            matched_id = match_knowledge_point_id(
                list(points_by_id.values()),
                parent_texts,
            )
        return points_by_id.get(matched_id) if matched_id else None

    @staticmethod
    def _get_owned_project_with_course(db, project_id: str, user_id: str) -> Project:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == user_id)
            .first()
        )
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        if not project.course_id:
            raise ValueError(f"Project {project_id} is not associated with a course")
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
