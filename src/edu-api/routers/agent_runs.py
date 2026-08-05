import asyncio
import json

from auth import get_current_user
from dependencies import get_agent_orchestration_service, get_queue_service
from edu_core.schemas.agent_orchestration import (
    AgentEvent,
    AgentRunCreateRequest,
    AgentRunDetail,
    AgentRunFeedbackRequest,
    AgentRunRetryRequest,
    AgentRunStepDetail,
    OrchestrationRunRequest,
)
from edu_core.schemas.users import UserDto
from edu_core.services import AgentOrchestrationService
from edu_queue.schemas import QueueTaskMessage, TaskType
from edu_queue.service import ArqQueueService, QueueService
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1", tags=["agent-runs"])


@router.post("/projects/{project_id}/agent-runs", response_model=AgentRunDetail)
def create_run(
    project_id: str,
    payload: AgentRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    queue_service: QueueService | ArqQueueService = Depends(get_queue_service),
):
    detail = service.create_agent_run(
        current_user.id,
        project_id,
        OrchestrationRunRequest(
            project_id=project_id,
            student_id=current_user.id,
            goal=payload.goal,
            trigger=payload.trigger,
            artifacts=payload.artifacts,
            meta=payload.meta,
            idempotency_key=payload.idempotency_key,
            budget=payload.budget,
        ),
    )
    background_tasks.add_task(
        queue_service.send_message,
        QueueTaskMessage(
            type=TaskType.AGENT_RUN,
            data={"run_id": detail.run_id, "user_id": current_user.id},
        ),
    )
    return detail


@router.get("/agent-runs/{run_id}", response_model=AgentRunDetail)
def get_run(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_agent_run(current_user.id, run_id)


@router.get("/agent-runs/{run_id}/events", response_model=list[AgentEvent])
def get_run_events(
    run_id: str,
    after_sequence: int = Query(0, ge=0),
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_agent_run_events(current_user.id, run_id, after_sequence)


@router.get("/agent-runs/{run_id}/steps", response_model=list[AgentRunStepDetail])
def get_run_steps(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.list_agent_run_steps(current_user.id, run_id)


@router.get("/agent-runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    after_sequence: int = Query(0, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    service.get_agent_run(current_user.id, run_id)
    cursor = max(after_sequence, int(last_event_id or 0))

    async def event_stream():
        nonlocal cursor
        idle_terminal_polls = 0
        while not await request.is_disconnected():
            events = service.get_agent_run_events(current_user.id, run_id, cursor)
            for event in events:
                cursor = event.sequence or cursor
                data = event.model_dump(mode="json")
                yield f"id: {cursor}\nevent: {event.event_type.value}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            detail = service.get_agent_run(current_user.id, run_id)
            if detail.status in {
                "completed",
                "partially_completed",
                "failed",
                "cancelled",
            }:
                idle_terminal_polls = idle_terminal_polls + 1 if not events else 0
                if idle_terminal_polls >= 1:
                    break
            if not events:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent-runs/{run_id}/cancel", response_model=AgentRunDetail)
def cancel_run(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.cancel_agent_run(current_user.id, run_id)


@router.post("/agent-runs/{run_id}/retry", response_model=AgentRunDetail)
def retry_run(
    run_id: str,
    payload: AgentRunRetryRequest,
    background_tasks: BackgroundTasks,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
    queue_service: QueueService | ArqQueueService = Depends(get_queue_service),
):
    detail = service.retry_agent_run(current_user.id, run_id, mode=payload.mode)
    background_tasks.add_task(
        queue_service.send_message,
        QueueTaskMessage(
            type=TaskType.AGENT_RUN,
            data={"run_id": detail.run_id, "user_id": current_user.id},
        ),
    )
    return detail


@router.post("/agent-runs/{run_id}/feedback", response_model=dict)
def add_run_feedback(
    run_id: str,
    payload: AgentRunFeedbackRequest,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.add_agent_run_feedback(current_user.id, run_id, payload)


@router.get("/agent-runs/{run_id}/skill-executions", response_model=list[dict])
def get_skill_executions(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_skill_executions(current_user.id, run_id)


@router.get("/agent-runs/{run_id}/tool-calls", response_model=list[dict])
def get_tool_calls(
    run_id: str,
    current_user: UserDto = Depends(get_current_user),
    service: AgentOrchestrationService = Depends(get_agent_orchestration_service),
):
    return service.get_tool_calls(current_user.id, run_id)
