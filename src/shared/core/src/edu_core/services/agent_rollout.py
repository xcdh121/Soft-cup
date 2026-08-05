"""Deterministic rollout assignment and automatic rollback decisions."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


FEATURE_FLAGS = {
    "agent_runtime_v2",
    "agent_profile_update_v2",
    "agent_real_trace_ui",
}


def rollout_bucket(subject_id: str, course_id: str, flag: str) -> int:
    if flag not in FEATURE_FLAGS:
        raise ValueError(f"unknown agent feature flag: {flag}")
    digest = sha256(f"{flag}:{course_id}:{subject_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % 100


def is_enabled(subject_id: str, course_id: str, flag: str, percentage: int) -> bool:
    if percentage not in {0, 5, 20, 50, 100}:
        raise ValueError("rollout percentage must be one of 0, 5, 20, 50, 100")
    return rollout_bucket(subject_id, course_id, flag) < percentage


@dataclass(frozen=True)
class RollbackThresholds:
    failure_rate: float = 0.005
    timeout_rate: float = 0.01
    unsupported_strong_claim_rate: float = 0.03
    cost_regression: float = 0.15
    complaint_rate: float = 0.01


def rollback_reasons(metrics: dict[str, float], thresholds: RollbackThresholds | None = None) -> list[str]:
    limits = thresholds or RollbackThresholds()
    checks = {
        "failure_rate": limits.failure_rate,
        "timeout_rate": limits.timeout_rate,
        "unsupported_strong_claim_rate": limits.unsupported_strong_claim_rate,
        "cost_regression": limits.cost_regression,
        "complaint_rate": limits.complaint_rate,
    }
    return [name for name, limit in checks.items() if metrics.get(name, 0.0) > limit]
