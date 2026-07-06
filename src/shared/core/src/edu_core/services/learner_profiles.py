"""Service for project-scoped learner profiles."""

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from edu_db.models import (
    Course,
    KnowledgePoint,
    LearnerProfile,
    LearnerProfileRevision,
    PracticeRecord,
    Project,
    StudentKnowledgeState,
)
from edu_db.session import get_session_factory

from edu_core.exceptions import NotFoundError
from edu_core.schemas.learner_profiles import (
    LearnerProfileDto,
    LearnerProfileRevisionDto,
)


PROFILE_FIELDS = (
    "major_background",
    "education_level",
    "current_course",
    "learning_goal",
    "knowledge_background",
    "learning_progress",
    "resource_preference",
    "cognitive_style",
    "common_error_types",
    "practical_ability",
    "available_study_time",
    "current_learning_state",
)


class LearnerProfileService:
    """Read and update one profile per user and project."""

    def get_profile(
        self, project_id: str, user_id: str
    ) -> LearnerProfileDto:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = self._get_profile(db, project_id, user_id)
            return LearnerProfileDto.model_validate(profile)

    def replace_profile(
        self, project_id: str, user_id: str, profile_data: dict
    ) -> LearnerProfileDto:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = (
                db.query(LearnerProfile)
                .filter(
                    LearnerProfile.project_id == project_id,
                    LearnerProfile.user_id == user_id,
                )
                .first()
            )
            if profile is None:
                profile = LearnerProfile(
                    id=str(uuid4()),
                    project_id=project_id,
                    user_id=user_id,
                )
                db.add(profile)

            old_data = dict(profile.profile_data or {})
            profile.profile_data = profile_data
            self._record_revisions(db, profile, old_data, profile_data)
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

    def patch_profile(
        self, project_id: str, user_id: str, profile_data: dict
    ) -> LearnerProfileDto:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = self._get_profile(db, project_id, user_id)
            old_data = dict(profile.profile_data or {})
            profile.profile_data = {
                **old_data,
                **profile_data,
            }
            self._record_revisions(
                db, profile, old_data, profile.profile_data
            )
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

    def refresh_profile(
        self, project_id: str, user_id: str
    ) -> LearnerProfileDto:
        with self._get_db_session() as db:
            project = self._get_owned_project(db, project_id, user_id)
            profile = (
                db.query(LearnerProfile)
                .filter(
                    LearnerProfile.project_id == project_id,
                    LearnerProfile.user_id == user_id,
                )
                .first()
            )
            if profile is None:
                profile = LearnerProfile(
                    id=str(uuid4()),
                    project_id=project_id,
                    user_id=user_id,
                )
                db.add(profile)

            old_data = dict(profile.profile_data or {})
            inferred_data = self._infer_profile_data(db, project, user_id)
            profile.profile_data = {
                **old_data,
                **inferred_data,
            }
            profile.last_refreshed_at = datetime.now(timezone.utc)
            self._record_revisions(
                db,
                profile,
                old_data,
                profile.profile_data,
                source_type="auto_refresh",
                source_id=project_id,
            )
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

    def list_revisions(
        self, project_id: str, user_id: str
    ) -> list[LearnerProfileRevisionDto]:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = self._get_profile(db, project_id, user_id)
            revisions = (
                db.query(LearnerProfileRevision)
                .filter(LearnerProfileRevision.profile_id == profile.id)
                .order_by(LearnerProfileRevision.created_at.desc())
                .all()
            )
            return [
                LearnerProfileRevisionDto.model_validate(revision)
                for revision in revisions
            ]

    @staticmethod
    def _record_revisions(
        db,
        profile: LearnerProfile,
        old_data: dict,
        new_data: dict,
        source_type: str = "manual",
        source_id: str | None = None,
    ) -> None:
        for field_key in sorted(set(old_data) | set(new_data)):
            old_value = old_data.get(field_key)
            new_value = new_data.get(field_key)
            if old_value == new_value:
                continue
            confidence = (
                new_value.get("confidence")
                if isinstance(new_value, dict)
                else None
            )
            db.add(
                LearnerProfileRevision(
                    id=str(uuid4()),
                    profile_id=profile.id,
                    field_key=field_key,
                    old_value=old_value,
                    new_value=new_value,
                    confidence=confidence,
                    source_type=source_type,
                    source_id=source_id,
                )
            )

    @staticmethod
    def _field(value, confidence: float, evidence: list[dict]):
        return {
            "value": value,
            "confidence": confidence,
            "status": "inferred",
            "evidence": evidence,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _infer_profile_data(
        self, db, project: Project, user_id: str
    ) -> dict:
        records = (
            db.query(PracticeRecord)
            .filter(
                PracticeRecord.project_id == project.id,
                PracticeRecord.user_id == user_id,
            )
            .order_by(PracticeRecord.created_at.desc())
            .all()
        )
        states = (
            db.query(StudentKnowledgeState, KnowledgePoint)
            .join(KnowledgePoint, StudentKnowledgeState.knowledge_point_id == KnowledgePoint.id)
            .filter(
                StudentKnowledgeState.user_id == user_id,
                KnowledgePoint.course_id == project.course_id,
            )
            .all()
            if project.course_id
            else []
        )
        course = (
            db.query(Course).filter(Course.id == project.course_id).first()
            if project.course_id
            else None
        )

        inferred = {}
        if course:
            inferred["current_course"] = self._field(
                course.name,
                0.9,
                [{"source_type": "project", "source_id": project.id}],
            )

        total_attempts = len(records)
        correct_attempts = sum(1 for record in records if record.was_correct)
        if total_attempts:
            accuracy = correct_attempts / total_attempts
            inferred["learning_progress"] = self._field(
                {
                    "attempt_count": total_attempts,
                    "correct_count": correct_attempts,
                    "accuracy": round(accuracy, 2),
                },
                min(0.95, 0.4 + total_attempts * 0.05),
                [{"source_type": "practice_records", "count": total_attempts}],
            )

            wrong_topics = {}
            for record in records:
                if not record.was_correct:
                    wrong_topics[record.topic] = wrong_topics.get(record.topic, 0) + 1
            if wrong_topics:
                common_errors = [
                    {"topic": topic, "count": count}
                    for topic, count in sorted(
                        wrong_topics.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:5]
                ]
                inferred["common_error_types"] = self._field(
                    common_errors,
                    min(0.9, 0.4 + sum(wrong_topics.values()) * 0.08),
                    [{"source_type": "practice_records", "count": sum(wrong_topics.values())}],
                )

        if states:
            mastery_scores = [state.mastery_score for state, _ in states]
            average_mastery = sum(mastery_scores) / len(mastery_scores)
            weak_points = [
                point.name
                for state, point in states
                if state.mastery_score < 60
            ][:5]
            inferred["knowledge_background"] = self._field(
                {
                    "average_mastery": round(average_mastery, 2),
                    "tracked_knowledge_points": len(states),
                    "weak_points": weak_points,
                },
                min(0.95, 0.45 + len(states) * 0.08),
                [{"source_type": "student_knowledge_states", "count": len(states)}],
            )
            inferred["current_learning_state"] = self._field(
                self._summarize_learning_state(average_mastery, weak_points),
                min(0.95, 0.45 + len(states) * 0.08),
                [{"source_type": "student_knowledge_states", "count": len(states)}],
            )

        return inferred

    @staticmethod
    def _summarize_learning_state(
        average_mastery: float, weak_points: list[str]
    ) -> str:
        if average_mastery >= 80 and not weak_points:
            return "整体掌握稳定，可进入进阶学习"
        if average_mastery >= 60:
            return "基础掌握中等，需要针对薄弱知识点巩固"
        return "当前仍处于补基础阶段，需要优先处理高频错误和低掌握知识点"

    @staticmethod
    def _update_completeness(profile: LearnerProfile) -> None:
        completed = sum(
            1
            for field in PROFILE_FIELDS
            if LearnerProfileService._has_value(
                (profile.profile_data or {}).get(field)
            )
        )
        profile.completeness_score = completed / len(PROFILE_FIELDS)
        profile.status = (
            "complete"
            if profile.completeness_score == 1
            else "incomplete"
        )

    @staticmethod
    def _has_value(field_data) -> bool:
        value = (
            field_data.get("value")
            if isinstance(field_data, dict) and "value" in field_data
            else field_data
        )
        return value not in (None, "", [], {})

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

    @staticmethod
    def _get_profile(
        db, project_id: str, user_id: str
    ) -> LearnerProfile:
        profile = (
            db.query(LearnerProfile)
            .filter(
                LearnerProfile.project_id == project_id,
                LearnerProfile.user_id == user_id,
            )
            .first()
        )
        if not profile:
            raise NotFoundError(
                f"Learner profile for project {project_id} not found"
            )
        return profile

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
