"""Risk scoring engine for test runs."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import RiskSignal, TestRun, TestRunNode, TestStepResult, ScreenAnalysis


class SignalType(str, Enum):
    """Risk signal types."""
    CRASH = "crash"
    LAYOUT_SHIFT = "layout_shift"
    FLAKY = "flaky"
    PERF_REGRESSION = "perf_regression"
    ASSERTION_FAILURE = "assertion_failure"
    ELEMENT_NOT_FOUND = "element_not_found"
    TIMEOUT = "timeout"
    AI_ANOMALY = "ai_anomaly"


@dataclass
class RiskSignalInput:
    """Input for risk signal calculation."""
    signal_type: str
    weight: float
    value: float
    evidence: Optional[dict] = None


class RiskEngine:
    """Engine for calculating risk scores based on signals."""
    
    # Default weights for different signal types
    DEFAULT_WEIGHTS = {
        SignalType.CRASH: 1.0,
        SignalType.LAYOUT_SHIFT: 0.6,
        SignalType.FLAKY: 0.5,
        SignalType.PERF_REGRESSION: 0.4,
        SignalType.ASSERTION_FAILURE: 0.8,
        SignalType.ELEMENT_NOT_FOUND: 0.7,
        SignalType.TIMEOUT: 0.6,
        SignalType.AI_ANOMALY: 0.7,
    }
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def calculate_score(self, signals: list[RiskSignalInput]) -> float:
        """Calculate overall risk score from signals (0-100)."""
        if not signals:
            return 0.0
        
        weighted_sum = sum(s.weight * s.value for s in signals)
        max_possible = sum(s.weight * 100 for s in signals) or 1.0
        
        score = (weighted_sum / max_possible) * 100
        return round(min(max(score, 0.0), 100.0), 2)
    
    async def analyze_run(self, run_id: UUID) -> tuple[float, list[RiskSignalInput]]:
        """Analyze a test run and generate risk signals."""
        signals: list[RiskSignalInput] = []
        
        # Get test run
        result = await self.db.execute(
            select(TestRun).where(TestRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return 0.0, []
        
        # Get run nodes
        result = await self.db.execute(
            select(TestRunNode).where(TestRunNode.test_run_id == run_id)
        )
        nodes = result.scalars().all()
        
        # Analyze node failures
        failed_nodes = [n for n in nodes if n.status == "failed"]
        total_nodes = len(nodes)
        
        if total_nodes > 0:
            failure_rate = (len(failed_nodes) / total_nodes) * 100
            if failure_rate > 0:
                signals.append(RiskSignalInput(
                    signal_type=SignalType.ASSERTION_FAILURE,
                    weight=self.DEFAULT_WEIGHTS[SignalType.ASSERTION_FAILURE],
                    value=failure_rate,
                    evidence={"failed_nodes": len(failed_nodes), "total_nodes": total_nodes}
                ))
        
        # Analyze crash signals
        for node in failed_nodes:
            if node.error_code and "crash" in node.error_code.lower():
                signals.append(RiskSignalInput(
                    signal_type=SignalType.CRASH,
                    weight=self.DEFAULT_WEIGHTS[SignalType.CRASH],
                    value=100.0,
                    evidence={"node_key": node.node_key, "error": node.error_message}
                ))
        
        # Analyze timeout signals
        for node in nodes:
            if node.error_code and "timeout" in node.error_code.lower():
                signals.append(RiskSignalInput(
                    signal_type=SignalType.TIMEOUT,
                    weight=self.DEFAULT_WEIGHTS[SignalType.TIMEOUT],
                    value=80.0,
                    evidence={"node_key": node.node_key, "duration_ms": node.duration_ms}
                ))
        
        # Analyze element not found
        for node in failed_nodes:
            if node.error_code and "element" in node.error_code.lower():
                signals.append(RiskSignalInput(
                    signal_type=SignalType.ELEMENT_NOT_FOUND,
                    weight=self.DEFAULT_WEIGHTS[SignalType.ELEMENT_NOT_FOUND],
                    value=70.0,
                    evidence={"node_key": node.node_key, "error": node.error_message}
                ))
        
        # Get AI anomaly signals from screen analyses
        ai_anomalies = await self._get_ai_anomalies(run_id)
        signals.extend(ai_anomalies)
        
        # Calculate final score
        score = self.calculate_score(signals)
        
        return score, signals
    
    async def _get_ai_anomalies(self, run_id: UUID) -> list[RiskSignalInput]:
        """Get AI-detected anomalies for a run."""
        signals = []
        
        # Get all step results for this run
        result = await self.db.execute(
            select(TestStepResult)
            .join(TestRunNode)
            .where(TestRunNode.test_run_id == run_id)
        )
        step_results = result.scalars().all()
        
        step_ids = [s.id for s in step_results]
        if not step_ids:
            return signals
        
        # Get screen analyses with anomalies
        result = await self.db.execute(
            select(ScreenAnalysis)
            .where(
                ScreenAnalysis.test_step_result_id.in_(step_ids),
                ScreenAnalysis.analysis_type == "anomaly"
            )
        )
        analyses = result.scalars().all()
        
        for analysis in analyses:
            if analysis.result_json.get("has_anomaly", False):
                confidence = float(analysis.confidence) if analysis.confidence else 0.5
                signals.append(RiskSignalInput(
                    signal_type=SignalType.AI_ANOMALY,
                    weight=self.DEFAULT_WEIGHTS[SignalType.AI_ANOMALY],
                    value=confidence * 100,
                    evidence={
                        "analysis_id": str(analysis.id),
                        "summary": analysis.result_json.get("summary", ""),
                        "category": analysis.result_json.get("category", "unknown")
                    }
                ))
        
        return signals
    
    async def save_signals(self, run_id: UUID, signals: list[RiskSignalInput]) -> None:
        """Save risk signals to database."""
        for signal in signals:
            risk_signal = RiskSignal(
                test_run_id=run_id,
                signal_type=signal.signal_type,
                weight=signal.weight,
                value=signal.value,
                evidence_json=signal.evidence or {}
            )
            self.db.add(risk_signal)
        
        await self.db.flush()
    
    def get_recommendation(self, score: float) -> str:
        """Get deployment recommendation based on risk score."""
        if score < 20:
            return "Low risk. Safe to proceed with deployment."
        elif score < 40:
            return "Minor risk. Review flagged issues, but deployment is likely safe."
        elif score < 60:
            return "Moderate risk. Address highlighted issues before deployment."
        elif score < 80:
            return "High risk. Critical issues detected. Fix before deployment."
        else:
            return "Critical risk. Do not deploy. Multiple severe issues detected."
    
    def get_risk_level(self, score: float) -> str:
        """Get risk level category."""
        if score < 20:
            return "low"
        elif score < 40:
            return "minor"
        elif score < 60:
            return "moderate"
        elif score < 80:
            return "high"
        else:
            return "critical"
