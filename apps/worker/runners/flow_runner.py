"""Flow runner for DAG-based test flow execution."""
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID

from .appium_runner import AppiumRunner
from .base import (
    ExecutionContext,
    NodeResult,
    RunResult,
    StepStatus,
    TestNode,
    TestStep,
)

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """Status of a flow node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EdgeCondition(str, Enum):
    """Condition type for flow edges."""
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    EXPRESSION = "expression"


@dataclass
class FlowEdge:
    """An edge in the flow DAG."""
    source_node: str
    target_node: str
    condition: EdgeCondition = EdgeCondition.ALWAYS
    condition_expr: Optional[str] = None


@dataclass
class FlowNode:
    """A node in the flow DAG."""
    node_key: str
    test_case_id: UUID
    test_case_name: str
    steps: list[TestStep]
    retry_on_failure: bool = False
    max_retries: int = 1
    timeout_sec: int = 300
    parallel_group: Optional[str] = None
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[NodeResult] = None


@dataclass
class FlowDefinition:
    """Definition of a test flow (DAG)."""
    flow_id: UUID
    flow_name: str
    entry_node: str
    nodes: dict[str, FlowNode] = field(default_factory=dict)
    edges: list[FlowEdge] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowResult:
    """Result of a flow execution."""
    flow_id: UUID
    run_id: UUID
    status: StepStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    total_nodes: int = 0
    passed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0


class FlowRunner:
    """Runner for executing DAG-based test flows."""

    def __init__(
        self,
        context: ExecutionContext,
        flow: FlowDefinition,
        screenshot_callback: Optional[Callable] = None,
    ):
        self.context = context
        self.flow = flow
        self._screenshot_callback = screenshot_callback
        self._is_running = False
        self._cancelled = False
        self._node_statuses: dict[str, NodeStatus] = {}
        self._node_results: dict[str, NodeResult] = {}
        self._execution_order: list[str] = []
        self._adjacency: dict[str, list[FlowEdge]] = defaultdict(list)
        self._reverse_adjacency: dict[str, list[FlowEdge]] = defaultdict(list)
        self._in_degree: dict[str, int] = defaultdict(int)
        
        # Build graph structures
        self._build_graph()

    def _build_graph(self) -> None:
        """Build adjacency lists and in-degree counts from flow definition."""
        # Initialize all nodes as pending
        for node_key in self.flow.nodes:
            self._node_statuses[node_key] = NodeStatus.PENDING
            self._in_degree[node_key] = 0

        # Build adjacency lists
        for edge in self.flow.edges:
            self._adjacency[edge.source_node].append(edge)
            self._reverse_adjacency[edge.target_node].append(edge)
            self._in_degree[edge.target_node] += 1

    def _get_ready_nodes(self) -> list[str]:
        """Get nodes that are ready to execute (all dependencies satisfied)."""
        ready = []
        for node_key, status in self._node_statuses.items():
            if status != NodeStatus.PENDING:
                continue

            # Check if all dependencies are satisfied
            incoming_edges = self._reverse_adjacency.get(node_key, [])
            
            # If no incoming edges, this node can start immediately
            # (entry_node or any root node in the DAG)
            if not incoming_edges:
                ready.append(node_key)
                continue

            # Check all incoming edges
            all_satisfied = True
            for edge in incoming_edges:
                source_status = self._node_statuses.get(edge.source_node)
                source_result = self._node_results.get(edge.source_node)

                if source_status not in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
                    all_satisfied = False
                    break

                # Check edge conditions
                if not self._evaluate_edge_condition(edge, source_result):
                    all_satisfied = False
                    break

            if all_satisfied:
                ready.append(node_key)

        return ready

    def _evaluate_edge_condition(
        self, edge: FlowEdge, source_result: Optional[NodeResult]
    ) -> bool:
        """Evaluate if an edge condition is satisfied."""
        if edge.condition == EdgeCondition.ALWAYS:
            return True

        if source_result is None:
            return False

        if edge.condition == EdgeCondition.ON_SUCCESS:
            return source_result.status == StepStatus.PASSED

        if edge.condition == EdgeCondition.ON_FAILURE:
            return source_result.status in (StepStatus.FAILED, StepStatus.ERROR)

        if edge.condition == EdgeCondition.EXPRESSION:
            return self._evaluate_expression(edge.condition_expr, source_result)

        return True

    def _evaluate_expression(
        self, expr: Optional[str], result: NodeResult
    ) -> bool:
        """Evaluate a condition expression."""
        if not expr:
            return True

        # Build evaluation context
        context = {
            "status": result.status.value,
            "passed": result.status == StepStatus.PASSED,
            "failed": result.status in (StepStatus.FAILED, StepStatus.ERROR),
            "duration_ms": result.duration_ms or 0,
            "retry_count": result.retry_count,
            "error_code": result.error_code,
        }

        # Add flow variables
        context.update(self.flow.variables)

        try:
            # Simple expression evaluation (limited for security)
            # In production, use a proper expression parser
            return bool(eval(expr, {"__builtins__": {}}, context))
        except Exception as e:
            logger.warning(f"Failed to evaluate expression '{expr}': {e}")
            return False

    def _should_skip_node(self, node_key: str) -> bool:
        """Check if a node should be skipped due to unmet conditions."""
        incoming_edges = self._reverse_adjacency.get(node_key, [])
        
        if not incoming_edges:
            return False

        # If all incoming edges have unmet conditions, skip
        for edge in incoming_edges:
            source_result = self._node_results.get(edge.source_node)
            if self._evaluate_edge_condition(edge, source_result):
                return False

        return True

    async def _execute_node(
        self,
        node: FlowNode,
        runner: AppiumRunner,
    ) -> NodeResult:
        """Execute a single flow node."""
        logger.info(f"Executing node: {node.node_key} ({node.test_case_name})")
        
        self._node_statuses[node.node_key] = NodeStatus.RUNNING

        try:
            # Convert FlowNode to TestNode
            test_node = TestNode(
                node_key=node.node_key,
                test_case_id=node.test_case_id,
                steps=node.steps,
                retry_on_failure=node.retry_on_failure,
                max_retries=node.max_retries,
            )

            # Execute with timeout
            result = await asyncio.wait_for(
                runner.execute_node(test_node),
                timeout=node.timeout_sec,
            )

            if result.status == StepStatus.PASSED:
                self._node_statuses[node.node_key] = NodeStatus.COMPLETED
            else:
                self._node_statuses[node.node_key] = NodeStatus.FAILED

            return result

        except asyncio.TimeoutError:
            logger.error(f"Node {node.node_key} timed out after {node.timeout_sec}s")
            self._node_statuses[node.node_key] = NodeStatus.FAILED
            return NodeResult(
                node_key=node.node_key,
                test_case_id=node.test_case_id,
                status=StepStatus.ERROR,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                error_code="TIMEOUT",
                error_message=f"Node execution timed out after {node.timeout_sec}s",
            )

        except Exception as e:
            logger.exception(f"Node {node.node_key} execution error: {e}")
            self._node_statuses[node.node_key] = NodeStatus.FAILED
            return NodeResult(
                node_key=node.node_key,
                test_case_id=node.test_case_id,
                status=StepStatus.ERROR,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                error_code="EXECUTION_ERROR",
                error_message=str(e),
            )

    async def _execute_parallel_group(
        self,
        nodes: list[FlowNode],
        runner: AppiumRunner,
    ) -> list[NodeResult]:
        """Execute a group of nodes in parallel."""
        # Note: For Appium, true parallel execution requires multiple devices
        # This implementation executes sequentially but groups by parallel_group
        results = []
        for node in nodes:
            result = await self._execute_node(node, runner)
            results.append(result)
            self._node_results[node.node_key] = result
            self._execution_order.append(node.node_key)

            if self._cancelled:
                break

        return results

    async def execute(self) -> FlowResult:
        """Execute the complete flow."""
        self._is_running = True
        started_at = datetime.utcnow()

        result = FlowResult(
            flow_id=self.flow.flow_id,
            run_id=self.context.run_id,
            status=StepStatus.RUNNING,
            started_at=started_at,
            total_nodes=len(self.flow.nodes),
        )

        try:
            # Create and setup runner
            runner = AppiumRunner(self.context)
            if self._screenshot_callback:
                runner.set_screenshot_callback(self._screenshot_callback)

            async with runner:
                while not self._cancelled:
                    # Get nodes ready to execute
                    ready_nodes = self._get_ready_nodes()

                    if not ready_nodes:
                        # Check if there are still pending nodes
                        pending = [
                            k for k, v in self._node_statuses.items()
                            if v == NodeStatus.PENDING
                        ]
                        
                        if pending:
                            # Mark unreachable nodes as skipped
                            for node_key in pending:
                                self._node_statuses[node_key] = NodeStatus.SKIPPED
                                result.skipped_nodes += 1
                        break

                    # Group ready nodes by parallel_group
                    parallel_groups: dict[Optional[str], list[FlowNode]] = defaultdict(list)
                    for node_key in ready_nodes:
                        node = self.flow.nodes[node_key]
                        
                        # Check if should skip
                        if self._should_skip_node(node_key):
                            self._node_statuses[node_key] = NodeStatus.SKIPPED
                            result.skipped_nodes += 1
                            self._execution_order.append(node_key)
                            continue
                            
                        parallel_groups[node.parallel_group].append(node)

                    # Execute each group
                    for group_name, group_nodes in parallel_groups.items():
                        if not group_nodes:
                            continue

                        logger.info(
                            f"Executing group '{group_name or 'default'}' "
                            f"with {len(group_nodes)} node(s)"
                        )

                        group_results = await self._execute_parallel_group(
                            group_nodes, runner
                        )

                        for node_result in group_results:
                            result.node_results[node_result.node_key] = node_result
                            if node_result.status == StepStatus.PASSED:
                                result.passed_nodes += 1
                            elif node_result.status in (StepStatus.FAILED, StepStatus.ERROR):
                                result.failed_nodes += 1

            # Determine final status
            if self._cancelled:
                result.status = StepStatus.SKIPPED
            elif result.failed_nodes > 0:
                result.status = StepStatus.FAILED
            else:
                result.status = StepStatus.PASSED

        except Exception as e:
            logger.exception(f"Flow execution error: {e}")
            result.status = StepStatus.ERROR

        finally:
            self._is_running = False
            result.ended_at = datetime.utcnow()
            result.duration_ms = int(
                (result.ended_at - started_at).total_seconds() * 1000
            )
            result.execution_order = self._execution_order

        return result

    def cancel(self) -> None:
        """Cancel the flow execution."""
        logger.info(f"Cancelling flow execution for run {self.context.run_id}")
        self._cancelled = True

    @property
    def is_running(self) -> bool:
        """Check if the flow is currently executing."""
        return self._is_running

    @classmethod
    def from_flow_data(
        cls,
        context: ExecutionContext,
        flow_id: UUID,
        flow_name: str,
        graph_json: dict[str, Any],
        node_bindings: list[dict[str, Any]],
        test_cases: dict[UUID, dict[str, Any]],
        screenshot_callback: Optional[Callable] = None,
    ) -> "FlowRunner":
        """Create a FlowRunner from database/API data."""
        # Parse nodes
        nodes: dict[str, FlowNode] = {}
        for binding in node_bindings:
            node_key = binding["node_key"]
            test_case_id = binding["test_case_id"]
            test_case = test_cases.get(test_case_id, {})

            # Parse DSL steps using shared helpers
            dsl_content = test_case.get("dsl_content", {})
            steps = _parse_dsl_steps(dsl_content)

            retry_policy = binding.get("retry_policy") or {}
            nodes[node_key] = FlowNode(
                node_key=node_key,
                test_case_id=test_case_id,
                test_case_name=test_case.get("name", node_key),
                steps=steps,
                retry_on_failure=retry_policy.get("enabled", False),
                max_retries=retry_policy.get("max_retries", 1),
                timeout_sec=binding.get("timeout_sec", 300),
                parallel_group=graph_json.get("nodes", {}).get(node_key, {}).get("parallel_group"),
            )

        # Parse edges
        edges: list[FlowEdge] = []
        for edge_data in graph_json.get("edges", []):
            condition = EdgeCondition(edge_data.get("condition", "always"))
            edges.append(FlowEdge(
                source_node=edge_data["source"],
                target_node=edge_data["target"],
                condition=condition,
                condition_expr=edge_data.get("condition_expr"),
            ))

        # Create flow definition
        flow = FlowDefinition(
            flow_id=flow_id,
            flow_name=flow_name,
            entry_node=graph_json.get("entry_node", ""),
            nodes=nodes,
            edges=edges,
            variables=graph_json.get("variables", {}),
        )

        return cls(context, flow, screenshot_callback)


# =============================================================================
# Shared DSL parsing helpers (must match execution.py logic)
# =============================================================================

def _parse_locator(step_data: dict) -> tuple[Optional[str], Optional[str]]:
    """Parse locator_type and locator_value from a DSL step dict.

    Supports:
      1. selector object:  {"selector": {"strategy": "id", "value": "my_btn"}}
      2. Explicit fields:  {"locator_type": "id", "target": "my_btn"}
      3. Compound target:  {"target": "id=my_btn"}
    """
    selector = step_data.get("selector")
    if isinstance(selector, dict):
        strategy = selector.get("strategy")
        value = selector.get("value")
        if strategy and value:
            return strategy, value

    locator_type = step_data.get("locator_type")
    target = step_data.get("target")

    if locator_type and target:
        return locator_type, target

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
    """Normalize action name from DSL step."""
    action = step_data.get("action") or step_data.get("type") or "unknown"

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

    if action == "scroll":
        direction = step_data.get("direction", "down")
        return "scroll_up" if direction == "up" else "scroll_down"

    if action == "wait" and step_data.get("condition"):
        return "wait_for_element"

    return action


def _build_step_metadata(step_data: dict) -> dict:
    """Build metadata dict from DSL step."""
    metadata = dict(step_data.get("params") or {})

    if step_data.get("type") == "swipe" or step_data.get("action") == "swipe":
        direction = step_data.get("direction", "up")
        distance = step_data.get("distance", 0.5)
        duration = step_data.get("duration", 500)
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

    if step_data.get("type") in ("wait",) or step_data.get("action") in ("wait",):
        if "duration" not in metadata:
            metadata["duration"] = step_data.get("duration", 1000)

    if step_data.get("type") == "long_press" or step_data.get("action") == "long_press":
        if "duration" not in metadata:
            metadata["duration"] = step_data.get("duration", 1000)

    if step_data.get("type") in ("launch_app", "close_app"):
        if "app_id" not in metadata:
            metadata["app_id"] = step_data.get("app_id")

    return metadata


def _parse_dsl_steps(dsl_content: dict) -> list[TestStep]:
    """Parse DSL content into a list of TestStep objects."""
    steps = []
    for i, step_data in enumerate(dsl_content.get("steps", [])):
        locator_type, locator_value = _parse_locator(step_data)
        input_value = step_data.get("value") or step_data.get("text")
        expected_value = step_data.get("expected")
        steps.append(TestStep(
            index=i,
            action=_normalize_action(step_data),
            locator_type=locator_type,
            locator_value=locator_value,
            input_value=input_value,
            expected_value=expected_value,
            timeout=step_data.get("timeout", 10),
            optional=step_data.get("optional") or step_data.get("continueOnError", False),
            metadata=_build_step_metadata(step_data),
        ))
    return steps
