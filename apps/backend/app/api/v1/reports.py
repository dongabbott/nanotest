"""Reports API endpoints for AI analysis and comparison."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.database import get_db
from app.domain.models import Project, TestRun, User
from app.services.test_run_service import TestRunService

router = APIRouter(tags=["Reports"])


# ============ Endpoints ============
# Note: ai-analyze, ai-summary, risk-score, compare, comparisons endpoints 
# are defined in runs.py with proper authentication


@router.get("/runs/{run_id}/step-analyses")
async def get_step_analyses(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    step_index: Optional[int] = Query(None, description="Filter by step index"),
    analysis_type: Optional[str] = Query(None, description="Filter by analysis type"),
    db: AsyncSession = Depends(get_db)
):
    """Get all AI analyses for steps in a test run."""
    from sqlalchemy import select
    
    # Verify run exists and user has access
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    run_service = TestRunService(db)
    analyses = await run_service.get_step_analyses(
        run_id=run_id,
        step_index=step_index,
        analysis_type=analysis_type
    )
    
    return {
        "run_id": run_id,
        "total": len(analyses),
        "analyses": [
            {
                "id": str(a.id),
                "step_result_id": str(a.test_step_result_id),
                "analysis_type": a.analysis_type,
                "model_name": a.model_name,
                "result": a.result_json,
                "confidence": a.confidence,
                "latency_ms": a.latency_ms,
                "created_at": a.created_at.isoformat()
            }
            for a in analyses
        ]
    }


@router.get("/projects/{project_id}/risk-trends")
async def get_project_risk_trends(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    days: int = Query(30, ge=1, le=90, description="Number of days to include"),
    db: AsyncSession = Depends(get_db)
):
    """Get risk score trends for a project over time."""
    from sqlalchemy import select
    from app.services.project_service import ProjectService
    
    # Verify project exists and user has access
    result = await db.execute(
        select(Project).where(
            Project.id == str(project_id),
            Project.tenant_id == current_user.tenant_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_service = ProjectService(db)
    trends = await project_service.get_risk_trends(project_id, days)
    
    return {
        "project_id": project_id,
        "days": days,
        "trends": trends
    }
