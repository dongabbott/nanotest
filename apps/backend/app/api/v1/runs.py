"""Test Runs API endpoints."""
import uuid as uuid_module
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import get_current_active_user
from app.core.database import get_db
from app.domain.models import (
    Project,
    RunComparison,
    TestFlow,
    TestPlan,
    TestRun,
    TestRunNode,
    TestStepResult,
    User,
)
from app.schemas.schemas import (
    AIAnalyzeRequest,
    AIAnalyzeResponse,
    AISummaryResponse,
    CompareRunsRequest,
    CompareRunsResponse,
    RiskScoreResponse,
    RunComparisonResponse,
    RunCreateRequest,
    RunCreateResponse,
    TestPlanCreate,
    TestPlanListResponse,
    TestPlanResponse,
    TestPlanUpdate,
    TestRunDetailResponse,
    TestRunListResponse,
    TestRunNodeResponse,
    TestRunResponse,
    TestStepResultResponse,
    ScreenAnalysisResponse,
)

from app.core.config import settings

router = APIRouter(tags=["Test Runs"])


async def verify_project_access(
    project_id: UUID,
    user: User,
    db: AsyncSession,
) -> Project:
    """Verify user has access to the project."""
    result = await db.execute(
        select(Project).where(
            Project.id == str(project_id),
            Project.tenant_id == user.tenant_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def generate_run_number() -> str:
    """Generate a unique run number."""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_suffix = uuid_module.uuid4().hex[:6].upper()
    return f"RUN-{timestamp}-{random_suffix}"


# =============================================================================
# Test Plan Endpoints
# =============================================================================


@router.post(
    "/projects/{project_id}/plans",
    response_model=TestPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_plan(
    project_id: UUID,
    payload: TestPlanCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new test plan."""
    await verify_project_access(project_id, current_user, db)

    # Verify flow exists
    result = await db.execute(
        select(TestFlow).where(
            TestFlow.id == str(payload.flow_id),
            TestFlow.project_id == str(project_id),
            TestFlow.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    plan = TestPlan(
        project_id=str(project_id),
        name=payload.name,
        trigger_type=payload.trigger_type,
        cron_expr=payload.cron_expr,
        flow_id=str(payload.flow_id),
        env_config=payload.env_config,
        is_enabled=payload.is_enabled,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)
    return TestPlanResponse.model_validate(plan)


@router.get("/projects/{project_id}/plans", response_model=TestPlanListResponse)
async def list_test_plans(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """List test plans for a project."""
    await verify_project_access(project_id, current_user, db)

    base_query = select(TestPlan).where(
        TestPlan.project_id == str(project_id),
        TestPlan.deleted_at.is_(None),
    )

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Get items
    query = (
        base_query.order_by(TestPlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    plans = result.scalars().all()

    return TestPlanListResponse(
        items=[TestPlanResponse.model_validate(p) for p in plans],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/plans/{plan_id}", response_model=TestPlanResponse)
async def get_test_plan(
    plan_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a test plan by ID."""
    result = await db.execute(
        select(TestPlan)
        .join(Project)
        .where(
            TestPlan.id == str(plan_id),
            Project.tenant_id == current_user.tenant_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    return TestPlanResponse.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=TestPlanResponse)
async def update_test_plan(
    plan_id: UUID,
    payload: TestPlanUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a test plan."""
    result = await db.execute(
        select(TestPlan)
        .join(Project)
        .where(
            TestPlan.id == str(plan_id),
            Project.tenant_id == current_user.tenant_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)

    await db.flush()
    await db.refresh(plan)
    return TestPlanResponse.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_plan(
    plan_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a test plan."""
    result = await db.execute(
        select(TestPlan)
        .join(Project)
        .where(
            TestPlan.id == str(plan_id),
            Project.tenant_id == current_user.tenant_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    plan.deleted_at = datetime.utcnow()
    await db.flush()


# =============================================================================
# Test Run Endpoints
# =============================================================================


@router.post(
    "/plans/{plan_id}/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_test_run(
    plan_id: UUID,
    payload: RunCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Trigger a new test run from a plan."""
    result = await db.execute(
        select(TestPlan)
        .join(Project)
        .where(
            TestPlan.id == str(plan_id),
            Project.tenant_id == current_user.tenant_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    if not plan.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test plan is disabled",
        )

    run = TestRun(
        project_id=plan.project_id,
        plan_id=plan_id,
        flow_id=plan.flow_id,
        run_no=generate_run_number(),
        status="queued",
        triggered_by=current_user.id,
        env_config=plan.env_config,
        summary={},
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    from app.tasks.execution import execute_test_run
    execute_test_run.delay(str(run.id))

    return RunCreateResponse(
        run_id=run.id,
        run_no=run.run_no,
        status=run.status,
    )


@router.post(
    "/plans/{plan_id}/trigger",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_plan(
    plan_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a test plan execution.
    """
    result = await db.execute(
        select(TestPlan)
        .join(Project)
        .where(
            TestPlan.id == str(plan_id),
            Project.tenant_id == current_user.tenant_id,
            TestPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test plan not found",
        )

    if not plan.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test plan is disabled",
        )

    run = TestRun(
        project_id=plan.project_id,
        plan_id=plan_id,
        flow_id=plan.flow_id,
        run_no=generate_run_number(),
        status="queued",
        triggered_by=current_user.id,
        env_config=plan.env_config,
        summary={},
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)

    from app.tasks.execution import execute_test_run
    execute_test_run.delay(str(run.id))

    return RunCreateResponse(
        run_id=run.id,
        run_no=run.run_no,
        status=run.status,
    )


@router.get("/projects/{project_id}/runs", response_model=TestRunListResponse)
async def list_test_runs(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: str = Query(None, alias="status"),
):
    """List test runs for a project."""
    await verify_project_access(project_id, current_user, db)

    base_query = select(TestRun).where(TestRun.project_id == str(project_id))

    if status_filter:
        base_query = base_query.where(TestRun.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Get items
    query = (
        base_query.order_by(TestRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    runs = result.scalars().all()

    return TestRunListResponse(
        items=[TestRunResponse.model_validate(r) for r in runs],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a test run by ID."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    return TestRunResponse.model_validate(run)


@router.get("/runs/{run_id}/detail", response_model=TestRunDetailResponse)
async def get_test_run_detail(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a test run with all nodes and steps in a single response."""
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .options(
            selectinload(TestRun.nodes).selectinload(TestRunNode.step_results),
        )
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    public_host = (settings.oss_url_scheme or "").rstrip("/")

    # Build nodes with steps
    nodes_response = []
    for node in sorted(run.nodes, key=lambda n: n.created_at):
        steps = []
        for s in sorted(node.step_results, key=lambda s: s.step_index):
            step_resp = TestStepResultResponse.model_validate(s)
            step_data = step_resp.model_dump()
            if step_data.get("screenshot_object_key") and public_host:
                step_data["screenshot_url"] = f"{public_host}/{step_data['screenshot_object_key']}"
            steps.append(step_data)

        node_resp = TestRunNodeResponse.model_validate(node)
        node_data = node_resp.model_dump()
        node_data["steps"] = steps
        nodes_response.append(node_data)

    return TestRunDetailResponse(
        id=run.id,
        project_id=run.project_id,
        plan_id=run.plan_id,
        flow_id=run.flow_id,
        run_no=run.run_no,
        status=run.status,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        summary=run.summary or {},
        env_config=run.env_config or {},
        created_at=run.created_at,
        updated_at=run.updated_at,
        nodes=nodes_response,
    )


@router.post("/runs/{run_id}/cancel", response_model=TestRunResponse)
async def cancel_test_run(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running test."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    if run.status not in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel run in '{run.status}' status",
        )

    run.status = "cancelled"
    run.finished_at = datetime.utcnow()
    await db.flush()
    await db.refresh(run)

    # TODO: Signal Celery to cancel the task

    return TestRunResponse.model_validate(run)


@router.get("/runs/{run_id}/nodes", response_model=list[TestRunNodeResponse])
async def get_run_nodes(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get all nodes for a test run."""
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    result = await db.execute(
        select(TestRunNode)
        .options(selectinload(TestRunNode.step_results))
        .where(TestRunNode.test_run_id == str(run_id))
        .order_by(TestRunNode.created_at)
    )
    nodes = result.scalars().all()

    nodes_response = []
    for node in nodes:
        steps = [
            TestStepResultResponse.model_validate(s)
            for s in sorted(node.step_results, key=lambda s: s.step_index)
        ]
        node_resp = TestRunNodeResponse.model_validate(node)
        node_resp.steps = steps
        nodes_response.append(node_resp)
    return nodes_response


@router.get("/runs/{run_id}/nodes/{node_id}/steps", response_model=list[TestStepResultResponse])
async def get_node_steps(
    run_id: UUID,
    node_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get all step results for a run node."""
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    result = await db.execute(
        select(TestStepResult)
        .where(TestStepResult.run_node_id == node_id)
        .order_by(TestStepResult.step_index)
    )
    steps = result.scalars().all()
    return [TestStepResultResponse.model_validate(s) for s in steps]


@router.get("/runs/{run_id}/steps", response_model=list[TestStepResultResponse])
async def get_run_steps(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get all step results for a test run (across all nodes)."""
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Get all steps from all nodes of this run
    result = await db.execute(
        select(TestStepResult)
        .join(TestRunNode)
        .where(TestRunNode.test_run_id == str(run_id))
        .order_by(TestRunNode.created_at, TestStepResult.step_index)
    )
    steps = result.scalars().all()
    return [TestStepResultResponse.model_validate(s) for s in steps]


@router.post("/runs/{run_id}/ai-analyze", response_model=AIAnalyzeResponse)
async def ai_analyze_run(
    run_id: UUID,
    payload: AIAnalyzeRequest = None,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI analysis for a test run."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Check run is completed
    if run.status not in ("passed", "failed", "completed", "partial"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot analyze run in '{run.status}' status. Run must be completed.",
        )

    # Generate a task ID for tracking
    task_id = uuid_module.uuid4().hex

    # Dispatch Celery task for AI analysis
    from app.tasks.analysis import analyze_test_run

    analysis_types = payload.analysis_types if payload and payload.analysis_types else ["anomaly"]
    analyze_test_run.apply_async(args=[str(run_id), analysis_types], task_id=task_id)

    return AIAnalyzeResponse(
        task_id=task_id,
        status="queued",
        message="AI analysis task has been queued",
    )


@router.get("/runs/{run_id}/ai-analyses", response_model=list[ScreenAnalysisResponse])
async def list_run_ai_analyses(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    analysis_type: Optional[str] = Query(None, description="Filter by analysis_type"),
):
    """List all AI screen analyses for a run (detailed rows)."""
    from app.domain.models import ScreenAnalysis

    # Verify run access
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test run not found")

    q = (
        select(ScreenAnalysis)
        .options(selectinload(ScreenAnalysis.step_result))
        .join(TestStepResult)
        .join(TestRunNode)
        .where(TestRunNode.test_run_id == str(run_id))
        .order_by(ScreenAnalysis.created_at.desc())
    )

    if analysis_type:
        q = q.where(ScreenAnalysis.analysis_type == analysis_type)

    result = await db.execute(q)
    rows = result.scalars().all()

    public_host = (settings.oss_url_scheme or "").rstrip("/")

    enriched: list[ScreenAnalysisResponse] = []
    for r in rows:
        resp = ScreenAnalysisResponse.model_validate(r)
        step = getattr(r, "step_result", None)
        object_key = getattr(step, "screenshot_object_key", None) if step is not None else None
        resp.screenshot_object_key = object_key
        if object_key and public_host:
            resp.screenshot_url = f"{public_host}/{object_key}"
        enriched.append(resp)

    return enriched


@router.get("/runs/{run_id}/steps/{step_id}/ai-analyses", response_model=list[ScreenAnalysisResponse])
async def list_step_ai_analyses(
    run_id: UUID,
    step_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """List AI analyses for a specific step in a run."""
    from app.domain.models import ScreenAnalysis

    # Verify run access
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == str(run_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test run not found")

    result = await db.execute(
        select(ScreenAnalysis)
        .where(ScreenAnalysis.test_step_result_id == step_id)
        .order_by(ScreenAnalysis.created_at.desc())
    )
    rows = result.scalars().all()

    step_result = await db.get(TestStepResult, str(step_id))
    public_host = (settings.oss_url_scheme or "").rstrip("/")
    object_key = getattr(step_result, "screenshot_object_key", None) if step_result else None

    enriched: list[ScreenAnalysisResponse] = []
    for r in rows:
        resp = ScreenAnalysisResponse.model_validate(r)
        resp.screenshot_object_key = object_key
        if object_key and public_host:
            resp.screenshot_url = f"{public_host}/{object_key}"
        enriched.append(resp)

    return enriched


@router.get("/runs/{run_id}/ai-summary", response_model=AISummaryResponse)
async def get_ai_summary(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get AI analysis summary for a test run."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Get AI analysis results from the run's summary or dedicated table
    # For now, return a placeholder response
    ai_summary = run.summary.get("ai_analysis", {})
    
    return AISummaryResponse(
        run_id=run_id,
        total_analyses=ai_summary.get("total_analyses", 0),
        anomaly_count=ai_summary.get("anomaly_count", 0),
        categories=ai_summary.get("categories", {}),
        highlights=ai_summary.get("highlights", []),
        risk_score=ai_summary.get("risk_score", 0.0),
    )


@router.get("/runs/{run_id}/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(
    run_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get risk score for a test run."""
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Calculate risk score based on run results
    summary = run.summary or {}
    total_nodes = summary.get("total_nodes", 0)
    failed_nodes = summary.get("failed_nodes", 0)
    
    # Simple risk calculation
    risk_score = 0.0
    signals = []
    
    if total_nodes > 0:
        failure_rate = failed_nodes / total_nodes
        risk_score = min(failure_rate * 100, 100.0)
        
        if failure_rate > 0.5:
            signals.append({
                "type": "high_failure_rate",
                "severity": "high",
                "message": f"More than 50% of test nodes failed ({failed_nodes}/{total_nodes})"
            })
        elif failure_rate > 0.2:
            signals.append({
                "type": "moderate_failure_rate",
                "severity": "medium",
                "message": f"More than 20% of test nodes failed ({failed_nodes}/{total_nodes})"
            })
    
    if run.status == "failed":
        signals.append({
            "type": "run_failed",
            "severity": "high",
            "message": "Test run completed with failed status"
        })

    # Determine recommendation
    if risk_score >= 70:
        recommendation = "Critical issues detected. Immediate investigation required."
    elif risk_score >= 40:
        recommendation = "Moderate risk. Review failed test cases before deployment."
    elif risk_score > 0:
        recommendation = "Low risk. Minor issues detected, consider reviewing."
    else:
        recommendation = "No issues detected. Safe to proceed."

    return RiskScoreResponse(
        run_id=run_id,
        risk_score=risk_score,
        signals=signals,
        recommendation=recommendation,
    )


@router.post("/runs/compare", response_model=CompareRunsResponse)
async def compare_runs(
    payload: CompareRunsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Compare two test runs."""
    # Verify baseline run exists and user has access
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == payload.baseline_run_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    baseline_run = result.scalar_one_or_none()
    if not baseline_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline run not found",
        )

    # Verify target run exists and user has access
    result = await db.execute(
        select(TestRun)
        .join(Project)
        .where(
            TestRun.id == payload.target_run_id,
            Project.tenant_id == current_user.tenant_id,
        )
    )
    target_run = result.scalar_one_or_none()
    if not target_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target run not found",
        )

    # Create comparison record
    comparison = RunComparison(
        project_id=baseline_run.project_id,
        baseline_run_id=payload.baseline_run_id,
        target_run_id=payload.target_run_id,
        diff_summary={},
        risk_score=0.0,
    )
    db.add(comparison)
    await db.flush()
    await db.refresh(comparison)

    # TODO: Dispatch async task to perform detailed comparison
    # from app.tasks.analysis import compare_test_runs
    # compare_test_runs.delay(str(comparison.id))

    return CompareRunsResponse(
        comparison_id=comparison.id,
        status="processing",
    )


@router.get("/comparisons/{comparison_id}", response_model=RunComparisonResponse)
async def get_comparison(
    comparison_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a run comparison by ID."""
    result = await db.execute(
        select(RunComparison)
        .join(Project)
        .where(
            RunComparison.id == str(comparison_id),
            Project.tenant_id == current_user.tenant_id,
        )
    )
    comparison = result.scalar_one_or_none()

    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found",
        )

    return RunComparisonResponse.model_validate(comparison)


@router.get("/oss/presign")
async def presign_oss_object(
    object_key: str = Query(..., description="OSS object key, e.g. screenshots/..."),
    expires: int = Query(3600, ge=60, le=24 * 3600, description="URL expiry in seconds"),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """Generate a short-lived presigned URL for an OSS object.

    Used by the Web UI to preview screenshots and download logs.
    """
    try:
        from app.integrations.aliyun.oss_client import get_oss_client

        client = get_oss_client()
        url = client.get_download_url(object_key, expires=expires)
        return {"url": url, "expires_in": expires}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to presign OSS url: {e}")
