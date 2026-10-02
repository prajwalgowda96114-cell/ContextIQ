"""Pydantic data models for ContextIQ."""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    PROCESSING = "PROCESSING"
    DECIDED = "DECIDED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REVIEWED = "REVIEWED"


class PriorityEnum(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ModalityEnum(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"


class Incident(BaseModel):
    incident_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    zone: str = "Unknown"
    status: StatusEnum = StatusEnum.PROCESSING
    priority: PriorityEnum = PriorityEnum.MEDIUM
    title: str = ""
    description: str = ""


class InputItem(BaseModel):
    input_id: str
    incident_id: str
    modality: ModalityEnum
    uri: str
    filename: str
    bytes_sha256: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Fact(BaseModel):
    fact_id: str
    incident_id: str
    input_id: str
    modality: ModalityEnum
    claim: str
    evidence_pointer: str  # quote | described image region | pdf page
    zone: str = "Unknown"
    hazard: str = "Unknown"
    severity: int | str = "unknown"  # 1-5 or "unknown"
    affected_people: int | str = "unknown"
    confidence: float = 0.9
    observable: bool = True


class Conflict(BaseModel):
    conflict_id: str
    incident_id: str
    fact_ids: list[str]
    description: str


class ReasonItem(BaseModel):
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)


class ConfidenceBreakdown(BaseModel):
    completeness: float = 0.0
    agreement: float = 0.0
    retrieval_relevance: float = 0.0
    evidence_coverage: float = 0.0
    model_uncertainty: float = 0.0
    conflict_penalty: float = 0.0
    total_score: float = 0.0


class Decision(BaseModel):
    decision_id: str
    incident_id: str
    version: int = 1
    priority: PriorityEnum
    recommended_action: str
    reasons: list[ReasonItem]
    confidence: float
    confidence_breakdown: ConfidenceBreakdown
    review_required: bool = False
    review_reason: str | None = None
    backends: dict[str, str] = Field(default_factory=dict)
    latency_ms: dict[str, int] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PastCase(BaseModel):
    case_id: str
    summary: str
    zone: str
    hazard: str
    outcome: str
    lessons: str
    similarity_score: float | None = None


class Feedback(BaseModel):
    feedback_id: str
    decision_id: str
    incident_id: str
    officer_action: str  # "approve" | "override"
    reason: str
    new_priority: PriorityEnum | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditEvent(BaseModel):
    event_id: str
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str
    incident_id: str
    stage: str
    backend: str
    detail: str
