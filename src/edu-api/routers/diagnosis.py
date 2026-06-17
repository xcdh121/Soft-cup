from auth import get_current_user
from dependencies import get_agent_orchestration_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    DiagnosisCreateRequest,
    DiagnosisResponse,
)
from edu_core.schemas.users import UserDto
from edu_core.services import AgentOrchestrationService
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/diagnosis", tags=["diagnosis"]
)


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_201_CREATED)
async def generate_diagnosis(
    project_id: str,
    request: DiagnosisCreateRequest | None = None,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        return await service.generate_diagnosis(
            user_id=current_user.id,
            project_id=project_id,
            trigger=request.trigger if request else None,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(
    project_id: str,
    diagnosis_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        diagnosis = service.get_diagnosis(diagnosis_id)
        if diagnosis.project_id != project_id or diagnosis.student_id != current_user.id:
            raise NotFoundError(f"Diagnosis {diagnosis_id} not found")
        return diagnosis
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{diagnosis_id}/trace", response_model=list[AgentEvent])
async def get_diagnosis_trace(
    project_id: str,
    diagnosis_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    try:
        diagnosis = service.get_diagnosis(diagnosis_id)
        if diagnosis.project_id != project_id or diagnosis.student_id != current_user.id:
            raise NotFoundError(f"Diagnosis {diagnosis_id} not found")
        return service.get_diagnosis_trace(diagnosis_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
