"""LLM client integration for AI-powered analysis."""
import base64
import time
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI

from app.core.config import settings


class LLMClient:
    """LLM client for AI-powered screenshot and test analysis."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.timeout = settings.ai_analysis_timeout

    async def analyze_screenshot(
        self,
        screenshot_bytes: bytes,
        analysis_type: str = "ui_state",
        additional_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Analyze a screenshot using vision model."""
        start_time = time.time()

        # Encode image to base64
        image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Build prompt based on analysis type
        prompts = {
            "ui_state": """Analyze this mobile app screenshot and describe:
1. The current screen/page type (login, home, settings, etc.)
2. Key UI elements visible (buttons, text fields, lists, etc.)
3. The apparent state of the app (loading, error, success, etc.)
4. Any actionable elements and their locations

Respond in JSON format with keys: screen_type, elements, state, actionable_items""",

            "anomaly": """Analyze this mobile app screenshot for potential issues:
1. UI rendering problems (overlapping elements, cut-off text, etc.)
2. Layout issues (misalignment, spacing problems)
3. Missing or broken images
4. Accessibility concerns
5. Any visual anomalies or bugs

Respond in JSON format with keys: has_anomaly, anomalies (list), severity, summary""",

            "element_detect": """Identify all interactive UI elements in this screenshot:
1. Buttons and their labels
2. Text input fields
3. Clickable links or text
4. Toggle switches, checkboxes, radio buttons
5. Navigation elements

For each element, provide: type, label/text, approximate_location (top/middle/bottom, left/center/right)

Respond in JSON format with key: elements (list of objects)""",
        }

        system_prompt = prompts.get(analysis_type, prompts["ui_state"])
        if additional_context:
            system_prompt += f"\n\nAdditional context: {additional_context}"

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": system_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1500,
                timeout=self.timeout,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content

            # Try to parse as JSON
            import json
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                result_json = {"raw_response": content}

            return {
                "success": True,
                "analysis_type": analysis_type,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
                "confidence": 0.85,  # Placeholder - could be derived from model response
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "analysis_type": analysis_type,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
                "confidence": 0.0,
            }

    async def compare_screenshots(
        self,
        baseline_bytes: bytes,
        target_bytes: bytes,
    ) -> dict[str, Any]:
        """Compare two screenshots for visual differences."""
        start_time = time.time()

        baseline_b64 = base64.b64encode(baseline_bytes).decode("utf-8")
        target_b64 = base64.b64encode(target_bytes).decode("utf-8")

        prompt = """Compare these two mobile app screenshots (first is baseline, second is current):
1. Identify visual differences between them
2. Categorize changes as: layout_change, text_change, color_change, element_added, element_removed, other
3. Assess the significance of changes (minor, moderate, significant)
4. Determine if changes appear intentional or could be bugs

Respond in JSON format with keys: differences (list), overall_similarity (0-100), risk_level (low/medium/high), summary"""

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{baseline_b64}",
                                    "detail": "high",
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{target_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=2000,
                timeout=self.timeout,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content

            import json
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                result_json = {"raw_response": content}

            return {
                "success": True,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
            }

    async def generate_test_suggestion(
        self,
        screenshot_bytes: bytes,
        current_test_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate test step suggestions based on current screen."""
        start_time = time.time()

        image_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = """Based on this mobile app screenshot, suggest the next test actions:
1. What interactive elements are available?
2. What would be logical test steps from this screen?
3. What assertions should be made?

Respond in JSON format with keys: 
- suggested_actions (list of {action, target, description})
- suggested_assertions (list of {type, target, expected})
- navigation_options (list of screens reachable from here)"""

        if current_test_context:
            prompt += f"\n\nCurrent test context: {current_test_context}"

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1500,
                timeout=self.timeout,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content

            import json
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                result_json = {"raw_response": content}

            return {
                "success": True,
                "result": result_json,
                "model": self.model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "model": self.model,
                "latency_ms": latency_ms,
            }


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
