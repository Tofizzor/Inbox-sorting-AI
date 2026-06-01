"""Guide configuration API."""

from fastapi import APIRouter, HTTPException

from db import repository
from schemas.messages import GuideResponse, GuideUpdateRequest

router = APIRouter(prefix="/guide", tags=["guide"])


def _validate_guide_structure(config: dict) -> None:
    if "label_schema" not in config:
        raise HTTPException(status_code=400, detail="guide config must include label_schema")
    schema = config["label_schema"]
    for key in ("category", "priority", "suggested_action"):
        if key not in schema or not isinstance(schema[key], list):
            raise HTTPException(
                status_code=400,
                detail=f"label_schema.{key} must be a non-empty list",
            )


@router.get("", response_model=GuideResponse)
def get_guide() -> GuideResponse:
    return GuideResponse(config=repository.get_guide_config())


@router.put("", response_model=GuideResponse)
def update_guide(request: GuideUpdateRequest) -> GuideResponse:
    _validate_guide_structure(request.config)
    updated = repository.update_guide_config(
        request.config, updated_by=request.updated_by
    )
    return GuideResponse(config=updated)
