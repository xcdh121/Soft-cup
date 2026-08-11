"""Service for project-scoped student knowledge states."""

import math

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from math import log
from uuid import uuid4

from edu_db.models import (
    AgentArtifact,
    AgentRun,
    Flashcard,
    FlashcardGroup,
    Explanation,
    ExplanationEvidence,
    InterventionOutcome,
    ItemKnowledgePointMapping,
    KnowledgePointKTParameter,
    KnowledgePoint,
    KnowledgePointRelation,
    KnowledgeStateEvent,
    LearningEvidenceEvent,
    KTParameterSet,
    PracticeRecord,
    Project,
    Quiz,
    QuizQuestion,
    Recommendation,
    RecommendationInteraction,
    StudentKnowledgeState,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.knowledge_states import (
    KnowledgeGraphDto,
    KnowledgeGraphEdgeDto,
    KnowledgeGraphNodeDto,
    KnowledgeStateDto,
    KnowledgeStateEventDto,
    KnowledgeStateRefreshDto,
)
from edu_core.schemas.closed_loop import (
    KTMetricDto,
    KnowledgeStateReplayDto,
)
from edu_core.services.bkt import (
    BKTParameters,
    apply_adjustments,
    classify_status,
    classify_trend,
    evidence_confidence,
    legacy_ewma,
    payload_hash,
    update_bkt,
)
from edu_core.services.knowledge_point_matching import match_knowledge_point_id


def _as_utc(value: datetime) -> datetime:
    """Normalize DB datetimes across SQLite and PostgreSQL."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _prediction_metrics(
    pairs: list[tuple[float, float]],
) -> tuple[float | None, float | None, float | None]:
    if not pairs:
        return None, None, None
    normalized = [
        (max(1e-12, min(1 - 1e-12, probability)), score)
        for probability, score in pairs
    ]
    brier = sum(
        (probability - score) ** 2 for probability, score in normalized
    ) / len(normalized)
    log_loss_value = -sum(
        score * log(probability) + (1 - score) * log(1 - probability)
        for probability, score in normalized
    ) / len(normalized)
    calibration_error = 0.0
    for bucket in range(10):
        lower, upper = bucket / 10, (bucket + 1) / 10
        bucket_pairs = [
            pair
            for pair in normalized
            if lower <= pair[0] < upper or (bucket == 9 and pair[0] == 1)
        ]
        if not bucket_pairs:
            continue
        predicted = sum(item[0] for item in bucket_pairs) / len(bucket_pairs)
        observed = sum(item[1] for item in bucket_pairs) / len(bucket_pairs)
        calibration_error += len(bucket_pairs) / len(normalized) * abs(
            predicted - observed
        )
    return brier, log_loss_value, calibration_error


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
                        mastery_probability=(
                            state.mastery_probability if state else 0
                        ),
                        p_correct_next=state.p_correct_next if state else 0,
                        confidence=state.confidence if state else 0,
                        evidence_confidence=(
                            state.evidence_confidence if state else 0
                        ),
                        trend=state.trend if state else "stable",
                        status=state.status if state else "not_started",
                        algorithm=state.algorithm if state else "legacy_ewma",
                        model_version=(
                            state.model_version if state else "legacy-rule-v1"
                        ),
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
            state.mastery_probability = max(0.0, min(1.0, mastery_score / 100.0))
            state.confidence = confidence
            state.evidence_confidence = confidence
            state.trend = trend
            state.status = status
            state.attempt_count = attempt_count
            state.correct_count = correct_count
            state.evidence = evidence
            state.last_practiced_at = last_practiced_at
            state.algorithm = "manual"
            state.model_version = "manual-v1"
            state.effective_event_count = float(attempt_count)
            state.state_version = int(state.state_version or 0) + 1
            state.lock_version = int(state.lock_version or 0) + 1
            event_id = str(uuid4())
            db.add(
                KnowledgeStateEvent(
                    id=event_id,
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
                    algorithm="manual",
                    model_version="manual-v1",
                    prior_mastery=score_before / 100.0,
                    posterior_after_learning=mastery_score / 100.0,
                    explanation_summary="知识状态由人工接口更新。",
                    reason_codes=["manual_update"],
                    occurred_at=last_practiced_at or datetime.now(timezone.utc),
                    processed_at=datetime.now(timezone.utc),
                    state_version=state.state_version,
                )
            )
            self._mark_learning_paths_stale(db, project_id, user_id)
            state.last_event_id = event_id
            db.commit()
            db.refresh(state)
            return self._to_dto(project_id, user_id, point, state)

    def refresh_states(self, project_id: str, user_id: str) -> KnowledgeStateRefreshDto:
        """Apply unprocessed practice records with expert BKT, idempotently."""
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
                    .with_for_update()
                    .all()
                )
            }
            records = (
                db.query(PracticeRecord)
                .filter(
                    PracticeRecord.project_id == project_id,
                    PracticeRecord.user_id == user_id,
                )
                .order_by(PracticeRecord.occurred_at, PracticeRecord.id)
                .all()
            )

            processed_count = 0
            already_processed_count = 0
            unmatched_count = 0
            updated: dict[str, tuple[KnowledgePoint, StudentKnowledgeState]] = {}

            for record in records:
                # Rows created before the normalized score column used only was_correct.
                if record.was_correct and float(record.score or 0) == 0:
                    record.score = 1.0
                item_mappings = (
                    db.query(ItemKnowledgePointMapping)
                    .filter(
                        ItemKnowledgePointMapping.item_type == record.item_type,
                        ItemKnowledgePointMapping.item_id == record.item_id,
                    )
                    .all()
                )
                mappings = [
                    item
                    for item in item_mappings
                    if item.review_status == "approved"
                ]
                resolved_points: list[tuple[KnowledgePoint, float, float]] = []
                if item_mappings:
                    total_weight = sum(max(0.0, item.weight) for item in mappings)
                    if abs(total_weight - 1.0) <= 0.000001:
                        resolved_points = [
                            (
                                points_by_id[item.knowledge_point_id],
                                item.weight,
                                item.mapping_confidence,
                            )
                            for item in mappings
                            if item.knowledge_point_id in points_by_id
                        ]
                    else:
                        record.mapping_status = "pending"
                        record.mapping_method = "manual_review"
                        unmatched_count += 1
                        continue
                    if not resolved_points:
                        record.mapping_status = "pending"
                        record.mapping_method = "manual_review"
                        unmatched_count += 1
                        continue
                if not resolved_points:
                    point = self._resolve_practice_knowledge_point(
                        db, record, points_by_id
                    )
                    if point:
                        resolved_points = [
                            (
                                point,
                                1.0,
                                record.mapping_confidence
                                if record.mapping_confidence is not None
                                else 0.7,
                            )
                        ]

                if not resolved_points:
                    record.mapping_status = "pending"
                    unmatched_count += 1
                    continue

                record.knowledge_point_id = resolved_points[0][0].id
                record.mapping_status = "resolved"
                if not record.mapping_method:
                    record.mapping_method = (
                        "manual_review" if mappings else "rule_match"
                    )
                for point, mapping_weight, mapping_confidence in resolved_points:
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
                            evidence=[],
                        )
                        db.add(state)
                        db.flush()
                        states_by_point[point.id] = state
                    event = self._apply_bkt_record(
                        db=db,
                        project=project,
                        point=point,
                        state=state,
                        record=record,
                        mapping_weight=mapping_weight,
                        mapping_confidence=mapping_confidence,
                    )
                    db.add(
                        LearningEvidenceEvent(
                            id=str(uuid4()),
                            project_id=project_id,
                            user_id=user_id,
                            knowledge_point_id=point.id,
                            event_type=event.event_type,
                            source_type="practice_record",
                            source_id=record.id,
                            idempotency_key=(
                                f"practice_record:{record.id}:{point.id}"
                            ),
                            occurred_at=(
                                record.occurred_at
                                or record.created_at
                                or datetime.now(timezone.utc)
                            ),
                            payload={
                                "observed_score": record.score,
                                "item_type": record.item_type,
                                "model_version": event.model_version,
                                "knowledge_state_event_id": event.id,
                            },
                        )
                    )
                    if record.is_verification and record.recommendation_id:
                        self._create_intervention_outcome(
                            db, project, state, record, event
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

    def _apply_bkt_record(
        self,
        *,
        db,
        project: Project,
        point: KnowledgePoint,
        state: StudentKnowledgeState,
        record: PracticeRecord,
        mapping_weight: float,
        mapping_confidence: float,
    ) -> KnowledgeStateEvent:
        parameter_set, parameters = self._resolve_parameters(
            db, project.course_id, point.id
        )
        effective = apply_adjustments(
            parameters,
            difficulty=record.difficulty_snapshot,
            answer_mode=record.answer_mode or record.item_type,
            difficulty_adjustments=parameter_set.difficulty_adjustments or {},
            answer_mode_adjustments=parameter_set.answer_mode_adjustments or {},
            is_verification=bool(record.is_verification),
        )
        effective = replace(
            effective, event_weight=effective.event_weight * mapping_weight
        ).normalized()
        previous_event = (
            db.query(KnowledgeStateEvent)
            .filter(
                KnowledgeStateEvent.user_id == state.user_id,
                KnowledgeStateEvent.knowledge_point_id == point.id,
            )
            .order_by(
                KnowledgeStateEvent.occurred_at.desc(),
                KnowledgeStateEvent.created_at.desc(),
            )
            .first()
        )
        prior = (
            float(state.mastery_probability)
            if state.algorithm == "expert_bkt" and state.state_version > 0
            else (
                float(state.mastery_score or 0) / 100.0
                if state.attempt_count
                else effective.initial_mastery
            )
        )
        occurred_at = record.occurred_at or record.created_at or datetime.now(
            timezone.utc
        )
        result = update_bkt(
            prior_mastery=prior,
            observed_score=record.score,
            parameters=effective,
            occurred_at=occurred_at,
            last_occurred_at=previous_event.occurred_at if previous_event else None,
        )
        score_before = round(result.prior_mastery * 100, 2)
        score_after = round(result.mastery_probability * 100, 2)
        impact = round(score_after - score_before, 2)
        legacy_before = 0.0
        if previous_event:
            legacy_before = float(
                (previous_event.shadow_results or {}).get(
                    "legacy_ewma",
                    previous_event.posterior_after_learning
                    if previous_event.posterior_after_learning is not None
                    else previous_event.score_after / 100.0,
                )
            )
        legacy_after = legacy_ewma(legacy_before, record.score)

        state.attempt_count = int(state.attempt_count or 0) + 1
        state.correct_count = int(state.correct_count or 0) + int(
            record.score >= 0.999
        )
        state.effective_event_count = float(state.effective_event_count or 0) + (
            result.event_weight
        )
        existing_confidences = [
            float(item.get("mapping_confidence", 0.7))
            for item in (state.evidence or [])
            if item.get("mapping_confidence") is not None
        ]
        average_confidence = sum(
            [*existing_confidences, mapping_confidence]
        ) / max(1, len(existing_confidences) + 1)
        state.evidence_confidence = evidence_confidence(
            state.effective_event_count, average_confidence
        )
        state.confidence = state.evidence_confidence
        state.mastery_probability = result.mastery_probability
        state.mastery_score = score_after
        state.p_correct_next = result.p_correct_next
        state.algorithm = "expert_bkt"
        state.model_version = parameter_set.version
        state.parameter_set_id = parameter_set.id
        state.threshold_version = "threshold-v1"
        state.state_version = int(state.state_version or 0) + 1
        state.lock_version = int(state.lock_version or 0) + 1
        state.last_practiced_at = occurred_at
        if record.is_verification:
            state.last_verified_at = occurred_at

        recent_probabilities = [
            value[0]
            for value in (
                db.query(KnowledgeStateEvent.posterior_after_learning)
                .filter(
                    KnowledgeStateEvent.user_id == state.user_id,
                    KnowledgeStateEvent.knowledge_point_id == point.id,
                    KnowledgeStateEvent.posterior_after_learning.isnot(None),
                )
                .order_by(KnowledgeStateEvent.occurred_at.desc())
                .limit(2)
                .all()
            )
        ][::-1]
        state.trend = classify_trend(
            [*recent_probabilities, result.mastery_probability][-3:]
        )
        days_since_verification = None
        if state.last_verified_at:
            days_since_verification = max(
                0.0,
                (datetime.now(timezone.utc) - _as_utc(state.last_verified_at)).total_seconds()
                / 86400.0,
            )
        state.status, state.status_reason_codes = classify_status(
            result.mastery_probability,
            state.evidence_confidence,
            event_count=state.effective_event_count,
            days_since_verification=days_since_verification,
        )

        explanation_summary = self._build_bkt_summary(result)
        evidence_item = {
            "event_type": "practice_record",
            "source_id": record.id,
            "item_type": record.item_type,
            "item_id": record.item_id,
            "topic": record.topic,
            "observed_score": record.score,
            "mapping_method": record.mapping_method,
            "mapping_confidence": mapping_confidence,
            "impact": impact,
        }
        state.evidence = [*(state.evidence or []), evidence_item][-100:]
        event = KnowledgeStateEvent(
            id=str(uuid4()),
            knowledge_state_id=state.id,
            project_id=project.id,
            user_id=state.user_id,
            knowledge_point_id=point.id,
            event_type="verification_result"
            if record.is_verification
            else "practice_result",
            source_type="practice_record",
            source_id=record.id,
            score_before=score_before,
            score_after=score_after,
            impact=impact,
            was_correct=record.was_correct,
            evidence=evidence_item,
            algorithm="expert_bkt",
            model_version=parameter_set.version,
            parameter_set_id=parameter_set.id,
            prior_mastery=result.prior_mastery,
            prior_after_forgetting=result.prior_after_forgetting,
            posterior_after_observation=result.posterior_after_observation,
            posterior_after_learning=result.mastery_probability,
            p_correct_before=result.p_correct_before,
            p_correct_next=result.p_correct_next,
            observed_score=result.observed_score,
            event_weight=result.event_weight,
            effective_parameters=result.effective_parameters,
            reason_codes=result.reason_codes,
            explanation_summary=explanation_summary,
            source_payload_hash=payload_hash(evidence_item),
            occurred_at=occurred_at,
            processed_at=datetime.now(timezone.utc),
            state_version=state.state_version,
            shadow_results={
                "legacy_p_correct_before": round(legacy_before, 6),
                "legacy_ewma": round(legacy_after, 6),
                "expert_bkt": round(result.mastery_probability, 6),
            },
        )
        db.add(event)
        db.flush()
        state.last_event_id = event.id
        explanation = Explanation(
            id=str(uuid4()),
            project_id=project.id,
            user_id=state.user_id,
            object_type="kt_event",
            object_id=event.id,
            summary=explanation_summary,
            reason_codes=result.reason_codes,
            model_version=parameter_set.version,
            threshold_version=state.threshold_version,
            confidence=state.evidence_confidence,
        )
        db.add(explanation)
        db.add(
            ExplanationEvidence(
                id=str(uuid4()),
                explanation_id=explanation.id,
                source_type="practice_record",
                source_id=record.id,
                knowledge_point_id=point.id,
                contribution_direction=(
                    "positive" if impact >= 0 else "negative"
                ),
                contribution_score=abs(impact) / 100.0,
                snapshot=evidence_item,
                display_order=0,
            )
        )
        return event

    @staticmethod
    def _build_bkt_summary(result) -> str:
        direction = "提升" if result.mastery_probability >= result.prior_mastery else "下降"
        evidence_note = ""
        if result.event_weight < 1:
            evidence_note = f"，本次证据权重为{result.event_weight:.2f}"
        return (
            f"本次作答使掌握概率从{result.prior_mastery:.0%}{direction}至"
            f"{result.mastery_probability:.0%}，下一题预测正确率为"
            f"{result.p_correct_next:.0%}{evidence_note}。"
        )

    @staticmethod
    def _resolve_parameters(
        db, course_id: str, knowledge_point_id: str
    ) -> tuple[KTParameterSet, BKTParameters]:
        override = (
            db.query(KnowledgePointKTParameter)
            .join(
                KTParameterSet,
                KTParameterSet.id == KnowledgePointKTParameter.parameter_set_id,
            )
            .filter(
                KnowledgePointKTParameter.knowledge_point_id == knowledge_point_id,
                KTParameterSet.status == "active",
            )
            .order_by(KTParameterSet.effective_from.desc())
            .first()
        )
        parameter_set = override and db.get(KTParameterSet, override.parameter_set_id)
        if parameter_set is None:
            parameter_set = (
                db.query(KTParameterSet)
                .filter(
                    KTParameterSet.status == "active",
                    KTParameterSet.scope_type == "course",
                    KTParameterSet.scope_id == course_id,
                )
                .order_by(KTParameterSet.effective_from.desc())
                .first()
            )
        if parameter_set is None:
            parameter_set = (
                db.query(KTParameterSet)
                .filter(
                    KTParameterSet.status == "active",
                    KTParameterSet.scope_type == "global",
                )
                .order_by(KTParameterSet.effective_from.desc())
                .first()
            )
        if parameter_set is None:
            parameter_set = KTParameterSet(
                id=str(uuid4()),
                name="Expert BKT default",
                version="bkt-v1.0",
                scope_type="global",
                status="active",
                expert_reason="Initial transparent expert defaults from the decision specification.",
                effective_from=datetime.now(timezone.utc),
            )
            db.add(parameter_set)
            db.flush()

        parameters = BKTParameters(
            initial_mastery=parameter_set.initial_mastery,
            learn_probability=parameter_set.learn_probability,
            slip_probability=parameter_set.slip_probability,
            guess_probability=parameter_set.guess_probability,
            forget_probability_daily=parameter_set.forget_probability_daily,
        )
        if override:
            parameters = replace(
                parameters,
                initial_mastery=(
                    override.initial_mastery_override
                    if override.initial_mastery_override is not None
                    else parameters.initial_mastery
                ),
                learn_probability=(
                    override.learn_override
                    if override.learn_override is not None
                    else parameters.learn_probability
                ),
                slip_probability=(
                    override.slip_override
                    if override.slip_override is not None
                    else parameters.slip_probability
                ),
                guess_probability=(
                    override.guess_override
                    if override.guess_override is not None
                    else parameters.guess_probability
                ),
                forget_probability_daily=(
                    override.forget_override
                    if override.forget_override is not None
                    else parameters.forget_probability_daily
                ),
            )
        return parameter_set, parameters.normalized()

    def _create_intervention_outcome(
        self,
        db,
        project: Project,
        state: StudentKnowledgeState,
        record: PracticeRecord,
        verification_event: KnowledgeStateEvent,
    ) -> None:
        if (
            db.query(InterventionOutcome)
            .filter(
                InterventionOutcome.verification_event_id == verification_event.id
            )
            .first()
        ):
            return
        recommendation = (
            db.query(Recommendation)
            .filter(
                Recommendation.id == record.recommendation_id,
                Recommendation.project_id == project.id,
                Recommendation.user_id == state.user_id,
            )
            .first()
        )
        if not recommendation:
            return
        baseline = None
        if recommendation.source_state_event_id:
            baseline = db.get(
                KnowledgeStateEvent, recommendation.source_state_event_id
            )
        if baseline is None:
            baseline = (
                db.query(KnowledgeStateEvent)
                .filter(
                    KnowledgeStateEvent.user_id == state.user_id,
                    KnowledgeStateEvent.knowledge_point_id
                    == state.knowledge_point_id,
                    KnowledgeStateEvent.id != verification_event.id,
                    KnowledgeStateEvent.occurred_at
                    <= verification_event.occurred_at,
                )
                .order_by(KnowledgeStateEvent.occurred_at.desc())
                .first()
            )
        if baseline is None:
            return
        completion = (
            db.query(RecommendationInteraction)
            .filter(
                RecommendationInteraction.recommendation_id == recommendation.id,
                RecommendationInteraction.event_type == "completed",
            )
            .order_by(RecommendationInteraction.occurred_at.desc())
            .first()
        )
        confidence = 0.4
        window_hours = 72
        if completion:
            elapsed_hours = max(
                0.0,
                (
                    _as_utc(verification_event.occurred_at)
                    - _as_utc(completion.occurred_at)
                ).total_seconds()
                / 3600.0,
            )
            if elapsed_hours <= 24:
                confidence, window_hours = 0.8, 24
            elif elapsed_hours <= 72:
                confidence, window_hours = 0.6, 72
            else:
                confidence, window_hours = 0.4, round(elapsed_hours)
        before = (
            baseline.posterior_after_learning
            if baseline.posterior_after_learning is not None
            else baseline.score_after / 100.0
        )
        after = verification_event.posterior_after_learning or (
            verification_event.score_after / 100.0
        )
        target = float((recommendation.expected_outcome or {}).get("target_mastery", 0.8))
        gain = after - before
        outcome = InterventionOutcome(
            id=str(uuid4()),
            project_id=project.id,
            user_id=state.user_id,
            recommendation_id=recommendation.id,
            knowledge_point_id=state.knowledge_point_id,
            baseline_state_event_id=baseline.id,
            verification_event_id=verification_event.id,
            mastery_before=before,
            mastery_after=after,
            mastery_gain=gain,
            verification_score=record.score,
            target_mastery=target,
            target_achieved=(gain >= 0.10 or after >= target),
            attribution_confidence=confidence,
            evaluation_window_hours=window_hours,
        )
        db.add(outcome)
        db.flush()
        explanation = Explanation(
            id=str(uuid4()),
            project_id=project.id,
            user_id=state.user_id,
            object_type="intervention_outcome",
            object_id=outcome.id,
            summary=(
                f"验证后掌握度从{before:.0%}变为{after:.0%}，"
                f"增益为{gain:.0%}。"
            ),
            reason_codes=[
                "target_achieved" if outcome.target_achieved else "target_not_achieved",
                "verified_after_recommendation",
            ],
            model_version=verification_event.model_version,
            confidence=confidence,
        )
        db.add(explanation)
        db.flush()
        outcome.explanation_id = explanation.id

    def list_events(
        self,
        project_id: str,
        knowledge_point_id: str,
        user_id: str,
        *,
        limit: int = 50,
        before: datetime | None = None,
        event_type: str | None = None,
        model_version: str | None = None,
    ) -> list[KnowledgeStateEventDto]:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
            self._get_course_knowledge_point(
                db, project.course_id, knowledge_point_id
            )
            query = db.query(KnowledgeStateEvent).filter(
                KnowledgeStateEvent.project_id == project_id,
                KnowledgeStateEvent.user_id == user_id,
                KnowledgeStateEvent.knowledge_point_id == knowledge_point_id,
            )
            if before:
                query = query.filter(KnowledgeStateEvent.occurred_at < before)
            if event_type:
                query = query.filter(KnowledgeStateEvent.event_type == event_type)
            if model_version:
                query = query.filter(
                    KnowledgeStateEvent.model_version == model_version
                )
            rows = (
                query.order_by(
                    KnowledgeStateEvent.occurred_at.desc(),
                    KnowledgeStateEvent.created_at.desc(),
                )
                .limit(max(1, min(limit, 200)))
                .all()
            )
            return [KnowledgeStateEventDto.model_validate(row) for row in rows]

    def replay_states(
        self,
        project_id: str,
        user_id: str,
        *,
        knowledge_point_id: str | None = None,
        dry_run: bool = False,
    ) -> KnowledgeStateReplayDto:
        """Deterministically recompute BKT events without deleting legacy evidence."""

        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
            points_query = db.query(KnowledgePoint).filter(
                KnowledgePoint.course_id == project.course_id
            )
            if knowledge_point_id:
                points_query = points_query.filter(
                    KnowledgePoint.id == knowledge_point_id
                )
            points = points_query.all()
            differences: list[dict] = []
            processed = 0
            rebuilt = 0
            for point in points:
                records = (
                    db.query(PracticeRecord)
                    .filter(
                        PracticeRecord.project_id == project_id,
                        PracticeRecord.user_id == user_id,
                        PracticeRecord.knowledge_point_id == point.id,
                        PracticeRecord.mapping_status == "resolved",
                    )
                    .order_by(PracticeRecord.occurred_at, PracticeRecord.id)
                    .all()
                )
                if not records:
                    continue
                parameter_set, base_parameters = self._resolve_parameters(
                    db, project.course_id, point.id
                )
                prior = base_parameters.initial_mastery
                legacy_prior = 0.0
                last_occurred_at = None
                event_count = 0.0
                mapping_confidences: list[float] = []
                computed: list[tuple[PracticeRecord, object, float, float]] = []
                for record in records:
                    effective = apply_adjustments(
                        base_parameters,
                        difficulty=record.difficulty_snapshot,
                        answer_mode=record.answer_mode or record.item_type,
                        difficulty_adjustments=parameter_set.difficulty_adjustments,
                        answer_mode_adjustments=parameter_set.answer_mode_adjustments,
                        is_verification=record.is_verification,
                    )
                    result = update_bkt(
                        prior_mastery=prior,
                        observed_score=record.score,
                        parameters=effective,
                        occurred_at=record.occurred_at,
                        last_occurred_at=last_occurred_at,
                    )
                    legacy_after = legacy_ewma(legacy_prior, record.score)
                    computed.append((record, result, legacy_prior, legacy_after))
                    prior = result.mastery_probability
                    legacy_prior = legacy_after
                    last_occurred_at = record.occurred_at
                    event_count += result.event_weight
                    mapping_confidences.append(record.mapping_confidence or 0.7)
                    processed += 1

                state = (
                    db.query(StudentKnowledgeState)
                    .filter(
                        StudentKnowledgeState.user_id == user_id,
                        StudentKnowledgeState.knowledge_point_id == point.id,
                    )
                    .first()
                )
                old_probability = (
                    state.mastery_probability
                    if state
                    else 0.0
                )
                differences.append(
                    {
                        "knowledge_point_id": point.id,
                        "before": round(old_probability, 6),
                        "after": round(prior, 6),
                        "delta": round(prior - old_probability, 6),
                        "event_count": len(computed),
                    }
                )
                if dry_run:
                    continue
                if state is None:
                    state = StudentKnowledgeState(
                        id=str(uuid4()),
                        user_id=user_id,
                        knowledge_point_id=point.id,
                        evidence=[],
                    )
                    db.add(state)
                    db.flush()
                for index, (record, result, legacy_before, legacy_after) in enumerate(
                    computed, start=1
                ):
                    event = (
                        db.query(KnowledgeStateEvent)
                        .filter(
                            KnowledgeStateEvent.user_id == user_id,
                            KnowledgeStateEvent.knowledge_point_id == point.id,
                            KnowledgeStateEvent.source_type == "practice_record",
                            KnowledgeStateEvent.source_id == record.id,
                        )
                        .first()
                    )
                    if event is None:
                        event = KnowledgeStateEvent(
                            id=str(uuid4()),
                            knowledge_state_id=state.id,
                            project_id=project_id,
                            user_id=user_id,
                            knowledge_point_id=point.id,
                            event_type="verification_result"
                            if record.is_verification
                            else "practice_result",
                            source_type="practice_record",
                            source_id=record.id,
                            score_before=0,
                            score_after=0,
                            impact=0,
                            evidence={},
                        )
                        db.add(event)
                    event.algorithm = "expert_bkt"
                    event.model_version = parameter_set.version
                    event.parameter_set_id = parameter_set.id
                    event.prior_mastery = result.prior_mastery
                    event.prior_after_forgetting = result.prior_after_forgetting
                    event.posterior_after_observation = (
                        result.posterior_after_observation
                    )
                    event.posterior_after_learning = result.mastery_probability
                    event.p_correct_before = result.p_correct_before
                    event.p_correct_next = result.p_correct_next
                    event.observed_score = result.observed_score
                    event.event_weight = result.event_weight
                    event.effective_parameters = result.effective_parameters
                    event.reason_codes = result.reason_codes
                    event.explanation_summary = self._build_bkt_summary(result)
                    event.occurred_at = record.occurred_at
                    event.processed_at = datetime.now(timezone.utc)
                    event.state_version = index
                    event.score_before = round(result.prior_mastery * 100, 2)
                    event.score_after = round(result.mastery_probability * 100, 2)
                    event.impact = event.score_after - event.score_before
                    event.was_correct = record.was_correct
                    event.shadow_results = {
                        "legacy_p_correct_before": legacy_before,
                        "legacy_ewma": legacy_after,
                        "expert_bkt": result.mastery_probability,
                    }
                    state.last_event_id = event.id
                state.mastery_probability = prior
                state.mastery_score = round(prior * 100, 2)
                state.p_correct_next = computed[-1][1].p_correct_next
                state.algorithm = "expert_bkt"
                state.model_version = parameter_set.version
                state.parameter_set_id = parameter_set.id
                state.effective_event_count = event_count
                state.evidence_confidence = evidence_confidence(
                    event_count,
                    sum(mapping_confidences) / len(mapping_confidences),
                )
                state.confidence = state.evidence_confidence
                state.attempt_count = len(records)
                state.correct_count = sum(item.score >= 0.999 for item in records)
                state.state_version = len(records)
                state.lock_version = int(state.lock_version or 0) + 1
                state.last_practiced_at = records[-1].occurred_at
                verified = [item for item in records if item.is_verification]
                state.last_verified_at = verified[-1].occurred_at if verified else None
                state.status, state.status_reason_codes = classify_status(
                    prior,
                    state.evidence_confidence,
                    event_count=event_count,
                    days_since_verification=0 if verified else None,
                )
                state.trend = classify_trend(
                    [item[1].mastery_probability for item in computed[-3:]]
                )
                rebuilt += 1
            if dry_run:
                db.rollback()
            else:
                db.commit()
            return KnowledgeStateReplayDto(
                processed_records=processed,
                rebuilt_states=rebuilt,
                dry_run=dry_run,
                differences=differences,
            )

    def get_metrics(self, project_id: str, user_id: str) -> KTMetricDto:
        with self._get_db_session() as db:
            project = self._get_owned_project_with_course(db, project_id, user_id)
            events = (
                db.query(KnowledgeStateEvent)
                .filter(
                    KnowledgeStateEvent.project_id == project_id,
                    KnowledgeStateEvent.user_id == user_id,
                    KnowledgeStateEvent.algorithm == "expert_bkt",
                    KnowledgeStateEvent.p_correct_before.isnot(None),
                    KnowledgeStateEvent.observed_score.isnot(None),
                )
                .all()
            )
            records = (
                db.query(PracticeRecord)
                .filter(
                    PracticeRecord.project_id == project_id,
                    PracticeRecord.user_id == user_id,
                )
                .all()
            )
            states = (
                db.query(StudentKnowledgeState)
                .join(
                    KnowledgePoint,
                    KnowledgePoint.id == StudentKnowledgeState.knowledge_point_id,
                )
                .filter(
                    StudentKnowledgeState.user_id == user_id,
                    KnowledgePoint.course_id == project.course_id,
                )
                .all()
            )
            brier, log_loss_value, ece = _prediction_metrics(
                [
                    (item.p_correct_before, item.observed_score)
                    for item in events
                ]
            )
            legacy_brier, legacy_log_loss, legacy_ece = _prediction_metrics(
                [
                    (
                        float(item.shadow_results["legacy_p_correct_before"]),
                        item.observed_score,
                    )
                    for item in events
                    if (item.shadow_results or {}).get(
                        "legacy_p_correct_before"
                    )
                    is not None
                ]
            )
            mapped = sum(item.mapping_status == "resolved" for item in records)
            low_evidence = sum(item.evidence_confidence < 0.40 for item in states)
            return KTMetricDto(
                event_count=len(events),
                brier_score=round(brier, 6) if brier is not None else None,
                log_loss=(
                    round(log_loss_value, 6)
                    if log_loss_value is not None
                    else None
                ),
                expected_calibration_error=round(ece, 6) if ece is not None else None,
                legacy_brier_score=(
                    round(legacy_brier, 6) if legacy_brier is not None else None
                ),
                legacy_log_loss=(
                    round(legacy_log_loss, 6)
                    if legacy_log_loss is not None
                    else None
                ),
                legacy_expected_calibration_error=(
                    round(legacy_ece, 6) if legacy_ece is not None else None
                ),
                brier_score_improvement=(
                    round(legacy_brier - brier, 6)
                    if legacy_brier is not None and brier is not None
                    else None
                ),
                log_loss_improvement=(
                    round(legacy_log_loss - log_loss_value, 6)
                    if legacy_log_loss is not None
                    and log_loss_value is not None
                    else None
                ),
                mapping_coverage=round(mapped / len(records), 6) if records else 0.0,
                low_evidence_ratio=round(low_evidence / len(states), 6) if states else 0.0,
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
            mastery_probability=state.mastery_probability if state else 0,
            p_correct_next=state.p_correct_next if state else 0,
            confidence=state.confidence if state else 0,
            evidence_confidence=state.evidence_confidence if state else 0,
            trend=state.trend if state else "stable",
            status=state.status if state else "not_started",
            algorithm=state.algorithm if state else "legacy_ewma",
            model_version=state.model_version if state else "legacy-rule-v1",
            parameter_set_id=state.parameter_set_id if state else None,
            threshold_version=state.threshold_version if state else "threshold-v1",
            effective_event_count=state.effective_event_count if state else 0,
            last_event_id=state.last_event_id if state else None,
            last_verified_at=state.last_verified_at if state else None,
            state_version=state.state_version if state else 0,
            status_reason_codes=state.status_reason_codes if state else [],
            latest_explanation=(
                {
                    "summary": state.events[-1].explanation_summary,
                    "reason_codes": state.events[-1].reason_codes or [],
                    "event_id": state.events[-1].id,
                }
                if state and state.events and state.events[-1].explanation_summary
                else None
            ),
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
