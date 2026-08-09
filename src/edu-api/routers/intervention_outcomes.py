from auth import get_current_user
from dependencies import get_learning_closed_loop_service
from edu_core.schemas.closed_loop import InterventionOutcomeDto
from edu_core.schemas.users import UserDto
from edu_core.services import LearningClosedLoopService
from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/intervention-outcomes",
    tags=["intervention-outcomes"],
)


@router.get("", response_model=list[InterventionOutcomeDto])
async def list_intervention_outcomes(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: LearningClosedLoopService = Depends(
        get_learning_closed_loop_service
    ),
):
    return service.list_intervention_outcomes(project_id, current_user.id)


@router.get("/{outcome_id}", response_model=InterventionOutcomeDto)
async def get_intervention_outcome(
    project_id: str,
    outcome_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: LearningClosedLoopService = Depends(
        get_learning_closed_loop_service
    ),
):
    return service.get_intervention_outcome(
        project_id, outcome_id, current_user.id
    )
