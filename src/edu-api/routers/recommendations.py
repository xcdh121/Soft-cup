from auth import get_current_user
from dependencies import get_agent_orchestration_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.agent_orchestration import (
    RecommendationGenerateRequest,
    RecommendationsResponse,
)
from edu_core.schemas.users import UserDto
from edu_core.services import AgentOrchestrationService
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/recommendations", tags=["recommendations"]
)


@router.get("", response_model=list[dict])
async def list_recommendations(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return service.list_recommendations(current_user.id, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/generate",
    response_model=RecommendationsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_recommendations(
    project_id: str,
    request: RecommendationGenerateRequest | None = None,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return await service.generate_recommendations(
            user_id=current_user.id,
            project_id=project_id,
            diagnosis_id=request.diagnosis_id if request else None,
            trigger=request.trigger if request else None,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
