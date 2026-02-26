"""Base runner interface for test execution."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class StepStatus(str, Enum):
    """Test step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StepResult:
    """Result of a single test step execution."""
    step_index: int
    action: str
    status: StepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    element_found: bool = True
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeResult:
    """Result of a test node (case) execution."""
    node_key: str
    test_case_id: UUID
    status: StepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    steps: list[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0


@dataclass
class RunResult:
    """Result of a complete test run."""
    run_id: UUID
    status: StepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    nodes: list[NodeResult] = field(default_factory=list)
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0


@dataclass
class TestStep:
    """A single test step to execute."""
    index: int
    action: str
    locator_type: Optional[str] = None
    locator_value: Optional[str] = None
    input_value: Optional[str] = None
    expected_value: Optional[str] = None
    timeout: int = 10
    optional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestNode:
    """A test node (case) to execute."""
    node_key: str
    test_case_id: UUID
    steps: list[TestStep]
    retry_on_failure: bool = False
    max_retries: int = 1
    timeout: int = 300


@dataclass
class ExecutionContext:
    """Context for test execution."""
    run_id: UUID
    project_id: UUID
    platform: str
    device_udid: str
    platform_version: str
    app_path: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None
    bundle_id: Optional[str] = None
    appium_server_url: Optional[str] = None
    appium_session_id: Optional[str] = None
    variables: dict[str, Any] = field(default_factory=dict)
    screenshot_on_step: bool = True
    screenshot_on_failure: bool = True


class BaseRunner(ABC):
    """Abstract base class for test runners."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self._is_running = False

    @abstractmethod
    async def setup(self) -> None:
        """Set up the runner (e.g., start Appium session)."""
        pass

    @abstractmethod
    async def teardown(self) -> None:
        """Tear down the runner (e.g., stop Appium session)."""
        pass

    @abstractmethod
    async def execute_step(self, step: TestStep) -> StepResult:
        """Execute a single test step."""
        pass

    @abstractmethod
    async def execute_node(self, node: TestNode) -> NodeResult:
        """Execute a test node (case)."""
        pass

    @abstractmethod
    async def execute_run(self, nodes: list[TestNode]) -> RunResult:
        """Execute a complete test run."""
        pass

    @abstractmethod
    async def take_screenshot(self) -> Optional[bytes]:
        """Take a screenshot of the current state."""
        pass

    @abstractmethod
    async def get_page_source(self) -> Optional[str]:
        """Get the current page/screen source."""
        pass

    @property
    def is_running(self) -> bool:
        """Check if the runner is currently executing."""
        return self._is_running

    async def __aenter__(self):
        """Async context manager entry."""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.teardown()
