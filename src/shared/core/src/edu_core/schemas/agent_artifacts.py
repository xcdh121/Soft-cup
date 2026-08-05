"""Versioned contracts shared by every orchestration agent.

The v1 orchestration API intentionally exposed plain dictionaries.  These
models are the v2 boundary: agents may keep their internal implementation, but
anything persisted or handed to another node is validated and versioned here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator


class ArtifactValidationStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"


class EvidenceRef(BaseModel):
    source_type: str
    source_id: str
    occurred_at: datetime | None = None
    excerpt: str | None = Field(default=None, max_length=500)


class SourceSnapshot(BaseModel):
    snapshot_id: str
    captured_at: datetime
    data_as_of: datetime | None = None
    freshness_seconds: int | None = Field(default=None, ge=0)


class ProfileField(BaseModel):
    value: Any | None = None
    status: str = "missing"
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class LearnerProfileArtifact(BaseModel):
    fields: dict[str, ProfileField] = Field(default_factory=dict)
    completeness: float = Field(0.0, ge=0.0, le=1.0)
    revision_id: str | None = None


class KnowledgeStateItem(BaseModel):
    knowledge_point_id: str
    knowledge_point_name: str | None = None
    status: str
    mastery: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    trend: str = "stable"
    evidence: list[EvidenceRef] = Field(default_factory=list)


class KnowledgeStateArtifact(BaseModel):
    states: list[KnowledgeStateItem] = Field(default_factory=list)
    update_version: str = "kt-v2"


class DiagnosisClaim(BaseModel):
    claim_id: str
    statement: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    counter_evidence: list[EvidenceRef] = Field(default_factory=list)
    requires_more_evidence: bool = False

    @model_validator(mode="after")
    def reject_unsupported_strong_claim(self):
        if self.confidence >= 0.7 and not self.evidence:
            raise ValueError("strong diagnosis claims require evidence")
        return self


class DiagnosisArtifact(BaseModel):
    summary: str
    claims: list[DiagnosisClaim] = Field(default_factory=list)
    degraded_reasons: list[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    recommendation_id: str
    resource_id: str | None = None
    resource_status: str = "available"
    title: str
    score: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class RecommendationArtifact(BaseModel):
    items: list[RecommendationItem] = Field(default_factory=list)


class LearningPathStep(BaseModel):
    step_id: str
    title: str
    knowledge_point_id: str
    resource_id: str | None = None
    estimated_minutes: int = Field(gt=0)
    prerequisites: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class LearningPathArtifact(BaseModel):
    steps: list[LearningPathStep] = Field(default_factory=list)
    total_minutes: int = Field(ge=0)
    stale: bool = False

    @model_validator(mode="after")
    def validate_total(self):
        expected = sum(step.estimated_minutes for step in self.steps)
        if self.total_minutes != expected:
            raise ValueError("total_minutes must equal the sum of step durations")
        return self


T = TypeVar("T")


class ArtifactEnvelope(BaseModel, Generic[T]):
    schema_version: str = "2.0"
    artifact_version: int = Field(1, ge=1)
    artifact_type: str
    producer: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_snapshot_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: ArtifactValidationStatus = ArtifactValidationStatus.VALID
    dependency_hash: str | None = None
    content_hash: str | None = None
    payload: T

    @model_validator(mode="after")
    def add_content_hash(self):
        if self.content_hash is None:
            encoded = str(self.payload).encode("utf-8")
            self.content_hash = sha256(encoded).hexdigest()
        return self


def upgrade_legacy_artifact(
    artifact: dict[str, Any],
    *,
    artifact_type: str,
    producer: str,
    source_snapshot_id: str,
    confidence: float = 0.5,
) -> ArtifactEnvelope[dict[str, Any]]:
    """Wrap a legacy dictionary without changing its payload shape."""

    if "schema_version" in artifact and "payload" in artifact:
        return ArtifactEnvelope[dict[str, Any]].model_validate(artifact)
    return ArtifactEnvelope[dict[str, Any]](
        artifact_type=artifact_type,
        producer=producer,
        source_snapshot_id=source_snapshot_id,
        confidence=confidence,
        payload=artifact,
    )
