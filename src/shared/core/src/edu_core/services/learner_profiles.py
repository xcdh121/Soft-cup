"""Service for project-scoped learner profiles."""

import re
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from edu_db.models import (
    Chat,
    ChatMessage,
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
    "preferred_knowledge_points",
    "common_error_types",
    "practical_ability",
    "available_study_time",
    "current_learning_state",
)

CHAT_PROFILE_FIELDS = frozenset(
    {
        "major_background",
        "education_level",
        "learning_goal",
        "resource_preference",
        "preferred_knowledge_points",
        "available_study_time",
    }
)

RESOURCE_PREFERENCE_LIMIT = 3
PREFERRED_KNOWLEDGE_POINT_LIMIT = 5


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

    def apply_chat_inferences(
        self,
        project_id: str,
        user_id: str,
        message_id: str,
        message_text: str,
        inferred_fields: dict,
    ) -> LearnerProfileDto | None:
        """Merge profile facts extracted from one user chat message.

        Chat is intentionally limited to background, goal, and preference fields.
        Knowledge mastery and learning-state fields remain owned by practice/KT.
        """
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

            old_data = dict(profile.profile_data or {}) if profile else {}
            new_data = dict(old_data)
            changed = False
            now = datetime.now(timezone.utc).isoformat()

            for field_key, candidate in inferred_fields.items():
                if field_key not in CHAT_PROFILE_FIELDS or not isinstance(candidate, dict):
                    continue
                value = candidate.get("value")
                if value in (None, "", [], {}):
                    continue
                try:
                    confidence = min(1.0, max(0.0, float(candidate.get("confidence", 0))))
                except (TypeError, ValueError):
                    continue
                if confidence < 0.55:
                    continue

                candidate_status = (
                    "confirmed"
                    if candidate.get("status") == "confirmed"
                    else "inferred"
                )
                existing = old_data.get(field_key)
                existing_field = existing if isinstance(existing, dict) else {}
                existing_value = (
                    existing_field.get("value")
                    if "value" in existing_field
                    else existing
                )
                if field_key == "resource_preference":
                    value = self._merge_resource_preferences(existing_value, value)
                elif field_key == "preferred_knowledge_points":
                    value = self._merge_distinct_values(
                        existing_value,
                        value,
                        limit=PREFERRED_KNOWLEDGE_POINT_LIMIT,
                    )
                # Values written manually before field metadata was introduced are
                # treated as confirmed so an LLM inference cannot silently replace them.
                existing_status = existing_field.get(
                    "status", "confirmed" if existing is not None else "missing"
                )
                try:
                    existing_confidence = float(existing_field.get("confidence", 0.5))
                except (TypeError, ValueError):
                    existing_confidence = 0.5

                if existing_status == "confirmed" and candidate_status != "confirmed":
                    continue
                if (
                    existing_value != value
                    and candidate_status != "confirmed"
                    and existing_confidence > confidence
                ):
                    continue

                evidence = list(existing_field.get("evidence") or [])
                if any(item.get("source_id") == message_id for item in evidence):
                    continue
                evidence.append(
                    {
                        "source_type": "chat_message",
                        "source_id": message_id,
                        "excerpt": message_text.strip()[:240],
                    }
                )
                merged = {
                    "value": value,
                    "confidence": max(existing_confidence, confidence)
                    if existing_value == value
                    else confidence,
                    "status": "confirmed"
                    if "confirmed" in (existing_status, candidate_status)
                    else "inferred",
                    "evidence": evidence[-20:],
                    "updated_at": now,
                }
                if self._revision_value(existing) != self._revision_value(merged):
                    new_data[field_key] = merged
                    changed = True

            if not changed:
                return LearnerProfileDto.model_validate(profile) if profile else None

            if profile is None:
                profile = LearnerProfile(
                    id=str(uuid4()),
                    project_id=project_id,
                    user_id=user_id,
                )
                db.add(profile)
            profile.profile_data = new_data
            profile.last_refreshed_at = datetime.now(timezone.utc)
            self._record_revisions(
                db,
                profile,
                old_data,
                new_data,
                source_type="chat_message",
                source_id=message_id,
            )
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

    @staticmethod
    def _merge_resource_preferences(existing, candidate) -> list[str]:
        """Keep stable resource-format preferences without unbounded growth."""

        return LearnerProfileService._merge_distinct_values(
            existing,
            candidate,
            limit=RESOURCE_PREFERENCE_LIMIT,
        )

    @staticmethod
    def _merge_distinct_values(existing, candidate, *, limit: int) -> list[str]:
        """Merge ordered string values while keeping the newest bounded set."""

        def as_items(value) -> list[str]:
            values = value if isinstance(value, list) else [value]
            return [
                str(item).strip()
                for item in values
                if item is not None and str(item).strip()
            ]

        merged: list[str] = []
        for item in [*as_items(existing), *as_items(candidate)]:
            if item not in merged:
                merged.append(item)
        return merged[-limit:]

    @staticmethod
    def extract_explicit_chat_fields(message_text: str) -> dict:
        """Extract unambiguous first-person goals before asynchronous LLM enrichment.

        This deliberately covers only explicit phrasing. It gives the profile an
        immediate, deterministic update for common messages such as
        ``我想学习最短路径`` while the background extractor handles richer prose.
        """
        text = " ".join(str(message_text or "").strip().split())
        if not text:
            return {}

        topic: str | None = None
        goal: str | None = None
        chinese_patterns = (
            r"(?:我想|我希望|我打算|我计划|我的目标是)\s*(学习|掌握|了解|弄懂|复习)\s*([^。！？!?，,；;]{1,80})",  # noqa: RUF001
            r"(?:我想|我希望|我打算|我计划)\s*([^。！？!?，,；;]{1,80})",  # noqa: RUF001
        )
        for pattern in chinese_patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            if match.lastindex == 2:
                action = match.group(1).strip()
                topic = match.group(2).strip()
                goal = f"{action}{topic}"
            else:
                goal = match.group(1).strip()
            break

        if goal is None:
            english_match = re.search(
                r"\bI\s+(?:want|hope|plan|intend)\s+to\s+"
                r"(learn|master|understand|review)\s+([^.!?;,]{1,80})",
                text,
                flags=re.IGNORECASE,
            )
            if english_match:
                action = english_match.group(1).lower()
                topic = english_match.group(2).strip()
                goal = f"{action} {topic}"

        if goal is None:
            return {}

        fields = {
            "learning_goal": {
                "value": goal,
                "confidence": 1.0,
                "status": "confirmed",
            }
        }
        if topic:
            fields["preferred_knowledge_points"] = {
                "value": [topic],
                "confidence": 1.0,
                "status": "confirmed",
            }
        return fields

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

    def confirm_field(
        self,
        project_id: str,
        user_id: str,
        field_key: str,
        value,
    ) -> LearnerProfileDto:
        if field_key not in PROFILE_FIELDS:
            raise ValueError(f"Unknown learner profile field: {field_key}")
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = self._get_profile(db, project_id, user_id)
            old_data = dict(profile.profile_data or {})
            new_data = {
                **old_data,
                field_key: {
                    "value": value,
                    "confidence": 1.0,
                    "status": "confirmed",
                    "evidence": [
                        {
                            "source_type": "user_confirmation",
                            "source_id": user_id,
                        }
                    ],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            profile.profile_data = new_data
            self._record_revisions(
                db,
                profile,
                old_data,
                new_data,
                source_type="user_confirmation",
                source_id=user_id,
            )
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

    def revert_revision(
        self, project_id: str, user_id: str, revision_id: str
    ) -> LearnerProfileDto:
        with self._get_db_session() as db:
            self._get_owned_project(db, project_id, user_id)
            profile = self._get_profile(db, project_id, user_id)
            revision = (
                db.query(LearnerProfileRevision)
                .filter(
                    LearnerProfileRevision.id == revision_id,
                    LearnerProfileRevision.profile_id == profile.id,
                )
                .first()
            )
            if not revision:
                raise NotFoundError(f"Learner profile revision {revision_id} not found")
            old_data = dict(profile.profile_data or {})
            new_data = dict(old_data)
            if revision.old_value is None:
                new_data.pop(revision.field_key, None)
            else:
                new_data[revision.field_key] = revision.old_value
            profile.profile_data = new_data
            self._record_revisions(
                db,
                profile,
                old_data,
                new_data,
                source_type="revision_revert",
                source_id=revision.id,
            )
            self._update_completeness(profile)
            db.commit()
            db.refresh(profile)
            return LearnerProfileDto.model_validate(profile)

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
            if LearnerProfileService._revision_value(
                old_value
            ) == LearnerProfileService._revision_value(new_value):
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
    def _revision_value(value):
        """Ignore refresh timestamps when deciding whether a field really changed."""
        if not isinstance(value, dict):
            return value
        return {key: item for key, item in value.items() if key != "updated_at"}

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

        inferred.update(
            self._infer_explicit_chat_data(db, project.id, user_id)
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

    def _infer_explicit_chat_data(
        self, db, project_id: str, user_id: str
    ) -> dict:
        """Backfill explicit goals from existing project conversations on refresh."""
        messages = (
            db.query(ChatMessage)
            .join(Chat, Chat.id == ChatMessage.chat_id)
            .filter(
                Chat.project_id == project_id,
                Chat.user_id == user_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(100)
            .all()
        )
        latest_goal = None
        preferred_points: list[str] = []
        preferred_evidence: list[dict] = []
        for message in messages:
            message_text = " ".join(
                str(part.text_content or "").strip()
                for part in message.parts
                if part.part_type == "text" and str(part.text_content or "").strip()
            )
            fields = self.extract_explicit_chat_fields(message_text)
            if not fields:
                continue
            evidence = {
                "source_type": "chat_message",
                "source_id": message.id,
                "excerpt": message_text[:240],
            }
            if latest_goal is None and "learning_goal" in fields:
                latest_goal = self._field(
                    fields["learning_goal"]["value"],
                    1.0,
                    [evidence],
                )
                latest_goal["status"] = "confirmed"
            for point in fields.get("preferred_knowledge_points", {}).get(
                "value", []
            ):
                if len(preferred_points) >= PREFERRED_KNOWLEDGE_POINT_LIMIT:
                    break
                if point not in preferred_points:
                    preferred_points.append(point)
                    preferred_evidence.append(evidence)

        inferred = {}
        if latest_goal is not None:
            inferred["learning_goal"] = latest_goal
        if preferred_points:
            field = self._field(
                list(reversed(preferred_points)),
                1.0,
                list(reversed(preferred_evidence)),
            )
            field["status"] = "confirmed"
            inferred["preferred_knowledge_points"] = field
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
