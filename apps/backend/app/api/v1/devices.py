"""Device management API endpoints."""
from datetime import datetime
from typing import Annotated, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.database import get_db
from app.domain.models import Device, RemoteAppiumServer, User
from app.schemas.schemas import (
    DeviceCreate,
    DeviceListResponse,
    DeviceResponse,
    DeviceUpdate,
)

import asyncio
import logging
import json as _json
import redis as _sync_redis
from app.core.config import settings as _settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Devices"])

# Session keepalive interval (seconds). Appium resets its newCommandTimeout
# each time a command is received, so pinging at this interval keeps sessions
# alive as long as the backend is running.
_KEEPALIVE_INTERVAL_SEC = 60

# Default newCommandTimeout set on new sessions (seconds).  This is the
# Appium-side idle timeout; the keepalive task ensures we always ping before
# it expires.
_NEW_COMMAND_TIMEOUT_SEC = 1800


# =============================================================================
# Pydantic Models for Device Discovery & Remote Server
# =============================================================================


class ScanLocalDevicesResponse(BaseModel):
    """Response for local device scan."""
    devices: List[dict]
    count: int
    message: str


class InstallPackageRequest(BaseModel):
    udid: str
    platform: str = Field(..., pattern="^(android|ios)$")
    package_id: str


class InstallPackageResponse(BaseModel):
    success: bool
    message: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """Request to test remote Appium connection."""
    host: str
    port: int = 4723
    path: str = ""


class TestConnectionResponse(BaseModel):
    """Response for connection test."""
    success: bool
    message: str
    server_info: Optional[dict] = None


class RemoteServerCreate(BaseModel):
    """Create remote server request."""
    name: str = Field(..., min_length=1, max_length=255)
    host: str
    port: int = 4723
    path: str = ""
    username: Optional[str] = None
    password: Optional[str] = None


class RemoteServerResponse(BaseModel):
    """Remote server response."""
    id: str
    name: str
    host: str
    port: int
    path: str
    status: str
    last_connected: Optional[datetime] = None
    device_count: int = 0


class PageSourceResponse(BaseModel):
    """Response for page source."""
    success: bool
    source: Optional[str] = None
    screenshot: Optional[str] = None
    message: str


class StartSessionRequest(BaseModel):
    """Request to start an Appium session."""
    server_url: str
    capabilities: dict


class StartSessionResponse(BaseModel):
    """Response for session start."""
    success: bool
    session_id: Optional[str] = None
    message: str


class ElementLocator(BaseModel):
    """Element locator information."""
    strategy: str
    value: str
    xpath: Optional[str] = None


class ParsedElement(BaseModel):
    """Parsed element from page source."""
    tag: str
    attributes: dict
    children: List["ParsedElement"] = []
    locators: List[ElementLocator] = []


# =============================================================================
# Session Management Models (基于包和设备创建 Session)
# =============================================================================


class CreateSessionFromPackageRequest(BaseModel):
    """Request to create Appium session from package and device."""
    device_udid: str
    package_id: str
    server_url: Optional[str] = None  # 可选，默认使用本地 Appium
    no_reset: bool = True  # 是否保留应用数据
    full_reset: bool = False  # 是否完全重置应用
    auto_launch: bool = True  # 是否自动启动应用
    extra_capabilities: Optional[dict] = None  # 额外的 capabilities


class SessionInfo(BaseModel):
    """Session information response."""
    session_id: str
    device_udid: str
    device_name: Optional[str] = None
    platform: str
    platform_version: Optional[str] = None
    package_id: Optional[str] = None
    package_name: Optional[str] = None
    app_name: Optional[str] = None
    server_url: str
    status: str  # active, disconnected, error
    created_at: datetime
    capabilities: dict


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: List[SessionInfo]
    count: int


class SessionActionRequest(BaseModel):
    """Request for session actions."""
    action: str = Field(..., pattern="^(screenshot|source|launch_app|close_app|reset_app)$")
    app_id: Optional[str] = None  # 用于 launch/close 特定应用


class SessionActionResponse(BaseModel):
    """Response for session actions."""
    success: bool
    message: str
    data: Optional[dict] = None


# ---------------------------------------------------------------------------
# Redis-backed Appium session store (replaces in-memory dict)
# ---------------------------------------------------------------------------

def _redis_client() -> _sync_redis.Redis:
    return _sync_redis.from_url(_settings.redis_url, decode_responses=True)


def _session_key(tenant_id: str, session_id: str) -> str:
    return f"appium:session:{tenant_id}:{session_id}"


def _tenant_sessions_pattern(tenant_id: str) -> str:
    return f"appium:session:{tenant_id}:*"


class _AppiumSessionStore:
    """Redis-backed store that exposes a dict-like interface for backward compat."""

    # ---- write ----
    @staticmethod
    def set(tenant_id: str, session_id: str, data: dict, ttl: int = 86400) -> None:
        """Store session info with a default TTL of 24 h."""
        r = _redis_client()
        # datetime objects are not JSON-serialisable; convert them
        safe = {}
        for k, v in data.items():
            if isinstance(v, datetime):
                safe[k] = v.isoformat()
            elif isinstance(v, UUID):
                safe[k] = str(v)
            else:
                safe[k] = v
        r.set(_session_key(tenant_id, session_id), _json.dumps(safe), ex=ttl)

    @staticmethod
    def delete(tenant_id: str, session_id: str) -> None:
        r = _redis_client()
        r.delete(_session_key(tenant_id, session_id))

    # ---- read ----
    @staticmethod
    def get(tenant_id: str, session_id: str) -> Optional[dict]:
        r = _redis_client()
        raw = r.get(_session_key(tenant_id, session_id))
        if raw is None:
            return None
        return _json.loads(raw)

    @staticmethod
    def get_all(tenant_id: str) -> dict[str, dict]:
        r = _redis_client()
        keys = r.keys(_tenant_sessions_pattern(tenant_id))
        result: dict[str, dict] = {}
        for key in keys:
            raw = r.get(key)
            if raw:
                data = _json.loads(raw)
                sid = data.get("session_id") or key.rsplit(":", 1)[-1]
                result[sid] = data
        return result

    @staticmethod
    def exists(tenant_id: str, session_id: str) -> bool:
        r = _redis_client()
        return bool(r.exists(_session_key(tenant_id, session_id)))

    @staticmethod
    def update_field(tenant_id: str, session_id: str, field: str, value) -> None:
        data = _AppiumSessionStore.get(tenant_id, session_id)
        if data:
            data[field] = value
            _AppiumSessionStore.set(tenant_id, session_id, data)


_appium_sessions_store = _AppiumSessionStore()

# Keep the old module-level name so that other modules that import it
# (e.g. flows.py) can still work – but it now proxies to Redis.
_appium_sessions: dict = {}  # DEPRECATED – only kept as fallback reference


# ---------------------------------------------------------------------------
# Session keepalive & auto-recovery helpers
# ---------------------------------------------------------------------------

async def _probe_session_alive(server_url: str, session_id: str) -> bool:
    """Send a lightweight probe to Appium to check if a session is still alive.

    Uses GET /session/{id} which is cheap and resets newCommandTimeout.
    Returns True if the session is alive, False otherwise.
    """
    import aiohttp

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            url = f"{server_url.rstrip('/')}/session/{session_id}"
            async with client.get(url) as resp:
                return resp.status == 200
    except Exception:
        return False


async def _recreate_session(server_url: str, capabilities: dict) -> Optional[str]:
    """Attempt to create a new Appium session using saved capabilities.

    Returns the new session_id on success, None on failure.
    """
    import aiohttp

    session_url = f"{server_url.rstrip('/')}/session"
    # Remove appium:app to avoid re-installing; keep appPackage/bundleId
    caps = dict(capabilities)
    caps.pop("appium:app", None)
    # Ensure the large timeout is carried over
    caps["appium:newCommandTimeout"] = _NEW_COMMAND_TIMEOUT_SEC

    request_body = {
        "capabilities": {
            "alwaysMatch": caps,
            "firstMatch": [{}],
        }
    }

    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(session_url, json=request_body) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data.get("value", {}).get("sessionId")
    except Exception as exc:
        logger.warning("Session recreation failed: %s", exc)
    return None


async def ensure_session_alive(tenant_id: str, session_id: str) -> tuple[str, dict]:
    """Ensure the given Appium session is alive; recreate transparently if not.

    Returns (effective_session_id, session_info_dict).
    Raises HTTPException(404) if the session record doesn't exist at all,
    or HTTPException(503) if recreation also fails.
    """
    session_info = _appium_sessions_store.get(tenant_id, session_id)
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    server_url = session_info.get("server_url", "")
    caps = session_info.get("capabilities", {})

    # Fast path – session is still alive
    if await _probe_session_alive(server_url, session_id):
        if session_info.get("status") != "active":
            _appium_sessions_store.update_field(tenant_id, session_id, "status", "active")
            session_info["status"] = "active"
        return session_id, session_info

    # Session expired – try to recreate
    logger.info(
        "Session %s expired on Appium server, attempting auto-recovery…",
        session_id,
    )
    new_session_id = await _recreate_session(server_url, caps)

    if not new_session_id:
        # Mark as disconnected so the UI reflects the real state
        _appium_sessions_store.update_field(tenant_id, session_id, "status", "expired")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session expired and auto-recovery failed. Please create a new session.",
        )

    # Migrate Redis record: copy data under the new session_id, delete the old one
    session_info["session_id"] = new_session_id
    session_info["status"] = "active"
    session_info["created_at"] = datetime.utcnow().isoformat()
    _appium_sessions_store.set(tenant_id, new_session_id, session_info)
    _appium_sessions_store.delete(tenant_id, session_id)

    logger.info(
        "Session auto-recovered: %s → %s",
        session_id,
        new_session_id,
    )
    return new_session_id, session_info


# ---------------------------------------------------------------------------
# Background keepalive task
# ---------------------------------------------------------------------------

_keepalive_task: Optional[asyncio.Task] = None


async def _keepalive_loop() -> None:
    """Periodically ping all active Appium sessions to prevent timeout."""
    import aiohttp

    while True:
        try:
            await asyncio.sleep(_KEEPALIVE_INTERVAL_SEC)
            r = _redis_client()
            # Scan all session keys across all tenants
            all_keys = r.keys("appium:session:*")

            for key in all_keys:
                raw = r.get(key)
                if not raw:
                    continue
                try:
                    data = _json.loads(raw)
                except Exception:
                    continue

                sess_status = data.get("status", "")
                if sess_status not in ("active", ""):
                    continue

                server_url = data.get("server_url", "")
                sid = data.get("session_id") or key.rsplit(":", 1)[-1]
                if not server_url or not sid:
                    continue

                alive = await _probe_session_alive(server_url, sid)

                if not alive:
                    # Extract tenant_id from Redis key pattern appium:session:{tenant}:{sid}
                    parts = key.split(":")
                    if len(parts) >= 4:
                        tenant_id = parts[2]
                        _appium_sessions_store.update_field(tenant_id, sid, "status", "expired")
                    logger.info("Keepalive: session %s is no longer alive, marked expired", sid)
        except asyncio.CancelledError:
            logger.info("Session keepalive task cancelled")
            return
        except Exception as exc:
            logger.warning("Keepalive loop error (will retry): %s", exc)


def start_keepalive_task() -> None:
    """Start the background keepalive task (idempotent)."""
    global _keepalive_task
    if _keepalive_task is None or _keepalive_task.done():
        loop = asyncio.get_event_loop()
        _keepalive_task = loop.create_task(_keepalive_loop())
        logger.info("Session keepalive background task started (interval=%ds)", _KEEPALIVE_INTERVAL_SEC)


def stop_keepalive_task() -> None:
    """Cancel the background keepalive task."""
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        _keepalive_task = None
        logger.info("Session keepalive background task stopped")


# =============================================================================
# Device Discovery & Remote Server Endpoints (MUST be before /devices/{device_id})
# =============================================================================


@router.post("/devices/scan-local", response_model=ScanLocalDevicesResponse)
async def scan_local_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Scan for locally connected devices (Android via ADB, iOS via libimobiledevice).
    This endpoint attempts to discover devices connected to the server.
    """
    discovered_devices = []
    
    # Try to scan Android devices via ADB
    try:
        import subprocess
        result = subprocess.run(
            ["adb", "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                udid = parts[0]
                adb_state = parts[1]
                if adb_state not in {"device", "offline", "unauthorized"}:
                    continue
                status_value = "connected" if adb_state == "device" else "disconnected"

                connection = "wifi" if ":" in udid else "usb"

                model = "Unknown"
                for part in parts:
                    if part.startswith("model:"):
                        model = part.split(":", 1)[1]

                discovered_devices.append({
                    "id": udid,
                    "udid": udid,
                    "name": model if model != "Unknown" else udid,
                    "platform": "android",
                    "version": "",
                    "model": model,
                    "status": status_value,
                    "connection": connection,
                })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass  # ADB not available or failed
    
    # Try to scan iOS devices (requires libimobiledevice)
    try:
        import subprocess
        result = subprocess.run(
            ["idevice_id", "-l"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            udids = result.stdout.strip().split("\n")
            for udid in udids:
                if udid.strip():
                    discovered_devices.append({
                        "id": udid.strip(),
                        "udid": udid.strip(),
                        "name": "iOS Device",
                        "platform": "ios",
                        "version": "",
                        "model": "iOS Device",
                        "status": "connected",
                        "connection": "usb",
                    })
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass  # libimobiledevice not available or failed

    if discovered_devices:
        udids = [d["udid"] for d in discovered_devices if d.get("udid")]
        result = await db.execute(
            select(Device).where(
                Device.tenant_id == str(current_user.tenant_id),
                Device.udid.in_(udids),
                Device.deleted_at.is_(None),
            )
        )
        db_devices = {d.udid: d for d in result.scalars().all()}
        for item in discovered_devices:
            dev = db_devices.get(item["udid"])
            if not dev:
                continue
            if dev.current_run_id:
                item["status"] = "busy"
                continue
            if dev.status == "busy":
                item["status"] = "busy"
            elif item.get("status") != "busy":
                item["status"] = "connected" if item.get("status") == "connected" else "disconnected"
    
    return ScanLocalDevicesResponse(
        devices=discovered_devices,
        count=len(discovered_devices),
        message=f"Found {len(discovered_devices)} device(s)" if discovered_devices else "No devices found. Ensure ADB/libimobiledevice is installed and devices are connected.",
    )


@router.post("/devices/install-package", response_model=InstallPackageResponse)
async def install_package_to_local_device(
    payload: InstallPackageRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    import subprocess
    import re
    import uuid as uuid_module
    from pathlib import Path

    from app.domain.models import AppPackage
    from app.core.config import settings
    from app.integrations.aliyun.oss_client import get_oss_client

    result = await db.execute(
        select(AppPackage).where(
            AppPackage.id == payload.package_id,
            AppPackage.tenant_id == str(current_user.tenant_id),
            AppPackage.deleted_at.is_(None),
        )
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

    if package.platform != payload.platform:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Package platform mismatch")

    def sanitize_filename(filename: str) -> str:
        name = Path(filename).name.replace("\x00", "")
        name = re.sub(r'[<>:"/\\\\|?*]+', "_", name).strip()
        if not name or name in {".", ".."}:
            return "package"
        return name[:200]

    def resolve_storage_root() -> Path:
        root = Path(settings.app_package_storage_dir)
        if root.is_absolute():
            return root
        backend_root = Path(__file__).resolve().parents[3]
        return (backend_root / root).resolve()

    def build_local_path() -> Path:
        root = resolve_storage_root()
        safe_filename = sanitize_filename(package.filename)
        return root / str(package.tenant_id) / str(package.project_id) / str(package.id) / safe_filename

    def write_local_copy(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid_module.uuid4().hex}.tmp")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
            tmp.replace(path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    local_path = Path(package.local_path) if package.local_path else build_local_path()
    if not local_path.exists():
        try:
            data = get_oss_client().download_bytes(package.object_key)
            write_local_copy(local_path, data)
            package.local_path = str(local_path)
            await db.commit()
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local package missing and download failed")

    if payload.platform == "android":
        cmd = ["adb", "-s", payload.udid, "install", "-r", str(local_path)]
    else:
        cmd = ["ideviceinstaller", "-u", payload.udid, "-i", str(local_path)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        tool = "adb" if payload.platform == "android" else "ideviceinstaller"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{tool} not installed on server")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_408_REQUEST_TIMEOUT, detail="Install command timed out")

    stdout = (proc.stdout or "").strip() or None
    stderr = (proc.stderr or "").strip() or None
    if proc.returncode != 0:
        return InstallPackageResponse(success=False, message="Install failed", stdout=stdout, stderr=stderr)

    device_result = await db.execute(
        select(Device).where(
            Device.tenant_id == str(current_user.tenant_id),
            Device.udid == payload.udid,
            Device.deleted_at.is_(None),
        )
    )
    db_device = device_result.scalar_one_or_none()
    if db_device:
        caps = dict(db_device.capabilities or {})
        caps["app_path"] = str(local_path)
        if payload.platform == "android":
            if getattr(package, "app_package", None):
                caps["app_package"] = package.app_package
            if getattr(package, "app_activity", None):
                caps["app_activity"] = package.app_activity
        else:
            if getattr(package, "bundle_id", None):
                caps["bundle_id"] = package.bundle_id
        db_device.capabilities = caps
        await db.commit()

    return InstallPackageResponse(success=True, message="Install succeeded", stdout=stdout, stderr=stderr)


@router.post("/devices/test-connection", response_model=TestConnectionResponse)
async def test_remote_connection(
    payload: TestConnectionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Test connection to a remote Appium server.
    """
    import asyncio
    import aiohttp
    
    base_path = payload.path.rstrip('/') if payload.path else ""
    url = f"http://{payload.host}:{payload.port}{base_path}/status"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return TestConnectionResponse(
                        success=True,
                        message="Connection successful",
                        server_info=data.get("value", {}),
                    )
                else:
                    return TestConnectionResponse(
                        success=False,
                        message=f"Server returned status {response.status}",
                    )
    except asyncio.TimeoutError:
        return TestConnectionResponse(
            success=False,
            message="Connection timed out",
        )
    except aiohttp.ClientError as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
        )


@router.post("/devices/remote-servers", response_model=RemoteServerResponse, status_code=status.HTTP_201_CREATED)
async def add_remote_server(
    payload: RemoteServerCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Add a remote Appium server configuration.
    """
    server = RemoteAppiumServer(
        tenant_id=str(current_user.tenant_id),
        name=payload.name,
        host=payload.host,
        port=payload.port,
        path=payload.path,
        username=payload.username,
        password=payload.password,
        status="unknown",
        last_connected=None,
        device_count=0,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    return RemoteServerResponse(
        id=server.id,
        name=server.name,
        host=server.host,
        port=server.port,
        path=server.path,
        status=server.status,
        last_connected=server.last_connected,
        device_count=server.device_count,
    )


@router.get("/devices/remote-servers", response_model=List[RemoteServerResponse])
async def list_remote_servers(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    List all configured remote Appium servers.
    """
    result = await db.execute(
        select(RemoteAppiumServer).where(
            RemoteAppiumServer.tenant_id == str(current_user.tenant_id),
            RemoteAppiumServer.deleted_at.is_(None),
        )
    )
    servers = result.scalars().all()
    return [
        RemoteServerResponse(
            id=s.id,
            name=s.name,
            host=s.host,
            port=s.port,
            path=s.path,
            status=s.status,
            last_connected=s.last_connected,
            device_count=s.device_count,
        )
        for s in servers
    ]


@router.delete("/devices/remote-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_remote_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a remote Appium server configuration.
    """
    result = await db.execute(
        select(RemoteAppiumServer).where(
            RemoteAppiumServer.id == server_id,
            RemoteAppiumServer.tenant_id == str(current_user.tenant_id),
            RemoteAppiumServer.deleted_at.is_(None),
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remote server not found")

    server.deleted_at = datetime.utcnow()
    await db.commit()


@router.post("/devices/remote-servers/{server_id}/refresh", response_model=ScanLocalDevicesResponse)
async def refresh_remote_devices(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh/scan devices from a remote Appium server.
    First checks server status, then retrieves active sessions.
    """
    import aiohttp
    
    result = await db.execute(
        select(RemoteAppiumServer).where(
            RemoteAppiumServer.id == server_id,
            RemoteAppiumServer.tenant_id == str(current_user.tenant_id),
            RemoteAppiumServer.deleted_at.is_(None),
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Remote server not found")

    base_path = server.path.rstrip("/") if server.path else ""
    base_url = f"http://{server.host}:{server.port}{base_path}"
    status_url = f"{base_url}/status"
    sessions_url = f"{base_url}/sessions"
    
    discovered_devices = []
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # First check server status
            async with session.get(status_url) as response:
                if response.status != 200:
                    server.status = "offline"
                    await db.commit()
                    return ScanLocalDevicesResponse(
                        devices=[],
                        count=0,
                        message=f"Server returned status {response.status}",
                    )
                
                status_data = await response.json()
                server_ready = status_data.get("value", {}).get("ready", False)
                server_version = status_data.get("value", {}).get("build", {}).get("version", "unknown")
                
                if not server_ready:
                    server.status = "offline"
                    await db.commit()
                    return ScanLocalDevicesResponse(
                        devices=[],
                        count=0,
                        message="Appium server is not ready to accept connections",
                    )
            
            # Server is alive, try to get active sessions
            try:
                async with session.get(sessions_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        sessions = data.get("value", [])
                        
                        for sess in sessions:
                            caps = sess.get("capabilities", {})
                            discovered_devices.append({
                                "udid": caps.get("udid", caps.get("deviceUDID", "unknown")),
                                "platform": caps.get("platformName", "unknown").lower(),
                                "model": caps.get("deviceModel", caps.get("deviceName", "Unknown")),
                                "status": "busy",
                                "connection": "remote",
                                "server_id": server_id,
                                "session_id": sess.get("id"),
                            })
            except Exception:
                # Sessions endpoint might not be available, that's okay
                pass
            
            # Update server status
            server.status = "online"
            server.last_connected = datetime.utcnow()
            server.device_count = len(discovered_devices)
            await db.commit()
            
    except aiohttp.ClientError as e:
        server.status = "offline"
        await db.commit()
        return ScanLocalDevicesResponse(
            devices=[],
            count=0,
            message=f"Failed to connect to remote server: {str(e)}",
        )
    except Exception as e:
        server.status = "offline"
        await db.commit()
        return ScanLocalDevicesResponse(
            devices=[],
            count=0,
            message=f"Unexpected error: {str(e)}",
        )
    
    message = f"Server online (v{server_version}). "
    if discovered_devices:
        message += f"Found {len(discovered_devices)} active session(s)."
    else:
        message += "No active sessions. Server is ready to accept new connections."
    
    return ScanLocalDevicesResponse(
        devices=discovered_devices,
        count=len(discovered_devices),
        message=message,
    )


@router.post("/devices/session/start", response_model=StartSessionResponse)
async def start_appium_session(
    payload: StartSessionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Start a new Appium session for element inspection."""
    import aiohttp
    
    url = f"{payload.server_url.rstrip('/')}/session"
    
    # Inject larger newCommandTimeout to prevent premature expiry
    caps = dict(payload.capabilities)
    caps.setdefault("appium:newCommandTimeout", _NEW_COMMAND_TIMEOUT_SEC)
    
    # W3C WebDriver protocol format for Appium 2.x/3.x
    request_body = {
        "capabilities": {
            "alwaysMatch": caps,
            "firstMatch": [{}]
        }
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=request_body) as response:
                data = await response.json()
                
                if response.status == 200:
                    session_id = data.get("value", {}).get("sessionId")
                    if session_id:
                        tenant_key = str(current_user.tenant_id)
                        _appium_sessions_store.set(tenant_key, session_id, {
                            "server_url": payload.server_url,
                            "capabilities": caps,
                        })
                        return StartSessionResponse(
                            success=True,
                            session_id=session_id,
                            message="Session started successfully",
                        )
                
                # Extract error message
                error_msg = data.get("value", {}).get("message") or data.get("value", {}).get("error") or "Failed to start session"
                return StartSessionResponse(
                    success=False,
                    message=error_msg,
                )
    except aiohttp.ClientError as e:
        return StartSessionResponse(
            success=False,
            message=f"Connection error: {str(e)}",
        )
    except Exception as e:
        return StartSessionResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
        )


@router.post("/devices/session/{session_id}/page-source", response_model=PageSourceResponse)
async def get_page_source(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get page source from an active Appium session."""
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)

    # Auto-recover if session expired
    try:
        effective_sid, session_info = await ensure_session_alive(tenant_key, session_id)
    except HTTPException as exc:
        return PageSourceResponse(success=False, message=exc.detail)
    
    server_url = session_info["server_url"]
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            source_url = f"{server_url.rstrip('/')}/session/{effective_sid}/source"
            async with client.get(source_url) as response:
                if response.status != 200:
                    return PageSourceResponse(
                        success=False,
                        message="Failed to get page source",
                    )
                source_data = await response.json()
                page_source = source_data.get("value", "")
            
            screenshot_url = f"{server_url.rstrip('/')}/session/{effective_sid}/screenshot"
            async with client.get(screenshot_url) as response:
                screenshot_base64 = None
                if response.status == 200:
                    screenshot_data = await response.json()
                    screenshot_base64 = screenshot_data.get("value")
            
            resp = PageSourceResponse(
                success=True,
                source=page_source,
                screenshot=screenshot_base64,
                message="Page source retrieved successfully",
            )
            # If session was recreated, inform the caller
            if effective_sid != session_id:
                resp.message += f" (session auto-recovered: {effective_sid})"
            return resp
    except Exception as e:
        return PageSourceResponse(
            success=False,
            message=f"Error: {str(e)}",
        )


@router.delete("/devices/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_appium_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Stop an active Appium session."""
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)
    
    session_info = _appium_sessions_store.get(tenant_key, session_id)
    
    if session_info:
        server_url = session_info["server_url"]
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                url = f"{server_url.rstrip('/')}/session/{session_id}"
                async with client.delete(url):
                    pass
        except Exception:
            pass
        
        _appium_sessions_store.delete(tenant_key, session_id)


# =============================================================================
# Session Management Endpoints (基于包和设备创建/管理 Session)
# =============================================================================


@router.post("/devices/sessions/create-from-package", response_model=SessionInfo)
async def create_session_from_package(
    payload: CreateSessionFromPackageRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    基于包信息和设备创建 Appium Session。
    自动从包中提取 appPackage/appActivity (Android) 或 bundleId (iOS)。
    """
    import aiohttp
    from app.domain.models import AppPackage
    from app.core.config import settings
    
    def normalize_server_url(url: str) -> str:
        """确保 server_url 是完整的 HTTP URL 格式"""
        if not url:
            return "http://127.0.0.1:4723"
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"
        return url.rstrip("/")
    
    # 1. 获取包信息
    result = await db.execute(
        select(AppPackage).where(
            AppPackage.id == payload.package_id,
            AppPackage.tenant_id == str(current_user.tenant_id),
            AppPackage.deleted_at.is_(None),
        )
    )
    package = result.scalar_one_or_none()
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    
    # 2. 获取设备信息（如果已注册）
    device_result = await db.execute(
        select(Device).where(
            Device.tenant_id == str(current_user.tenant_id),
            Device.udid == payload.device_udid,
            Device.deleted_at.is_(None),
        )
    )
    db_device = device_result.scalar_one_or_none()
    
    platform_version = ""
    device_name = payload.device_udid
    if db_device:
        platform_version = db_device.platform_version or ""
        device_name = db_device.name or db_device.model or payload.device_udid
    
    # 3. 构建 capabilities (use larger newCommandTimeout)
    caps = {
        "platformName": "iOS" if package.platform == "ios" else "Android",
        "appium:automationName": "UiAutomator2" if package.platform == "android" else "XCUITest",
        "appium:deviceName": payload.device_udid,
        "appium:udid": payload.device_udid,
        "appium:noReset": payload.no_reset,
        "appium:fullReset": payload.full_reset,
        "appium:newCommandTimeout": _NEW_COMMAND_TIMEOUT_SEC,
    }
    
    if platform_version:
        caps["appium:platformVersion"] = platform_version
    
    if package.platform == "android":
        if package.app_package:
            caps["appium:appPackage"] = package.app_package
        elif package.package_name:
            caps["appium:appPackage"] = package.package_name
        if package.app_activity:
            caps["appium:appActivity"] = package.app_activity
        if package.local_path and payload.auto_launch:
            caps["appium:app"] = package.local_path
    else:  # iOS
        if package.bundle_id:
            caps["appium:bundleId"] = package.bundle_id
        elif package.package_name:
            caps["appium:bundleId"] = package.package_name
        if package.local_path and payload.auto_launch:
            caps["appium:app"] = package.local_path
    
    # Merge extra capabilities
    if payload.extra_capabilities:
        for key, value in payload.extra_capabilities.items():
            if not key.startswith("appium:") and key not in ("platformName",):
                key = f"appium:{key}"
            caps[key] = value
    
    # 4. 确定 Appium Server URL (自动添加 http:// 前缀)
    server_url = normalize_server_url(payload.server_url or getattr(settings, 'appium_server_url', 'http://127.0.0.1:4723'))
    
    # 5. 创建 Session
    session_url = f"{server_url}/session"
    try:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            request_body = {
                "capabilities": {
                    "alwaysMatch": caps,
                    "firstMatch": [{}]
                }
            }
            async with client.post(session_url, json=request_body) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    error_msg = response_data.get("value", {}).get("message", "Failed to create session")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Appium error: {error_msg}"
                    )
                
                session_id = response_data.get("value", {}).get("sessionId")
                if not session_id:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Session created but no session ID returned"
                    )
    except aiohttp.ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Appium server at {server_url}: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    
    # 6. 保存 Session 信息
    tenant_key = str(current_user.tenant_id)
    
    session_info_data = {
        "session_id": session_id,
        "device_udid": payload.device_udid,
        "device_name": device_name,
        "platform": package.platform,
        "platform_version": platform_version,
        "package_id": package.id,
        "package_name": package.package_name,
        "app_name": package.app_name,
        "server_url": server_url,
        "status": "active",
        "created_at": datetime.utcnow(),
        "capabilities": caps,
    }
    
    _appium_sessions_store.set(tenant_key, session_id, session_info_data)
    
    # 7. 更新设备状态为 busy（如果已注册）
    if db_device:
        db_device.status = "busy"
        await db.commit()
    
    return SessionInfo(**session_info_data)


@router.get("/devices/sessions", response_model=SessionListResponse)
async def list_active_sessions(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """列出当前租户的所有活跃 Appium Sessions。"""
    tenant_key = str(current_user.tenant_id)
    sessions = _appium_sessions_store.get_all(tenant_key)
    
    session_list = []
    for s in sessions.values():
        # Handle both old format (simple dict) and new format (SessionInfo dict)
        if "session_id" in s:
            session_list.append(SessionInfo(**s))
        else:
            # Old format compatibility
            session_list.append(SessionInfo(
                session_id=s.get("session_id", "unknown"),
                device_udid=s.get("capabilities", {}).get("appium:udid", "unknown"),
                platform=s.get("capabilities", {}).get("platformName", "unknown").lower(),
                server_url=s.get("server_url", ""),
                status="active",
                created_at=datetime.utcnow(),
                capabilities=s.get("capabilities", {}),
            ))
    
    return SessionListResponse(sessions=session_list, count=len(session_list))


@router.get("/devices/sessions/{session_id}", response_model=SessionInfo)
async def get_session_detail(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """获取指定 Session 的详细信息。"""
    tenant_key = str(current_user.tenant_id)
    session_info = _appium_sessions_store.get(tenant_key, session_id)
    
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if "session_id" in session_info:
        return SessionInfo(**session_info)
    else:
        return SessionInfo(
            session_id=session_id,
            device_udid=session_info.get("capabilities", {}).get("appium:udid", "unknown"),
            platform=session_info.get("capabilities", {}).get("platformName", "unknown").lower(),
            server_url=session_info.get("server_url", ""),
            status="active",
            created_at=datetime.utcnow(),
            capabilities=session_info.get("capabilities", {}),
        )


@router.post("/devices/sessions/{session_id}/action", response_model=SessionActionResponse)
async def perform_session_action(
    session_id: str,
    payload: SessionActionRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    对 Session 执行操作：
    - screenshot: 截图
    - source: 获取页面源码
    - launch_app: 启动应用
    - close_app: 关闭应用
    - reset_app: 重置应用
    """
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)

    # Auto-recover if session expired
    try:
        effective_sid, session_info = await ensure_session_alive(tenant_key, session_id)
    except HTTPException as exc:
        return SessionActionResponse(success=False, message=exc.detail)
    
    server_url = session_info.get("server_url", "")
    base_url = f"{server_url}/session/{effective_sid}"
    
    # Get platform and package info
    platform = session_info.get("platform", "android")
    package_name = session_info.get("package_name") or session_info.get("capabilities", {}).get("appium:appPackage")
    
    recovery_note = ""
    if effective_sid != session_id:
        recovery_note = " (session auto-recovered)"
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            if payload.action == "screenshot":
                async with client.get(f"{base_url}/screenshot") as response:
                    if response.status == 200:
                        data = await response.json()
                        return SessionActionResponse(
                            success=True,
                            message="Screenshot captured" + recovery_note,
                            data={"screenshot": data.get("value"), "session_id": effective_sid}
                        )
                    return SessionActionResponse(success=False, message="Failed to capture screenshot")
            
            elif payload.action == "source":
                async with client.get(f"{base_url}/source") as response:
                    if response.status == 200:
                        data = await response.json()
                        return SessionActionResponse(
                            success=True,
                            message="Page source retrieved" + recovery_note,
                            data={"source": data.get("value"), "session_id": effective_sid}
                        )
                    return SessionActionResponse(success=False, message="Failed to get page source")
            
            elif payload.action == "launch_app":
                app_id = payload.app_id or package_name
                if not app_id:
                    return SessionActionResponse(success=False, message="No app ID specified")
                
                key = "bundleId" if platform == "ios" else "appId"
                async with client.post(f"{base_url}/appium/device/activate_app", json={key: app_id}) as response:
                    if response.status == 200:
                        return SessionActionResponse(success=True, message=f"App {app_id} launched" + recovery_note)
                    return SessionActionResponse(success=False, message="Failed to launch app")
            
            elif payload.action == "close_app":
                app_id = payload.app_id or package_name
                if not app_id:
                    return SessionActionResponse(success=False, message="No app ID specified")
                
                key = "bundleId" if platform == "ios" else "appId"
                async with client.post(f"{base_url}/appium/device/terminate_app", json={key: app_id}) as response:
                    if response.status == 200:
                        return SessionActionResponse(success=True, message=f"App {app_id} closed" + recovery_note)
                    return SessionActionResponse(success=False, message="Failed to close app")
            
            elif payload.action == "reset_app":
                app_id = payload.app_id or package_name
                if not app_id:
                    return SessionActionResponse(success=False, message="No app ID specified")
                
                key = "bundleId" if platform == "ios" else "appId"
                await client.post(f"{base_url}/appium/device/terminate_app", json={key: app_id})
                await client.post(f"{base_url}/appium/device/activate_app", json={key: app_id})
                return SessionActionResponse(success=True, message=f"App {app_id} reset" + recovery_note)
    
    except aiohttp.ClientError as e:
        _appium_sessions_store.update_field(tenant_key, effective_sid, "status", "disconnected")
        return SessionActionResponse(success=False, message=f"Connection error: {str(e)}")
    except Exception as e:
        return SessionActionResponse(success=False, message=f"Error: {str(e)}")


@router.post("/devices/sessions/{session_id}/refresh", response_model=SessionInfo)
async def refresh_session_status(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """刷新 Session 状态，检查是否仍然活跃。"""
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)
    session_info = _appium_sessions_store.get(tenant_key, session_id)
    
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    server_url = session_info.get("server_url", "")
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.get(f"{server_url}/session/{session_id}") as response:
                if response.status == 200:
                    _appium_sessions_store.update_field(tenant_key, session_id, "status", "active")
                else:
                    _appium_sessions_store.update_field(tenant_key, session_id, "status", "disconnected")
    except Exception:
        _appium_sessions_store.update_field(tenant_key, session_id, "status", "error")
    
    session_info = _appium_sessions_store.get(tenant_key, session_id)
    
    if "session_id" in session_info:
        return SessionInfo(**session_info)
    else:
        return SessionInfo(
            session_id=session_id,
            device_udid=session_info.get("capabilities", {}).get("appium:udid", "unknown"),
            platform=session_info.get("capabilities", {}).get("platformName", "unknown").lower(),
            server_url=server_url,
            status=session_info.get("status", "unknown"),
            created_at=datetime.utcnow(),
            capabilities=session_info.get("capabilities", {}),
        )


@router.delete("/devices/sessions/{session_id}/terminate")
async def terminate_session_and_release(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """终止 Appium Session 并释放设备。"""
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)
    session_info = _appium_sessions_store.get(tenant_key, session_id)
    
    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    server_url = session_info.get("server_url", "")
    device_udid = session_info.get("device_udid")
    
    # 1. 终止 Appium Session
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            await client.delete(f"{server_url}/session/{session_id}")
    except Exception:
        pass
    
    # 2. 从内存中删除
    _appium_sessions_store.delete(tenant_key, session_id)
    
    # 3. 释放设备（如果已注册）
    if device_udid:
        device_result = await db.execute(
            select(Device).where(
                Device.tenant_id == str(current_user.tenant_id),
                Device.udid == device_udid,
                Device.deleted_at.is_(None),
            )
        )
        db_device = device_result.scalar_one_or_none()
        if db_device and db_device.status == "busy":
            db_device.status = "available"
            db_device.current_run_id = None
            await db.commit()
    
    return {"message": "Session terminated successfully"}


# =============================================================================
# Device Endpoints
# =============================================================================


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    platform: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all devices for the tenant."""
    base_query = select(Device).where(
        Device.tenant_id == str(current_user.tenant_id),
        Device.deleted_at.is_(None),
    )

    if platform:
        base_query = base_query.where(Device.platform == platform)
    if status_filter:
        base_query = base_query.where(Device.status == status_filter)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    query = (
        base_query.order_by(Device.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    devices = result.scalars().all()

    return DeviceListResponse(
        items=[DeviceResponse.model_validate(d) for d in devices],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Register a new device."""
    result = await db.execute(
        select(Device).where(
            Device.tenant_id == str(current_user.tenant_id),
            Device.udid == payload.udid,
            Device.deleted_at.is_(None),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with UDID '{payload.udid}' already exists",
        )

    device = Device(
        tenant_id=str(current_user.tenant_id),
        name=payload.name,
        udid=payload.udid,
        platform=payload.platform,
        platform_version=payload.platform_version,
        model=payload.model,
        manufacturer=payload.manufacturer,
        status="available",
        capabilities=payload.capabilities or {},
        tags=payload.tags or [],
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a device by ID."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == str(current_user.tenant_id),
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    return DeviceResponse.model_validate(device)


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == str(current_user.tenant_id),
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a device."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == str(current_user.tenant_id),
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    device.deleted_at = datetime.utcnow()
    await db.commit()
