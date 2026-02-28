"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, model_validator
from app.core.config import settings


# =============================================================================
# Base Schemas
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Auth Schemas
# =============================================================================

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Login response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str
    tenant_id: str
    role: str
    exp: datetime


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="qa", pattern="^(owner|admin|qa|viewer)$")


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=6)
    tenant_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    """User update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, pattern="^(owner|admin|qa|viewer)$")
    is_active: Optional[bool] = None


class UserResponse(UserBase, TimestampSchema):
    """User response schema."""
    id: UUID
    tenant_id: UUID
    is_active: bool


# Rebuild models with forward references
LoginResponse.model_rebuild()


# =============================================================================
# Tenant Schemas
# =============================================================================

class TenantBase(BaseModel):
    """Base tenant schema."""
    name: str = Field(..., min_length=1, max_length=255)


class TenantCreate(TenantBase):
    """Tenant creation schema."""
    pass


class TenantResponse(TenantBase, TimestampSchema):
    """Tenant response schema."""
    id: UUID
    status: str


# =============================================================================
# Project Schemas
# =============================================================================

class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    platform: str = Field(..., pattern="^(ios|android|hybrid)$")
    repo_url: Optional[str] = None
    default_branch: str = Field(default="main")


class ProjectCreate(ProjectBase):
    """Project creation schema."""
    pass


class ProjectUpdate(BaseModel):
    """Project update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    repo_url: Optional[str] = None
    default_branch: Optional[str] = None


class ProjectResponse(ProjectBase, TimestampSchema):
    """Project response schema."""
    id: UUID
    tenant_id: UUID


class ProjectListResponse(BaseModel):
    """Project list response schema."""
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Test Case Schemas
# =============================================================================

class TestStepSchema(BaseModel):
    """Test step in DSL."""
    model_config = ConfigDict(extra="allow")

    action: str
    target: Optional[str] = None
    locator_type: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    params: Optional[dict[str, Any]] = None
    timeout: Optional[int] = None
    optional: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_action(cls, data: Any) -> Any:
        if isinstance(data, dict) and "action" not in data and "type" in data:
            return {**data, "action": data["type"]}
        return data


class TestCaseDSL(BaseModel):
    """Test case DSL content."""
    name: str
    steps: list[TestStepSchema]
    setup: Optional[list[TestStepSchema]] = None
    teardown: Optional[list[TestStepSchema]] = None
    variables: Optional[dict[str, Any]] = None


class TestCaseBase(BaseModel):
    """Base test case schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class TestCaseCreate(TestCaseBase):
    """Test case creation schema."""
    dsl_content: TestCaseDSL


class TestCaseUpdate(BaseModel):
    """Test case update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    dsl_content: Optional[TestCaseDSL] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class TestCaseResponse(TestCaseBase, TimestampSchema):
    """Test case response schema."""
    id: UUID
    project_id: UUID
    dsl_version: int
    dsl_content: dict[str, Any]


class TestCaseListResponse(BaseModel):
    """Test case list response schema."""
    items: list[TestCaseResponse]
    total: int
    page: int
    page_size: int


class TestCaseVersionResponse(TimestampSchema):
    """Test case version response schema."""
    id: UUID
    test_case_id: UUID
    version_no: int
    dsl_content: dict[str, Any]
    change_log: Optional[str]
    created_by: Optional[UUID]


class CreateVersionRequest(BaseModel):
    """Request to create a new version."""
    change_log: Optional[str] = None


class ValidateDSLRequest(BaseModel):
    """DSL validation request."""
    dsl_content: TestCaseDSL


class ValidateDSLResponse(BaseModel):
    """DSL validation response."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Test Flow Schemas
# =============================================================================

class FlowNodeSchema(BaseModel):
    """Flow node definition."""
    id: str
    type: str  # test_case, condition, parallel, wait
    label: Optional[str] = None
    position: Optional[dict[str, float]] = None
    data: Optional[dict[str, Any]] = None


class FlowEdgeSchema(BaseModel):
    """Flow edge definition."""
    id: str
    source: str
    target: str
    condition: Optional[str] = None
    label: Optional[str] = None


class FlowGraphSchema(BaseModel):
    """Flow graph definition."""
    nodes: list[FlowNodeSchema]
    edges: list[FlowEdgeSchema]


class TestFlowBase(BaseModel):
    """Base test flow schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class TestFlowCreate(TestFlowBase):
    """Test flow creation schema."""
    graph_json: FlowGraphSchema
    entry_node: Optional[str] = None


class TestFlowUpdate(BaseModel):
    """Test flow update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    graph_json: Optional[FlowGraphSchema] = None
    entry_node: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class TestFlowResponse(TestFlowBase, TimestampSchema):
    """Test flow response schema."""
    id: UUID
    project_id: UUID
    graph_json: dict[str, Any]
    entry_node: Optional[str]


class TestFlowListResponse(BaseModel):
    """Test flow list response schema."""
    items: list[TestFlowResponse]
    total: int
    page: int
    page_size: int


class FlowNodeBindingCreate(BaseModel):
    """Flow node binding creation schema."""
    node_key: str
    test_case_id: UUID
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    timeout_sec: int = Field(default=300, ge=1, le=3600)


class FlowNodeBindingResponse(TimestampSchema):
    """Flow node binding response schema."""
    id: UUID
    flow_id: UUID
    node_key: str
    test_case_id: UUID
    retry_policy: dict[str, Any]
    timeout_sec: int


class CompileFlowResponse(BaseModel):
    """Flow compilation response."""
    success: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    compiled_graph: Optional[dict[str, Any]] = None


# =============================================================================
# Device Schemas
# =============================================================================

class DeviceBase(BaseModel):
    """Base device schema."""
    name: str = Field(..., min_length=1, max_length=255)
    udid: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(..., pattern="^(ios|android)$")
    platform_version: str
    model: str
    manufacturer: Optional[str] = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class DeviceCreate(DeviceBase):
    """Device creation schema."""
    pass


class DeviceUpdate(BaseModel):
    """Device update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    platform_version: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(available|busy|offline|maintenance)$")
    capabilities: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None


class DeviceResponse(DeviceBase, TimestampSchema):
    """Device response schema."""
    id: UUID
    tenant_id: UUID
    status: str
    last_heartbeat: Optional[datetime] = None
    current_run_id: Optional[UUID] = None


class DeviceListResponse(BaseModel):
    """Device list response schema."""
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Test Plan Schemas
# =============================================================================

class TestPlanBase(BaseModel):
    """Base test plan schema."""
    name: str = Field(..., min_length=1, max_length=255)
    trigger_type: str = Field(default="manual", pattern="^(manual|cron|webhook)$")
    cron_expr: Optional[str] = None
    env_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class TestPlanCreate(TestPlanBase):
    """Test plan creation schema."""
    flow_id: UUID


class TestPlanUpdate(BaseModel):
    """Test plan update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    trigger_type: Optional[str] = Field(None, pattern="^(manual|cron|webhook)$")
    cron_expr: Optional[str] = None
    env_config: Optional[dict[str, Any]] = None
    is_enabled: Optional[bool] = None


class TestPlanResponse(TestPlanBase, TimestampSchema):
    """Test plan response schema."""
    id: UUID
    project_id: UUID
    flow_id: UUID


class TestPlanListResponse(BaseModel):
    """Test plan list response schema."""
    items: list[TestPlanResponse]
    total: int
    page: int
    page_size: int


# =============================================================================
# Test Run Schemas
# =============================================================================

class TestRunCreate(BaseModel):
    """Test run creation schema."""
    flow_id: UUID
    plan_id: Optional[UUID] = None
    trigger_type: str = Field(default="manual", pattern="^(manual|api|cron|webhook|retry)$")
    config: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    env_config: dict[str, Any] = Field(default_factory=dict)


class FlowRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    plan_id: Optional[UUID] = Field(
        default=None,
        validation_alias=AliasChoices("plan_id", "planId"),
    )
    appium_session_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("appium_session_id", "session_id", "sessionId"),
    )


class RunCreateRequest(BaseModel):
    """Run creation request."""
    trigger: str = Field(default="manual", pattern="^(manual|api|cron|webhook)$")
    device_ids: Optional[list[UUID]] = None


class RunCreateResponse(BaseModel):
    """Run creation response."""
    run_id: UUID
    run_no: str
    status: str


class TestRunSummary(BaseModel):
    """Test run summary."""
    total_nodes: int = 0
    passed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0


class TestRunResponse(TimestampSchema):
    """Test run response schema."""
    id: UUID
    project_id: UUID
    plan_id: Optional[UUID]
    flow_id: UUID
    run_no: str
    status: str
    triggered_by: Optional[UUID]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    summary: dict[str, Any]
    env_config: dict[str, Any]


class TestRunListResponse(BaseModel):
    """Test run list response schema."""
    items: list[TestRunResponse]
    total: int
    page: int
    page_size: int


class TestRunNodeResponse(TimestampSchema):
    """Test run node response schema."""
    id: UUID
    test_run_id: UUID
    node_key: str
    test_case_id: UUID
    device_id: Optional[UUID] = None
    status: str
    attempt: int = 1
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    steps: list["TestStepResultResponse"] = Field(default_factory=list)


class TestStepResultResponse(TimestampSchema):
    """Test step result response schema."""
    id: UUID
    run_node_id: UUID
    step_index: int
    action: str
    input_payload: dict[str, Any]
    status: str
    assertion_result: dict[str, Any]
    screenshot_object_key: Optional[str]
    screenshot_url: Optional[str] = None
    page_source_object_key: Optional[str] = None
    page_source_url: Optional[str] = None
    raw_log_object_key: Optional[str]
    duration_ms: Optional[int]


class TestRunDetailResponse(TimestampSchema):
    """Detailed test run response with nodes and steps."""
    id: UUID
    project_id: UUID
    plan_id: Optional[UUID] = None
    flow_id: UUID
    run_no: str
    status: str
    triggered_by: Optional[UUID] = None
    trigger_type: str = "manual"
    config: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary: dict[str, Any] = Field(default_factory=dict)
    env_config: dict[str, Any] = Field(default_factory=dict)
    nodes: list[TestRunNodeResponse] = Field(default_factory=list)


# Rebuild TestRunNodeResponse to resolve forward reference
TestRunNodeResponse.model_rebuild()


# =============================================================================
# AI Analysis Schemas
# =============================================================================

class AIAnalyzeRequest(BaseModel):
    """AI analysis request."""
    analysis_types: list[str] = Field(
        default=["page_structure"],
        description="Types: ui_state, anomaly, element_detect, page_structure"
    )
    include_steps: Optional[list[UUID]] = None


class AIAnalyzeResponse(BaseModel):
    """AI analysis response."""
    task_id: str
    status: str
    message: str


class ScreenAnalysisResponse(TimestampSchema):
    """Screen analysis response schema."""
    id: UUID
    test_step_result_id: UUID
    model_name: str
    prompt_version: str
    analysis_type: str
    result_json: dict[str, Any]
    confidence: float
    latency_ms: int

    # Screenshot context for better UX
    screenshot_object_key: Optional[str] = None
    screenshot_url: Optional[str] = None


class AISummaryResponse(BaseModel):
    """AI summary response."""
    run_id: UUID
    total_analyses: int
    anomaly_count: int
    categories: dict[str, int]
    highlights: list[dict[str, Any]]
    risk_score: float


class CompareRunsRequest(BaseModel):
    """Compare runs request."""
    baseline_run_id: UUID
    target_run_id: UUID


class CompareRunsResponse(BaseModel):
    """Compare runs response."""
    comparison_id: UUID
    status: str


class RunComparisonResponse(TimestampSchema):
    """Run comparison response schema."""
    id: UUID
    project_id: UUID
    baseline_run_id: UUID
    target_run_id: UUID
    diff_summary: dict[str, Any]
    risk_score: float
    report_object_key: Optional[str]


class RiskScoreResponse(BaseModel):
    """Risk score response."""
    run_id: UUID
    risk_score: float
    signals: list[dict[str, Any]]
    recommendation: str


# =============================================================================
# App Package Schemas
# =============================================================================

def _public_object_url(object_key: str) -> str:
    host = (settings.oss_url_scheme or "").rstrip("/")
    return f"{host}/{object_key.lstrip('/')}" if host else object_key

class AppPackageBase(BaseModel):
    """Base app package schema."""
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class AppPackageUploadResponse(BaseModel):
    """Response after uploading a package."""
    id: UUID
    filename: str
    platform: str
    package_name: str
    app_name: Optional[str] = None
    version_name: str
    version_code: Optional[int] = None
    build_number: Optional[str] = None
    file_size: int
    file_hash: str
    local_path: Optional[str] = None
    
    # Android specific
    min_sdk_version: Optional[int] = None
    target_sdk_version: Optional[int] = None
    app_activity: Optional[str] = None
    app_package: Optional[str] = None
    
    # iOS specific
    bundle_id: Optional[str] = None
    minimum_os_version: Optional[str] = None
    supported_platforms: Optional[list[str]] = None
    
    # Additional
    permissions: Optional[list[str]] = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    
    # CDN URLs - 直接使用 object_key（已包含完整路径）
    download_url: Optional[str] = None
    icon_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_package(cls, package) -> "AppPackageUploadResponse":
        """Create response from package model with CDN URLs."""
        # object_key 已经包含完整路径，如: china/nanotest/packages/app.apk
        data = {
            "id": package.id,
            "filename": package.filename,
            "platform": package.platform,
            "package_name": package.package_name,
            "app_name": package.app_name,
            "version_name": package.version_name,
            "version_code": package.version_code,
            "build_number": package.build_number,
            "file_size": package.file_size,
            "file_hash": package.file_hash,
            "local_path": getattr(package, "local_path", None),
            "min_sdk_version": package.min_sdk_version,
            "target_sdk_version": package.target_sdk_version,
            "app_activity": package.app_activity,
            "app_package": package.app_package,
            "bundle_id": package.bundle_id,
            "minimum_os_version": package.minimum_os_version,
            "supported_platforms": package.supported_platforms,
            "permissions": package.permissions,
            "extra_metadata": package.extra_metadata or {},
            "download_url": _public_object_url(package.object_key) if package.object_key else None,
            "icon_url": _public_object_url(package.icon_object_key) if package.icon_object_key else None,
        }
        return cls(**data)


class AppPackageResponse(AppPackageUploadResponse, TimestampSchema):
    """Full app package response schema."""
    project_id: UUID
    tenant_id: UUID
    object_key: str
    icon_object_key: Optional[str] = None
    status: str
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    uploaded_by: Optional[UUID] = None
    
    @classmethod
    def from_package(cls, package) -> "AppPackageResponse":
        """Create response from package model with CDN URLs."""
        # object_key 已经包含完整路径，如: china/nanotest/packages/app.apk
        data = {
            "id": package.id,
            "filename": package.filename,
            "platform": package.platform,
            "package_name": package.package_name,
            "app_name": package.app_name,
            "version_name": package.version_name,
            "version_code": package.version_code,
            "build_number": package.build_number,
            "file_size": package.file_size,
            "file_hash": package.file_hash,
            "local_path": getattr(package, "local_path", None),
            "min_sdk_version": package.min_sdk_version,
            "target_sdk_version": package.target_sdk_version,
            "app_activity": package.app_activity,
            "app_package": package.app_package,
            "bundle_id": package.bundle_id,
            "minimum_os_version": package.minimum_os_version,
            "supported_platforms": package.supported_platforms,
            "permissions": package.permissions,
            "extra_metadata": package.extra_metadata or {},
            "download_url": _public_object_url(package.object_key) if package.object_key else None,
            "icon_url": _public_object_url(package.icon_object_key) if package.icon_object_key else None,
            "project_id": package.project_id,
            "tenant_id": package.tenant_id,
            "object_key": package.object_key,
            "icon_object_key": package.icon_object_key,
            "status": package.status,
            "description": package.description,
            "tags": package.tags or [],
            "uploaded_by": package.uploaded_by,
            "created_at": package.created_at,
            "updated_at": package.updated_at,
        }
        return cls(**data)


class AppPackageUpdate(BaseModel):
    """App package update schema."""
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = Field(None, pattern="^(active|archived)$")


class AppPackageListResponse(BaseModel):
    """App package list response schema."""
    items: list[AppPackageResponse]
    total: int
    page: int
    page_size: int


class AppPackageDownloadResponse(BaseModel):
    """App package download URL response."""
    download_url: str
    expires_in: int = 3600


class AppPackageIconResponse(BaseModel):
    """App package icon URL response."""
    icon_url: Optional[str] = None
    expires_in: int = 3600


# =============================================================================
# Common Schemas
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    database: str
    redis: str


class ErrorResponse(BaseModel):
    """Error response schema."""
    detail: str
    code: Optional[str] = None
    errors: Optional[list[dict[str, Any]]] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class TaskStatusResponse(BaseModel):
    """Celery task status response."""
    task_id: str
    state: str
    status: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
