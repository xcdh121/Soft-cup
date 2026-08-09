from auth import get_current_user
from dependencies import get_kt_configuration_service
from edu_core.schemas.closed_loop import (
    ItemKnowledgePointMappingCreate,
    KTParameterSetCreate,
    KTParameterSetDto,
    KnowledgePointKTOverrideCreate,
)
from edu_core.schemas.users import UserDto
from edu_core.services import KTConfigurationService
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1/kt", tags=["knowledge-tracing-config"])


def require_admin(user: UserDto) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")


@router.get("/parameter-sets", response_model=list[KTParameterSetDto])
async def list_parameter_sets(
    current_user: UserDto = Depends(get_current_user),
    service: KTConfigurationService = Depends(get_kt_configuration_service),
):
    require_admin(current_user)
    return service.list_parameter_sets()


@router.post(
    "/parameter-sets",
    response_model=KTParameterSetDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_parameter_set(
    request: KTParameterSetCreate,
    current_user: UserDto = Depends(get_current_user),
    service: KTConfigurationService = Depends(get_kt_configuration_service),
):
    require_admin(current_user)
    return service.create_parameter_set(request, current_user.id)


@router.post(
    "/parameter-sets/{parameter_set_id}/activate",
    response_model=KTParameterSetDto,
)
async def activate_parameter_set(
    parameter_set_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: KTConfigurationService = Depends(get_kt_configuration_service),
):
    require_admin(current_user)
    return service.activate_parameter_set(parameter_set_id)


@router.put("/knowledge-points/{knowledge_point_id}/parameters")
async def set_knowledge_point_override(
    knowledge_point_id: str,
    request: KnowledgePointKTOverrideCreate,
    current_user: UserDto = Depends(get_current_user),
    service: KTConfigurationService = Depends(get_kt_configuration_service),
):
    require_admin(current_user)
    return service.set_knowledge_point_override(knowledge_point_id, request)


@router.put("/item-mappings")
async def upsert_item_mapping(
    request: ItemKnowledgePointMappingCreate,
    current_user: UserDto = Depends(get_current_user),
    service: KTConfigurationService = Depends(get_kt_configuration_service),
):
    require_admin(current_user)
    return service.upsert_item_mapping(request)
