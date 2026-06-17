"""AI-related API endpoints."""
from __future__ import annotations

import base64
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_active_user
from app.domain.models import User
from app.integrations.llm.client import get_llm_client

router = APIRouter(tags=["AI"])


class GenerateTestStepsRequest(BaseModel):
    """Request body for AI test step generation."""
    screenshot_base64: str = Field(..., description="Base64-encoded screenshot PNG")
    page_source_xml: str = Field(..., description="Page source XML from Appium")
    platform: str = Field(default="android", description="Platform: android or ios")
    test_scenario: Optional[str] = Field(default=None, description="Optional test scenario description")


class GenerateTestStepsResponse(BaseModel):
    """Response for AI test step generation."""
    success: bool
    test_name: Optional[str] = None
    description: Optional[str] = None
    steps: list[dict] = Field(default_factory=list)
    confidence: float = 0.0
    notes: Optional[str] = None
    model: Optional[str] = None
    latency_ms: int = 0
    error: Optional[str] = None


@router.post("/ai/generate-test-steps", response_model=GenerateTestStepsResponse)
async def generate_test_steps(
    payload: GenerateTestStepsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """Generate test case steps from a screenshot and page XML using AI.

    This endpoint takes a device screenshot and page source XML,
    sends them to the configured vision-language model, and returns
    a list of executable test steps in TestCaseStepDesigner format.
    """
    # Decode screenshot
    try:
        screenshot_bytes = base64.b64decode(payload.screenshot_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 screenshot data")

    if len(screenshot_bytes) < 100:
        raise HTTPException(status_code=400, detail="Screenshot data too small, possibly corrupted")

    if not payload.page_source_xml or len(payload.page_source_xml.strip()) < 10:
        raise HTTPException(status_code=400, detail="Page source XML is empty or too short")

    # Call LLM
    llm_client = get_llm_client()
    result = await llm_client.generate_test_steps(
        screenshot_bytes=screenshot_bytes,
        page_source_xml=payload.page_source_xml,
        platform=payload.platform,
        test_scenario=payload.test_scenario,
    )

    if not result.get("success"):
        return GenerateTestStepsResponse(
            success=False,
            error=result.get("error", "Unknown error"),
            model=result.get("model"),
            latency_ms=result.get("latency_ms", 0),
        )

    ai_result = result.get("result", {})
    return GenerateTestStepsResponse(
        success=True,
        test_name=ai_result.get("test_name"),
        description=ai_result.get("description"),
        steps=ai_result.get("steps", []),
        confidence=ai_result.get("confidence", 0.0),
        notes=ai_result.get("notes"),
        model=result.get("model"),
        latency_ms=result.get("latency_ms", 0),
    )
