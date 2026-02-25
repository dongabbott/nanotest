"""Test Flows API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.database import get_db
from app.domain.models import FlowNodeBinding, Project, TestCase, TestFlow, TestRun, User
from app.schemas.schemas import (
    CompileFlowResponse,
    FlowNodeBindingCreate,
    FlowNodeBindingResponse,
    TestFlowCreate,
    TestFlowListResponse,
    TestFlowResponse,
    TestFlowUpdate,
    TestRunCreate,
    TestRunResponse,
)

router = APIRouter(tags=["Test Flows"])


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


@router.post(
    "/projects/{project_id}/flows",
    response_model=TestFlowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_flow(
    project_id: UUID,
    payload: TestFlowCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new test flow."""
    await verify_project_access(project_id, current_user, db)

    flow = TestFlow(
        project_id=str(project_id),
        name=payload.name,
        description=payload.description,
        graph_json=payload.graph_json.model_dump(),
        entry_node=payload.entry_node,
        status=payload.status,
    )
    db.add(flow)
    await db.flush()
    await db.refresh(flow)
    return TestFlowResponse.model_validate(flow)


@router.get("/projects/{project_id}/flows", response_model=TestFlowListResponse)
async def list_test_flows(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List test flows for a project."""
    await verify_project_access(project_id, current_user, db)

    base_query = select(TestFlow).where(
        TestFlow.project_id == str(project_id),
        TestFlow.deleted_at.is_(None),
    )

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    query = (
        base_query.order_by(TestFlow.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    flows = result.scalars().all()

    return TestFlowListResponse(
        items=[TestFlowResponse.model_validate(f) for f in flows],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/flows/{flow_id}", response_model=TestFlowResponse)
async def get_test_flow(
    flow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a test flow by ID."""
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    return TestFlowResponse.model_validate(flow)


@router.put("/flows/{flow_id}", response_model=TestFlowResponse)
async def update_test_flow(
    flow_id: UUID,
    payload: TestFlowUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a test flow."""
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    
    if "graph_json" in update_data and update_data["graph_json"]:
        flow.graph_json = update_data.pop("graph_json").model_dump() if hasattr(update_data["graph_json"], "model_dump") else update_data.pop("graph_json")

    for field, value in update_data.items():
        setattr(flow, field, value)

    await db.flush()
    await db.refresh(flow)
    return TestFlowResponse.model_validate(flow)


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_flow(
    flow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a test flow."""
    from datetime import datetime

    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    flow.deleted_at = datetime.utcnow()
    await db.flush()


@router.post(
    "/flows/{flow_id}/bindings",
    response_model=FlowNodeBindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flow_binding(
    flow_id: UUID,
    payload: FlowNodeBindingCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a node binding for a flow."""
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(payload.test_case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    binding = FlowNodeBinding(
        flow_id=str(flow_id),
        node_key=payload.node_key,
        test_case_id=str(payload.test_case_id),
        retry_policy=payload.retry_policy,
        timeout_sec=payload.timeout_sec,
    )
    db.add(binding)
    await db.flush()
    await db.refresh(binding)
    return FlowNodeBindingResponse.model_validate(binding)


@router.get("/flows/{flow_id}/bindings", response_model=list[FlowNodeBindingResponse])
async def list_flow_bindings(
    flow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """List all node bindings for a flow."""
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    result = await db.execute(
        select(FlowNodeBinding).where(FlowNodeBinding.flow_id == str(flow_id))
    )
    bindings = result.scalars().all()
    return [FlowNodeBindingResponse.model_validate(b) for b in bindings]


@router.post("/flows/{flow_id}/compile", response_model=CompileFlowResponse)
async def compile_flow(
    flow_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Compile and validate a test flow."""
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()

    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )

    errors = []
    warnings = []
    
    graph = flow.graph_json
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        errors.append("Flow must have at least one node")

    if flow.entry_node:
        entry_exists = any(n.get("id") == flow.entry_node for n in nodes)
        if not entry_exists:
            errors.append(f"Entry node '{flow.entry_node}' not found in graph")

    result = await db.execute(
        select(FlowNodeBinding).where(FlowNodeBinding.flow_id == str(flow_id))
    )
    bindings = result.scalars().all()
    bound_nodes = {b.node_key for b in bindings}

    for node in nodes:
        if node.get("type") == "test_case":
            if node.get("id") not in bound_nodes:
                warnings.append(f"Node '{node.get('id')}' has no test case binding")

    node_ids = {n.get("id") for n in nodes}
    for edge in edges:
        if edge.get("source") not in node_ids:
            errors.append(f"Edge source '{edge.get('source')}' not found")
        if edge.get("target") not in node_ids:
            errors.append(f"Edge target '{edge.get('target')}' not found")

    return CompileFlowResponse(
        success=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        compiled_graph=graph if len(errors) == 0 else None,
    )


@router.post("/flows/{flow_id}/runs", response_model=TestRunResponse, status_code=status.HTTP_201_CREATED)
async def create_flow_run(
    flow_id: UUID,
    payload: TestRunCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create and trigger a new test run for a flow."""
    from datetime import datetime
    from app.tasks.execution import execute_test_run
    
    result = await db.execute(
        select(TestFlow)
        .join(Project)
        .where(
            TestFlow.id == str(flow_id),
            Project.tenant_id == current_user.tenant_id,
            TestFlow.deleted_at.is_(None),
        )
    )
    flow = result.scalar_one_or_none()
    
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test flow not found",
        )
    
    result = await db.execute(
        select(func.count()).where(FlowNodeBinding.flow_id == str(flow_id))
    )
    binding_count = result.scalar() or 0
    if binding_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flow has no node bindings. Add test cases to the flow before running.",
        )
    
    result = await db.execute(
        select(func.count()).where(TestRun.flow_id == str(flow_id))
    )
    run_count = (result.scalar() or 0) + 1
    run_no = f"RUN-{str(flow_id)[:8].upper()}-{run_count:04d}"
    
    test_run = TestRun(
        project_id=flow.project_id,
        plan_id=payload.plan_id,
        flow_id=str(flow_id),
        run_no=run_no,
        status="queued",
        triggered_by=current_user.id,
        env_config=payload.env_config or {},
    )
    db.add(test_run)
    await db.flush()
    await db.refresh(test_run)
    
    execute_test_run.delay(str(test_run.id))
    
    return TestRunResponse.model_validate(test_run)
