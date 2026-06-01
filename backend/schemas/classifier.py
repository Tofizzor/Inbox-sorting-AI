"""API request/response schemas for the /classify endpoint.

Project convention
------------------
- `models/`  -> core domain shapes + the LLM contract (EmailInput, ClassificationResult).
- `schemas/` -> what the HTTP layer specifically accepts and returns.

Why separate them
-----------------
The API response often carries *system metadata* that is not part of the AI's
decision: whether the result needs human review, which model produced it, etc.
Keeping that metadata out of `ClassificationResult` keeps the AI contract (and
the labeled test dataset) clean, while still giving API clients what they need.
"""

from pydantic import BaseModel

from models.classifier_models import ClassificationResult, EmailInput


class ClassifyRequest(BaseModel):
    """Request body for POST /classify: the email we want triaged."""

    email: EmailInput


class ClassifyResponse(BaseModel):
    """Response body for POST /classify: the decision plus system metadata."""

    result: ClassificationResult
    # True when the model output failed validation or looked low-confidence, so
    # a human should review before any automated action is taken.
    needs_review: bool = False
    # Which model produced this result (handy for auditing/debugging later).
    model: str = ""
