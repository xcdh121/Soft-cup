from abc import ABC, abstractmethod

from edu_core.schemas.agent_orchestration import AgentName, AgentResult, AgentRunContext


class BaseOrchestrationAgent(ABC):
    agent_name: AgentName
    artifact_key: str

    @abstractmethod
    async def run(self, context: AgentRunContext) -> AgentResult:
        """Run the agent and return a structured result."""
