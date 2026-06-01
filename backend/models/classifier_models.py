"""Core domain models for Phase 1 email triage."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    HUMAN = "human"
    EVENT = "event"
    SPAM = "spam"
    MACHINE_GENERATED = "machine_generated"


class Priority(str, Enum):
    URGENT_ACTION = "urgent_action"
    NON_URGENT_ACTION = "non_urgent_action"
    IGNORE = "ignore"


class SuggestedAction(str, Enum):
    ACKNOWLEDGE = "acknowledge"
    ESCALATE = "escalate"
    ARCHIVE = "archive"
    IGNORE = "ignore"
    ASK_HUMAN = "ask_human"


class EmailInput(BaseModel):
    subject: str
    body: str
    sender: Optional[str] = None
    timestamp: Optional[datetime] = None


class ClassificationResult(BaseModel):
    """Eval / legacy shape (classification only, no extraction)."""

    category: Category
    priority: Priority
    reason: str
    suggested_action: SuggestedAction


class ExtractedFields(BaseModel):
    order_ids: list[str] = Field(default_factory=list)
    instance_names: list[str] = Field(default_factory=list)
    error_summary: Optional[str] = None
    sender_name: Optional[str] = None
    detected_keywords: list[str] = Field(default_factory=list)


class LLMAnalysisOutput(BaseModel):
    """Shape the model must return (destination computed in Python)."""

    category: Category
    priority: Priority
    suggested_action: SuggestedAction
    reason: str
    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)


class EmailAnalysis(BaseModel):
    """Full analysis after validation and destination mapping."""

    category: Category
    priority: Priority
    suggested_action: SuggestedAction
    reason: str
    destination: str
    extracted_fields: ExtractedFields = Field(default_factory=ExtractedFields)


def compute_destination(category: Category, priority: Priority) -> str:
    """Map category + priority to a folder/queue name for the UI."""
    if category == Category.SPAM:
        return "spam"
    if category == Category.EVENT:
        return "events"
    if category == Category.HUMAN:
        if priority == Priority.URGENT_ACTION:
            return "urgent_human"
        return "human_queue"
    if category == Category.MACHINE_GENERATED:
        if priority == Priority.URGENT_ACTION:
            return "alerts_urgent"
        if priority == Priority.IGNORE:
            return "alerts_archive"
        return "alerts_review"
    return "human_queue"
