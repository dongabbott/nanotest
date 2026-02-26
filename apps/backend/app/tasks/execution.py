"""Test execution Celery tasks with Appium Runner integration."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# =============================================================================
# WebSocket Event Publisher
# =============================================================================

class EventPublisher:
    """Publish real-time events via Redis pub/sub."""
    
    @staticmethod
    async def publish(channel: str, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to Redis channel."""
        from app.core.config import settings
        import redis.asyncio as redis
        
        try:
            client = redis.from_url(settings.redis_url)
            message = json.dumps({
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            })
            await client.publish(channel, message)
            await client.close()
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")
    
    @staticmethod
    def publish_sync(channel: str, event_type: str, data: dict[str, Any]) -> None:
        """Synchronous publish for use in Celery tasks."""
        import redis
        from app.core.config import settings
        
        try:
            client = redis.from_url(settings.redis_url)
            message = json.dumps({
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            })
            client.publish(channel, message)
            client.close()
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")


# =============================================================================
# DSL Step Parsing Helpers
# =============================================================================

def _parse_locator(step_data: dict) -> tuple[Optional[str], Optional[str]]:
    """Parse locator_type and locator_value from a DSL step dict.

    Supports multiple formats:
      1. selector object:  {"selector": {"strategy": "id", "value": "my_btn"}}
      2. Explicit fields:  {"locator_type": "id", "target": "my_btn"}
      3. Compound target:  {"target": "id=my_btn"}
      4. target only:      {"target": "my_btn"} → locator_type=None
    """
    # Format 1: selector object (from frontend TestCaseStepDesigner)
    selector = step_data.get("selector")
    if isinstance(selector, dict):
        strategy = selector.get("strategy")
        value = selector.get("value")
        if strategy and value:
            return strategy, value

    # Format 2: explicit locator_type + target
    locator_type = step_data.get("locator_type")
    target = step_data.get("target")

    if locator_type and target:
        return locator_type, target

    # Format 3: compound target e.g. "id=my_btn"
    if target and "=" in target:
        parts = target.split("=", 1)
        known = {
            "id", "xpath", "accessibility_id", "class_name", "name",
            "css", "android_uiautomator", "ios_predicate", "ios_class_chain",
        }
        if parts[0].strip().lower() in known:
            return parts[0].strip(), parts[1].strip()

    return locator_type, target


def _normalize_action(step_data: dict) -> str:
    """Normalize action name from DSL step.

    The frontend designer uses 'type' field for action name (e.g. 'tap', 'swipe'),
    while the backend expects 'action'. Also maps frontend action names to runner
    action names where they differ.
    """
    action = step_data.get("action") or step_data.get("type") or "unknown"

    # Map frontend assert conditions to runner actions
    if action == "assert":
        condition = step_data.get("condition", "exists")
        mapping = {
            "exists": "assert_exists",
            "not_exists": "assert_not_exists",
            "visible": "assert_exists",
            "text_equals": "assert_text",
            "text_contains": "assert_contains",
            "enabled": "assert_exists",
        }
        return mapping.get(condition, "assert_exists")

    # Map frontend 'scroll' with direction to runner actions
    if action == "scroll":
        direction = step_data.get("direction", "down")
        return "scroll_up" if direction == "up" else "scroll_down"

    # Map 'wait' with condition to 'wait_for_element'
    if action == "wait" and step_data.get("condition"):
        return "wait_for_element"

    return action


def _build_step_metadata(step_data: dict) -> dict:
    """Build metadata dict from DSL step, merging explicit params with
    top-level fields that the runner expects in metadata."""
    metadata = dict(step_data.get("params") or {})

    # Swipe: runner expects metadata.coords
    if step_data.get("type") == "swipe" or step_data.get("action") == "swipe":
        direction = step_data.get("direction", "up")
        distance = step_data.get("distance", 0.5)
        duration = step_data.get("duration", 500)
        # Convert direction + distance into absolute coords
        # Using a 1080x1920 reference; actual coords are relative
        cx, cy = 540, 960
        half_h = int(960 * distance)
        half_w = int(540 * distance)
        coord_map = {
            "up":    {"start_x": cx, "start_y": cy + half_h, "end_x": cx, "end_y": cy - half_h},
            "down":  {"start_x": cx, "start_y": cy - half_h, "end_x": cx, "end_y": cy + half_h},
            "left":  {"start_x": cx + half_w, "start_y": cy, "end_x": cx - half_w, "end_y": cy},
            "right": {"start_x": cx - half_w, "start_y": cy, "end_x": cx + half_w, "end_y": cy},
        }
        coords = coord_map.get(direction, coord_map["up"])
        coords["duration"] = duration
        metadata["coords"] = coords

    # Wait: runner expects metadata.duration (ms)
    if step_data.get("type") in ("wait",) or step_data.get("action") in ("wait",):
        if "duration" not in metadata:
            metadata["duration"] = step_data.get("duration", 1000)

    # Long press: runner expects metadata.duration
    if step_data.get("type") == "long_press" or step_data.get("action") == "long_press":
        if "duration" not in metadata:
            metadata["duration"] = step_data.get("duration", 1000)

    # Launch/close app: runner expects metadata.app_id
    if step_data.get("type") in ("launch_app", "close_app"):
        if "app_id" not in metadata:
            metadata["app_id"] = step_data.get("app_id")

    return metadata


# =============================================================================
# Main Execution Task
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.execution.execute_test_run")
def execute_test_run(self, run_id: str, device_config: Optional[dict] = None) -> dict[str, Any]:
    """
    Execute a complete test run with Appium Runner integration.
    
    Args:
        run_id: The test run ID
        device_config: Optional device configuration override
    
    Returns:
        Execution result summary
    """
    from app.core.database import AsyncSessionLocal
    from app.domain.models import (
        TestRun, TestRunNode, TestStepResult, FlowNodeBinding, 
        TestCase, Device, TestFlow
    )
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async def _execute():
        async with AsyncSessionLocal() as db:
            # Get the test run with related data
            result = await db.execute(
                select(TestRun)
                .options(selectinload(TestRun.flow))
                .where(TestRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Run not found"}

            # Publish run started event
            EventPublisher.publish_sync(
                f"run:{run_id}",
                "run.started",
                {"run_id": run_id, "status": "running"}
            )

            # Update status to running
            run.status = "running"
            run.started_at = datetime.utcnow()
            await db.commit()

            try:
                # Get flow bindings with test cases
                result = await db.execute(
                    select(FlowNodeBinding)
                    .options(selectinload(FlowNodeBinding.test_case))
                    .where(FlowNodeBinding.flow_id == run.flow_id)
                )
                bindings = result.scalars().all()

                if not bindings:
                    raise ValueError("No test cases bound to flow")

                # Get device if specified
                device = None
                if run.env_config.get("device_id"):
                    device_result = await db.execute(
                        select(Device).where(Device.id == run.env_config["device_id"])
                    )
                    device = device_result.scalar_one_or_none()

                # Build execution context
                exec_context = _build_execution_context(run, device, device_config)

                # Determine execution strategy:
                # Use FlowRunner for DAG-based execution if flow has edges/entry_node,
                # otherwise fall back to sequential execution.
                flow = run.flow
                graph = flow.graph_json or {}
                edges = graph.get("edges", [])
                entry_node = flow.entry_node or graph.get("entry_node")

                if edges and entry_node:
                    execution_result = await _execute_flow_with_dag(
                        db, run, flow, bindings, exec_context
                    )
                else:
                    execution_result = await _execute_nodes_with_runner(
                        db, run, bindings, exec_context
                    )

                # Update run with results
                run.status = execution_result["status"]
                run.finished_at = datetime.utcnow()
                run.summary = execution_result["summary"]
                await db.commit()

                # Publish run completed event
                EventPublisher.publish_sync(
                    f"run:{run_id}",
                    "run.completed",
                    {
                        "run_id": run_id,
                        "status": run.status,
                        "summary": run.summary,
                    }
                )

                return {
                    "success": True,
                    "run_id": run_id,
                    "status": run.status,
                    "summary": run.summary,
                }

            except Exception as e:
                logger.exception(f"Run execution failed: {e}")
                run.status = "failed"
                run.finished_at = datetime.utcnow()
                run.summary = {"error": str(e)}
                await db.commit()

                # Publish run failed event
                EventPublisher.publish_sync(
                    f"run:{run_id}",
                    "run.failed",
                    {"run_id": run_id, "error": str(e)}
                )

                return {"success": False, "error": str(e)}

    return asyncio.run(_execute())


def _build_execution_context(
    run, 
    device: Optional[Any], 
    device_config: Optional[dict]
) -> dict[str, Any]:
    """Build execution context for the runner.

    Priority (highest → lowest):
      1. Fields stored in run.env_config (set by the API from Appium session data)
      2. Device record from DB
      3. Explicit device_config override passed to the task
      4. Defaults (mock context)
    """
    env = run.env_config or {}

    context = {
        "run_id": str(run.id),
        "project_id": str(run.project_id),
        "flow_id": str(run.flow_id),
        "variables": env.get("variables", {}),
        "use_real_runner": env.get("use_real_runner", False),
        "screenshot_on_failure": env.get("screenshot_on_failure", True),
        # If env_config does not specify screenshot_on_step, decide later based on runner type.
        "screenshot_on_step": env.get("screenshot_on_step"),
    }

    # Add device info from DB device record
    if device:
        context.update({
            "platform": device.platform,
            "device_udid": device.udid,
            "platform_version": device.platform_version,
            "app_path": device.capabilities.get("app_path"),
            "app_package": device.capabilities.get("app_package"),
            "app_activity": device.capabilities.get("app_activity"),
            "bundle_id": device.capabilities.get("bundle_id"),
        })
    elif device_config:
        context.update(device_config)
    else:
        # Default mock context for testing
        context.update({
            "platform": "android",
            "device_udid": "emulator-5554",
            "platform_version": "13",
        })

    # env_config fields (written by create_flow_run from Appium session)
    # always override because they come from the actual session the user chose.
    _env_keys = [
        "platform",
        "device_udid",
        "platform_version",
        "appium_server_url",
        "appium_session_id",
        "app_package",
        "app_activity",
        "bundle_id",
        "app_path",
    ]
    for key in _env_keys:
        val = env.get(key)
        if val:
            context[key] = val

    # If an appium_session_id is present, force real runner
    if context.get("appium_session_id"):
        context["use_real_runner"] = True

    # Default screenshot policy:
    # - Real device/Appium execution: capture screenshots on each step unless explicitly disabled.
    # - Mock execution: default stays False (avoid useless uploads)
    if context.get("screenshot_on_step") is None:
        context["screenshot_on_step"] = bool(context.get("use_real_runner"))

    return context


def _build_test_steps_from_dsl(dsl_content: dict) -> list:
    """Build TestStep list from DSL content dict using consistent locator parsing."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "worker"))
    from runners.flow_runner import _parse_dsl_steps

    return _parse_dsl_steps(dsl_content)


async def _execute_flow_with_dag(
    db,
    run,
    flow,
    bindings: list,
    exec_context: dict[str, Any],
) -> dict[str, Any]:
    """Execute flow using the DAG-aware FlowRunner for proper topological order,
    conditional edges, and parallel group support."""
    from app.domain.models import TestRunNode, TestStepResult
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "worker"))
    from runners.flow_runner import FlowRunner
    from runners.base import ExecutionContext

    # Build data structures expected by FlowRunner.from_flow_data
    node_bindings_data = []
    test_cases_data = {}
    for binding in bindings:
        tc = binding.test_case
        node_bindings_data.append({
            "node_key": binding.node_key,
            "test_case_id": binding.test_case_id,
            "retry_policy": binding.retry_policy or {},
            "timeout_sec": binding.timeout_sec or 300,
        })
        test_cases_data[binding.test_case_id] = {
            "name": tc.name,
            "dsl_content": tc.dsl_content,
        }

    context = ExecutionContext(
        run_id=exec_context["run_id"],
        project_id=exec_context["project_id"],
        platform=exec_context.get("platform", "android"),
        device_udid=exec_context.get("device_udid", ""),
        platform_version=exec_context.get("platform_version", ""),
        app_path=exec_context.get("app_path"),
        app_package=exec_context.get("app_package"),
        app_activity=exec_context.get("app_activity"),
        bundle_id=exec_context.get("bundle_id"),
        appium_server_url=exec_context.get("appium_server_url"),
        appium_session_id=exec_context.get("appium_session_id"),
        variables=exec_context.get("variables", {}),
        screenshot_on_failure=exec_context.get("screenshot_on_failure", True),
        screenshot_on_step=exec_context.get("screenshot_on_step", False),
    )

    use_real_runner = exec_context.get("use_real_runner", False)

    graph_json = flow.graph_json or {}

    flow_runner = FlowRunner.from_flow_data(
        context=context,
        flow_id=flow.id,
        flow_name=flow.name,
        graph_json=graph_json,
        node_bindings=node_bindings_data,
        test_cases=test_cases_data,
    )

    if not use_real_runner:
        # For mock execution, run nodes sequentially using mock executor
        return await _execute_nodes_with_runner(db, run, bindings, exec_context)

    flow_result = await flow_runner.execute()

    # Persist node/step results to DB
    total_steps = 0
    passed_steps = 0
    failed_steps = 0

    for node_key, node_result in flow_result.node_results.items():
        node_record = TestRunNode(
            test_run_id=run.id,
            node_key=node_key,
            test_case_id=str(node_result.test_case_id),
            status=node_result.status.value,
            attempt=node_result.retry_count + 1,
            duration_ms=node_result.duration_ms,
            error_message=node_result.error_message,
            error_code=node_result.error_code,
        )
        db.add(node_record)
        await db.flush()

        for s in node_result.steps:
            step_record = TestStepResult(
                run_node_id=node_record.id,
                step_index=s.step_index,
                action=s.action,
                input_payload={"value": s.actual_value, "metadata": s.metadata},
                status=s.status.value,
                assertion_result={
                    "expected": s.expected_value,
                    "actual": s.actual_value,
                },
                screenshot_object_key=s.screenshot_path,
                duration_ms=s.duration_ms,
            )
            db.add(step_record)
            total_steps += 1
            if s.status.value == "passed":
                passed_steps += 1
            elif s.status.value in ("failed", "error"):
                failed_steps += 1

        await db.commit()

        EventPublisher.publish_sync(
            f"run:{run.id}",
            "node.completed",
            {
                "run_id": str(run.id),
                "node_key": node_key,
                "status": node_result.status.value,
                "duration_ms": node_result.duration_ms,
            }
        )

    status = flow_result.status.value
    # Normalize status: StepStatus uses "passed"/"failed"
    if status == "error":
        status = "failed"

    return {
        "status": status,
        "summary": {
            "total_nodes": flow_result.total_nodes,
            "passed_nodes": flow_result.passed_nodes,
            "failed_nodes": flow_result.failed_nodes,
            "skipped_nodes": flow_result.skipped_nodes,
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
        },
    }


async def _execute_nodes_with_runner(
    db,
    run,
    bindings: list,
    exec_context: dict[str, Any],
) -> dict[str, Any]:
    """Execute nodes sequentially using Appium Runner or mock execution."""
    from app.domain.models import TestRunNode, TestStepResult
    
    total_nodes = len(bindings)
    passed_nodes = 0
    failed_nodes = 0
    skipped_nodes = 0
    total_steps = 0
    passed_steps = 0
    failed_steps = 0

    use_real_runner = exec_context.get("use_real_runner", False)

    for binding in bindings:
        # Create run node record
        node = TestRunNode(
            test_run_id=run.id,
            node_key=binding.node_key,
            test_case_id=binding.test_case_id,
            status="running",
            attempt=1,
        )
        db.add(node)
        await db.flush()

        # Publish node started event
        EventPublisher.publish_sync(
            f"run:{run.id}",
            "node.started",
            {
                "run_id": str(run.id),
                "node_key": binding.node_key,
                "test_case_id": str(binding.test_case_id),
            }
        )

        try:
            if use_real_runner:
                # Use real Appium Runner
                node_result = await _execute_node_with_appium(
                    binding, exec_context
                )
            else:
                # Mock execution for testing
                node_result = await _mock_execute_node(binding)

            # Save step results
            for step_result in node_result.get("steps", []):
                step_record = TestStepResult(
                    run_node_id=node.id,
                    step_index=step_result["step_index"],
                    action=step_result["action"],
                    input_payload=step_result.get("input_payload", {}),
                    status=step_result["status"],
                    assertion_result=step_result.get("assertion_result", {}),
                    screenshot_object_key=step_result.get("screenshot_path"),
                    duration_ms=step_result.get("duration_ms"),
                )
                db.add(step_record)

                total_steps += 1
                if step_result["status"] == "passed":
                    passed_steps += 1
                elif step_result["status"] == "failed":
                    failed_steps += 1

            # Update node status
            node.status = node_result["status"]
            node.duration_ms = node_result.get("duration_ms", 0)
            node.error_message = node_result.get("error_message")
            node.error_code = node_result.get("error_code")

            if node_result["status"] == "passed":
                passed_nodes += 1
            else:
                failed_nodes += 1

        except Exception as e:
            logger.exception(f"Node execution failed: {e}")
            node.status = "failed"
            node.error_message = str(e)
            node.error_code = "EXECUTION_ERROR"
            failed_nodes += 1

        await db.commit()

        # Publish node completed event
        EventPublisher.publish_sync(
            f"run:{run.id}",
            "node.completed",
            {
                "run_id": str(run.id),
                "node_key": binding.node_key,
                "status": node.status,
                "duration_ms": node.duration_ms,
            }
        )

    # Determine overall status
    if failed_nodes == 0:
        status = "passed"
    elif passed_nodes == 0:
        status = "failed"
    else:
        status = "partial"

    return {
        "status": status,
        "summary": {
            "total_nodes": total_nodes,
            "passed_nodes": passed_nodes,
            "failed_nodes": failed_nodes,
            "skipped_nodes": skipped_nodes,
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
        },
    }


async def _execute_node_with_appium(
    binding,
    exec_context: dict[str, Any],
) -> dict[str, Any]:
    """Execute a node using the real Appium Runner."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "worker"))
    
    from runners.appium_runner import AppiumRunner
    from runners.base import ExecutionContext, TestNode

    # Build execution context
    context = ExecutionContext(
        run_id=exec_context["run_id"],
        project_id=exec_context["project_id"],
        platform=exec_context.get("platform", "android"),
        device_udid=exec_context.get("device_udid"),
        platform_version=exec_context.get("platform_version"),
        app_path=exec_context.get("app_path"),
        app_package=exec_context.get("app_package"),
        app_activity=exec_context.get("app_activity"),
        bundle_id=exec_context.get("bundle_id"),
        appium_server_url=exec_context.get("appium_server_url"),
        appium_session_id=exec_context.get("appium_session_id"),
        variables=exec_context.get("variables", {}),
        screenshot_on_failure=exec_context.get("screenshot_on_failure", True),
        screenshot_on_step=exec_context.get("screenshot_on_step", False),
    )

    # Build test node from binding using consistent locator parsing
    test_case = binding.test_case
    dsl_content = test_case.dsl_content
    steps = _build_test_steps_from_dsl(dsl_content)

    retry_policy = binding.retry_policy or {}
    node = TestNode(
        node_key=binding.node_key,
        test_case_id=str(binding.test_case_id),
        steps=steps,
        retry_on_failure=retry_policy.get("enabled", False),
        max_retries=retry_policy.get("max_retries", 0),
        timeout=binding.timeout_sec or 300,
    )

    # Execute with runner
    runner = AppiumRunner(context)
    try:
        await runner.setup()
        result = await runner.execute_node(node)
        
        return {
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "error_message": result.error_message,
            "error_code": result.error_code,
            "steps": [
                {
                    "step_index": s.step_index,
                    "action": s.action,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "error_message": s.error_message,
                    "screenshot_path": s.screenshot_path,
                    "input_payload": {"value": s.actual_value, "metadata": s.metadata},
                    "assertion_result": {
                        "expected": s.expected_value,
                        "actual": s.actual_value,
                    },
                }
                for s in result.steps
            ],
        }
    finally:
        await runner.teardown()


async def _mock_execute_node(binding) -> dict[str, Any]:
    """Mock node execution for testing without real devices."""
    import random
    
    test_case = binding.test_case
    dsl_content = test_case.dsl_content
    steps_data = dsl_content.get("steps", [])

    # Simulate execution time
    await asyncio.sleep(0.1)

    # Generate mock step results
    steps = []
    node_passed = True
    
    for i, step_data in enumerate(steps_data):
        # 90% pass rate for mock
        step_passed = random.random() < 0.9
        
        steps.append({
            "step_index": i,
            "action": step_data.get("action", "unknown"),
            "status": "passed" if step_passed else "failed",
            "duration_ms": random.randint(100, 500),
            "input_payload": {"target": step_data.get("target")},
            "assertion_result": {},
        })
        
        if not step_passed and not step_data.get("optional", False):
            node_passed = False

    return {
        "status": "passed" if node_passed else "failed",
        "duration_ms": sum(s["duration_ms"] for s in steps),
        "steps": steps,
    }


# =============================================================================
# Single Node Execution Task
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.execution.execute_single_node")
def execute_single_node(
    self,
    run_id: str,
    node_key: str,
    test_case_id: str,
    device_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a single test node (for parallel execution).
    """
    from app.core.database import AsyncSessionLocal
    from app.domain.models import TestCase, FlowNodeBinding
    from sqlalchemy import select

    async def _execute():
        async with AsyncSessionLocal() as db:
            # Get test case
            result = await db.execute(
                select(TestCase).where(TestCase.id == test_case_id)
            )
            test_case = result.scalar_one_or_none()
            if not test_case:
                return {"success": False, "error": "Test case not found"}

            # Get binding for retry policy
            result = await db.execute(
                select(FlowNodeBinding).where(
                    FlowNodeBinding.node_key == node_key,
                    FlowNodeBinding.test_case_id == test_case_id,
                )
            )
            binding = result.scalar_one_or_none()

            # Create mock binding if not found
            class MockBinding:
                def __init__(self):
                    self.node_key = node_key
                    self.test_case_id = test_case_id
                    self.test_case = test_case
                    self.retry_policy = {}
                    self.timeout_sec = 300

            exec_binding = binding or MockBinding()
            exec_binding.test_case = test_case

            # Execute
            exec_context = {
                "run_id": run_id,
                "project_id": str(test_case.project_id),
                **device_config,
            }

            if device_config.get("use_real_runner"):
                node_result = await _execute_node_with_appium(exec_binding, exec_context)
            else:
                node_result = await _mock_execute_node(exec_binding)

            return {
                "success": True,
                "node_key": node_key,
                **node_result,
            }

    return asyncio.run(_execute())


# =============================================================================
# Retry Failed Nodes Task
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.execution.retry_failed_nodes")
def retry_failed_nodes(self, run_id: str) -> dict[str, Any]:
    """
    Retry all failed nodes in a test run.
    """
    from app.core.database import AsyncSessionLocal
    from app.domain.models import TestRun, TestRunNode, FlowNodeBinding
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    async def _retry():
        async with AsyncSessionLocal() as db:
            # Get failed nodes
            result = await db.execute(
                select(TestRunNode)
                .where(
                    TestRunNode.test_run_id == run_id,
                    TestRunNode.status == "failed",
                )
            )
            failed_nodes = result.scalars().all()

            if not failed_nodes:
                return {"success": True, "message": "No failed nodes to retry"}

            # Get run
            result = await db.execute(
                select(TestRun).where(TestRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Run not found"}

            # Update run status
            run.status = "running"
            await db.commit()

            retried = 0
            passed = 0

            for node in failed_nodes:
                # Increment attempt
                node.attempt += 1
                node.status = "running"
                await db.commit()

                # Get binding with test_case eagerly loaded
                result = await db.execute(
                    select(FlowNodeBinding)
                    .options(selectinload(FlowNodeBinding.test_case))
                    .where(
                        FlowNodeBinding.flow_id == run.flow_id,
                        FlowNodeBinding.node_key == node.node_key,
                    )
                )
                binding = result.scalar_one_or_none()

                if binding:
                    # Execute retry
                    node_result = await _mock_execute_node(binding)
                    node.status = node_result["status"]
                    node.duration_ms = node_result.get("duration_ms")
                    
                    retried += 1
                    if node_result["status"] == "passed":
                        passed += 1

                await db.commit()

            # Update run summary
            run.status = "passed" if passed == retried else "partial"
            run.summary["retried_nodes"] = retried
            run.summary["retry_passed"] = passed
            await db.commit()

            return {
                "success": True,
                "retried": retried,
                "passed": passed,
            }

    return asyncio.run(_retry())


# =============================================================================
# Cancel Run Task
# =============================================================================

@celery_app.task(bind=True, name="app.tasks.execution.cancel_test_run")
def cancel_test_run(self, run_id: str) -> dict[str, Any]:
    """
    Cancel a running test run.
    """
    from app.core.database import AsyncSessionLocal
    from app.domain.models import TestRun, TestRunNode
    from sqlalchemy import select, update

    async def _cancel():
        async with AsyncSessionLocal() as db:
            # Get run
            result = await db.execute(
                select(TestRun).where(TestRun.id == run_id)
            )
            run = result.scalar_one_or_none()
            if not run:
                return {"success": False, "error": "Run not found"}

            if run.status not in ("queued", "running"):
                return {"success": False, "error": f"Cannot cancel run in status: {run.status}"}

            # Update run status
            run.status = "cancelled"
            run.finished_at = datetime.utcnow()

            # Cancel pending nodes
            await db.execute(
                update(TestRunNode)
                .where(
                    TestRunNode.test_run_id == run_id,
                    TestRunNode.status.in_(["pending", "running"]),
                )
                .values(status="cancelled")
            )

            await db.commit()

            # Publish cancellation event
            EventPublisher.publish_sync(
                f"run:{run_id}",
                "run.cancelled",
                {"run_id": run_id}
            )

            return {"success": True, "run_id": run_id}

    return asyncio.run(_cancel())
