"""Domain models for Phase 2 AI-drafted replies.

`models/` holds domain shapes + the LLM contract. The HTTP request/response shapes
live in `schemas/replies.py`; persistence lives in `db/repository.py`.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReplyStatus(str, Enum):
    """States in the reply lifecycle.

    draft -> edited -> approved -> sent. `sent` is terminal. Regenerating a reply
    creates a brand-new row in state `draft`, so it must be re-approved before send.
    """

    DRAFT = "draft"
    EDITED = "edited"
    APPROVED = "approved"
    SENT = "sent"


class ReplyTone(str, Enum):
    """Requested tone for the drafted reply (defaults to professional)."""

    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    FORMAL = "formal"
    EMPATHETIC = "empathetic"
    CONCISE = "concise"


class LLMReplyOutput(BaseModel):
    """The contract the model must return for a reply draft.

    Kept deliberately small: the model produces text only. Routing/approval are
    never read from the model — they are computed and enforced server-side.
    """

    reply: str


class DraftReply(BaseModel):
    """Full domain representation of a stored reply."""

    id: str
    message_id: str
    analysis_id: Optional[str] = None
    generated_text: str
    edited_text: Optional[str] = None
    status: ReplyStatus = ReplyStatus.DRAFT
    tone: str = ReplyTone.PROFESSIONAL.value
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    sent_at: Optional[str] = None

    @property
    def current_text(self) -> str:
        """The human-facing text: the edited version if present, else the AI draft."""
        return self.edited_text if self.edited_text else self.generated_text


# Validation bounds for generated reply text. A reply is a few short sentences; we
# reject empty/whitespace output and anything implausibly long before persisting.
MIN_REPLY_CHARS = 2
MAX_REPLY_CHARS = 2000
