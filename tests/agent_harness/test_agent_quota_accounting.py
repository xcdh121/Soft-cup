import asyncio

import pytest

from edu_core.schemas.agent_orchestration import (
    AgentContextData,
    AgentRunContext,
    RunStatus,
    SupervisorRunResult,
)
from edu_core.services.agent_orchestration import (
    AgentOrchestrationService,
    InMemoryOrchestrationStore,
)


class _Quota:
    def __init__(self):
        self.reservations = []
        self.commits = []
        self.releases = []

    def reserve(self, **kwargs):
        self.reservations.append(kwargs)
        return {}

    def commit(self, *, idempotency_key):
        self.commits.append(idempotency_key)
        return {}

    def release(self, *, idempotency_key):
        self.releases.append(idempotency_key)
        return {}


class _Supervisor:
    async def run(self, request, event_sink=None):
        del event_sink
        context = AgentRunContext(
            run_id=request.meta["run_id"],
            project_id=request.project_id,
            student_id=request.student_id,
            goal=request.goal,
            context=request.context,
        )
        return SupervisorRunResult(
            run_id=context.run_id,
            status=RunStatus.COMPLETED,
            context=context,
            final_result={"diagnosis": {"summary": "ready"}},
        )


class _FailingSupervisor:
    async def run(self, request, event_sink=None):
        del request, event_sink
        raise RuntimeError("provider unavailable")


class _CancelledSupervisor:
    async def run(self, request, event_sink=None):
        del request, event_sink
        raise asyncio.CancelledError


def _service(supervisor, quota):
    service = AgentOrchestrationService(
        supervisor=supervisor,
        store=InMemoryOrchestrationStore(),
        quota_service=quota,
    )
    service._load_context = lambda _user_id, _project_id: AgentContextData()
    return service


def test_completed_agent_run_commits_reserved_quota():
    quota = _Quota()

    response = asyncio.run(
        _service(_Supervisor(), quota).generate_diagnosis("user-1", "project-1")
    )

    assert response.diagnosis["summary"] == "ready"
    assert quota.reservations[0]["resource_type"] == "agent_run"
    assert quota.reservations[0]["quantity"] == 1
    assert quota.commits == [quota.reservations[0]["idempotency_key"]]
    assert quota.releases == []


def test_failed_agent_run_releases_reserved_quota():
    quota = _Quota()

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(
            _service(_FailingSupervisor(), quota).generate_diagnosis(
                "user-1", "project-1"
            )
        )

    assert quota.commits == []
    assert quota.releases == [quota.reservations[0]["idempotency_key"]]


def test_cancelled_agent_run_releases_reserved_quota():
    quota = _Quota()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            _service(_CancelledSupervisor(), quota).generate_diagnosis(
                "user-1", "project-1"
            )
        )

    assert quota.commits == []
    assert quota.releases == [quota.reservations[0]["idempotency_key"]]
