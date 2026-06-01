"""Reply API: draft (AI) -> edit (human) -> approve (human) -> send (mock).

The approval gate is enforced in services.reply; here it surfaces as HTTP 409 so a
premature send is impossible from the API, not just the UI.
"""

from fastapi import APIRouter, HTTPException

from schemas.replies import (
    ApproveReplyRequest,
    DraftReplyRequest,
    EditReplyRequest,
    ReplyResponse,
    SendReplyRequest,
)
from services import reply as reply_service
from services.llm_client import ProviderUnavailableError
from services.reply import (
    InvalidReplyTransition,
    MessageNotFoundError,
    NoAnalysisError,
    ReplyGenerationFailedError,
    ReplyNotFoundError,
)

router = APIRouter(prefix="/messages", tags=["replies"])


@router.post("/{message_id}/draft-reply", response_model=ReplyResponse, status_code=201)
def draft_reply(message_id: str, request: DraftReplyRequest | None = None) -> ReplyResponse:
    tone = (request.tone if request else DraftReplyRequest().tone).value
    try:
        row = reply_service.draft_reply_for_message(message_id, tone=tone)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoAnalysisError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ReplyGenerationFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ReplyResponse.from_row(row)


@router.get("/{message_id}/reply", response_model=ReplyResponse)
def get_reply(message_id: str) -> ReplyResponse:
    try:
        row = reply_service.get_reply(message_id)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReplyResponse.from_row(row)


@router.patch("/{message_id}/reply", response_model=ReplyResponse)
def edit_reply(message_id: str, request: EditReplyRequest) -> ReplyResponse:
    try:
        row = reply_service.edit_reply(
            message_id, request.edited_text, editor=request.editor
        )
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidReplyTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReplyResponse.from_row(row)


@router.post("/{message_id}/reply/approve", response_model=ReplyResponse)
def approve_reply(message_id: str, request: ApproveReplyRequest | None = None) -> ReplyResponse:
    approved_by = (request.approved_by if request else ApproveReplyRequest().approved_by)
    try:
        row = reply_service.approve_reply(message_id, approved_by=approved_by)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidReplyTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReplyResponse.from_row(row)


@router.post("/{message_id}/reply/send", response_model=ReplyResponse)
def send_reply(message_id: str, request: SendReplyRequest | None = None) -> ReplyResponse:
    actor = (request.actor if request else SendReplyRequest().actor)
    try:
        row = reply_service.send_reply(message_id, actor=actor)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReplyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidReplyTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ReplyResponse.from_row(row)
