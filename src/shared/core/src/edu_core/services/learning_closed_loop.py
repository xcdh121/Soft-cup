"""Recommendation feedback, intervention outcomes and path-version services."""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from edu_db.models import (
    Explanation,
    InterventionOutcome,
    KTParameterSet,
    KnowledgePoint,
    KnowledgePointKTParameter,
    ItemKnowledgePointMapping,
    KnowledgeStateEvent,
    LearningPath,
    LearningPathStep,
    Project,
    Quiz,
    Recommendation,
    RecommendationInteraction,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.closed_loop import (
    InterventionOutcomeDto,
    ItemKnowledgePointMappingCreate,
    KTParameterSetCreate,
    KTParameterSetDto,
    KnowledgePointKTOverrideCreate,
    RecommendationFeedbackCreate,
    RecommendationInteractionDto,
)

if TYPE_CHECKING:
    from edu_queue.service import ArqQueueService, QueueService


logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class LearningClosedLoopService:
    def __init__(
        self, queue_service: "QueueService | ArqQueueService | None" = None
    ) -> None:
        self.queue_service = queue_service

    def record_recommendation_feedback(
        self,
        project_id: str,
        recommendation_id: str,
        user_id: str,
        request: RecommendationFeedbackCreate,
    ) -> RecommendationInteractionDto:
        with self._get_db_session() as db:
            recommendation = (
                db.query(Recommendation)
                .filter(
                    Recommendation.id == recommendation_id,
                    Recommendation.project_id == project_id,
                    Recommendation.user_id == user_id,
                )
                .first()
            )
            if not recommendation:
                raise NotFoundError(
                    f"Recommendation {recommendation_id} not found"
                )
            interaction = RecommendationInteraction(
                id=str(uuid4()),
                recommendation_id=recommendation_id,
                user_id=user_id,
                project_id=project_id,
                event_type=request.event_type,
                resource_id=request.resource_id,
                learning_session_id=request.learning_session_id,
                progress=request.progress,
                duration_ms=request.duration_ms,
                rating=request.rating,
                reason_code=request.reason_code,
                occurred_at=request.occurred_at or datetime.now(timezone.utc),
                metadata_json=dict(request.metadata),
            )
            verification_task = None
            should_generate_verification = False
            if request.event_type == "completed":
                recommendation.status = "completed"
                verification_task, should_generate_verification = (
                    self._ensure_verification_task(db, recommendation)
                )
                if verification_task:
                    interaction.metadata_json["verification_task_id"] = (
                        verification_task.id
                    )
                    interaction.metadata_json["verification_required"] = True
            elif request.event_type in {"dismissed", "skipped"}:
                recommendation.status = request.event_type
            # Retain the old JSON field as a compatibility summary.
            recommendation.feedback = {
                "event": request.event_type,
                "progress": request.progress,
                "rating": request.rating,
                "occurred_at": interaction.occurred_at.isoformat(),
            }
            db.add(interaction)
            db.commit()
            db.refresh(interaction)
            if should_generate_verification and verification_task:
                self._queue_verification_quiz(
                    db=db,
                    task=verification_task,
                    recommendation=recommendation,
                )
            return self._interaction_dto(interaction)

    @staticmethod
    def _ensure_verification_task(
        db, recommendation: Recommendation
    ) -> tuple[LearningPathStep | None, bool]:
        """Create one dedicated verification quiz after actual resource completion."""
        paths = (
            db.query(LearningPath)
            .filter(
                LearningPath.project_id == recommendation.project_id,
                LearningPath.user_id == recommendation.user_id,
                LearningPath.status == "active",
            )
            .order_by(LearningPath.version.desc(), LearningPath.created_at.desc())
            .with_for_update()
            .all()
        )
        path = next(
            (
                item
                for item in paths
                if recommendation.id in (item.based_on_recommendation_ids or [])
            ),
            None,
        )
        if path is None:
            return None, False
        existing = (
            db.query(LearningPathStep)
            .filter(
                LearningPathStep.learning_path_id == path.id,
                LearningPathStep.recommendation_id == recommendation.id,
                LearningPathStep.step_type == "verification",
            )
            .first()
        )
        if existing and existing.target_id:
            return existing, False
        previous_steps = (
            db.query(LearningPathStep)
            .filter(LearningPathStep.learning_path_id == path.id)
            .order_by(LearningPathStep.step_no.desc())
            .all()
        )
        source_event = (
            db.get(KnowledgeStateEvent, recommendation.source_state_event_id)
            if recommendation.source_state_event_id
            else None
        )
        plan = dict(recommendation.verification_plan or {})
        knowledge_point_id = (
            source_event.knowledge_point_id if source_event else None
        )
        knowledge_point = (
            db.get(KnowledgePoint, knowledge_point_id)
            if knowledge_point_id
            else None
        )
        topic = (
            knowledge_point.name
            if knowledge_point
            else recommendation.title or "当前薄弱知识点"
        )
        quiz = Quiz(
            id=str(uuid4()),
            project_id=recommendation.project_id,
            name=f"{topic} · 推荐完成后验证",
            description=(
                "根据本次推荐学习结果单独生成的验证测验；"
                "用于复测掌握度，不复用推荐资源本身。"
            ),
        )
        db.add(quiz)

        task = existing or LearningPathStep(
            id=str(uuid4()),
            learning_path_id=path.id,
            step_no=(previous_steps[0].step_no + 1) if previous_steps else 1,
            step_type="verification",
            recommendation_id=recommendation.id,
        )
        task.target_id = quiz.id
        task.knowledge_point_id = knowledge_point_id
        task.objective = (
            plan.get("objective") or f"完成“{topic}”推荐后的独立验证测验"
        )
        task.acceptance_condition = {
            **plan,
            "is_verification": True,
            "resource_type": "quiz",
            "resource_origin": "generated_after_recommendation_completion",
            "generation_status": "queued",
            "recommendation_id": recommendation.id,
            "quiz_id": quiz.id,
            "topic": topic,
        }
        task.baseline_mastery = (
            source_event.posterior_after_learning
            if source_event
            and source_event.posterior_after_learning is not None
            else None
        )
        task.target_mastery = float(
            (recommendation.expected_outcome or {}).get("target_mastery", 0.8)
        )
        task.status = "pending"
        db.add(task)
        db.flush()
        return task, True

    def _queue_verification_quiz(
        self,
        *,
        db,
        task: LearningPathStep,
        recommendation: Recommendation,
    ) -> None:
        """Queue brand-new questions for the dedicated verification quiz."""
        if not self.queue_service or not task.target_id:
            condition = dict(task.acceptance_condition or {})
            condition["generation_status"] = "not_queued"
            task.acceptance_condition = condition
            db.commit()
            return

        from edu_queue.schemas import QueueTaskMessage, QuizGenerationData, TaskType

        condition = dict(task.acceptance_condition or {})
        topic = str(condition.get("topic") or recommendation.title)
        task_data: QuizGenerationData = {
            "project_id": recommendation.project_id,
            "quiz_id": task.target_id,
            "topic": topic,
            "custom_instructions": (
                f"请围绕知识点“{topic}”单独生成 5 道全新的验证选择题。"
                "这些题目用于学生完成推荐资源后的再诊断，不要复用推荐资源中的原题；"
                "题目应覆盖概念辨析与应用，难度由易到难，选项与解析全部使用中文。"
            ),
            "user_id": recommendation.user_id,
            "count": 5,
        }
        message: QueueTaskMessage = {
            "type": TaskType.QUIZ_GENERATION,
            "data": task_data,
        }
        try:
            job_id = self.queue_service.send_message(message)
            condition["generation_status"] = "generating"
            if job_id:
                condition["generation_job_id"] = str(job_id)
        except Exception as exc:
            logger.exception(
                "Failed to queue verification quiz %s", task.target_id
            )
            condition["generation_status"] = "failed"
            condition["generation_error"] = str(exc)[:500]
        task.acceptance_condition = condition
        db.commit()

    def list_recommendation_interactions(
        self, project_id: str, recommendation_id: str, user_id: str
    ) -> list[RecommendationInteractionDto]:
        with self._get_db_session() as db:
            if not (
                db.query(Recommendation.id)
                .filter(
                    Recommendation.id == recommendation_id,
                    Recommendation.project_id == project_id,
                    Recommendation.user_id == user_id,
                )
                .first()
            ):
                raise NotFoundError(
                    f"Recommendation {recommendation_id} not found"
                )
            rows = (
                db.query(RecommendationInteraction)
                .filter(
                    RecommendationInteraction.recommendation_id
                    == recommendation_id,
                    RecommendationInteraction.user_id == user_id,
                )
                .order_by(RecommendationInteraction.occurred_at)
                .all()
            )
            return [self._interaction_dto(item) for item in rows]

    def list_intervention_outcomes(
        self, project_id: str, user_id: str
    ) -> list[InterventionOutcomeDto]:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            rows = (
                db.query(InterventionOutcome)
                .filter(
                    InterventionOutcome.project_id == project_id,
                    InterventionOutcome.user_id == user_id,
                )
                .order_by(InterventionOutcome.evaluated_at.desc())
                .all()
            )
            return [InterventionOutcomeDto.model_validate(item) for item in rows]

    def get_intervention_outcome(
        self, project_id: str, outcome_id: str, user_id: str
    ) -> InterventionOutcomeDto:
        with self._get_db_session() as db:
            row = (
                db.query(InterventionOutcome)
                .filter(
                    InterventionOutcome.id == outcome_id,
                    InterventionOutcome.project_id == project_id,
                    InterventionOutcome.user_id == user_id,
                )
                .first()
            )
            if not row:
                raise NotFoundError(f"Intervention outcome {outcome_id} not found")
            return InterventionOutcomeDto.model_validate(row)

    def adjust_learning_path(
        self,
        project_id: str,
        path_id: str,
        user_id: str,
        *,
        trigger_type: str = "intervention_outcomes",
        trigger_id: str | None = None,
        outcome_ids: list[str] | None = None,
    ) -> LearningPath:
        with self._get_db_session() as db:
            path = (
                db.query(LearningPath)
                .filter(
                    LearningPath.id == path_id,
                    LearningPath.project_id == project_id,
                    LearningPath.user_id == user_id,
                )
                .with_for_update()
                .first()
            )
            if not path:
                raise NotFoundError(f"Learning path {path_id} not found")

            is_aggregate = trigger_type == "intervention_outcomes" or bool(
                outcome_ids
            )
            normalized_trigger_type = (
                "intervention_outcomes" if is_aggregate else trigger_type
            )
            existing = (
                db.query(LearningPath)
                .filter(
                    LearningPath.previous_path_id == path.id,
                    LearningPath.adjust_trigger_type == normalized_trigger_type,
                )
                .order_by(LearningPath.version.desc())
                .first()
            )
            if existing:
                return existing

            if is_aggregate:
                recommendation_ids = list(path.based_on_recommendation_ids or [])
                if not recommendation_ids:
                    raise ValueError(
                        "The learning path has no recommendations to adjust"
                    )
                candidate_outcomes = (
                    db.query(InterventionOutcome)
                    .filter(
                        InterventionOutcome.project_id == project_id,
                        InterventionOutcome.user_id == user_id,
                        InterventionOutcome.recommendation_id.in_(
                            recommendation_ids
                        ),
                    )
                    .order_by(InterventionOutcome.evaluated_at.desc())
                    .all()
                )
                latest_by_recommendation: dict[str, InterventionOutcome] = {}
                for item in candidate_outcomes:
                    latest_by_recommendation.setdefault(
                        item.recommendation_id, item
                    )
                outcomes = [
                    latest_by_recommendation[recommendation_id]
                    for recommendation_id in recommendation_ids
                    if recommendation_id in latest_by_recommendation
                ]
                if not outcomes:
                    raise ValueError(
                        "No verified recommendation outcomes are available"
                    )
                latest_ids = {item.id for item in outcomes}
                if outcome_ids and set(outcome_ids) != latest_ids:
                    raise ValueError(
                        "Intervention outcomes changed; refresh the learning path"
                    )
            else:
                if trigger_type != "intervention_outcome" or not trigger_id:
                    raise ValueError(
                        "Only intervention outcome adjustments are supported"
                    )
                outcome = (
                    db.query(InterventionOutcome)
                    .filter(
                        InterventionOutcome.id == trigger_id,
                        InterventionOutcome.project_id == project_id,
                        InterventionOutcome.user_id == user_id,
                    )
                    .first()
                )
                if not outcome:
                    raise NotFoundError(
                        f"Intervention outcome {trigger_id} not found"
                    )
                outcomes = [outcome]

            included_outcome_ids = [item.id for item in outcomes]
            decision_by_knowledge_point: dict[str, InterventionOutcome] = {}
            for item in outcomes:
                current = decision_by_knowledge_point.get(
                    item.knowledge_point_id
                )
                if current is None or _as_utc(item.evaluated_at) > _as_utc(
                    current.evaluated_at
                ):
                    decision_by_knowledge_point[item.knowledge_point_id] = item
            decision_outcomes = list(decision_by_knowledge_point.values())
            unmet_outcomes = [
                item for item in decision_outcomes if not item.target_achieved
            ]

            now = datetime.now(timezone.utc)
            path.status = "replaced"
            path.replaced_at = now
            content = dict(path.content or {})
            content["adjustment"] = {
                "trigger_type": normalized_trigger_type,
                "trigger_ids": included_outcome_ids,
                "outcome_count": len(outcomes),
                "knowledge_point_count": len(decision_outcomes),
                "target_achieved_count": len(decision_outcomes)
                - len(unmet_outcomes),
                "needs_reinforcement_count": len(unmet_outcomes),
                "results": [
                    {
                        "outcome_id": item.id,
                        "recommendation_id": item.recommendation_id,
                        "knowledge_point_id": item.knowledge_point_id,
                        "mastery_before": item.mastery_before,
                        "mastery_after": item.mastery_after,
                        "target_mastery": item.target_mastery,
                        "target_achieved": item.target_achieved,
                        "evaluated_at": item.evaluated_at.isoformat(),
                    }
                    for item in outcomes
                ],
            }
            new_path = LearningPath(
                id=str(uuid4()),
                run_id=path.run_id,
                diagnosis_id=path.diagnosis_id,
                project_id=project_id,
                user_id=user_id,
                content=content,
                based_on_recommendation_ids=path.based_on_recommendation_ids or [],
                version=int(path.version or 1) + 1,
                previous_path_id=path.id,
                adjust_trigger_type=normalized_trigger_type,
                adjust_trigger_id=(
                    trigger_id if normalized_trigger_type == "intervention_outcome" else None
                ),
                adjust_trigger_ids=included_outcome_ids,
                status="active",
                activated_at=now,
            )
            db.add(new_path)
            db.flush()

            old_steps = (
                db.query(LearningPathStep)
                .filter(LearningPathStep.learning_path_id == path.id)
                .order_by(LearningPathStep.step_no)
                .all()
            )
            next_step = 1
            for outcome in unmet_outcomes:
                db.add(
                    LearningPathStep(
                        id=str(uuid4()),
                        learning_path_id=new_path.id,
                        step_no=next_step,
                        step_type="targeted_practice",
                        knowledge_point_id=outcome.knowledge_point_id,
                        recommendation_id=outcome.recommendation_id,
                        objective="继续巩固未达到目标掌握度的知识点",
                        acceptance_condition={
                            "target_mastery": outcome.target_mastery,
                            "requires_verification": True,
                        },
                        baseline_mastery=outcome.mastery_after,
                        target_mastery=outcome.target_mastery,
                    )
                )
                next_step += 1
            for old in old_steps:
                db.add(
                    LearningPathStep(
                        id=str(uuid4()),
                        learning_path_id=new_path.id,
                        step_no=next_step,
                        step_type=old.step_type,
                        target_id=old.target_id,
                        knowledge_point_id=old.knowledge_point_id,
                        recommendation_id=old.recommendation_id,
                        objective=old.objective,
                        acceptance_condition=old.acceptance_condition or {},
                        baseline_mastery=old.baseline_mastery,
                        target_mastery=old.target_mastery,
                        status="pending" if old.status != "completed" else "completed",
                        completed_at=old.completed_at,
                        completion_event_id=old.completion_event_id,
                    )
                )
                next_step += 1

            explanation = Explanation(
                id=str(uuid4()),
                project_id=project_id,
                user_id=user_id,
                object_type="path_adjustment",
                object_id=new_path.id,
                summary=(
                    f"已综合 {len(outcomes)} 项最新验证结果；"
                    f"{len(decision_outcomes) - len(unmet_outcomes)} 个知识点达标，"
                    f"{len(unmet_outcomes)} 个知识点需要继续巩固。"
                ),
                reason_codes=(
                    ["intervention_targets_achieved"]
                    if not unmet_outcomes
                    else ["intervention_targets_need_reinforcement"]
                ),
                model_version="path-rule-v3",
                confidence=sum(
                    item.attribution_confidence for item in outcomes
                )
                / len(outcomes),
            )
            db.add(explanation)
            db.flush()
            new_path.explanation_id = explanation.id
            db.commit()
            db.refresh(new_path)
            return new_path

    @staticmethod
    def _interaction_dto(
        item: RecommendationInteraction,
    ) -> RecommendationInteractionDto:
        return RecommendationInteractionDto(
            id=item.id,
            recommendation_id=item.recommendation_id,
            user_id=item.user_id,
            project_id=item.project_id,
            event_type=item.event_type,
            resource_id=item.resource_id,
            learning_session_id=item.learning_session_id,
            progress=item.progress,
            duration_ms=item.duration_ms,
            rating=item.rating,
            reason_code=item.reason_code,
            occurred_at=item.occurred_at,
            metadata=item.metadata_json or {},
        )

    @staticmethod
    def _get_owned_project(db, project_id: str, user_id: str) -> Project:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == user_id)
            .first()
        )
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        return project

    @contextmanager
    def _get_db_session(self):
        db = get_session_factory()()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class KTConfigurationService:
    def list_parameter_sets(self) -> list[KTParameterSetDto]:
        with self._get_db_session() as db:
            rows = db.query(KTParameterSet).order_by(KTParameterSet.created_at).all()
            return [KTParameterSetDto.model_validate(item) for item in rows]

    def create_parameter_set(
        self, request: KTParameterSetCreate, created_by: str
    ) -> KTParameterSetDto:
        with self._get_db_session() as db:
            row = KTParameterSet(
                id=str(uuid4()),
                created_by=created_by,
                **request.model_dump(),
            )
            if request.status == "active":
                self._retire_conflicting(db, row.scope_type, row.scope_id)
            db.add(row)
            db.commit()
            db.refresh(row)
            return KTParameterSetDto.model_validate(row)

    def activate_parameter_set(self, parameter_set_id: str) -> KTParameterSetDto:
        with self._get_db_session() as db:
            row = db.get(KTParameterSet, parameter_set_id)
            if not row:
                raise NotFoundError(f"KT parameter set {parameter_set_id} not found")
            self._retire_conflicting(db, row.scope_type, row.scope_id)
            row.status = "active"
            row.effective_from = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
            return KTParameterSetDto.model_validate(row)

    def set_knowledge_point_override(
        self,
        knowledge_point_id: str,
        request: KnowledgePointKTOverrideCreate,
    ) -> dict:
        with self._get_db_session() as db:
            if not db.get(KnowledgePoint, knowledge_point_id):
                raise NotFoundError(f"Knowledge point {knowledge_point_id} not found")
            if not db.get(KTParameterSet, request.parameter_set_id):
                raise NotFoundError(
                    f"KT parameter set {request.parameter_set_id} not found"
                )
            row = (
                db.query(KnowledgePointKTParameter)
                .filter(
                    KnowledgePointKTParameter.knowledge_point_id
                    == knowledge_point_id,
                    KnowledgePointKTParameter.parameter_set_id
                    == request.parameter_set_id,
                )
                .first()
            ) or KnowledgePointKTParameter(
                id=str(uuid4()),
                knowledge_point_id=knowledge_point_id,
                parameter_set_id=request.parameter_set_id,
            )
            for key, value in request.model_dump(exclude={"parameter_set_id"}).items():
                setattr(row, key, value)
            row.reviewed_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return {
                "id": row.id,
                "knowledge_point_id": row.knowledge_point_id,
                **request.model_dump(),
                "reviewed_at": row.reviewed_at,
            }

    def upsert_item_mapping(
        self, request: ItemKnowledgePointMappingCreate
    ) -> dict:
        with self._get_db_session() as db:
            if not db.get(KnowledgePoint, request.knowledge_point_id):
                raise NotFoundError(
                    f"Knowledge point {request.knowledge_point_id} not found"
                )
            row = (
                db.query(ItemKnowledgePointMapping)
                .filter(
                    ItemKnowledgePointMapping.item_type == request.item_type,
                    ItemKnowledgePointMapping.item_id == request.item_id,
                    ItemKnowledgePointMapping.knowledge_point_id
                    == request.knowledge_point_id,
                )
                .first()
            ) or ItemKnowledgePointMapping(id=str(uuid4()))
            for key, value in request.model_dump().items():
                setattr(row, key, value)
            db.add(row)
            db.flush()
            total_weight = sum(
                value[0]
                for value in db.query(ItemKnowledgePointMapping.weight)
                .filter(
                    ItemKnowledgePointMapping.item_type == request.item_type,
                    ItemKnowledgePointMapping.item_id == request.item_id,
                    ItemKnowledgePointMapping.review_status == "approved",
                )
                .all()
            )
            if total_weight > 1.000001:
                raise ValueError("Approved knowledge-point mapping weights cannot exceed 1")
            db.commit()
            return {"id": row.id, **request.model_dump(), "total_weight": total_weight}

    @staticmethod
    def _retire_conflicting(db, scope_type: str, scope_id: str | None) -> None:
        db.query(KTParameterSet).filter(
            KTParameterSet.scope_type == scope_type,
            KTParameterSet.scope_id == scope_id,
            KTParameterSet.status == "active",
        ).update({"status": "retired"}, synchronize_session=False)

    @contextmanager
    def _get_db_session(self):
        db = get_session_factory()()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
