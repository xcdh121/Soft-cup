"""Router for practice record operations."""

from auth import get_current_user
from dependencies import get_knowledge_state_service, get_practice_service
from edu_core.schemas.practice import PracticeRecordDto
from edu_core.schemas.users import UserDto
from edu_core.services import KnowledgeStateService, PracticeService
from fastapi import APIRouter, Depends, HTTPException

from routers.schemas import PracticeRecordBatchCreate, PracticeRecordCreate

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/practice-records", tags=["practice-records"]
)


@router.get("", response_model=list[PracticeRecordDto])
async def list_practice_records(
    project_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
):
    """List practice records for a project."""
    try:
        return service.list_practice_records(
            user_id=current_user.id,
            project_id=project_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=PracticeRecordDto, status_code=201)
async def create_practice_record(
    project_id: str,
    record: PracticeRecordCreate,
    current_user: UserDto = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
    knowledge_state_service: KnowledgeStateService = Depends(
        get_knowledge_state_service
    ),
):
    """Create a single practice record."""
    try:
        created_record = service.create_practice_record(
            user_id=current_user.id,
            project_id=project_id,
            **record.model_dump(),
        )
        try:
            knowledge_state_service.refresh_states(project_id, current_user.id)
        except ValueError:
            # Legacy projects without a course can still keep practice records.
            pass
        return created_record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=list[PracticeRecordDto], status_code=201)
async def create_practice_records_batch(
    project_id: str,
    batch: PracticeRecordBatchCreate,
    current_user: UserDto = Depends(get_current_user),
    service: PracticeService = Depends(get_practice_service),
    knowledge_state_service: KnowledgeStateService = Depends(
        get_knowledge_state_service
    ),
):
    """Create multiple practice records."""
    try:
        records_data = [r.model_dump() for r in batch.practice_records]
        created_records = service.create_practice_records_batch(
            user_id=current_user.id,
            project_id=project_id,
            practice_records_data=records_data,
        )
        try:
            knowledge_state_service.refresh_states(project_id, current_user.id)
        except ValueError:
            # Legacy projects without a course can still keep practice records.
            pass
        return created_records
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
