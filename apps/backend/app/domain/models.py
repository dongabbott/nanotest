"""Domain models for the application."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# =============================================================================
# Organization & Project Domain
# =============================================================================

class Tenant(Base, TimestampMixin):
    """Multi-tenant organization."""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, suspended

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="tenant")


class User(Base, TimestampMixin):
    """User account."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="qa")  # owner, admin, qa, viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """Test project."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # ios, android, hybrid
    repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main")

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="projects")
    test_cases: Mapped[list["TestCase"]] = relationship("TestCase", back_populates="project")
    test_flows: Mapped[list["TestFlow"]] = relationship("TestFlow", back_populates="project")
    test_plans: Mapped[list["TestPlan"]] = relationship("TestPlan", back_populates="project")
    test_runs: Mapped[list["TestRun"]] = relationship("TestRun", back_populates="project")
    app_packages: Mapped[list["AppPackage"]] = relationship("AppPackage", back_populates="project")


# =============================================================================
# App Package Domain
# =============================================================================

class AppPackage(Base, TimestampMixin, SoftDeleteMixin):
    """Mobile app package (APK/IPA) with parsed metadata."""
    __tablename__ = "app_packages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    
    # Basic info
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)  # OSS object key
    local_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Platform
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # android, ios
    
    # Parsed metadata
    package_name: Mapped[str] = mapped_column(String(500), nullable=False)  # com.example.app
    app_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Display name
    version_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 1.0.0
    version_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 (Android only)
    build_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # iOS build number
    
    # Android specific
    min_sdk_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_sdk_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    app_activity: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Main activity
    app_package: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Same as package_name for Android
    
    # iOS specific
    bundle_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Same as package_name for iOS
    minimum_os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supported_platforms: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # iPhone, iPad, etc.
    
    # Additional metadata
    permissions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # App permissions
    icon_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # App icon object key
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # Any additional info
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, archived
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    
    # Uploader
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="app_packages")

    __table_args__ = (
        Index("ix_app_packages_project_platform", "project_id", "platform"),
        Index("ix_app_packages_package_name", "package_name"),
        Index("ix_app_packages_tenant", "tenant_id"),
    )


# =============================================================================
# Device Management Domain
# =============================================================================

class RemoteAppiumServer(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "remote_appium_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=4723)
    path: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    last_connected: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    device_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_remote_appium_servers_tenant", "tenant_id"),
        Index("ix_remote_appium_servers_host_port", "host", "port"),
    )


# =============================================================================
# Test Asset Domain
# =============================================================================

class TestCase(Base, TimestampMixin, SoftDeleteMixin):
    """Test case with DSL definition."""
    __tablename__ = "test_cases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dsl_version: Mapped[int] = mapped_column(Integer, default=1)
    dsl_content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, active, archived

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="test_cases")
    versions: Mapped[list["TestCaseVersion"]] = relationship("TestCaseVersion", back_populates="test_case")

    __table_args__ = (
        Index("ix_test_cases_project_status", "project_id", "status"),
    )


class TestCaseVersion(Base, TimestampMixin):
    """Version history for test cases."""
    __tablename__ = "test_case_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    test_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_cases.id"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    dsl_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Relationships
    test_case: Mapped["TestCase"] = relationship("TestCase", back_populates="versions")


class TestFlow(Base, TimestampMixin, SoftDeleteMixin):
    """Test flow with DAG definition."""
    __tablename__ = "test_flows"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    graph_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    entry_node: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, active, archived

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="test_flows")
    node_bindings: Mapped[list["FlowNodeBinding"]] = relationship("FlowNodeBinding", back_populates="flow")


class FlowNodeBinding(Base, TimestampMixin):
    """Binding between flow nodes and test cases."""
    __tablename__ = "flow_node_bindings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_flows.id"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    test_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_cases.id"), nullable=False
    )
    retry_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=300)

    # Relationships
    flow: Mapped["TestFlow"] = relationship("TestFlow", back_populates="node_bindings")
    test_case: Mapped["TestCase"] = relationship("TestCase")


# =============================================================================
# Execution & Device Domain
# =============================================================================

class Device(Base, TimestampMixin, SoftDeleteMixin):
    """Device for testing."""
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    udid: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # ios, android
    platform_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="available")  # available, busy, offline, maintenance
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class TestPlan(Base, TimestampMixin, SoftDeleteMixin):
    """Test plan for scheduling."""
    __tablename__ = "test_plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual, cron, webhook
    cron_expr: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_flows.id"), nullable=False
    )
    env_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="test_plans")
    flow: Mapped["TestFlow"] = relationship("TestFlow")


class TestRun(Base, TimestampMixin):
    """Test run execution record."""
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    plan_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("test_plans.id"), nullable=True
    )
    flow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_flows.id"), nullable=False
    )
    run_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")  # queued, running, success, failed, partial, cancelled
    triggered_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    env_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="test_runs")
    plan: Mapped[Optional["TestPlan"]] = relationship("TestPlan")
    flow: Mapped["TestFlow"] = relationship("TestFlow")
    nodes: Mapped[list["TestRunNode"]] = relationship("TestRunNode", back_populates="test_run")
    risk_signals: Mapped[list["RiskSignal"]] = relationship("RiskSignal", back_populates="test_run")

    __table_args__ = (
        Index("ix_test_runs_project_started", "project_id", "started_at"),
        Index("ix_test_runs_status", "status"),
    )


class TestRunNode(Base, TimestampMixin):
    """Individual node execution in a test run."""
    __tablename__ = "test_run_nodes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    test_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    test_case_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, running, success, failed, skipped
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="nodes")
    step_results: Mapped[list["TestStepResult"]] = relationship("TestStepResult", back_populates="run_node")


class TestStepResult(Base, TimestampMixin):
    """Individual step result within a node."""
    __tablename__ = "test_step_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    run_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_run_nodes.id"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, success, failed
    assertion_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    screenshot_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    page_source_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_log_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    run_node: Mapped["TestRunNode"] = relationship("TestRunNode", back_populates="step_results")
    screen_analyses: Mapped[list["ScreenAnalysis"]] = relationship("ScreenAnalysis", back_populates="step_result")


# =============================================================================
# AI Analysis & Report Domain
# =============================================================================

class ScreenAnalysis(Base, TimestampMixin):
    """AI analysis of a screenshot."""
    __tablename__ = "screen_analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    test_step_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_step_results.id"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ui_state, anomaly, element_detect
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    step_result: Mapped["TestStepResult"] = relationship("TestStepResult", back_populates="screen_analyses")


class RunComparison(Base, TimestampMixin):
    """Comparison between two test runs."""
    __tablename__ = "run_comparisons"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    baseline_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    diff_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    report_object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class RiskSignal(Base, TimestampMixin):
    """Risk signal for a test run."""
    __tablename__ = "risk_signals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    test_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # crash, layout_shift, flaky, perf_regression
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    test_run: Mapped["TestRun"] = relationship("TestRun", back_populates="risk_signals")


# =============================================================================
# Audit & Observability Domain
# =============================================================================

class AuditLog(Base):
    """Audit log entry."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
    )


class EventOutbox(Base, TimestampMixin):
    """Event outbox for reliable event publishing."""
    __tablename__ = "event_outbox"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, published, failed

    __table_args__ = (
        Index("ix_event_outbox_status", "status"),
    )
