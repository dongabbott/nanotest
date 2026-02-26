"""WebSocket endpoints for real-time updates."""
import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import redis.asyncio as redis

from app.core.config import settings
from app.core.security import decode_token

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

    def disconnect(self, websocket: WebSocket, channel: str):
        """Remove a WebSocket connection."""
        if channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.active_connections[channel].remove(websocket)
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        logger.info(f"WebSocket disconnected from channel: {channel}")

    async def broadcast(self, channel: str, message: dict[str, Any]):
        """Broadcast a message to all connections on a channel."""
        if channel in self.active_connections:
            disconnected = []
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            
            # Clean up disconnected
            for conn in disconnected:
                self.disconnect(conn, channel)


manager = ConnectionManager()


async def verify_ws_token(token: str) -> dict[str, Any] | None:
    """Verify WebSocket authentication token."""
    try:
        payload = decode_token(token)
        return payload
    except Exception:
        return None


@router.websocket("/ws/runs/{run_id}")
async def websocket_run_updates(
    websocket: WebSocket,
    run_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time test run updates.
    
    Connect to receive events:
    - run.started: Run has started
    - run.completed: Run has completed
    - run.failed: Run has failed
    - run.cancelled: Run was cancelled
    - node.started: A node started executing
    - node.completed: A node completed
    - step.completed: A step completed (if enabled)
    """
    # Verify token
    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    channel = f"run:{run_id}"
    await manager.connect(websocket, channel)

    # Create Redis subscriber
    redis_client = redis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "run_id": str(run_id),
        })

        # Listen for messages from both WebSocket and Redis
        async def redis_listener():
            """Listen for Redis pub/sub messages."""
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await websocket.send_json(data)
                    except Exception as e:
                        logger.warning(f"Failed to send Redis message: {e}")

        async def websocket_listener():
            """Listen for WebSocket messages (ping/pong, commands)."""
            while True:
                try:
                    data = await websocket.receive_json()
                    
                    # Handle ping
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    
                    # Handle subscription to step events
                    elif data.get("type") == "subscribe_steps":
                        step_channel = f"run:{run_id}:steps"
                        await pubsub.subscribe(step_channel)
                        await websocket.send_json({
                            "type": "subscribed",
                            "channel": step_channel,
                        })
                
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.warning(f"WebSocket receive error: {e}")
                    break

        # Run both listeners concurrently
        await asyncio.gather(
            redis_listener(),
            websocket_listener(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {run_id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket, channel)
        await pubsub.unsubscribe(channel)
        await redis_client.close()


@router.websocket("/ws/projects/{project_id}/events")
async def websocket_project_events(
    websocket: WebSocket,
    project_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for project-level events.
    
    Events:
    - run.created: New run created
    - run.completed: Run completed
    - test_case.updated: Test case was updated
    - analysis.completed: AI analysis completed
    """
    # Verify token
    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    channel = f"project:{project_id}"
    await manager.connect(websocket, channel)

    redis_client = redis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    try:
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "project_id": str(project_id),
        })

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception as e:
                    logger.warning(f"Failed to send message: {e}")

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, channel)
        await pubsub.unsubscribe(channel)
        await redis_client.close()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for dashboard-level events.
    
    Events:
    - run.started: Any run started
    - run.completed: Any run completed
    - system.alert: System alerts
    """
    user = await verify_ws_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    channel = "dashboard:global"
    await manager.connect(websocket, channel)

    redis_client = redis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    try:
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
        })

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, channel)
        await pubsub.unsubscribe(channel)
        await redis_client.close()
