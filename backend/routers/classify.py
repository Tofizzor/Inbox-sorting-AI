"""Stateless classify endpoint for quick testing."""

from fastapi import APIRouter, HTTPException

from config import get_settings
from models.classifier_models import ClassificationResult
from schemas.classifier import ClassifyRequest, ClassifyResponse
from services.classifier import AnalysisFailedError, analyze_email
from services.llm_client import ProviderUnavailableError

router = APIRouter(tags=["triage"])


@router.post("/classify", response_model=ClassifyResponse)
def classify_endpoint(request: ClassifyRequest) -> ClassifyResponse:
    settings = get_settings()
    try:
        analysis = analyze_email(request.email, message_id=None, persist=False)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnalysisFailedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ClassifyResponse(
        result=ClassificationResult(
            category=analysis.category,
            priority=analysis.priority,
            reason=analysis.reason,
            suggested_action=analysis.suggested_action,
        ),
        needs_review=False,
        model=settings.llm_model,
    )
