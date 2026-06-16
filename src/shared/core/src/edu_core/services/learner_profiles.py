"""Service for project-scoped learner profiles."""

from contextlib import contextmanager
from uuid import uuid4

from edu_db.models import LearnerProfile, LearnerProfileRevision, Project
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
                    source_type="manual",
                )
            )

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
