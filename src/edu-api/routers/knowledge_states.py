"""Router for project-scoped student knowledge states."""

from datetime import datetime

from auth import get_current_user
from dependencies import get_knowledge_state_service
from edu_core.exceptions import NotFoundError
from edu_core.schemas.knowledge_states import (
    KnowledgeGraphDto,
    KnowledgeStateDto,
    KnowledgeStateEventDto,
    KnowledgeStateRefreshDto,
)
from edu_core.schemas.closed_loop import (
    KTMetricDto,
    KnowledgeStateReplayDto,
    KnowledgeStateReplayRequest,
)
from edu_core.services import KnowledgeStateService
from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get(
    "/{knowledge_point_id}/events",
    response_model=list[KnowledgeStateEventDto],
)
async def list_knowledge_state_events(
    project_id: str,
    knowledge_point_id: str,
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = None,
    event_type: str | None = None,
    model_version: str | None = None,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    return service.list_events(
        project_id,
        knowledge_point_id,
        current_user.id,
        limit=limit,
        before=before,
        event_type=event_type,
        model_version=model_version,
    )


@router.post("/replay", response_model=KnowledgeStateReplayDto)
async def replay_knowledge_states(
    project_id: str,
    request: KnowledgeStateReplayRequest,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    return service.replay_states(
        project_id,
        current_user.id,
        knowledge_point_id=request.knowledge_point_id,
        dry_run=request.dry_run,
    )


@router.get("/metrics/summary", response_model=KTMetricDto)
async def get_knowledge_tracing_metrics(
    project_id: str,
    current_user=Depends(get_current_user),
    service: KnowledgeStateService = Depends(get_knowledge_state_service),
):
    return service.get_metrics(project_id, current_user.id)


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
