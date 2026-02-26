"""Appium-based test runner for mobile automation."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from .base import (
    BaseRunner,
    ExecutionContext,
    NodeResult,
    RunResult,
    StepResult,
    StepStatus,
    TestNode,
    TestStep,
)

logger = logging.getLogger(__name__)


class AppiumRunner(BaseRunner):
    """Runner implementation using Appium for mobile test execution."""

    # Supported actions mapping
    ACTIONS = {
        "tap": "_action_tap",
        "click": "_action_tap",
        "input": "_action_input",
        "type": "_action_input",
        "clear": "_action_clear",
        "swipe": "_action_swipe",
        "scroll_down": "_action_scroll_down",
        "scroll_up": "_action_scroll_up",
        "long_press": "_action_long_press",
        "back": "_action_back",
        "home": "_action_home",
        "wait": "_action_wait",
        "wait_for_element": "_action_wait_for_element",
        "assert_exists": "_action_assert_exists",
        "assert_not_exists": "_action_assert_not_exists",
        "assert_text": "_action_assert_text",
        "assert_contains": "_action_assert_contains",
        "launch_app": "_action_launch_app",
        "close_app": "_action_close_app",
        "screenshot": "_action_screenshot",
    }

    def __init__(self, context: ExecutionContext):
        super().__init__(context)
        self._client = None
        self._screenshot_callback = None
        self._oss_client = None

    def set_screenshot_callback(self, callback):
        """Set callback for saving screenshots."""
        self._screenshot_callback = callback

    async def setup(self) -> None:
        """Set up the Appium session."""
        from app.integrations.appium.client import AppiumClient

        logger.info(f"Setting up Appium session for run {self.context.run_id}")

        self._client = AppiumClient(
            platform=self.context.platform,
            device_udid=self.context.device_udid,
            platform_version=self.context.platform_version,
            server_url=self.context.appium_server_url,
            existing_session_id=self.context.appium_session_id,
            app_path=self.context.app_path,
            app_package=self.context.app_package,
            app_activity=self.context.app_activity,
            bundle_id=self.context.bundle_id,
        )

        # Run in executor since Appium client is synchronous
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._client.start_session)

        logger.info("Appium session started successfully")

    async def teardown(self) -> None:
        """Tear down the Appium session."""
        if self._client:
            logger.info(f"Tearing down Appium session for run {self.context.run_id}")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.stop_session)
            self._client = None

    async def take_screenshot(self) -> Optional[bytes]:
        """Take a screenshot of the current state."""
        if not self._client:
            return None
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._client.take_screenshot)
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
            return None

    async def _upload_screenshot(
        self,
        screenshot: bytes,
        step_index: int,
        label: str = "",
    ) -> Optional[str]:
        """Upload screenshot to Aliyun OSS and return the object key.

        Path format:
          screenshots/{run_id}/{node_key}/{step_index}_{label}_{timestamp}.png
        """
        try:
            from app.integrations.aliyun.oss_client import get_oss_client

            if self._oss_client is None:
                self._oss_client = get_oss_client()

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
            suffix = f"_{label}" if label else ""
            object_key = (
                f"screenshots/{self.context.run_id}/"
                f"step{step_index}{suffix}_{timestamp}.png"
            )

            loop = asyncio.get_event_loop()
            full_key = await loop.run_in_executor(
                None,
                lambda: self._oss_client.upload_bytes(
                    object_key, screenshot, "image/png"
                ),
            )
            logger.info(f"Screenshot uploaded: {full_key}")
            return full_key

        except Exception as e:
            logger.warning(f"Failed to upload screenshot to OSS: {e}")
            return None

    async def get_page_source(self) -> Optional[str]:
        """Get the current page source."""
        if not self._client:
            return None
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._client.get_page_source)
        except Exception as e:
            logger.warning(f"Failed to get page source: {e}")
            return None

    async def execute_step(self, step: TestStep) -> StepResult:
        """Execute a single test step."""
        started_at = datetime.utcnow()
        result = StepResult(
            step_index=step.index,
            action=step.action,
            status=StepStatus.RUNNING,
            started_at=started_at,
        )

        try:
            # Get action handler
            action_method_name = self.ACTIONS.get(step.action.lower())
            if not action_method_name:
                raise ValueError(f"Unknown action: {step.action}")

            action_method = getattr(self, action_method_name)

            # Execute action
            loop = asyncio.get_event_loop()
            action_result = await loop.run_in_executor(
                None, lambda: action_method(step)
            )

            # Update result based on action output
            if action_result:
                result.actual_value = action_result.get("actual_value")
                result.metadata = action_result.get("metadata", {})

            result.status = StepStatus.PASSED
            result.expected_value = step.expected_value

        except AssertionError as e:
            result.status = StepStatus.FAILED
            result.error_message = str(e)
            result.error_code = "ASSERTION_FAILED"
            result.element_found = "not found" not in str(e).lower()

        except Exception as e:
            error_code = self._classify_error(e)
            if step.optional:
                result.status = StepStatus.SKIPPED
            else:
                result.status = StepStatus.ERROR
            result.error_message = str(e)
            result.error_code = error_code
            result.element_found = error_code != "ELEMENT_NOT_FOUND"

        finally:
            result.ended_at = datetime.utcnow()
            result.duration_ms = int(
                (result.ended_at - started_at).total_seconds() * 1000
            )

            # Take screenshot and upload to OSS
            should_capture = self.context.screenshot_on_step or (
                self.context.screenshot_on_failure
                and result.status in (StepStatus.FAILED, StepStatus.ERROR)
            )
            if should_capture:
                screenshot = await self.take_screenshot()
                if screenshot:
                    label = result.status.value
                    # Prefer the external callback if set, otherwise upload to OSS
                    if self._screenshot_callback:
                        path = await self._screenshot_callback(
                            self.context.run_id,
                            step.index,
                            screenshot,
                        )
                        result.screenshot_path = path
                    else:
                        result.screenshot_path = await self._upload_screenshot(
                            screenshot, step.index, label
                        )

        return result

    async def execute_node(self, node: TestNode) -> NodeResult:
        """Execute a test node (case)."""
        started_at = datetime.utcnow()
        result = NodeResult(
            node_key=node.node_key,
            test_case_id=node.test_case_id,
            status=StepStatus.RUNNING,
            started_at=started_at,
        )

        retry_count = 0
        max_retries = node.max_retries if node.retry_on_failure else 0

        while retry_count <= max_retries:
            result.steps = []
            node_failed = False

            for step in node.steps:
                step_result = await self.execute_step(step)
                result.steps.append(step_result)

                if step_result.status in (StepStatus.FAILED, StepStatus.ERROR):
                    if not step.optional:
                        node_failed = True
                        break

            if not node_failed:
                break

            retry_count += 1
            if retry_count <= max_retries:
                logger.info(
                    f"Retrying node {node.node_key} (attempt {retry_count + 1})"
                )

        result.retry_count = retry_count

        # Determine final status
        failed_steps = [
            s for s in result.steps
            if s.status in (StepStatus.FAILED, StepStatus.ERROR)
            and not node.steps[s.step_index].optional
        ]

        if failed_steps:
            result.status = StepStatus.FAILED
            result.error_message = failed_steps[0].error_message
            result.error_code = failed_steps[0].error_code
        else:
            result.status = StepStatus.PASSED

        result.ended_at = datetime.utcnow()
        result.duration_ms = int(
            (result.ended_at - started_at).total_seconds() * 1000
        )

        return result

    async def execute_run(self, nodes: list[TestNode]) -> RunResult:
        """Execute a complete test run."""
        self._is_running = True
        started_at = datetime.utcnow()

        result = RunResult(
            run_id=self.context.run_id,
            status=StepStatus.RUNNING,
            started_at=started_at,
        )

        try:
            for node in nodes:
                logger.info(f"Executing node: {node.node_key}")
                node_result = await self.execute_node(node)
                result.nodes.append(node_result)

                # Count steps
                for step in node_result.steps:
                    result.total_steps += 1
                    if step.status == StepStatus.PASSED:
                        result.passed_steps += 1
                    elif step.status == StepStatus.FAILED:
                        result.failed_steps += 1
                    elif step.status == StepStatus.SKIPPED:
                        result.skipped_steps += 1

            # Determine final status
            failed_nodes = [n for n in result.nodes if n.status == StepStatus.FAILED]
            if failed_nodes:
                result.status = StepStatus.FAILED
            else:
                result.status = StepStatus.PASSED

        except Exception as e:
            logger.exception(f"Run execution error: {e}")
            result.status = StepStatus.ERROR

        finally:
            self._is_running = False
            result.ended_at = datetime.utcnow()
            result.duration_ms = int(
                (result.ended_at - started_at).total_seconds() * 1000
            )

        return result

    # ==========================================================================
    # Action Implementations
    # ==========================================================================

    def _action_tap(self, step: TestStep) -> dict[str, Any]:
        """Tap on an element."""
        self._client.tap(step.locator_type, step.locator_value)
        return {}

    def _action_input(self, step: TestStep) -> dict[str, Any]:
        """Input text into an element."""
        text = self._resolve_variable(step.input_value)
        self._client.input_text(step.locator_type, step.locator_value, text)
        return {"actual_value": text}

    def _action_clear(self, step: TestStep) -> dict[str, Any]:
        """Clear text from an element."""
        self._client.clear_text(step.locator_type, step.locator_value)
        return {}

    def _action_swipe(self, step: TestStep) -> dict[str, Any]:
        """Perform a swipe gesture."""
        coords = step.metadata.get("coords", {})
        self._client.swipe(
            coords.get("start_x", 500),
            coords.get("start_y", 1500),
            coords.get("end_x", 500),
            coords.get("end_y", 500),
            coords.get("duration", 500),
        )
        return {}

    def _action_scroll_down(self, step: TestStep) -> dict[str, Any]:
        """Scroll down on the screen."""
        self._client.scroll_down()
        return {}

    def _action_scroll_up(self, step: TestStep) -> dict[str, Any]:
        """Scroll up on the screen."""
        self._client.scroll_up()
        return {}

    def _action_long_press(self, step: TestStep) -> dict[str, Any]:
        """Long press on an element."""
        duration = step.metadata.get("duration", 1000)
        self._client.long_press(step.locator_type, step.locator_value, duration)
        return {}

    def _action_back(self, step: TestStep) -> dict[str, Any]:
        """Press the back button."""
        self._client.back()
        return {}

    def _action_home(self, step: TestStep) -> dict[str, Any]:
        """Press the home button."""
        self._client.home()
        return {}

    def _action_wait(self, step: TestStep) -> dict[str, Any]:
        """Wait for a specified duration."""
        import time
        duration = step.metadata.get("duration", 1000) / 1000
        time.sleep(duration)
        return {}

    def _action_wait_for_element(self, step: TestStep) -> dict[str, Any]:
        """Wait for an element to appear."""
        self._client.wait_for_element(
            step.locator_type,
            step.locator_value,
            step.timeout,
        )
        return {}

    def _action_assert_exists(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element exists."""
        exists = self._client.element_exists(step.locator_type, step.locator_value)
        if not exists:
            raise AssertionError(
                f"Element not found: {step.locator_type}={step.locator_value}"
            )
        return {"actual_value": "exists"}

    def _action_assert_not_exists(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element does not exist."""
        exists = self._client.element_exists(step.locator_type, step.locator_value)
        if exists:
            raise AssertionError(
                f"Element unexpectedly found: {step.locator_type}={step.locator_value}"
            )
        return {"actual_value": "not_exists"}

    def _action_assert_text(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element has specific text."""
        actual = self._client.get_element_text(step.locator_type, step.locator_value)
        expected = self._resolve_variable(step.expected_value)
        if actual != expected:
            raise AssertionError(
                f"Text mismatch: expected '{expected}', got '{actual}'"
            )
        return {"actual_value": actual}

    def _action_assert_contains(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element's text contains a substring."""
        actual = self._client.get_element_text(step.locator_type, step.locator_value)
        expected = self._resolve_variable(step.expected_value)
        if expected not in actual:
            raise AssertionError(
                f"Text does not contain '{expected}': got '{actual}'"
            )
        return {"actual_value": actual}

    def _action_launch_app(self, step: TestStep) -> dict[str, Any]:
        """Launch the app."""
        app_id = step.metadata.get("app_id")
        self._client.launch_app(app_id)
        return {}

    def _action_close_app(self, step: TestStep) -> dict[str, Any]:
        """Close the app."""
        app_id = step.metadata.get("app_id")
        self._client.close_app(app_id)
        return {}

    def _action_screenshot(self, step: TestStep) -> dict[str, Any]:
        """Take a screenshot (explicitly requested)."""
        # Screenshot will be taken by the step execution flow
        return {}

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _resolve_variable(self, value: Optional[str]) -> str:
        """Resolve variable references in a value."""
        if not value:
            return ""
        if value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            return str(self.context.variables.get(var_name, value))
        return value

    def _classify_error(self, error: Exception) -> str:
        """Classify an error into an error code."""
        error_str = str(error).lower()

        if "nosuchelement" in error_str or "not found" in error_str:
            return "ELEMENT_NOT_FOUND"
        elif "timeout" in error_str:
            return "TIMEOUT"
        elif "session" in error_str:
            return "SESSION_ERROR"
        elif "crash" in error_str:
            return "APP_CRASH"
        elif "connection" in error_str:
            return "CONNECTION_ERROR"
        else:
            return "UNKNOWN_ERROR"
