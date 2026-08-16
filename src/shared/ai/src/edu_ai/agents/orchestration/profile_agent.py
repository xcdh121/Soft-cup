from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    FieldStatus,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class ProfileAgent(BaseOrchestrationAgent):
    agent_name = AgentName.PROFILE
    artifact_key = "profile"

    canonical_fields = (
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
    recommendation_fields = (
        "major_background",
        "current_course",
        "learning_goal",
        "knowledge_background",
        "resource_preference",
        "preferred_knowledge_points",
        "available_study_time",
    )

    async def run(self, context: AgentRunContext) -> AgentResult:
        profile = context.context.learner_profile or {}
        raw_profile_data = profile.get("profile_data", profile)
        profile_data = {
            field: self._field_value(raw_profile_data.get(field))
            for field in self.canonical_fields
            if self._has_value(self._field_value(raw_profile_data.get(field)))
        }
        stored_completeness = profile.get("completeness_score")
        completeness = (
            float(stored_completeness)
            if isinstance(stored_completeness, int | float)
            else self._score_completeness(profile_data)
        )
        missing_fields = [
            field
            for field in self.recommendation_fields
            if not self._has_value(profile_data.get(field))
        ]

        preferred_knowledge_points = profile_data.get(
            "preferred_knowledge_points", []
        )
        resource_preference = profile_data.get("resource_preference", [])
        available_study_time = profile_data.get("available_study_time")

        result = {
            "profile_snapshot": {
                "id": profile.get("id"),
                "status": profile.get("status", "missing" if not profile else "active"),
                "profile_data": profile_data,
                "completeness_score": completeness,
            },
            "profile_missing_fields": missing_fields,
            "profile_update_suggestions": [],
            "profile_summary": {
                **profile_data,
                # Compatibility aliases for consumers not yet migrated to the
                # canonical learner-profile field names.
                "preferred_topics": preferred_knowledge_points,
                "preferred_resource_type": resource_preference,
                "preferred_pace": available_study_time,
            },
        }

        if profile_data:
            return AgentResult(
                agent_name=self.agent_name,
                status=RunStatus.COMPLETED,
                summary="Loaded learner profile context.",
                result=result,
                reason_codes=["profile_loaded"],
                reason_text=[
                    "Learner profile is available for personalized diagnosis and recommendations."
                ],
                confidence=max(0.5, completeness),
                field_status=FieldStatus.CONFIRMED,
            )

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="Learner profile is missing; default preference context was used.",
            result=result,
            reason_codes=["profile_missing"],
            reason_text=[
                "No learner profile data was available, so later agents should avoid strong personalization claims."
            ],
            confidence=0.3,
            field_status=FieldStatus.MISSING,
            fallback_used=True,
            fallback_reason="profile_missing",
        )

    @staticmethod
    def _field_value(field_data):
        if isinstance(field_data, dict) and "value" in field_data:
            return field_data.get("value")
        return field_data

    @staticmethod
    def _has_value(value) -> bool:
        return value not in (None, "", [], {})

    def _score_completeness(self, profile_data: dict) -> float:
        if not profile_data:
            return 0.0
        present = sum(
            1
            for field in self.canonical_fields
            if self._has_value(profile_data.get(field))
        )
        return round(present / len(self.canonical_fields), 2)
