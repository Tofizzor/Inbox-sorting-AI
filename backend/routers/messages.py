"""Messages API: ingest, analyze, list, detail, audit."""

from fastapi import APIRouter, HTTPException

from db import repository
from models.classifier_models import EmailInput
from schemas.messages import (
    AnalyzeMessageResponse,
    AuditEventResponse,
    CreateMessageRequest,
    CreateMessageResponse,
    MessageDetailResponse,
    MessageListItem,
)
from services.classifier import AnalysisFailedError, analyze_email
from services.llm_client import ProviderUnavailableError

router = APIRouter(prefix="/messages", tags=["messages"])


def _to_detail(data: dict) -> MessageDetailResponse:
    analysis = data.get("analysis")
    return MessageDetailResponse(
        id=data["id"],
        email=data["email"],
        source=data["source"],
        created_at=data["created_at"],
        analysis=analysis,
    )


@router.post("", response_model=CreateMessageResponse, status_code=201)
def create_message(request: CreateMessageRequest) -> CreateMessageResponse:
    message_id = repository.create_message(request.email, source=request.source)
    detail = repository.get_message_with_latest_analysis(message_id)
    assert detail is not None
    return CreateMessageResponse(
        id=detail["id"],
        subject=detail["email"]["subject"],
        source=detail["source"],
        created_at=detail["created_at"],
    )


@router.get("", response_model=list[MessageListItem])
def list_messages(limit: int = 50, offset: int = 0) -> list[MessageListItem]:
    rows = repository.list_messages(limit=limit, offset=offset)
    return [MessageListItem(**row) for row in rows]


@router.get("/{message_id}", response_model=MessageDetailResponse)
def get_message(message_id: str) -> MessageDetailResponse:
    data = repository.get_message_with_latest_analysis(message_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return _to_detail(data)


@router.post("/{message_id}/analyze", response_model=AnalyzeMessageResponse)
def analyze_message(message_id: str) -> AnalyzeMessageResponse:
    data = repository.get_message_with_latest_analysis(message_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Message not found")

    email = EmailInput(
        subject=data["email"]["subject"],
        body=data["email"]["body"],
        sender=data["email"].get("sender"),
    )
    try:
        analyze_email(email, message_id=message_id, persist=True)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisFailedError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    updated = repository.get_message_with_latest_analysis(message_id)
    assert updated is not None
    return AnalyzeMessageResponse(message=_to_detail(updated))


@router.get("/{message_id}/audit", response_model=list[AuditEventResponse])
def get_message_audit(message_id: str) -> list[AuditEventResponse]:
    if not repository.message_exists(message_id):
        raise HTTPException(status_code=404, detail="Message not found")
    events = repository.get_message_audit(message_id)
    return [AuditEventResponse(**e) for e in events]
