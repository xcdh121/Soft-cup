from edu_core.schemas.agent_orchestration import (
    AgentName,
    AgentResult,
    AgentRunContext,
    RunStatus,
)

from edu_ai.agents.orchestration.base import BaseOrchestrationAgent


class ProfileAgent(BaseOrchestrationAgent):
    agent_name = AgentName.PROFILE
    artifact_key = "profile"

    async def run(self, context: AgentRunContext) -> AgentResult:
        profile = context.context.learner_profile or {}
        profile_data = profile.get("profile_data", profile)
        completeness = self._score_completeness(profile_data)
        missing_fields = [
            field
            for field in ("learning_style", "preferred_resource_type", "preferred_pace")
            if not profile_data.get(field)
        ]

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
                "learning_style": profile_data.get("learning_style", "unknown"),
                "preferred_resource_type": profile_data.get(
                    "preferred_resource_type", []
                ),
                "preferred_pace": profile_data.get("preferred_pace"),
            },
        }

        return AgentResult(
            agent_name=self.agent_name,
            status=RunStatus.COMPLETED,
            summary="已读取学习画像并生成偏好上下文"
            if profile
            else "未发现学习画像，已使用缺省偏好上下文",
            result=result,
            reason_codes=["profile_loaded" if profile else "profile_missing"],
            reason_text=["学习画像可用于个性化诊断和推荐"]
            if profile
            else ["画像接口尚未提供有效数据，后续 Agent 将降级运行"],
        )

    def _score_completeness(self, profile_data: dict) -> float:
        fields = ("learning_style", "preferred_resource_type", "preferred_pace")
        if not profile_data:
            return 0.0
        present = sum(1 for field in fields if profile_data.get(field))
        return round(present / len(fields), 2)
