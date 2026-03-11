"""AI Analysis Service for screen and test analysis."""
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ScreenAnalysis, TestStepResult, TestRunNode
from app.integrations.llm.client import LLMClient, get_llm_client


class AnalysisType(str, Enum):
    """Types of AI analysis."""
    UI_STATE = "ui_state"
    ANOMALY = "anomaly"
    ELEMENT_DETECT = "element_detect"
    COMPARISON = "comparison"
    SUMMARY = "summary"


@dataclass
class AnalysisResult:
    """Result from AI analysis."""
    analysis_type: str
    result: dict[str, Any]
    confidence: float
    latency_ms: int
    model_name: str
    prompt_version: str


class AIAnalysisService:
    """Service for AI-powered test analysis."""
    
    # Prompt templates for different analysis types
    PROMPT_TEMPLATES = {
        AnalysisType.UI_STATE: {
            "version": "v1.0",
            "system": """You are an expert mobile UI analyzer. Analyze the provided screenshot and describe:
1. Current screen/page type (login, home, settings, etc.)
2. Visible UI elements and their states
3. Any loading indicators or progress bars
4. Overall UI state assessment

Respond in JSON format with keys: screen_type, elements, loading_state, assessment""",
        },
        AnalysisType.ANOMALY: {
            "version": "v1.0",
            "system": """You are a mobile app QA expert. Analyze the screenshot for visual anomalies:
1. Layout issues (overlapping elements, misalignment)
2. Text problems (truncation, wrong encoding, missing text)
3. Image issues (missing images, broken icons)
4. Color/contrast problems
5. Unexpected UI states

Respond in JSON format with keys: has_anomaly, anomalies (list), severity (low/medium/high), summary""",
        },
        AnalysisType.ELEMENT_DETECT: {
            "version": "v1.0", 
            "system": """You are a UI element detection specialist. For the given screenshot:
1. Identify all interactive elements (buttons, inputs, links)
2. Provide their approximate locations
3. Describe their visual appearance
4. Suggest possible selectors

Respond in JSON format with keys: elements (list with type, location, description, suggested_selector)""",
        },
        AnalysisType.COMPARISON: {
            "version": "v1.0",
            "system": """You are comparing two mobile app screenshots (baseline vs current). Analyze:
1. Visual differences between the two screenshots
2. Functional changes (new/removed elements)
3. Layout shifts
4. Potential regression issues

Respond in JSON format with keys: has_differences, differences (list), regression_risk (low/medium/high), summary""",
        },
        AnalysisType.SUMMARY: {
            "version": "v1.0",
            "system": """You are a QA test analyst. Based on the test execution data provided:
1. Summarize the overall test results
2. Identify key failure patterns
3. Highlight critical issues
4. Provide actionable recommendations

Respond in JSON format with keys: summary, failure_patterns, critical_issues, recommendations""",
        },
    }
    
    def __init__(self, db: AsyncSession, llm_client: Optional[LLMClient] = None):
        self.db = db
        self.llm_client = llm_client or get_llm_client()
    
    async def analyze_screen(
        self,
        image_url: str,
        analysis_type: AnalysisType,
        context: Optional[dict] = None,
        image_bytes: Optional[bytes] = None
    ) -> AnalysisResult:
        """Analyze a single screenshot.
        
        Args:
            image_url: URL of the image (used if image_bytes not provided)
            analysis_type: Type of analysis to perform
            context: Additional context for the analysis
            image_bytes: Raw image bytes (preferred over URL for direct analysis)
        """
        start_time = time.time()
        
        template = self.PROMPT_TEMPLATES[analysis_type]
        
        # Build context string
        context_str = None
        if context:
            context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        
        # Use image bytes if available, otherwise fetch from URL
        if image_bytes:
            result = await self.llm_client.analyze_screenshot(
                screenshot_bytes=image_bytes,
                analysis_type=analysis_type.value,
                additional_context=context_str
            )
        else:
            # Fetch image from URL and analyze
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                image_bytes = response.content
            
            result = await self.llm_client.analyze_screenshot(
                screenshot_bytes=image_bytes,
                analysis_type=analysis_type.value,
                additional_context=context_str
            )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return AnalysisResult(
            analysis_type=analysis_type.value,
            result=result.get("result", {}),
            confidence=result.get("confidence", 0.8),
            latency_ms=result.get("latency_ms", latency_ms),
            model_name=result.get("model", "gpt-4-vision"),
            prompt_version=template["version"]
        )
    
    async def analyze_step(
        self,
        step_result_id: UUID,
        screenshot_url: str,
        analysis_types: list[AnalysisType]
    ) -> list[ScreenAnalysis]:
        """Analyze a test step and save results."""
        analyses = []
        
        for analysis_type in analysis_types:
            result = await self.analyze_screen(
                image_url=screenshot_url,
                analysis_type=analysis_type
            )
            
            # Create and save analysis record
            screen_analysis = ScreenAnalysis(
                test_step_result_id=step_result_id,
                model_name=result.model_name,
                prompt_version=result.prompt_version,
                analysis_type=result.analysis_type,
                result_json=result.result,
                confidence=result.confidence,
                latency_ms=result.latency_ms
            )
            self.db.add(screen_analysis)
            analyses.append(screen_analysis)
        
        await self.db.flush()
        return analyses
    
    async def compare_screenshots(
        self,
        baseline_url: str,
        current_url: str,
        context: Optional[dict] = None,
        baseline_bytes: Optional[bytes] = None,
        current_bytes: Optional[bytes] = None
    ) -> AnalysisResult:
        """Compare two screenshots for differences.
        
        Args:
            baseline_url: URL of baseline screenshot
            current_url: URL of current screenshot  
            context: Additional context for comparison
            baseline_bytes: Raw bytes of baseline image (preferred)
            current_bytes: Raw bytes of current image (preferred)
        """
        start_time = time.time()
        
        template = self.PROMPT_TEMPLATES[AnalysisType.COMPARISON]
        
        # Fetch images if bytes not provided
        if not baseline_bytes or not current_bytes:
            import httpx
            async with httpx.AsyncClient() as client:
                if not baseline_bytes:
                    response = await client.get(baseline_url)
                    baseline_bytes = response.content
                if not current_bytes:
                    response = await client.get(current_url)
                    current_bytes = response.content
        
        result = await self.llm_client.compare_screenshots(
            baseline_bytes=baseline_bytes,
            target_bytes=current_bytes
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        return AnalysisResult(
            analysis_type=AnalysisType.COMPARISON.value,
            result=result.get("result", {}),
            confidence=0.85 if result.get("success") else 0.0,
            latency_ms=result.get("latency_ms", latency_ms),
            model_name=result.get("model", "gpt-4-vision"),
            prompt_version=template["version"]
        )
    
    async def generate_run_summary(
        self,
        run_data: dict[str, Any]
    ) -> AnalysisResult:
        """Generate AI summary for a test run."""
        start_time = time.time()
        
        template = self.PROMPT_TEMPLATES[AnalysisType.SUMMARY]
        
        # Build summary prompt
        summary_text = f"""Test Run Summary Analysis:

Run Statistics:
- Total Steps: {run_data.get('total_steps', 0)}
- Passed: {run_data.get('passed', 0)}
- Failed: {run_data.get('failed', 0)}
- Skipped: {run_data.get('skipped', 0)}
- Duration: {run_data.get('duration_ms', 0)}ms

Pass Rate: {run_data.get('passed', 0) / max(run_data.get('total_steps', 1), 1) * 100:.1f}%

Failure Details:
{run_data.get('failure_details', 'No failures recorded')}

AI Anomalies Detected:
{run_data.get('anomalies', 'No anomalies detected')}

Risk Signals:
{run_data.get('risk_signals', 'No risk signals')}
"""
        
        # Use text generation (no image)
        try:
            from openai import AsyncOpenAI
            from app.core.config import settings
            
            client_kwargs = {}
            if settings.llm_base_url:
                client_kwargs["base_url"] = settings.llm_base_url

            client = AsyncOpenAI(api_key=settings.llm_api_key, **client_kwargs)
            response = await client.chat.completions.create(
                model=settings.llm_chat_model,
                messages=[
                    {"role": "system", "content": template["system"]},
                    {"role": "user", "content": summary_text}
                ],
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            import json
            content = response.choices[0].message.content
            try:
                result_json = json.loads(content)
            except json.JSONDecodeError:
                result_json = {"summary": content, "recommendations": []}
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            return AnalysisResult(
                analysis_type=AnalysisType.SUMMARY.value,
                result=result_json,
                confidence=0.9,
                latency_ms=latency_ms,
                model_name=settings.llm_chat_model,
                prompt_version=template["version"]
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return AnalysisResult(
                analysis_type=AnalysisType.SUMMARY.value,
                result={"error": str(e), "summary": "Failed to generate summary"},
                confidence=0.0,
                latency_ms=latency_ms,
                model_name="unknown",
                prompt_version=template["version"]
            )
    
    async def get_step_analyses(self, step_result_id: UUID) -> list[ScreenAnalysis]:
        """Get all analyses for a step result."""
        result = await self.db.execute(
            select(ScreenAnalysis)
            .where(ScreenAnalysis.test_step_result_id == step_result_id)
            .order_by(ScreenAnalysis.created_at)
        )
        return list(result.scalars().all())
    
    async def detect_flaky_patterns(
        self,
        test_case_id: UUID,
        recent_runs: int = 10
    ) -> dict[str, Any]:
        """Detect flaky test patterns from recent runs."""
        # Get recent step results for this test case
        result = await self.db.execute(
            select(TestStepResult)
            .join(TestRunNode, TestStepResult.run_node_id == TestRunNode.id)
            .where(TestRunNode.test_case_id == test_case_id)
            .order_by(TestStepResult.created_at.desc())
            .limit(recent_runs * 20)  # Assume ~20 steps per run
        )
        step_results = result.scalars().all()
        
        if not step_results:
            return {"is_flaky": False, "confidence": 1.0, "patterns": []}
        
        # Group by step index and analyze consistency
        step_stats: dict[int, dict] = {}
        for step in step_results:
            if step.step_index not in step_stats:
                step_stats[step.step_index] = {"passed": 0, "failed": 0}
            
            if step.status == "passed":
                step_stats[step.step_index]["passed"] += 1
            elif step.status == "failed":
                step_stats[step.step_index]["failed"] += 1
        
        # Identify flaky steps (inconsistent pass/fail)
        flaky_patterns = []
        for step_index, stats in step_stats.items():
            total = stats["passed"] + stats["failed"]
            if total > 2:
                pass_rate = stats["passed"] / total
                # Flaky if pass rate is between 20% and 80%
                if 0.2 < pass_rate < 0.8:
                    flaky_patterns.append({
                        "step_index": step_index,
                        "pass_rate": round(pass_rate * 100, 1),
                        "sample_size": total
                    })
        
        return {
            "is_flaky": len(flaky_patterns) > 0,
            "confidence": 0.85,
            "patterns": flaky_patterns,
            "recommendation": "Consider adding retries or stabilizing the test" if flaky_patterns else None
        }
