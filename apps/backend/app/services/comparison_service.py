"""Run Comparison Service for comparing test runs."""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import (
    RunComparison,
    TestRun,
    TestRunNode,
    TestStepResult,
    RiskSignal,
)
from app.services.ai_service import AIAnalysisService
from app.services.risk_engine import RiskEngine, RiskSignalInput
from app.integrations.minio.client import MinioClient


class DiffType(str, Enum):
    """Types of differences between runs."""
    STATUS_CHANGE = "status_change"
    DURATION_CHANGE = "duration_change"
    NEW_FAILURE = "new_failure"
    FIXED = "fixed"
    VISUAL_DIFF = "visual_diff"
    STEP_COUNT_CHANGE = "step_count_change"


@dataclass
class NodeDiff:
    """Difference found in a node."""
    node_key: str
    diff_type: DiffType
    baseline_value: Any
    target_value: Any
    description: str
    severity: str  # low, medium, high


@dataclass
class StepDiff:
    """Difference found in a step."""
    node_key: str
    step_index: int
    diff_type: DiffType
    baseline_value: Any
    target_value: Any
    baseline_screenshot: Optional[str]
    target_screenshot: Optional[str]
    ai_analysis: Optional[dict]


class ComparisonService:
    """Service for comparing test runs."""
    
    # Thresholds for detecting significant changes
    DURATION_CHANGE_THRESHOLD = 0.2  # 20% change
    
    def __init__(
        self,
        db: AsyncSession,
        ai_service: Optional[AIAnalysisService] = None,
        minio_client: Optional[MinioClient] = None
    ):
        self.db = db
        self.ai_service = ai_service
        self.minio_client = minio_client
        self.risk_engine = RiskEngine()
    
    async def compare_runs(
        self,
        baseline_run_id: UUID,
        target_run_id: UUID,
        include_ai_analysis: bool = True
    ) -> RunComparison:
        """Compare two test runs and generate comparison report."""
        # Load both runs with their nodes and steps
        baseline_run = await self._load_run_with_details(baseline_run_id)
        target_run = await self._load_run_with_details(target_run_id)
        
        if not baseline_run or not target_run:
            raise ValueError("One or both runs not found")
        
        if baseline_run.project_id != target_run.project_id:
            raise ValueError("Cannot compare runs from different projects")
        
        # Compare nodes
        node_diffs = await self._compare_nodes(baseline_run, target_run)
        
        # Compare steps and screenshots
        step_diffs = await self._compare_steps(
            baseline_run, target_run, include_ai_analysis
        )
        
        # Generate diff summary
        diff_summary = self._generate_diff_summary(node_diffs, step_diffs)
        
        # Calculate risk score
        risk_signals = self._generate_risk_signals(node_diffs, step_diffs, target_run_id)
        risk_score = self.risk_engine.score(risk_signals)
        
        # Save risk signals
        for signal in risk_signals:
            risk_signal = RiskSignal(
                test_run_id=target_run_id,
                signal_type=signal.signal_type,
                weight=signal.weight,
                value=signal.value,
                evidence_json=signal.evidence
            )
            self.db.add(risk_signal)
        
        # Generate and upload report
        report_object_key = await self._generate_report(
            baseline_run, target_run, diff_summary, risk_score
        )
        
        # Create comparison record
        comparison = RunComparison(
            project_id=baseline_run.project_id,
            baseline_run_id=baseline_run_id,
            target_run_id=target_run_id,
            diff_summary=diff_summary,
            risk_score=risk_score,
            report_object_key=report_object_key
        )
        self.db.add(comparison)
        await self.db.flush()
        
        return comparison
    
    async def _load_run_with_details(self, run_id: UUID) -> Optional[TestRun]:
        """Load a run with all its nodes and steps."""
        result = await self.db.execute(
            select(TestRun)
            .options(
                selectinload(TestRun.nodes).selectinload(TestRunNode.step_results)
            )
            .where(TestRun.id == run_id)
        )
        return result.scalar_one_or_none()
    
    async def _compare_nodes(
        self,
        baseline_run: TestRun,
        target_run: TestRun
    ) -> list[NodeDiff]:
        """Compare nodes between two runs."""
        diffs: list[NodeDiff] = []
        
        baseline_nodes = {n.node_key: n for n in baseline_run.nodes}
        target_nodes = {n.node_key: n for n in target_run.nodes}
        
        all_node_keys = set(baseline_nodes.keys()) | set(target_nodes.keys())
        
        for node_key in all_node_keys:
            baseline_node = baseline_nodes.get(node_key)
            target_node = target_nodes.get(node_key)
            
            # Node only in baseline (removed)
            if baseline_node and not target_node:
                diffs.append(NodeDiff(
                    node_key=node_key,
                    diff_type=DiffType.STEP_COUNT_CHANGE,
                    baseline_value=baseline_node.status,
                    target_value=None,
                    description=f"Node '{node_key}' was removed",
                    severity="medium"
                ))
                continue
            
            # Node only in target (added)
            if target_node and not baseline_node:
                diffs.append(NodeDiff(
                    node_key=node_key,
                    diff_type=DiffType.STEP_COUNT_CHANGE,
                    baseline_value=None,
                    target_value=target_node.status,
                    description=f"Node '{node_key}' was added",
                    severity="low"
                ))
                continue
            
            # Compare status
            if baseline_node.status != target_node.status:
                if baseline_node.status == "passed" and target_node.status == "failed":
                    diffs.append(NodeDiff(
                        node_key=node_key,
                        diff_type=DiffType.NEW_FAILURE,
                        baseline_value=baseline_node.status,
                        target_value=target_node.status,
                        description=f"Node '{node_key}' started failing",
                        severity="high"
                    ))
                elif baseline_node.status == "failed" and target_node.status == "passed":
                    diffs.append(NodeDiff(
                        node_key=node_key,
                        diff_type=DiffType.FIXED,
                        baseline_value=baseline_node.status,
                        target_value=target_node.status,
                        description=f"Node '{node_key}' was fixed",
                        severity="low"
                    ))
                else:
                    diffs.append(NodeDiff(
                        node_key=node_key,
                        diff_type=DiffType.STATUS_CHANGE,
                        baseline_value=baseline_node.status,
                        target_value=target_node.status,
                        description=f"Node '{node_key}' status changed",
                        severity="medium"
                    ))
            
            # Compare duration
            if baseline_node.duration_ms and target_node.duration_ms:
                duration_change = (
                    (target_node.duration_ms - baseline_node.duration_ms) 
                    / baseline_node.duration_ms
                )
                if abs(duration_change) > self.DURATION_CHANGE_THRESHOLD:
                    severity = "high" if duration_change > 0.5 else "medium"
                    diffs.append(NodeDiff(
                        node_key=node_key,
                        diff_type=DiffType.DURATION_CHANGE,
                        baseline_value=baseline_node.duration_ms,
                        target_value=target_node.duration_ms,
                        description=f"Node '{node_key}' duration changed by {duration_change*100:.1f}%",
                        severity=severity
                    ))
        
        return diffs
    
    async def _compare_steps(
        self,
        baseline_run: TestRun,
        target_run: TestRun,
        include_ai_analysis: bool
    ) -> list[StepDiff]:
        """Compare steps between two runs."""
        diffs: list[StepDiff] = []
        
        # Build step maps
        baseline_steps = self._build_step_map(baseline_run)
        target_steps = self._build_step_map(target_run)
        
        all_step_keys = set(baseline_steps.keys()) | set(target_steps.keys())
        
        for step_key in all_step_keys:
            node_key, step_index = step_key
            baseline_step = baseline_steps.get(step_key)
            target_step = target_steps.get(step_key)
            
            if not baseline_step or not target_step:
                continue
            
            # Compare status
            if baseline_step.status != target_step.status:
                ai_analysis = None
                
                # If visual comparison is available, use AI
                if (
                    include_ai_analysis 
                    and self.ai_service
                    and baseline_step.screenshot_object_key 
                    and target_step.screenshot_object_key
                ):
                    baseline_url = await self._get_screenshot_url(baseline_step.screenshot_object_key)
                    target_url = await self._get_screenshot_url(target_step.screenshot_object_key)
                    
                    if baseline_url and target_url:
                        analysis_result = await self.ai_service.compare_screenshots(
                            baseline_url=baseline_url,
                            current_url=target_url,
                            context={
                                "step_action": baseline_step.action,
                                "baseline_status": baseline_step.status,
                                "target_status": target_step.status
                            }
                        )
                        ai_analysis = analysis_result.result
                
                diff_type = DiffType.NEW_FAILURE if (
                    baseline_step.status == "passed" and target_step.status == "failed"
                ) else DiffType.STATUS_CHANGE
                
                diffs.append(StepDiff(
                    node_key=node_key,
                    step_index=step_index,
                    diff_type=diff_type,
                    baseline_value=baseline_step.status,
                    target_value=target_step.status,
                    baseline_screenshot=baseline_step.screenshot_object_key,
                    target_screenshot=target_step.screenshot_object_key,
                    ai_analysis=ai_analysis
                ))
        
        return diffs
    
    def _build_step_map(self, run: TestRun) -> dict[tuple[str, int], TestStepResult]:
        """Build a map of (node_key, step_index) -> step_result."""
        step_map = {}
        for node in run.nodes:
            for step in node.step_results:
                step_map[(node.node_key, step.step_index)] = step
        return step_map
    
    async def _get_screenshot_url(self, object_key: str) -> Optional[str]:
        """Get presigned URL for a screenshot."""
        if not self.minio_client:
            return None
        try:
            return await self.minio_client.presign_get(object_key)
        except Exception:
            return None
    
    def _generate_diff_summary(
        self,
        node_diffs: list[NodeDiff],
        step_diffs: list[StepDiff]
    ) -> dict[str, Any]:
        """Generate a summary of all differences."""
        summary = {
            "total_node_diffs": len(node_diffs),
            "total_step_diffs": len(step_diffs),
            "new_failures": 0,
            "fixed": 0,
            "regressions": 0,
            "performance_changes": 0,
            "high_severity_count": 0,
            "medium_severity_count": 0,
            "low_severity_count": 0,
            "node_diffs": [],
            "step_diffs": []
        }
        
        for diff in node_diffs:
            summary["node_diffs"].append({
                "node_key": diff.node_key,
                "type": diff.diff_type.value,
                "description": diff.description,
                "severity": diff.severity
            })
            
            if diff.diff_type == DiffType.NEW_FAILURE:
                summary["new_failures"] += 1
            elif diff.diff_type == DiffType.FIXED:
                summary["fixed"] += 1
            elif diff.diff_type == DiffType.DURATION_CHANGE:
                summary["performance_changes"] += 1
            
            if diff.severity == "high":
                summary["high_severity_count"] += 1
            elif diff.severity == "medium":
                summary["medium_severity_count"] += 1
            else:
                summary["low_severity_count"] += 1
        
        for diff in step_diffs:
            summary["step_diffs"].append({
                "node_key": diff.node_key,
                "step_index": diff.step_index,
                "type": diff.diff_type.value,
                "baseline_screenshot": diff.baseline_screenshot,
                "target_screenshot": diff.target_screenshot,
                "ai_analysis": diff.ai_analysis
            })
            
            if diff.diff_type == DiffType.NEW_FAILURE:
                summary["regressions"] += 1
        
        return summary
    
    def _generate_risk_signals(
        self,
        node_diffs: list[NodeDiff],
        step_diffs: list[StepDiff],
        run_id: UUID
    ) -> list[RiskSignalInput]:
        """Generate risk signals from comparison results."""
        signals = []
        
        # New failures signal
        new_failures = sum(1 for d in node_diffs if d.diff_type == DiffType.NEW_FAILURE)
        if new_failures > 0:
            signals.append(RiskSignalInput(
                signal_type="new_failure",
                weight=1.0,
                value=min(new_failures / 5.0, 1.0),  # Normalize to max 1.0
                evidence={"count": new_failures, "nodes": [
                    d.node_key for d in node_diffs if d.diff_type == DiffType.NEW_FAILURE
                ]}
            ))
        
        # Performance regression signal
        perf_regressions = [
            d for d in node_diffs 
            if d.diff_type == DiffType.DURATION_CHANGE 
            and d.target_value > d.baseline_value
        ]
        if perf_regressions:
            avg_increase = sum(
                (d.target_value - d.baseline_value) / d.baseline_value 
                for d in perf_regressions
            ) / len(perf_regressions)
            signals.append(RiskSignalInput(
                signal_type="perf_regression",
                weight=0.6,
                value=min(avg_increase, 1.0),
                evidence={
                    "affected_nodes": len(perf_regressions),
                    "avg_increase_pct": round(avg_increase * 100, 1)
                }
            ))
        
        # Step-level regression signal
        step_regressions = sum(1 for d in step_diffs if d.diff_type == DiffType.NEW_FAILURE)
        if step_regressions > 0:
            signals.append(RiskSignalInput(
                signal_type="step_regression",
                weight=0.8,
                value=min(step_regressions / 10.0, 1.0),
                evidence={"count": step_regressions}
            ))
        
        return signals
    
    async def _generate_report(
        self,
        baseline_run: TestRun,
        target_run: TestRun,
        diff_summary: dict[str, Any],
        risk_score: float
    ) -> Optional[str]:
        """Generate and upload comparison report."""
        if not self.minio_client:
            return None
        
        import json
        from datetime import datetime
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "baseline": {
                "run_id": str(baseline_run.id),
                "run_no": baseline_run.run_no,
                "status": baseline_run.status,
                "started_at": baseline_run.started_at.isoformat() if baseline_run.started_at else None
            },
            "target": {
                "run_id": str(target_run.id),
                "run_no": target_run.run_no,
                "status": target_run.status,
                "started_at": target_run.started_at.isoformat() if target_run.started_at else None
            },
            "risk_score": risk_score,
            "summary": diff_summary
        }
        
        object_key = f"reports/comparisons/{baseline_run.project_id}/{baseline_run.id}_{target_run.id}.json"
        
        await self.minio_client.put_object(
            object_key=object_key,
            data=json.dumps(report, indent=2).encode(),
            content_type="application/json"
        )
        
        return object_key
    
    async def get_comparison(self, comparison_id: UUID) -> Optional[RunComparison]:
        """Get a comparison by ID."""
        result = await self.db.execute(
            select(RunComparison).where(RunComparison.id == comparison_id)
        )
        return result.scalar_one_or_none()
    
    async def list_comparisons(
        self,
        project_id: UUID,
        limit: int = 20,
        offset: int = 0
    ) -> list[RunComparison]:
        """List comparisons for a project."""
        result = await self.db.execute(
            select(RunComparison)
            .where(RunComparison.project_id == project_id)
            .order_by(RunComparison.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
