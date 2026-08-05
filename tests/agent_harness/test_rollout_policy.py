from edu_core.services.agent_rollout import is_enabled, rollback_reasons, rollout_bucket


def test_rollout_assignment_is_stable_and_monotonic():
    bucket = rollout_bucket("user-1", "course-1", "agent_runtime_v2")
    assert bucket == rollout_bucket("user-1", "course-1", "agent_runtime_v2")
    assert is_enabled("user-1", "course-1", "agent_runtime_v2", 20) is (bucket < 20)
    assert is_enabled("user-1", "course-1", "agent_runtime_v2", 100)


def test_rollback_triggers_on_any_safety_regression():
    assert rollback_reasons({"failure_rate": 0.02}) == ["failure_rate"]
