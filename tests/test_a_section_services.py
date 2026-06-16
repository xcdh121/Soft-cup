import unittest
from contextlib import ExitStack
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from edu_db.models import (
    Base,
    Course,
    KnowledgePoint,
    KnowledgeStateEvent,
    LearnerProfileRevision,
    Project,
    Quiz,
    QuizQuestion,
    StudentKnowledgeState,
    User,
)
from edu_core.services.course_resources import CourseResourceService
from edu_core.services.knowledge_states import KnowledgeStateService
from edu_core.services.learner_profiles import LearnerProfileService
from edu_core.services.practice import PracticeService


class ASectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.patches = ExitStack()
        for target in (
            "edu_core.services.course_resources.get_session_factory",
            "edu_core.services.learner_profiles.get_session_factory",
            "edu_core.services.knowledge_states.get_session_factory",
            "edu_core.services.practice.get_session_factory",
        ):
            self.patches.enter_context(
                patch(target, return_value=self.session_factory)
            )

        with self.session_factory() as db:
            db.add_all(
                [
                    User(id="user-1", name="Test", email="test@example.com"),
                    Course(id="course-1", owner_id="user-1", name="Databases"),
                    Project(
                        id="project-1",
                        owner_id="user-1",
                        course_id="course-1",
                        name="Database project",
                    ),
                    KnowledgePoint(
                        id="kp-1",
                        course_id="course-1",
                        name="Transactions",
                        tags=["ACID"],
                    ),
                    Quiz(
                        id="quiz-1",
                        project_id="project-1",
                        name="Transaction quiz",
                    ),
                    QuizQuestion(
                        id="question-1",
                        quiz_id="quiz-1",
                        project_id="project-1",
                        question_text="What does atomicity mean?",
                        option_a="A",
                        option_b="B",
                        option_c="C",
                        option_d="D",
                        correct_option="a",
                    ),
                ]
            )
            db.commit()

    def tearDown(self):
        self.patches.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_course_resource_create_and_list(self):
        service = CourseResourceService()
        created = service.create_resource(
            "course-1",
            "user-1",
            chapter_id=None,
            document_id=None,
            generated_resource_id=None,
            resource_type="lecture_note",
            title="Transaction notes",
            description=None,
            source_type="internal",
            source_url=None,
            difficulty_level="beginner",
            estimated_minutes=15,
            license_info=None,
            target_audiences=["beginner"],
            metadata={"format": "markdown"},
            knowledge_point_ids=["kp-1"],
        )

        self.assertEqual(created.knowledge_point_ids, ["kp-1"])
        self.assertEqual(service.list_resources("course-1", "user-1")[0].id, created.id)

    def test_profile_updates_create_field_revisions(self):
        service = LearnerProfileService()
        service.replace_profile(
            "project-1",
            "user-1",
            {"learning_goal": {"value": "Pass", "confidence": 0.8}},
        )
        profile = service.patch_profile(
            "project-1",
            "user-1",
            {
                "learning_goal": {"value": "Master databases", "confidence": 0.9},
                "education_level": {"value": "Undergraduate"},
            },
        )

        revisions = service.list_revisions("project-1", "user-1")
        self.assertEqual(profile.completeness_score, 2 / 12)
        self.assertEqual(len(revisions), 3)
        with self.session_factory() as db:
            self.assertEqual(db.query(LearnerProfileRevision).count(), 3)

    def test_practice_refresh_is_automatic_and_idempotent(self):
        practice_service = PracticeService()
        state_service = KnowledgeStateService()
        practice_service.create_practice_record(
            user_id="user-1",
            project_id="project-1",
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id="kp-1",
            topic="Transactions",
            user_answer="a",
            correct_answer="a",
            was_correct=True,
        )

        first = state_service.refresh_states("project-1", "user-1")
        second = state_service.refresh_states("project-1", "user-1")

        self.assertEqual(first.processed_count, 1)
        self.assertEqual(first.updated_states[0].mastery_score, 30)
        self.assertEqual(second.processed_count, 0)
        self.assertEqual(second.already_processed_count, 1)
        with self.session_factory() as db:
            state = db.query(StudentKnowledgeState).one()
            self.assertEqual(state.attempt_count, 1)
            self.assertEqual(state.correct_count, 1)
            self.assertEqual(db.query(KnowledgeStateEvent).count(), 1)

    def test_topic_tag_fallback_updates_state(self):
        practice_service = PracticeService()
        record = practice_service.create_practice_record(
            user_id="user-1",
            project_id="project-1",
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id=None,
            topic="acid",
            user_answer="b",
            correct_answer="a",
            was_correct=False,
        )
        result = KnowledgeStateService().refresh_states(
            "project-1", "user-1"
        )

        self.assertEqual(record.knowledge_point_id, "kp-1")
        self.assertEqual(result.processed_count, 1)
        self.assertEqual(result.updated_states[0].mastery_score, 0)
        self.assertEqual(result.updated_states[0].status, "learning")


if __name__ == "__main__":
    unittest.main()
