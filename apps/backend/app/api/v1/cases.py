"""Test Cases API endpoints."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.database import get_db
from app.domain.models import Project, TestCase, TestCaseVersion, User
from app.schemas.schemas import (
    CreateVersionRequest,
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
    TestCaseVersionResponse,
    ValidateDSLRequest,
    ValidateDSLResponse,
)

router = APIRouter(tags=["Test Cases"])


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
    "/projects/{project_id}/cases",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case(
    project_id: UUID,
    payload: TestCaseCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new test case."""
    await verify_project_access(project_id, current_user, db)

    test_case = TestCase(
        project_id=str(project_id),
        name=payload.name,
        description=payload.description,
        dsl_content=payload.dsl_content.model_dump(),
        tags=payload.tags,
        status=payload.status,
    )
    db.add(test_case)
    await db.flush()
    await db.refresh(test_case)
    return TestCaseResponse.model_validate(test_case)


@router.get("/projects/{project_id}/cases", response_model=TestCaseListResponse)
async def list_test_cases(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str = Query(None, alias="status"),
    tag: str = Query(None),
):
    """List test cases for a project."""
    await verify_project_access(project_id, current_user, db)

    base_query = select(TestCase).where(
        TestCase.project_id == str(project_id),
        TestCase.deleted_at.is_(None),
    )

    if status_filter:
        base_query = base_query.where(TestCase.status == status_filter)

    if tag:
        base_query = base_query.where(TestCase.tags.contains([tag]))

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    query = (
        base_query.order_by(TestCase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    cases = result.scalars().all()

    return TestCaseListResponse(
        items=[TestCaseResponse.model_validate(c) for c in cases],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}", response_model=TestCaseResponse)
async def get_test_case(
    case_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a test case by ID."""
    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    return TestCaseResponse.model_validate(test_case)


@router.put("/cases/{case_id}", response_model=TestCaseResponse)
async def update_test_case(
    case_id: UUID,
    payload: TestCaseUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a test case."""
    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    
    if "dsl_content" in update_data and update_data["dsl_content"]:
        test_case.dsl_content = update_data.pop("dsl_content").model_dump() if hasattr(update_data["dsl_content"], "model_dump") else update_data.pop("dsl_content")
        test_case.dsl_version += 1

    for field, value in update_data.items():
        setattr(test_case, field, value)

    await db.flush()
    await db.refresh(test_case)
    return TestCaseResponse.model_validate(test_case)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    case_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a test case."""
    from datetime import datetime

    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    test_case.deleted_at = datetime.utcnow()
    await db.flush()


@router.post(
    "/cases/{case_id}/versions",
    response_model=TestCaseVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_case_version(
    case_id: UUID,
    payload: CreateVersionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of a test case."""
    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    test_case = result.scalar_one_or_none()

    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    max_version_result = await db.execute(
        select(func.max(TestCaseVersion.version_no)).where(
            TestCaseVersion.test_case_id == str(case_id)
        )
    )
    max_version = max_version_result.scalar() or 0

    version = TestCaseVersion(
        test_case_id=str(case_id),
        version_no=max_version + 1,
        dsl_content=test_case.dsl_content,
        change_log=payload.change_log,
        created_by=current_user.id,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return TestCaseVersionResponse.model_validate(version)


@router.get("/cases/{case_id}/versions", response_model=list[TestCaseVersionResponse])
async def list_test_case_versions(
    case_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """List all versions of a test case."""
    result = await db.execute(
        select(TestCase)
        .join(Project)
        .where(
            TestCase.id == str(case_id),
            Project.tenant_id == current_user.tenant_id,
            TestCase.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )

    result = await db.execute(
        select(TestCaseVersion)
        .where(TestCaseVersion.test_case_id == str(case_id))
        .order_by(TestCaseVersion.version_no.desc())
    )
    versions = result.scalars().all()
    return [TestCaseVersionResponse.model_validate(v) for v in versions]


@router.post("/cases/validate-dsl", response_model=ValidateDSLResponse)
async def validate_dsl(
    payload: ValidateDSLRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Validate DSL content."""
    errors = []
    warnings = []

    dsl = payload.dsl_content

    if not dsl.name or len(dsl.name.strip()) == 0:
        errors.append("DSL name is required")

    if not dsl.steps or len(dsl.steps) == 0:
        errors.append("At least one step is required")

    valid_actions = {
        "launch_app", "close_app", "tap", "click", "input", "swipe",
        "scroll", "wait", "assert", "screenshot", "back", "home",
        "clear", "long_press", "double_tap", "drag",
    }

    for i, step in enumerate(dsl.steps):
        if step.action not in valid_actions:
            warnings.append(f"Step {i + 1}: Unknown action '{step.action}'")

        if step.action in ("tap", "click", "input", "clear", "long_press"):
            if not step.target:
                errors.append(f"Step {i + 1}: '{step.action}' requires a target")

        if step.action == "input":
            if step.value is None:
                errors.append(f"Step {i + 1}: 'input' requires a value")

    return ValidateDSLResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
