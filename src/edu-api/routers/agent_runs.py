from auth import get_current_user
from dependencies import get_agent_orchestration_service
from edu_core.schemas.agent_orchestration import AgentEvent, AgentRunDetail
from edu_core.schemas.users import UserDto
from edu_core.services import AgentOrchestrationService
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/agent-runs", tags=["agent-runs"])


@router.get("/{run_id}", response_model=AgentRunDetail)
def get_run(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_agent_run(current_user.id, run_id)


@router.get("/{run_id}/events", response_model=list[AgentEvent])
def get_run_events(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_agent_run_events(current_user.id, run_id)


@router.get("/{run_id}/skill-executions", response_model=list[dict])
def get_skill_executions(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_skill_executions(current_user.id, run_id)


@router.get("/{run_id}/tool-calls", response_model=list[dict])
def get_tool_calls(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_tool_calls(current_user.id, run_id)
