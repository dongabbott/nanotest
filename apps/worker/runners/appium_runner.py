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
        "double_tap": "_action_double_tap",
        "scroll": "_action_scroll",
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
        "wait_for": "_action_wait_for_element",
        "wait_for_element": "_action_wait_for_element",
        "wait_invisible": "_action_wait_invisible",
        "assert_exists": "_action_assert_exists",
        "assert_not_exists": "_action_assert_not_exists",
        "assert_visible": "_action_assert_visible",
        "assert_text": "_action_assert_text",
        "assert_contains": "_action_assert_contains",
        "launch_app": "_action_launch_app",
        "close_app": "_action_close_app",
        "screenshot": "_action_screenshot",
        "tap_xy": "_action_tap_xy",
        "hide_keyboard": "_action_hide_keyboard",
        "reset_app": "_action_reset_app",
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

    async def _upload_page_source(
        self,
        page_source: str,
        step_index: int,
        label: str = "",
    ) -> Optional[str]:
        """Upload page source XML to Aliyun OSS and return the object key.

        Path format mirrors screenshots:
          page_sources/{self.context.run_id}/step{step_index}_{label}_{timestamp}.xml
        """
        try:
            from app.integrations.aliyun.oss_client import get_oss_client

            if self._oss_client is None:
                self._oss_client = get_oss_client()

            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
            suffix = f"_{label}" if label else ""
            object_key = (
                f"page_sources/{self.context.run_id}/"
                f"step{step_index}{suffix}_{timestamp}.xml"
            )

            xml_bytes = page_source.encode("utf-8")
            loop = asyncio.get_event_loop()
            full_key = await loop.run_in_executor(
                None,
                lambda: self._oss_client.upload_bytes(
                    object_key, xml_bytes, "text/xml"
                ),
            )
            logger.info(f"Page source uploaded: {full_key}")
            return full_key

        except Exception as e:
            logger.warning(f"Failed to upload page source to OSS: {e}")
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
        result.metadata = dict(step.metadata or {})

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
                action_metadata = action_result.get("metadata", {}) or {}
                if isinstance(action_metadata, dict):
                    result.metadata.update(action_metadata)

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
            # Plan A: if the step is an explicit 'screenshot' action, do not double-capture
            # (the step itself is used as a marker; automatic capture is skipped)
            is_explicit_screenshot_step = (step.action or '').lower() == 'screenshot'

            should_capture = (not is_explicit_screenshot_step) and (
                self.context.screenshot_on_step or (
                    self.context.screenshot_on_failure
                    and result.status in (StepStatus.FAILED, StepStatus.ERROR)
                )
            )

            if should_capture:
                capture_started = datetime.utcnow()
                screenshot = await self.take_screenshot()
                page_source = await self.get_page_source()
                capture_ended = datetime.utcnow()
                result.metadata["screenshot_capture_ms"] = int(
                    (capture_ended - capture_started).total_seconds() * 1000
                )

                if screenshot:
                    upload_started = datetime.utcnow()
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
                    upload_ended = datetime.utcnow()
                    result.metadata["screenshot_upload_ms"] = int(
                        (upload_ended - upload_started).total_seconds() * 1000
                    )

                # Upload page source XML (paired with screenshot)
                if page_source:
                    try:
                        ps_upload_started = datetime.utcnow()
                        label = result.status.value
                        result.page_source_path = await self._upload_page_source(
                            page_source, step.index, label
                        )
                        ps_upload_ended = datetime.utcnow()
                        result.metadata["page_source_upload_ms"] = int(
                            (ps_upload_ended - ps_upload_started).total_seconds() * 1000
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save page source: {e}")

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

    def _action_double_tap(self, step: TestStep) -> dict[str, Any]:
        """Double-tap on an element."""
        self._client.double_tap(step.locator_type, step.locator_value)
        return {}

    def _action_scroll(self, step: TestStep) -> dict[str, Any]:
        """Scroll the screen (up/down)."""
        direction = (step.input_value or step.metadata.get("direction") or "down")
        self._client.scroll(str(direction))
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

    def _action_wait_invisible(self, step: TestStep) -> dict[str, Any]:
        """Wait until an element disappears."""
        timeout = int(step.input_value) if (step.input_value and str(step.input_value).isdigit()) else step.timeout
        self._client.wait_invisible(step.locator_type, step.locator_value, timeout)
        return {"actual_value": "invisible"}

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

    def _action_assert_visible(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element is visible."""
        # Prefer explicit visible wait
        self._client.wait_for_visible(step.locator_type, step.locator_value, step.timeout)
        return {"actual_value": "visible"}

    def _action_assert_text(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element has specific text."""
        actual = self._client.get_element_text(step.locator_type, step.locator_value)
        expected = self._resolve_variable(step.expected_value or step.input_value)
        if actual != expected:
            raise AssertionError(
                f"Text mismatch: expected '{expected}', got '{actual}'"
            )
        return {"actual_value": actual}

    def _action_assert_contains(self, step: TestStep) -> dict[str, Any]:
        """Assert that an element's text contains a substring."""
        actual = self._client.get_element_text(step.locator_type, step.locator_value)
        expected = self._resolve_variable(step.expected_value or step.input_value)
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

    def _action_reset_app(self, step: TestStep) -> dict[str, Any]:
        """Reset/restart the app."""
        self._client.reset_app()
        return {}

    def _action_screenshot(self, step: TestStep) -> dict[str, Any]:
        """Take a screenshot (explicitly requested)."""
        # Screenshot will be taken by the step execution flow
        return {}

    def _action_tap_xy(self, step: TestStep) -> dict[str, Any]:
        """Tap at coordinates provided as 'x,y'."""
        raw = (step.input_value or '').strip()
        if not raw or ',' not in raw:
            raise ValueError("tap_xy requires value in format 'x,y'")
        xs, ys = raw.split(',', 1)
        x = int(float(xs.strip()))
        y = int(float(ys.strip()))
        self._client.tap_xy(x, y)
        return {"actual_value": f"{x},{y}"}

    def _action_hide_keyboard(self, step: TestStep) -> dict[str, Any]:
        """Hide the on-screen keyboard."""
        self._client.hide_keyboard()
        return {}

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _resolve_variable(self, value: Optional[str]) -> str:
        """Resolve variable references and dynamic generators in a value.

        Supported:
          - ${var}: context variable replacement
          - ${random_email()}, ${random_phone()}, ${random_text(n)}, ${uuid()}
          - ${now(fmt)}: datetime in UTC, fmt like %Y%m%d%H%M%S

        Notes:
          - This is a lightweight expression system, not a full eval.
        """
        if not value:
            return ""

        text = str(value)

        # Fast path: exactly one ${...}
        if text.startswith("${") and text.endswith("}"):
            expr = text[2:-1].strip()
            return str(self._eval_expr(expr))

        # Replace all ${...} occurrences inside the string
        import re

        def repl(m: re.Match) -> str:
            expr = m.group(1).strip()
            try:
                return str(self._eval_expr(expr))
            except Exception:
                return m.group(0)

        return re.sub(r"\$\{([^}]+)\}", repl, text)

    def _eval_expr(self, expr: str) -> Any:
        """Evaluate a limited expression used in ${...}."""
        import re
        from runners.text_generators import eval_generator

        expr = (expr or "").strip()

        # variable
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expr):
            return self.context.variables.get(expr, "${" + expr + "}")

        generated = eval_generator(expr)
        if generated is not None:
            return generated

        # Fallback: return raw
        return "${" + expr + "}"

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
