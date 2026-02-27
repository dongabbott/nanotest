"""AI analysis Celery tasks."""
import asyncio
from typing import Any, List

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.analysis.analyze_test_run")
def analyze_test_run(self, run_id: str, analysis_types: List[str]) -> dict[str, Any]:
    """Analyze screenshots from a test run using AI."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import ScreenAnalysis, TestRun, TestRunNode, TestStepResult
    from app.integrations.llm.client import get_llm_client
    from app.integrations.aliyun.oss_client import get_oss_client
    from sqlalchemy import select
    import structlog

    async def _analyze():
        async with AsyncSessionLocal() as db:
            logger = structlog.get_logger()
            # Get the test run
            result = await db.execute(
                select(TestRun).where(TestRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Run not found"}

            # Get all step results with screenshots
            result = await db.execute(
                select(TestStepResult)
                .join(TestRunNode)
                .where(
                    TestRunNode.test_run_id == run_id,
                    TestStepResult.screenshot_object_key.isnot(None),
                )
            )
            steps = result.scalars().all()

            llm_client = get_llm_client()
            oss_client = get_oss_client()
            
            analyses_created = 0

            for step in steps:
                screenshot_bytes: bytes | None = None
                try:
                    screenshot_bytes = oss_client.download_bytes(step.screenshot_object_key)
                except Exception as e:
                    for analysis_type in analysis_types:
                        db.add(
                            ScreenAnalysis(
                                test_step_result_id=step.id,
                                model_name=getattr(llm_client, "model", "unknown"),
                                prompt_version="v1",
                                analysis_type=analysis_type,
                                result_json={"success": False, "stage": "download", "error": str(e)},
                                confidence=0.0,
                                latency_ms=0,
                            )
                        )
                        analyses_created += 1
                    logger.exception("AI screenshot download failed", run_id=run_id, step_id=step.id)
                    continue

                for analysis_type in analysis_types:
                    try:
                        ai_result = await llm_client.analyze_screenshot(
                            screenshot_bytes,
                            analysis_type=analysis_type,
                        )
                        if ai_result.get("success"):
                            result_json = ai_result.get("result", {})
                            confidence = float(ai_result.get("confidence") or 0.0)
                            latency_ms = int(ai_result.get("latency_ms") or 0)
                        else:
                            result_json = {"success": False, "stage": "llm", **(ai_result or {})}
                            confidence = 0.0
                            latency_ms = int((ai_result or {}).get("latency_ms") or 0)

                        db.add(
                            ScreenAnalysis(
                                test_step_result_id=step.id,
                                model_name=str(ai_result.get("model") or getattr(llm_client, "model", "unknown")),
                                prompt_version="v1",
                                analysis_type=analysis_type,
                                result_json=result_json,
                                confidence=confidence,
                                latency_ms=latency_ms,
                            )
                        )
                        analyses_created += 1
                    except Exception as e:
                        db.add(
                            ScreenAnalysis(
                                test_step_result_id=step.id,
                                model_name=getattr(llm_client, "model", "unknown"),
                                prompt_version="v1",
                                analysis_type=analysis_type,
                                result_json={"success": False, "stage": "exception", "error": str(e)},
                                confidence=0.0,
                                latency_ms=0,
                            )
                        )
                        analyses_created += 1
                        logger.exception("AI screenshot analyze failed", run_id=run_id, step_id=step.id, analysis_type=analysis_type)

            await db.commit()

            return {
                "success": True,
                "run_id": run_id,
                "analyses_created": analyses_created,
            }

    return asyncio.run(_analyze())


@celery_app.task(bind=True, name="app.tasks.analysis.compare_test_runs")
def compare_test_runs(self, comparison_id: str) -> dict[str, Any]:
    """Compare two test runs using AI."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import RunComparison, TestRun, TestStepResult, TestRunNode
    from app.integrations.llm.client import get_llm_client
    from app.integrations.aliyun.oss_client import get_oss_client
    from sqlalchemy import select

    async def _compare():
        async with AsyncSessionLocal() as db:
            # Get the comparison record
            result = await db.execute(
                select(RunComparison).where(RunComparison.id == comparison_id)
            )
            comparison = result.scalar_one_or_none()
            if not comparison:
                return {"success": False, "error": "Comparison not found"}

            llm_client = get_llm_client()
            oss_client = get_oss_client()

            # Get screenshots from both runs
            async def get_run_screenshots(run_id):
                result = await db.execute(
                    select(TestStepResult)
                    .join(TestRunNode)
                    .where(
                        TestRunNode.test_run_id == run_id,
                        TestStepResult.screenshot_object_key.isnot(None),
                    )
                    .order_by(TestStepResult.step_index)
                )
                return result.scalars().all()

            baseline_steps = await get_run_screenshots(comparison.baseline_run_id)
            target_steps = await get_run_screenshots(comparison.target_run_id)

            differences = []
            total_similarity = 0
            comparison_count = 0

            # Compare matching steps
            for baseline_step, target_step in zip(baseline_steps, target_steps):
                try:
                    baseline_bytes = oss_client.download_bytes(baseline_step.screenshot_object_key)
                    target_bytes = oss_client.download_bytes(target_step.screenshot_object_key)

                    result = await llm_client.compare_screenshots(
                        baseline_bytes,
                        target_bytes,
                    )

                    if result["success"]:
                        differences.append({
                            "step_index": baseline_step.step_index,
                            "result": result["result"],
                        })
                        similarity = result["result"].get("overall_similarity", 100)
                        total_similarity += similarity
                        comparison_count += 1

                except Exception as e:
                    print(f"Error comparing steps: {e}")

            # Calculate risk score
            avg_similarity = total_similarity / comparison_count if comparison_count > 0 else 100
            risk_score = max(0, 100 - avg_similarity)

            # Update comparison record
            comparison.diff_summary = {
                "differences": differences,
                "comparison_count": comparison_count,
                "average_similarity": avg_similarity,
            }
            comparison.risk_score = risk_score
            await db.commit()

            return {
                "success": True,
                "comparison_id": comparison_id,
                "risk_score": risk_score,
            }

    return asyncio.run(_compare())


@celery_app.task(bind=True, name="app.tasks.analysis.calculate_risk_signals")
def calculate_risk_signals(self, run_id: str) -> dict[str, Any]:
    """Calculate risk signals for a test run."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import RiskSignal, ScreenAnalysis, TestRun, TestRunNode, TestStepResult
    from sqlalchemy import select

    async def _calculate():
        async with AsyncSessionLocal() as db:
            # Get all analyses for this run
            result = await db.execute(
                select(ScreenAnalysis)
                .join(TestStepResult)
                .join(TestRunNode)
                .where(TestRunNode.test_run_id == run_id)
            )
            analyses = result.scalars().all()

            # Calculate signals based on analysis results
            signals = []

            # Count anomalies
            anomaly_count = sum(
                1 for a in analyses
                if a.analysis_type == "anomaly" and a.result_json.get("has_anomaly", False)
            )
            if anomaly_count > 0:
                signal = RiskSignal(
                    test_run_id=run_id,
                    signal_type="layout_shift",
                    weight=0.3,
                    value=min(anomaly_count * 10, 100),
                    evidence_json={"anomaly_count": anomaly_count},
                )
                db.add(signal)
                signals.append(signal)

            # Check for failed nodes
            result = await db.execute(
                select(TestRunNode).where(
                    TestRunNode.test_run_id == run_id,
                    TestRunNode.status == "failed",
                )
            )
            failed_nodes = result.scalars().all()
            if failed_nodes:
                signal = RiskSignal(
                    test_run_id=run_id,
                    signal_type="crash",
                    weight=0.5,
                    value=min(len(failed_nodes) * 20, 100),
                    evidence_json={"failed_node_count": len(failed_nodes)},
                )
                db.add(signal)
                signals.append(signal)

            await db.commit()

            return {
                "success": True,
                "run_id": run_id,
                "signals_created": len(signals),
            }

    return asyncio.run(_calculate())
