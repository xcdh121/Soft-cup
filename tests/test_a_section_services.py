import unittest
from contextlib import ExitStack
from unittest.mock import patch

from edu_core.services.chats import ChatService
from edu_core.services.course_resources import CourseResourceService
from edu_core.services.courses import CourseService
from edu_core.services.knowledge_states import KnowledgeStateService
from edu_core.services.learner_profiles import LearnerProfileService
from edu_core.services.practice import PracticeService
from edu_db.models import (
    Base,
    Course,
    CourseChapter,
    CourseResourceKnowledgePoint,
    Document,
    KnowledgePoint,
    KnowledgePointRelation,
    KnowledgeStateEvent,
    LearnerProfile,
    LearnerProfileRevision,
    PracticeRecord,
    Project,
    Quiz,
    QuizQuestion,
    StudentKnowledgeState,
    User,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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
            "edu_core.services.courses.get_session_factory",
            "edu_core.services.learner_profiles.get_session_factory",
            "edu_core.services.knowledge_states.get_session_factory",
            "edu_core.services.practice.get_session_factory",
        ):
            self.patches.enter_context(patch(target, return_value=self.session_factory))

        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id="user-1",
                        username="test-user",
                        name="Test",
                        email="test@example.com",
                    ),
                    Course(id="course-1", owner_id="user-1", name="Databases"),
                    CourseChapter(
                        id="chapter-1",
                        course_id="course-1",
                        title="Transactions",
                        position=1,
                    ),
                    Project(
                        id="project-1",
                        owner_id="user-1",
                        course_id="course-1",
                        name="Database project",
                    ),
                    KnowledgePoint(
                        id="kp-1",
                        course_id="course-1",
                        chapter_id="chapter-1",
                        name="Transactions",
                        tags=["ACID"],
                    ),
                    KnowledgePoint(
                        id="kp-2",
                        course_id="course-1",
                        chapter_id="chapter-1",
                        name="Isolation Levels",
                        position=1,
                        tags=["isolation"],
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

    def test_course_resource_exposes_its_document_project(self):
        with self.session_factory() as db:
            db.add(
                Project(
                    id="source-project",
                    owner_id="user-1",
                    course_id="course-1",
                    name="Course PDF source",
                )
            )
            db.add(
                Document(
                    id="course-pdf",
                    owner_id="user-1",
                    project_id="source-project",
                    file_name="transactions.pdf",
                    file_type="pdf",
                    file_size=1024,
                )
            )
            db.commit()

        resource = CourseResourceService().create_resource(
            "course-1",
            "user-1",
            chapter_id="chapter-1",
            document_id="course-pdf",
            generated_resource_id=None,
            resource_type="pdf",
            title="Transaction textbook",
            description=None,
            source_type="internal",
            source_url=None,
            difficulty_level="beginner",
            estimated_minutes=30,
            license_info=None,
            target_audiences=[],
            metadata={},
            knowledge_point_ids=["kp-1"],
        )

        self.assertEqual(resource.document_project_id, "source-project")

    def test_knowledge_point_get_and_update(self):
        service = CourseService()
        point = service.get_knowledge_point("kp-1", "user-1")
        self.assertEqual(point.name, "Transactions")

        updated = service.update_knowledge_point(
            knowledge_point_id="kp-1",
            owner_id="user-1",
            description="## 一句话介绍\n事务保证一组操作共同成功或失败。",
            difficulty_level="beginner",
            tags=["ACID", "transaction"],
            fields_to_update={"description", "difficulty_level", "tags"},
        )

        self.assertEqual(updated.difficulty_level, "beginner")
        self.assertIn("共同成功或失败", updated.description)
        self.assertEqual(updated.tags, ["ACID", "transaction"])

    def test_resource_can_be_created_from_knowledge_point(self):
        service = CourseResourceService()
        resource = service.create_resource_for_knowledge_point(
            "kp-1",
            "user-1",
            chapter_id=None,
            document_id=None,
            generated_resource_id=None,
            resource_type="article",
            title="Transaction reference",
            description="External reading",
            source_type="external",
            source_url="https://example.com/transactions",
            difficulty_level="beginner",
            estimated_minutes=10,
            license_info=None,
            target_audiences=["beginner"],
            metadata={},
            knowledge_point_ids=["kp-2"],
        )

        self.assertEqual(resource.course_id, "course-1")
        self.assertEqual(resource.chapter_id, "chapter-1")
        self.assertEqual(set(resource.knowledge_point_ids), {"kp-1", "kp-2"})
        listed = service.list_resources_by_knowledge_point("kp-1", "user-1")
        self.assertEqual(listed[0].id, resource.id)
        with self.session_factory() as db:
            self.assertEqual(db.query(CourseResourceKnowledgePoint).count(), 2)

    def test_knowledge_point_relations_create_list_and_delete(self):
        service = CourseService()
        relation = service.create_knowledge_point_relation(
            course_id="course-1",
            owner_id="user-1",
            source_knowledge_point_id="kp-1",
            target_knowledge_point_id="kp-2",
            relation_type="prerequisite",
            strength=0.8,
            description="Transactions before isolation levels",
        )

        relations = service.list_knowledge_point_relations("course-1", "user-1")
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0].source_knowledge_point_id, "kp-1")
        self.assertEqual(relations[0].target_knowledge_point_id, "kp-2")

        service.delete_knowledge_point_relation("course-1", relation.id, "user-1")
        with self.session_factory() as db:
            self.assertEqual(db.query(KnowledgePointRelation).count(), 0)

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

    def test_chat_inferences_update_only_conversational_profile_fields(self):
        service = LearnerProfileService()
        profile = service.apply_chat_inferences(
            "project-1",
            "user-1",
            "message-1",
            "I study computer science and prefer diagrams.",
            {
                "major_background": {
                    "value": "Computer science",
                    "confidence": 0.96,
                    "status": "confirmed",
                },
                "resource_preference": {
                    "value": ["diagrams"],
                    "confidence": 0.91,
                    "status": "confirmed",
                },
                "knowledge_background": {
                    "value": "expert",
                    "confidence": 0.99,
                    "status": "confirmed",
                },
            },
        )

        self.assertIsNotNone(profile)
        self.assertIn("major_background", profile.profile_data)
        self.assertIn("resource_preference", profile.profile_data)
        self.assertNotIn("knowledge_background", profile.profile_data)
        preference = profile.profile_data["resource_preference"]
        self.assertEqual(preference["evidence"][0]["source_type"], "chat_message")
        self.assertEqual(preference["evidence"][0]["source_id"], "message-1")
        revisions = service.list_revisions("project-1", "user-1")
        self.assertEqual(len(revisions), 2)
        self.assertTrue(all(item.source_type == "chat_message" for item in revisions))

    def test_tutor_context_combines_profile_course_and_learning_evidence(self):
        with self.session_factory() as db:
            db.add_all(
                [
                    LearnerProfile(
                        id="profile-1",
                        user_id="user-1",
                        project_id="project-1",
                        status="active",
                        completeness_score=0.25,
                        profile_data={
                            "current_course": {"value": "数据库系统"},
                            "learning_goal": {"value": "准备期末考试"},
                            "resource_preference": {"value": ["笔记", "刷题"]},
                        },
                    ),
                    StudentKnowledgeState(
                        id="state-1",
                        user_id="user-1",
                        knowledge_point_id="kp-1",
                        mastery_score=35,
                        confidence=0.8,
                        trend="down",
                        status="learning",
                        attempt_count=4,
                        correct_count=1,
                        evidence=[],
                    ),
                    PracticeRecord(
                        id="practice-1",
                        user_id="user-1",
                        project_id="project-1",
                        knowledge_point_id="kp-1",
                        item_type="quiz",
                        item_id="question-1",
                        topic="Transactions",
                        user_answer="b",
                        correct_answer="a",
                        was_correct=False,
                    ),
                ]
            )
            db.commit()

            project, profile, evidence = (
                ChatService._load_tutor_personalization_context(
                    db_session=db,
                    project_id="project-1",
                    user_id="user-1",
                )
            )

        self.assertEqual(project["course_name"], "Databases")
        self.assertEqual(profile["fields"]["learning_goal"], "准备期末考试")
        self.assertEqual(profile["fields"]["resource_preference"], ["笔记", "刷题"])
        self.assertEqual(evidence["weak_points"][0]["name"], "Transactions")
        self.assertEqual(evidence["overall_mastery"], 35)
        self.assertEqual(evidence["recent_accuracy"], 0)

    def test_chat_inferences_are_idempotent_and_protect_confirmed_values(self):
        service = LearnerProfileService()
        service.replace_profile(
            "project-1",
            "user-1",
            {
                "learning_goal": {
                    "value": "Pass the database exam",
                    "confidence": 0.9,
                    "status": "confirmed",
                }
            },
        )
        inferred = {
            "learning_goal": {
                "value": "Become a database administrator",
                "confidence": 0.8,
                "status": "inferred",
            }
        }
        service.apply_chat_inferences(
            "project-1", "user-1", "message-2", "Databases seem useful.", inferred
        )
        service.apply_chat_inferences(
            "project-1", "user-1", "message-2", "Databases seem useful.", inferred
        )

        profile = service.get_profile("project-1", "user-1")
        self.assertEqual(
            profile.profile_data["learning_goal"]["value"],
            "Pass the database exam",
        )
        self.assertEqual(len(service.list_revisions("project-1", "user-1")), 1)

    def test_chat_inferences_merge_up_to_three_resource_preferences(self):
        service = LearnerProfileService()
        service.replace_profile(
            "project-1",
            "user-1",
            {
                "resource_preference": {
                    "value": ["编程题", "学习笔记"],
                    "confidence": 1.0,
                    "status": "confirmed",
                }
            },
        )

        profile = service.apply_chat_inferences(
            "project-1",
            "user-1",
            "message-preference",
            "我也喜欢通过选择题巩固。",
            {
                "resource_preference": {
                    "value": ["选择题"],
                    "confidence": 0.95,
                    "status": "confirmed",
                }
            },
        )

        self.assertEqual(
            profile.profile_data["resource_preference"]["value"],
            ["编程题", "学习笔记", "选择题"],
        )

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
        self.assertAlmostEqual(first.updated_states[0].mastery_score, 58.59, places=2)
        self.assertEqual(first.updated_states[0].algorithm, "expert_bkt")
        self.assertEqual(second.processed_count, 0)
        self.assertEqual(second.already_processed_count, 1)
        with self.session_factory() as db:
            state = db.query(StudentKnowledgeState).one()
            self.assertEqual(state.attempt_count, 1)
            self.assertEqual(state.correct_count, 1)
            self.assertEqual(db.query(KnowledgeStateEvent).count(), 1)

    def test_practice_uses_quiz_question_knowledge_point_association(self):
        with self.session_factory() as db:
            question = (
                db.query(QuizQuestion).filter(QuizQuestion.id == "question-1").one()
            )
            question.question_text = "Which statement is correct?"
            question.knowledge_point_id = "kp-1"
            db.commit()

        record = PracticeService().create_practice_record(
            user_id="user-1",
            project_id="project-1",
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id=None,
            topic="Which statement is correct?",
            user_answer="a",
            correct_answer="a",
            was_correct=True,
        )
        result = KnowledgeStateService().refresh_states("project-1", "user-1")

        self.assertEqual(record.knowledge_point_id, "kp-1")
        self.assertEqual(result.processed_count, 1)
        self.assertAlmostEqual(result.updated_states[0].mastery_score, 58.59, places=2)

    def test_legacy_quiz_question_matches_knowledge_point_from_content(self):
        with self.session_factory() as db:
            question = (
                db.query(QuizQuestion).filter(QuizQuestion.id == "question-1").one()
            )
            question.question_text = "Which Transactions property guarantees atomicity?"
            question.knowledge_point_id = None
            db.commit()

        record = PracticeService().create_practice_record(
            user_id="user-1",
            project_id="project-1",
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id=None,
            topic="Which Transactions property guarantees atomicity?",
            user_answer="a",
            correct_answer="a",
            was_correct=True,
        )

        self.assertEqual(record.knowledge_point_id, "kp-1")

    def test_refresh_backfills_unmatched_historical_practice(self):
        with self.session_factory() as db:
            db.add_all(
                [
                    PracticeRecord(
                        id="legacy-practice",
                        user_id="user-1",
                        project_id="project-1",
                        knowledge_point_id=None,
                        item_type="quiz",
                        item_id="question-1",
                        topic="Transactions guarantee atomicity",
                        user_answer="a",
                        correct_answer="a",
                        was_correct=True,
                    ),
                    PracticeRecord(
                        id="legacy-practice-2",
                        user_id="user-1",
                        project_id="project-1",
                        knowledge_point_id=None,
                        item_type="quiz",
                        item_id="question-1",
                        topic="Transactions preserve consistency",
                        user_answer="a",
                        correct_answer="a",
                        was_correct=True,
                    ),
                ]
            )
            db.commit()

        result = KnowledgeStateService().refresh_states("project-1", "user-1")

        with self.session_factory() as db:
            record = db.query(PracticeRecord).filter_by(id="legacy-practice").one()
            self.assertEqual(record.knowledge_point_id, "kp-1")
            self.assertEqual(db.query(StudentKnowledgeState).count(), 1)
            self.assertAlmostEqual(
                db.query(StudentKnowledgeState).one().mastery_score, 95.12, places=2
            )
        self.assertEqual(result.processed_count, 2)
        self.assertEqual(result.unmatched_count, 0)

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
        result = KnowledgeStateService().refresh_states("project-1", "user-1")

        self.assertEqual(record.knowledge_point_id, "kp-1")
        self.assertEqual(result.processed_count, 1)
        self.assertAlmostEqual(result.updated_states[0].mastery_score, 14.67, places=2)
        self.assertEqual(result.updated_states[0].status, "insufficient_evidence")

    def test_knowledge_graph_includes_relations_and_mastery(self):
        CourseService().create_knowledge_point_relation(
            course_id="course-1",
            owner_id="user-1",
            source_knowledge_point_id="kp-1",
            target_knowledge_point_id="kp-2",
            relation_type="prerequisite",
            strength=0.75,
        )
        KnowledgeStateService().upsert_state(
            project_id="project-1",
            knowledge_point_id="kp-1",
            user_id="user-1",
            mastery_score=72,
            confidence=0.7,
            trend="up",
            status="learning",
            attempt_count=4,
            correct_count=3,
            evidence=[],
            last_practiced_at=None,
        )

        graph = KnowledgeStateService().get_knowledge_graph("project-1", "user-1")

        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.edges), 1)
        transaction_node = next(node for node in graph.nodes if node.id == "kp-1")
        self.assertEqual(transaction_node.mastery_score, 72)
        self.assertEqual(graph.edges[0].source, "kp-1")
        self.assertEqual(graph.edges[0].target, "kp-2")

    def test_profile_refresh_infers_fields_from_practice_and_states(self):
        PracticeService().create_practice_record(
            user_id="user-1",
            project_id="project-1",
            item_type="quiz",
            item_id="question-1",
            knowledge_point_id="kp-1",
            topic="Transactions",
            user_answer="b",
            correct_answer="a",
            was_correct=False,
        )
        KnowledgeStateService().refresh_states("project-1", "user-1")

        profile = LearnerProfileService().refresh_profile("project-1", "user-1")

        self.assertIn("current_course", profile.profile_data)
        self.assertIn("learning_progress", profile.profile_data)
        self.assertIn("common_error_types", profile.profile_data)
        self.assertIn("current_learning_state", profile.profile_data)
        self.assertEqual(profile.profile_data["current_course"]["value"], "Databases")
        self.assertEqual(
            profile.profile_data["learning_progress"]["value"]["attempt_count"], 1
        )
        revisions = LearnerProfileService().list_revisions("project-1", "user-1")
        self.assertTrue(
            any(revision.source_type == "auto_refresh" for revision in revisions)
        )


if __name__ == "__main__":
    unittest.main()
