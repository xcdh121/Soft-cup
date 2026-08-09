from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from edu_core.schemas.closed_loop import (
    ItemKnowledgePointMappingCreate,
    KTParameterSetCreate,
    KnowledgePointKTOverrideCreate,
    RecommendationFeedbackCreate,
)
from edu_core.services.bkt import (
    BKTParameters,
    apply_adjustments,
    classify_status,
    evidence_confidence,
    update_bkt,
)
from edu_core.services.knowledge_states import KnowledgeStateService
from edu_core.services.learning_closed_loop import (
    KTConfigurationService,
    LearningClosedLoopService,
)
from edu_core.services.practice import PracticeService
from edu_db.models import (
    AgentRun,
    Base,
    Course,
    CourseChapter,
    InterventionOutcome,
    KnowledgePoint,
    KnowledgeStateEvent,
    LearningPath,
    LearningPathStep,
    Project,
    Quiz,
    QuizQuestion,
    Recommendation,
    StudentKnowledgeState,
    User,
)


def test_bkt_correct_wrong_partial_and_verification():
    now = datetime.now(timezone.utc)
    base = BKTParameters()
    correct = update_bkt(
        prior_mastery=0.2,
        observed_score=1,
        parameters=base,
        occurred_at=now,
        last_occurred_at=None,
    )
    wrong = update_bkt(
        prior_mastery=0.2,
        observed_score=0,
        parameters=base,
        occurred_at=now,
        last_occurred_at=None,
    )
    partial = update_bkt(
        prior_mastery=0.2,
        observed_score=0.5,
        parameters=base,
        occurred_at=now,
        last_occurred_at=None,
    )
    verification_parameters = apply_adjustments(
        base,
        difficulty="medium",
        answer_mode="quiz",
        is_verification=True,
    )
    verification = update_bkt(
        prior_mastery=0.2,
        observed_score=1,
        parameters=verification_parameters,
        occurred_at=now,
        last_occurred_at=None,
    )

    assert wrong.mastery_probability < partial.mastery_probability
    assert partial.mastery_probability < correct.mastery_probability
    assert verification.posterior_after_learning == pytest.approx(
        verification.posterior_after_observation
    )
    assert correct.mastery_probability == pytest.approx(0.585882, abs=1e-6)


def test_bkt_forgetting_confidence_and_status():
    now = datetime.now(timezone.utc)
    result = update_bkt(
        prior_mastery=0.9,
        observed_score=1,
        parameters=BKTParameters(forget_probability_daily=0.1),
        occurred_at=now,
        last_occurred_at=now - timedelta(days=10),
    )
    assert result.prior_after_forgetting < 0.9
    low_confidence = evidence_confidence(1, 0.5)
    status, reasons = classify_status(
        0.9, low_confidence, event_count=1, days_since_verification=None
    )
    assert status == "insufficient_evidence"
    assert "low_evidence_confidence" in reasons


@pytest.fixture()
def closed_loop_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    patches = ExitStack()
    for target in (
        "edu_core.services.knowledge_states.get_session_factory",
        "edu_core.services.practice.get_session_factory",
        "edu_core.services.learning_closed_loop.get_session_factory",
    ):
        patches.enter_context(patch(target, return_value=factory))
    with factory() as db:
        db.add_all(
            [
                User(id="user-1", username="learner", is_admin=True),
                Course(id="course-1", owner_id="user-1", name="Course"),
                CourseChapter(
                    id="chapter-1", course_id="course-1", title="Chapter", position=1
                ),
                Project(
                    id="project-1",
                    owner_id="user-1",
                    course_id="course-1",
                    name="Project",
                ),
                KnowledgePoint(
                    id="kp-1",
                    course_id="course-1",
                    chapter_id="chapter-1",
                    name="Gradient descent",
                ),
                Quiz(id="quiz-1", project_id="project-1", name="Quiz"),
                QuizQuestion(
                    id="question-1",
                    quiz_id="quiz-1",
                    project_id="project-1",
                    knowledge_point_id="kp-1",
                    question_text="Question",
                    option_a="A",
                    option_b="B",
                    option_c="C",
                    option_d="D",
                    correct_option="a",
                ),
                AgentRun(
                    id="run-1",
                    project_id="project-1",
                    user_id="user-1",
                    goal="closed_loop",
                    status="completed",
                ),
            ]
        )
        db.commit()
    try:
        yield factory
    finally:
        patches.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_full_feedback_verification_outcome_and_path_adjustment(closed_loop_database):
    practice = PracticeService()
    states = KnowledgeStateService()

    class CapturingQueue:
        def __init__(self):
            self.messages = []

        def send_message(self, message):
            self.messages.append(message)
            return "verification-job-1"

    queue = CapturingQueue()
    closed_loop = LearningClosedLoopService(queue_service=queue)
    now = datetime.now(timezone.utc)

    practice.create_practice_record(
        user_id="user-1",
        project_id="project-1",
        item_type="quiz",
        item_id="question-1",
        knowledge_point_id="kp-1",
        topic="Gradient descent",
        user_answer="b",
        correct_answer="a",
        was_correct=False,
        score=0,
        occurred_at=now,
    )
    states.refresh_states("project-1", "user-1")
    with closed_loop_database() as db:
        baseline = db.query(KnowledgeStateEvent).one()
        db.add(
            Recommendation(
                id="rec-1",
                run_id="run-1",
                project_id="project-1",
                user_id="user-1",
                recommendation_type="resource",
                title="Targeted material",
                reason_codes=["weak_mastery"],
                reason_text=["Review the weak point"],
                source_state_event_id=baseline.id,
                expected_outcome={"target_mastery": 0.8},
                verification_plan={"within_hours": 72},
            )
        )
        db.add(
            LearningPath(
                id="path-1",
                run_id="run-1",
                project_id="project-1",
                user_id="user-1",
                content={"title": "v1", "path_steps": []},
                based_on_recommendation_ids=["rec-1"],
            )
        )
        db.commit()

    with closed_loop_database() as db:
        assert db.query(LearningPathStep).count() == 0
        assert (
            db.query(Quiz)
            .filter(Quiz.name.contains("推荐完成后验证"))
            .count()
            == 0
        )

    feedback = closed_loop.record_recommendation_feedback(
        "project-1",
        "rec-1",
        "user-1",
        RecommendationFeedbackCreate(
            event_type="completed", progress=1, occurred_at=now + timedelta(hours=1)
        ),
    )
    assert feedback.event_type == "completed"
    assert feedback.metadata["verification_required"] is True
    with closed_loop_database() as db:
        verification_task = db.query(LearningPathStep).one()
        assert verification_task.step_type == "verification"
        assert verification_task.recommendation_id == "rec-1"
        assert verification_task.status == "pending"
        assert verification_task.target_id is not None
        verification_quiz = db.get(Quiz, verification_task.target_id)
        assert verification_quiz is not None
        assert "推荐完成后验证" in verification_quiz.name
        assert verification_task.acceptance_condition["resource_type"] == "quiz"
        assert (
            verification_task.acceptance_condition["resource_origin"]
            == "generated_after_recommendation_completion"
        )
    assert len(queue.messages) == 1
    assert queue.messages[0]["type"].value == "quiz_generation"
    assert queue.messages[0]["data"]["quiz_id"] == verification_task.target_id
    assert queue.messages[0]["data"]["count"] == 5

    practice.create_practice_record(
        user_id="user-1",
        project_id="project-1",
        item_type="quiz",
        item_id="question-1",
        knowledge_point_id="kp-1",
        topic="Gradient descent verification",
        user_answer="a",
        correct_answer="a",
        was_correct=True,
        score=1,
        recommendation_id="rec-1",
        is_verification=True,
        occurred_at=now + timedelta(hours=2),
    )
    states.refresh_states("project-1", "user-1")

    outcomes = closed_loop.list_intervention_outcomes("project-1", "user-1")
    assert len(outcomes) == 1
    assert outcomes[0].attribution_confidence == pytest.approx(0.8)
    assert outcomes[0].verification_score == 1

    with closed_loop_database() as db:
        path = db.get(LearningPath, "path-1")
        first_outcome = db.get(InterventionOutcome, outcomes[0].id)
        baseline_event = db.get(
            KnowledgeStateEvent, first_outcome.baseline_state_event_id
        )
        state = db.query(StudentKnowledgeState).one()
        second_verification_event = KnowledgeStateEvent(
            id="verification-event-2",
            knowledge_state_id=state.id,
            project_id="project-1",
            user_id="user-1",
            knowledge_point_id="kp-1",
            event_type="verification",
            source_type="practice_record",
            source_id="verification-record-2",
            score_before=90,
            score_after=40,
            impact=-50,
            was_correct=False,
            posterior_after_learning=0.4,
            occurred_at=now + timedelta(hours=3),
        )
        db.add(
            Recommendation(
                id="rec-2",
                run_id="run-1",
                project_id="project-1",
                user_id="user-1",
                recommendation_type="quiz",
                title="Second targeted resource",
                reason_codes=["weak_mastery"],
                reason_text=["Verify the same point again"],
                source_state_event_id=baseline_event.id,
                expected_outcome={"target_mastery": 0.8},
                verification_plan={"within_hours": 72},
            )
        )
        db.add(second_verification_event)
        db.flush()
        db.add(
            InterventionOutcome(
                id="outcome-2",
                project_id="project-1",
                user_id="user-1",
                recommendation_id="rec-2",
                knowledge_point_id="kp-1",
                baseline_state_event_id=baseline_event.id,
                verification_event_id=second_verification_event.id,
                mastery_before=0.2,
                mastery_after=0.4,
                mastery_gain=0.2,
                verification_score=0,
                target_mastery=0.8,
                target_achieved=False,
                attribution_confidence=0.7,
                evaluation_window_hours=72,
                evaluated_at=now + timedelta(hours=3),
            )
        )
        path.based_on_recommendation_ids = ["rec-1", "rec-2"]
        db.commit()

    latest_outcomes = closed_loop.list_intervention_outcomes(
        "project-1", "user-1"
    )
    latest_outcome_ids = [item.id for item in latest_outcomes]

    path_v2 = closed_loop.adjust_learning_path(
        "project-1",
        "path-1",
        "user-1",
        trigger_type="intervention_outcomes",
        outcome_ids=latest_outcome_ids,
    )
    assert path_v2.version == 2
    assert path_v2.previous_path_id == "path-1"
    assert path_v2.adjust_trigger_type == "intervention_outcomes"
    assert set(path_v2.adjust_trigger_ids) == set(latest_outcome_ids)
    assert path_v2.content["adjustment"]["outcome_count"] == 2
    assert path_v2.content["adjustment"]["knowledge_point_count"] == 1
    assert path_v2.content["adjustment"]["needs_reinforcement_count"] == 1

    repeated_path = closed_loop.adjust_learning_path(
        "project-1",
        "path-1",
        "user-1",
        trigger_type="intervention_outcomes",
        outcome_ids=latest_outcome_ids,
    )
    assert repeated_path.id == path_v2.id
    with closed_loop_database() as db:
        assert db.query(InterventionOutcome).count() == 2
        assert (
            db.query(LearningPathStep)
            .filter(
                LearningPathStep.learning_path_id == path_v2.id,
                LearningPathStep.step_type == "targeted_practice",
            )
            .count()
            == 1
        )
        assert db.query(StudentKnowledgeState).one().last_verified_at is not None


def test_replay_is_deterministic_and_metrics_are_available(closed_loop_database):
    practice = PracticeService()
    states = KnowledgeStateService()
    practice.create_practice_record(
        user_id="user-1",
        project_id="project-1",
        item_type="quiz",
        item_id="question-1",
        knowledge_point_id="kp-1",
        topic="Gradient descent",
        user_answer="a",
        correct_answer="a",
        was_correct=True,
        score=1,
    )
    states.refresh_states("project-1", "user-1")
    dry_run = states.replay_states("project-1", "user-1", dry_run=True)
    applied = states.replay_states("project-1", "user-1", dry_run=False)
    second = states.replay_states("project-1", "user-1", dry_run=True)
    metrics = states.get_metrics("project-1", "user-1")

    assert dry_run.processed_records == 1
    assert applied.rebuilt_states == 1
    assert second.differences[0]["delta"] == pytest.approx(0)
    assert metrics.event_count == 1
    assert metrics.mapping_coverage == 1
    assert metrics.legacy_brier_score is not None
    assert metrics.brier_score_improvement is not None


def test_parameter_precedence_and_weighted_multi_point_mapping(
    closed_loop_database,
):
    with closed_loop_database() as db:
        db.add(
            KnowledgePoint(
                id="kp-2",
                course_id="course-1",
                chapter_id="chapter-1",
                name="Loss function",
            )
        )
        db.commit()

    config = KTConfigurationService()
    config.create_parameter_set(
        KTParameterSetCreate(
            name="Global",
            version="bkt-global-v1",
            scope_type="global",
            learn_probability=0.15,
            status="active",
        ),
        "user-1",
    )
    course_parameters = config.create_parameter_set(
        KTParameterSetCreate(
            name="Course",
            version="bkt-course-v1",
            scope_type="course",
            scope_id="course-1",
            learn_probability=0.20,
            status="active",
        ),
        "user-1",
    )
    config.set_knowledge_point_override(
        "kp-1",
        KnowledgePointKTOverrideCreate(
            parameter_set_id=course_parameters.id,
            learn_override=0.30,
            expert_reason="This concept benefits from more guided practice.",
        ),
    )
    config.upsert_item_mapping(
        ItemKnowledgePointMappingCreate(
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id="kp-1",
            weight=0.4,
        )
    )
    config.upsert_item_mapping(
        ItemKnowledgePointMappingCreate(
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id="kp-2",
            weight=0.6,
        )
    )

    PracticeService().create_practice_record(
        user_id="user-1",
        project_id="project-1",
        item_type="quiz",
        item_id="question-1",
        knowledge_point_id="kp-1",
        topic="Gradient descent and loss",
        user_answer="a",
        correct_answer="a",
        was_correct=True,
        score=1,
    )
    result = KnowledgeStateService().refresh_states("project-1", "user-1")

    assert result.processed_count == 2
    with closed_loop_database() as db:
        events = {
            item.knowledge_point_id: item
            for item in db.query(KnowledgeStateEvent).all()
        }
        assert events["kp-1"].event_weight == pytest.approx(0.4)
        assert events["kp-2"].event_weight == pytest.approx(0.6)
        assert events["kp-1"].effective_parameters[
            "learn_probability"
        ] == pytest.approx(0.30)
        assert events["kp-2"].effective_parameters[
            "learn_probability"
        ] == pytest.approx(0.20)
