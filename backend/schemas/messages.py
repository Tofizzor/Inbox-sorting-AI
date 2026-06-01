"""API schemas for messages and guide endpoints."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from models.classifier_models import EmailInput, ExtractedFields


class CreateMessageRequest(BaseModel):
    email: EmailInput
    source: str = "api"


class CreateMessageResponse(BaseModel):
    id: str
    subject: str
    source: str
    created_at: str


class AnalysisResponse(BaseModel):
    id: str
    category: str
    priority: str
    suggested_action: str
    reason: str
    destination: str
    extracted_fields: ExtractedFields
    model_name: Optional[str] = None
    needs_review: bool = False
    attempt_count: int = 1
    created_at: str


class MessageDetailResponse(BaseModel):
    id: str
    email: dict
    source: str
    created_at: str
    analysis: Optional[AnalysisResponse] = None


class MessageListItem(BaseModel):
    id: str
    subject: str
    sender: Optional[str] = None
    source: str
    created_at: str
    destination: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    needs_review: Optional[bool] = None


class GuideUpdateRequest(BaseModel):
    config: dict[str, Any]
    updated_by: str = "user"


class GuideResponse(BaseModel):
    config: dict[str, Any]


class AuditEventResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: Optional[str]
    action: str
    actor: str
    payload: Optional[dict] = None
    created_at: str


class AnalyzeMessageResponse(BaseModel):
    message: MessageDetailResponse


class ErrorResponse(BaseModel):
    detail: str
    needs_review: bool = False
