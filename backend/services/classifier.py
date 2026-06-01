"""Triage pipeline: preprocess → Ollama → validate → destination."""

import json
import re
from typing import Optional

from pydantic import ValidationError

from config import get_settings
from models.classifier_models import (
    Category,
    ClassificationResult,
    EmailAnalysis,
    EmailInput,
    LLMAnalysisOutput,
    Priority,
    compute_destination,
)
from db import repository
from services import guide, llm_client, preprocessor
from services.llm_client import LLMError, ProviderUnavailableError


class AnalysisFailedError(Exception):
    """All retry attempts exhausted."""

    def __init__(self, message: str, needs_review: bool = True):
        super().__init__(message)
        self.needs_review = needs_review


def parse_llm_response(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start : end + 1])


def validate_analysis(data: dict) -> LLMAnalysisOutput:
    return LLMAnalysisOutput.model_validate(data)


def to_email_analysis(llm_output: LLMAnalysisOutput) -> EmailAnalysis:
    destination = compute_destination(llm_output.category, llm_output.priority)
    return EmailAnalysis(
        category=llm_output.category,
        priority=llm_output.priority,
        suggested_action=llm_output.suggested_action,
        reason=llm_output.reason,
        destination=destination,
        extracted_fields=llm_output.extracted_fields,
    )


def classify_email(email: EmailInput) -> ClassificationResult:
    """Stateless classification-only (eval tests). No DB, no extraction required."""
    analysis = analyze_email(email, message_id=None, persist=False)
    return ClassificationResult(
        category=analysis.category,
        priority=analysis.priority,
        reason=analysis.reason,
        suggested_action=analysis.suggested_action,
    )


def analyze_email(
    email: EmailInput,
    message_id: Optional[str] = None,
    *,
    persist: bool = True,
) -> EmailAnalysis:
    settings = get_settings()
    max_retries = settings.max_llm_retries
    system_prompt = guide.build_system_prompt()
    user_prompt = preprocessor.build_user_prompt(email)
    last_error = "unknown error"

    for attempt in range(1, max_retries + 1):
        attempt_user_prompt = user_prompt
        if attempt > 1:
            attempt_user_prompt += (
                f"\n\nPrevious response was invalid: {last_error}. "
                "Return ONLY valid JSON matching the schema."
            )
        raw = ""
        try:
            raw = llm_client.call_llm(system_prompt, attempt_user_prompt)
            data = parse_llm_response(raw)
            llm_output = validate_analysis(data)
            analysis = to_email_analysis(llm_output)

            if message_id and persist:
                repository.save_analysis(
                    message_id,
                    analysis,
                    model_name=settings.llm_model,
                    needs_review=False,
                    attempt_count=attempt,
                )
            return analysis

        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            if message_id and persist:
                repository.save_analysis_attempt(
                    message_id,
                    attempt,
                    raw or None,
                    error_type="validation" if isinstance(exc, ValidationError) else "json_parse",
                    error_detail=last_error,
                )
        except (ProviderUnavailableError, LLMError) as exc:
            last_error = str(exc)
            if message_id and persist:
                repository.save_analysis_attempt(
                    message_id,
                    attempt,
                    raw or None,
                    error_type="ollama_error",
                    error_detail=last_error,
                )
            raise

    if message_id and persist:
        repository.record_analyze_failed(message_id, last_error, max_retries)

    raise AnalysisFailedError(
        f"Analysis failed after {max_retries} attempts: {last_error}",
        needs_review=True,
    )
