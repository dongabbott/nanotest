"""Report aggregation Celery tasks."""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.reports.generate_run_report")
def generate_run_report(self, run_id: str, report_format: str = "json") -> dict[str, Any]:
    """Generate a comprehensive report for a test run."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import (
        TestRun, TestRunNode, TestStepResult, ScreenAnalysis, 
        RiskSignal, TestCase, TestFlow
    )
    from app.integrations.minio.client import get_minio_client
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import json

    async def _generate():
        async with AsyncSessionLocal() as db:
            # Get the test run with related data
            result = await db.execute(
                select(TestRun)
                .options(selectinload(TestRun.nodes))
                .where(TestRun.id == UUID(run_id))
            )
            run = result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Run not found"}

            # Get all nodes with step results
            result = await db.execute(
                select(TestRunNode)
                .options(selectinload(TestRunNode.step_results))
                .where(TestRunNode.test_run_id == UUID(run_id))
                .order_by(TestRunNode.order_index)
            )
            nodes = result.scalars().all()

            # Get risk signals
            result = await db.execute(
                select(RiskSignal).where(RiskSignal.test_run_id == UUID(run_id))
            )
            risk_signals = result.scalars().all()

            # Calculate overall metrics
            total_nodes = len(nodes)
            passed_nodes = sum(1 for n in nodes if n.status == "passed")
            failed_nodes = sum(1 for n in nodes if n.status == "failed")
            skipped_nodes = sum(1 for n in nodes if n.status == "skipped")

            total_steps = sum(len(n.step_results) for n in nodes)
            passed_steps = sum(
                sum(1 for s in n.step_results if s.status == "passed")
                for n in nodes
            )
            failed_steps = sum(
                sum(1 for s in n.step_results if s.status == "failed")
                for n in nodes
            )

            # Calculate total duration
            total_duration_ms = sum(
                sum(s.duration_ms or 0 for s in n.step_results)
                for n in nodes
            )

            # Build node details
            node_details = []
            for node in nodes:
                step_details = []
                for step in sorted(node.step_results, key=lambda s: s.step_index):
                    # Get analyses for this step
                    result = await db.execute(
                        select(ScreenAnalysis)
                        .where(ScreenAnalysis.test_step_result_id == step.id)
                    )
                    analyses = result.scalars().all()

                    step_details.append({
                        "step_index": step.step_index,
                        "action": step.action,
                        "status": step.status,
                        "duration_ms": step.duration_ms,
                        "error_message": step.error_message,
                        "has_screenshot": step.screenshot_object_key is not None,
                        "analyses": [
                            {
                                "type": a.analysis_type,
                                "confidence": a.confidence,
                                "result": a.result_json,
                            }
                            for a in analyses
                        ],
                    })

                node_details.append({
                    "node_id": str(node.id),
                    "test_case_id": str(node.test_case_id) if node.test_case_id else None,
                    "order_index": node.order_index,
                    "status": node.status,
                    "retry_count": node.retry_count,
                    "started_at": node.started_at.isoformat() if node.started_at else None,
                    "finished_at": node.finished_at.isoformat() if node.finished_at else None,
                    "steps": step_details,
                })

            # Build risk signal summary
            risk_summary = {
                "total_signals": len(risk_signals),
                "signals": [
                    {
                        "type": s.signal_type,
                        "weight": s.weight,
                        "value": s.value,
                        "evidence": s.evidence_json,
                    }
                    for s in risk_signals
                ],
                "overall_risk_score": run.risk_score,
            }

            # Build the report
            report = {
                "report_id": f"report-{run_id}",
                "generated_at": datetime.utcnow().isoformat(),
                "run": {
                    "id": str(run.id),
                    "test_flow_id": str(run.test_flow_id) if run.test_flow_id else None,
                    "status": run.status,
                    "trigger": run.trigger,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                    "device_info": run.device_info,
                    "app_info": run.app_info,
                },
                "summary": {
                    "total_nodes": total_nodes,
                    "passed_nodes": passed_nodes,
                    "failed_nodes": failed_nodes,
                    "skipped_nodes": skipped_nodes,
                    "pass_rate": (passed_nodes / total_nodes * 100) if total_nodes > 0 else 0,
                    "total_steps": total_steps,
                    "passed_steps": passed_steps,
                    "failed_steps": failed_steps,
                    "total_duration_ms": total_duration_ms,
                },
                "risk": risk_summary,
                "nodes": node_details,
            }

            # Store report in MinIO if needed
            if report_format == "json":
                minio_client = get_minio_client()
                report_key = f"reports/{run_id}/report.json"
                report_bytes = json.dumps(report, indent=2).encode("utf-8")
                minio_client.upload_bytes(
                    "reports",
                    report_key,
                    report_bytes,
                    content_type="application/json",
                )
                report["report_url"] = report_key

            return {
                "success": True,
                "run_id": run_id,
                "report": report,
            }

    return asyncio.run(_generate())


@celery_app.task(bind=True, name="app.tasks.reports.generate_project_summary")
def generate_project_summary(
    self, 
    project_id: str, 
    days: int = 7
) -> dict[str, Any]:
    """Generate a summary report for a project over a time period."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import Project, TestRun, TestFlow
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload

    async def _generate():
        async with AsyncSessionLocal() as db:
            # Get the project
            result = await db.execute(
                select(Project).where(Project.id == UUID(project_id))
            )
            project = result.scalar_one_or_none()
            if not project:
                return {"success": False, "error": "Project not found"}

            # Get test runs in the time period
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await db.execute(
                select(TestRun)
                .join(TestFlow)
                .where(
                    TestFlow.project_id == UUID(project_id),
                    TestRun.created_at >= cutoff_date,
                )
                .order_by(TestRun.created_at.desc())
            )
            runs = result.scalars().all()

            # Calculate statistics
            total_runs = len(runs)
            passed_runs = sum(1 for r in runs if r.status == "passed")
            failed_runs = sum(1 for r in runs if r.status == "failed")

            # Calculate average risk score
            risk_scores = [r.risk_score for r in runs if r.risk_score is not None]
            avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0

            # Calculate average duration
            durations = []
            for run in runs:
                if run.started_at and run.finished_at:
                    duration = (run.finished_at - run.started_at).total_seconds() * 1000
                    durations.append(duration)
            avg_duration_ms = sum(durations) / len(durations) if durations else 0

            # Group runs by day
            runs_by_day: Dict[str, Dict[str, int]] = {}
            for run in runs:
                day_key = run.created_at.strftime("%Y-%m-%d")
                if day_key not in runs_by_day:
                    runs_by_day[day_key] = {"total": 0, "passed": 0, "failed": 0}
                runs_by_day[day_key]["total"] += 1
                if run.status == "passed":
                    runs_by_day[day_key]["passed"] += 1
                elif run.status == "failed":
                    runs_by_day[day_key]["failed"] += 1

            # Get top failing test cases
            from app.domain.models import TestRunNode
            result = await db.execute(
                select(
                    TestRunNode.test_case_id,
                    func.count(TestRunNode.id).label("fail_count")
                )
                .join(TestRun)
                .join(TestFlow)
                .where(
                    TestFlow.project_id == UUID(project_id),
                    TestRun.created_at >= cutoff_date,
                    TestRunNode.status == "failed",
                )
                .group_by(TestRunNode.test_case_id)
                .order_by(func.count(TestRunNode.id).desc())
                .limit(10)
            )
            top_failures = result.all()

            summary = {
                "project_id": str(project_id),
                "project_name": project.name,
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "overview": {
                    "total_runs": total_runs,
                    "passed_runs": passed_runs,
                    "failed_runs": failed_runs,
                    "pass_rate": (passed_runs / total_runs * 100) if total_runs > 0 else 0,
                    "avg_risk_score": avg_risk_score,
                    "avg_duration_ms": avg_duration_ms,
                },
                "trend": {
                    "runs_by_day": runs_by_day,
                },
                "top_failures": [
                    {"test_case_id": str(tc_id), "fail_count": count}
                    for tc_id, count in top_failures
                    if tc_id is not None
                ],
            }

            return {
                "success": True,
                "project_id": project_id,
                "summary": summary,
            }

    return asyncio.run(_generate())


@celery_app.task(bind=True, name="app.tasks.reports.aggregate_comparison_report")
def aggregate_comparison_report(
    self,
    baseline_run_id: str,
    target_run_ids: List[str],
) -> dict[str, Any]:
    """Generate an aggregated comparison report across multiple runs."""
    from app.core.database import AsyncSessionLocal
    from app.domain.models import TestRun, RunComparison
    from sqlalchemy import select

    async def _aggregate():
        async with AsyncSessionLocal() as db:
            # Get baseline run
            result = await db.execute(
                select(TestRun).where(TestRun.id == UUID(baseline_run_id))
            )
            baseline = result.scalar_one_or_none()
            if not baseline:
                return {"success": False, "error": "Baseline run not found"}

            comparisons = []
            for target_id in target_run_ids:
                # Get comparison if exists
                result = await db.execute(
                    select(RunComparison).where(
                        RunComparison.baseline_run_id == UUID(baseline_run_id),
                        RunComparison.target_run_id == UUID(target_id),
                    )
                )
                comparison = result.scalar_one_or_none()

                if comparison:
                    comparisons.append({
                        "target_run_id": target_id,
                        "risk_score": comparison.risk_score,
                        "diff_summary": comparison.diff_summary,
                        "created_at": comparison.created_at.isoformat() if comparison.created_at else None,
                    })

            # Calculate aggregate metrics
            risk_scores = [c["risk_score"] for c in comparisons if c["risk_score"] is not None]
            avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
            max_risk = max(risk_scores) if risk_scores else 0

            report = {
                "baseline_run_id": baseline_run_id,
                "comparison_count": len(comparisons),
                "aggregate_metrics": {
                    "average_risk_score": avg_risk,
                    "max_risk_score": max_risk,
                    "high_risk_count": sum(1 for r in risk_scores if r > 70),
                    "medium_risk_count": sum(1 for r in risk_scores if 30 < r <= 70),
                    "low_risk_count": sum(1 for r in risk_scores if r <= 30),
                },
                "comparisons": comparisons,
                "generated_at": datetime.utcnow().isoformat(),
            }

            return {
                "success": True,
                "report": report,
            }

    return asyncio.run(_aggregate())


@celery_app.task(bind=True, name="app.tasks.reports.cleanup_old_reports")
def cleanup_old_reports(self, retention_days: int = 30) -> dict[str, Any]:
    """Clean up old reports from storage."""
    from app.integrations.minio.client import get_minio_client
    from datetime import datetime, timedelta

    try:
        minio_client = get_minio_client()
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # List and delete old report objects
        deleted_count = 0
        objects = minio_client.list_objects("reports", prefix="reports/")
        
        for obj in objects:
            if obj.last_modified and obj.last_modified < cutoff_date:
                minio_client.delete_object("reports", obj.object_name)
                deleted_count += 1

        return {
            "success": True,
            "deleted_count": deleted_count,
            "retention_days": retention_days,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
