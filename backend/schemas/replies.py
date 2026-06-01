"""HTTP request/response schemas for Phase 2 reply endpoints.

`schemas/` is the HTTP I/O boundary; domain shapes live in `models/reply_models.py`.
"""

from typing import Optional

from pydantic import BaseModel, Field

from models.reply_models import ReplyTone


class DraftReplyRequest(BaseModel):
    """Optional body for POST /draft-reply. Defaults to a professional tone."""

    tone: ReplyTone = ReplyTone.PROFESSIONAL


class EditReplyRequest(BaseModel):
    """Human edit. edited_text must be non-empty (empty replies must not be sendable)."""

    edited_text: str = Field(min_length=1, max_length=5000)
    editor: str = "user"


class ApproveReplyRequest(BaseModel):
    approved_by: str = "user"


class SendReplyRequest(BaseModel):
    actor: str = "user"


class ReplyResponse(BaseModel):
    id: str
    message_id: str
    analysis_id: Optional[str] = None
    generated_text: str
    edited_text: Optional[str] = None
    status: str
    tone: str
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    sent_at: Optional[str] = None
    # Convenience for clients: the text that would actually be sent.
    current_text: str

    @classmethod
    def from_row(cls, row: dict) -> "ReplyResponse":
        current_text = row.get("edited_text") or row["generated_text"]
        return cls(**row, current_text=current_text)
