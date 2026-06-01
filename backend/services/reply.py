"""Reply drafting + the human-approval state machine.

This is a SECOND LLM call, fully separate from triage (classifier.py), so each is
testable in isolation. The model only produces text; whether a reply is ever sent is
decided by humans and enforced here (and again by a 409 guard in the router).

Lifecycle: draft -> edited -> approved -> sent. Regenerating creates a new draft row.
The single hard invariant: a reply can be sent only from status `approved`.
"""

import json
from typing import Optional

from pydantic import ValidationError

from config import get_settings
from db import repository
from models.classifier_models import EmailAnalysis, EmailInput
from models.reply_models import (
    MAX_REPLY_CHARS,
    MIN_REPLY_CHARS,
    LLMReplyOutput,
    ReplyStatus,
)
from services import guide, llm_client
from services.classifier import parse_llm_response
from services.llm_client import LLMError, ProviderUnavailableError


class MessageNotFoundError(Exception):
    """No such message."""


class NoAnalysisError(Exception):
    """A reply was requested for a message that has not been analyzed yet."""


class ReplyNotFoundError(Exception):
    """No reply exists for the message yet."""


class InvalidReplyTransition(Exception):
    """An action is illegal for the reply's current status (maps to HTTP 409)."""


class ReplyGenerationFailedError(Exception):
    """All retry attempts produced invalid/empty reply text (maps to HTTP 422)."""

    def __init__(self, message: str, needs_review: bool = True):
        super().__init__(message)
        self.needs_review = needs_review


def _validate_reply_text(text: str) -> str:
    """Reject empty/oversized output before it can be persisted as a usable draft."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Reply text is empty.")
    if len(cleaned) < MIN_REPLY_CHARS:
        raise ValueError(f"Reply text too short ({len(cleaned)} chars).")
    if len(cleaned) > MAX_REPLY_CHARS:
        raise ValueError(
            f"Reply text too long ({len(cleaned)} chars; max {MAX_REPLY_CHARS})."
        )
    return cleaned


def generate_reply(
    email: EmailInput,
    analysis: EmailAnalysis,
    *,
    message_id: Optional[str] = None,
    tone: str = "professional",
    log: bool = True,
) -> str:
    """Make the separate, validated LLM call that drafts a short reply.

    Mirrors the classifier's parse -> validate -> retry -> attempt-logging shape. On
    repeated failure, logs attempts, flags the analysis for review, and raises — it
    never returns or persists garbage.
    """
    settings = get_settings()
    max_retries = settings.max_llm_retries
    system_prompt = guide.build_reply_system_prompt(tone)
    user_prompt = guide.build_reply_user_prompt(email, analysis)
    last_error = "unknown error"

    for attempt in range(1, max_retries + 1):
        attempt_user_prompt = user_prompt
        if attempt > 1:
            attempt_user_prompt += (
                f"\n\nPrevious response was invalid: {last_error}. "
                'Return ONLY valid JSON: {"reply": "..."}.'
            )
        raw = ""
        try:
            raw = llm_client.call_llm(system_prompt, attempt_user_prompt)
            data = parse_llm_response(raw)
            reply_out = LLMReplyOutput.model_validate(data)
            return _validate_reply_text(reply_out.reply)
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            if message_id and log:
                repository.log_reply_attempt(
                    message_id,
                    attempt,
                    raw or None,
                    error_type="validation"
                    if isinstance(exc, ValidationError)
                    else "reply_parse",
                    error_detail=last_error,
                )
        except (ProviderUnavailableError, LLMError) as exc:
            last_error = str(exc)
            if message_id and log:
                repository.log_reply_attempt(
                    message_id,
                    attempt,
                    raw or None,
                    error_type="provider_error",
                    error_detail=last_error,
                )
            raise

    if message_id and log:
        repository.mark_analysis_needs_review(message_id, last_error)

    raise ReplyGenerationFailedError(
        f"Reply generation failed after {max_retries} attempts: {last_error}",
        needs_review=True,
    )


def draft_reply_for_message(message_id: str, *, tone: str = "professional") -> dict:
    """Generate and persist a new draft reply. Requires an existing analysis."""
    detail = repository.get_message_with_latest_analysis(message_id)
    if detail is None:
        raise MessageNotFoundError("Message not found")

    analysis_dict = detail.get("analysis")
    if analysis_dict is None:
        raise NoAnalysisError("Message must be analyzed before a reply can be drafted.")

    email = EmailInput(
        subject=detail["email"]["subject"],
        body=detail["email"]["body"],
        sender=detail["email"].get("sender"),
    )
    analysis = EmailAnalysis.model_validate(analysis_dict)

    reply_text = generate_reply(email, analysis, message_id=message_id, tone=tone)

    return repository.create_draft_reply(
        message_id,
        analysis_dict.get("id"),
        reply_text,
        tone=tone,
        model_name=get_settings().llm_model,
        prompt_version=guide.REPLY_PROMPT_VERSION,
    )


def _require_latest_reply(message_id: str) -> dict:
    if not repository.message_exists(message_id):
        raise MessageNotFoundError("Message not found")
    reply = repository.get_latest_reply(message_id)
    if reply is None:
        raise ReplyNotFoundError("No reply has been drafted for this message yet.")
    return reply


def get_reply(message_id: str) -> dict:
    """Return the latest reply for the message (404s if message/reply missing)."""
    return _require_latest_reply(message_id)


def edit_reply(message_id: str, edited_text: str, *, editor: str = "user") -> dict:
    """Apply a human edit. Allowed unless the reply has already been sent."""
    reply = _require_latest_reply(message_id)
    if reply["status"] == ReplyStatus.SENT.value:
        raise InvalidReplyTransition("Cannot edit a reply that has already been sent.")
    return repository.update_reply_edit(
        reply["id"], message_id, edited_text, editor=editor
    )


def approve_reply(message_id: str, *, approved_by: str = "user") -> dict:
    """Record explicit human approval. Cannot approve an already-sent reply."""
    reply = _require_latest_reply(message_id)
    if reply["status"] == ReplyStatus.SENT.value:
        raise InvalidReplyTransition("Cannot approve a reply that has already been sent.")
    return repository.approve_reply(reply["id"], message_id, approved_by=approved_by)


def send_reply(message_id: str, *, actor: str = "user") -> dict:
    """MOCK send. The safety gate: only an `approved` reply may be sent.

    No SMTP/network. Any other status raises InvalidReplyTransition -> HTTP 409.
    """
    reply = _require_latest_reply(message_id)
    if reply["status"] != ReplyStatus.APPROVED.value:
        raise InvalidReplyTransition(
            f"Reply must be approved before sending (current status: {reply['status']})."
        )
    return repository.mark_reply_sent(reply["id"], message_id, actor=actor)
