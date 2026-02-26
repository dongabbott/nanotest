"""Event publishing utilities for real-time updates."""
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client for event publishing."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


async def close_redis_client():
    """Close the Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


class EventPublisher:
    """Publisher for real-time events via Redis pub/sub."""

    @staticmethod
    def _serialize(data: Any) -> str:
        """Serialize data for Redis."""
        def default(obj):
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(data, default=default)

    @classmethod
    async def publish(cls, channel: str, event_type: str, data: dict[str, Any]):
        """Publish an event to a Redis channel."""
        try:
            client = await get_redis_client()
            message = {
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            }
            await client.publish(channel, cls._serialize(message))
            logger.debug(f"Published event {event_type} to {channel}")
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

    @classmethod
    async def publish_run_event(
        cls,
        run_id: UUID,
        event_type: str,
        data: dict[str, Any],
        project_id: UUID | None = None,
    ):
        """Publish a test run event."""
        # Publish to run-specific channel
        await cls.publish(f"run:{run_id}", event_type, data)
        
        # Also publish to project channel if provided
        if project_id:
            await cls.publish(f"project:{project_id}", event_type, {
                "run_id": str(run_id),
                **data,
            })
        
        # Publish to global dashboard
        await cls.publish("dashboard:global", event_type, {
            "run_id": str(run_id),
            "project_id": str(project_id) if project_id else None,
            **data,
        })

    @classmethod
    async def run_started(
        cls,
        run_id: UUID,
        project_id: UUID,
        flow_name: str,
        total_nodes: int,
    ):
        """Emit run started event."""
        await cls.publish_run_event(
            run_id=run_id,
            event_type="run.started",
            data={
                "flow_name": flow_name,
                "total_nodes": total_nodes,
                "status": "running",
            },
            project_id=project_id,
        )

    @classmethod
    async def run_completed(
        cls,
        run_id: UUID,
        project_id: UUID,
        status: str,
        passed: int,
        failed: int,
        duration_ms: int,
    ):
        """Emit run completed event."""
        await cls.publish_run_event(
            run_id=run_id,
            event_type="run.completed",
            data={
                "status": status,
                "passed": passed,
                "failed": failed,
                "duration_ms": duration_ms,
            },
            project_id=project_id,
        )

    @classmethod
    async def run_failed(
        cls,
        run_id: UUID,
        project_id: UUID,
        error: str,
    ):
        """Emit run failed event."""
        await cls.publish_run_event(
            run_id=run_id,
            event_type="run.failed",
            data={
                "status": "failed",
                "error": error,
            },
            project_id=project_id,
        )

    @classmethod
    async def node_started(
        cls,
        run_id: UUID,
        node_id: str,
        node_name: str,
        node_index: int,
    ):
        """Emit node started event."""
        await cls.publish(f"run:{run_id}", "node.started", {
            "node_id": node_id,
            "node_name": node_name,
            "node_index": node_index,
        })

    @classmethod
    async def node_completed(
        cls,
        run_id: UUID,
        node_id: str,
        node_name: str,
        status: str,
        duration_ms: int,
        error: str | None = None,
    ):
        """Emit node completed event."""
        await cls.publish(f"run:{run_id}", "node.completed", {
            "node_id": node_id,
            "node_name": node_name,
            "status": status,
            "duration_ms": duration_ms,
            "error": error,
        })

    @classmethod
    async def step_completed(
        cls,
        run_id: UUID,
        node_id: str,
        step_index: int,
        step_action: str,
        status: str,
        screenshot_url: str | None = None,
    ):
        """Emit step completed event (detailed channel)."""
        await cls.publish(f"run:{run_id}:steps", "step.completed", {
            "node_id": node_id,
            "step_index": step_index,
            "step_action": step_action,
            "status": status,
            "screenshot_url": screenshot_url,
        })

    @classmethod
    async def analysis_completed(
        cls,
        project_id: UUID,
        run_id: UUID,
        analysis_type: str,
        summary: str,
    ):
        """Emit analysis completed event."""
        await cls.publish(f"project:{project_id}", "analysis.completed", {
            "run_id": str(run_id),
            "analysis_type": analysis_type,
            "summary": summary,
        })
