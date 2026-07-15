"""Router for project-scoped student knowledge states."""

from auth import get_current_user
from dependencies import get_knowledge_state_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.knowledge_states import (
    KnowledgeGraphDto,
    KnowledgeStateDto,
    KnowledgeStateRefreshDto,
)
from edu_core.services import KnowledgeStateService
from fastapi import APIRouter, Depends, HTTPException

from routers.schemas import KnowledgeStateUpsert


router = APIRouter(
    prefix="/api/v1/projects/{project_id}/knowledge-states",
    tags=["knowledge-states"],
)
knowledge_graph_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/knowledge-graph",
    tags=["knowledge-graph"],
)


@knowledge_graph_router.get("", response_model=KnowledgeGraphDto)
async def get_knowledge_graph(
    project_id: str,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    try:
        return service.get_knowledge_graph(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/refresh",
    response_model=KnowledgeStateRefreshDto,
)
async def refresh_knowledge_states(
    project_id: str,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    try:
        return service.refresh_states(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[KnowledgeStateDto])
async def list_knowledge_states(
    project_id: str,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    try:
        return service.list_states(project_id, current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{knowledge_point_id}",
    response_model=KnowledgeStateDto,
)
async def get_knowledge_state(
    project_id: str,
    knowledge_point_id: str,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    try:
        return service.get_state(
            project_id, knowledge_point_id, current_user.id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put(
    "/{knowledge_point_id}",
    response_model=KnowledgeStateDto,
)
async def upsert_knowledge_state(
    project_id: str,
    knowledge_point_id: str,
    state: KnowledgeStateUpsert,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    try:
        return service.upsert_state(
            project_id=project_id,
            knowledge_point_id=knowledge_point_id,
            user_id=current_user.id,
            **state.model_dump(),
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
