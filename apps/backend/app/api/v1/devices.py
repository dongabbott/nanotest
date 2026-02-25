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
from app.domain.models import Device, DevicePool, DevicePoolMember, Project, User
from app.schemas.schemas import (
    DeviceCreate,
    DeviceListResponse,
    DevicePoolCreate,
    DevicePoolListResponse,
    DevicePoolResponse,
    DevicePoolUpdate,
    DeviceResponse,
    DeviceUpdate,
)

router = APIRouter(tags=["Devices"])


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


# In-memory storage for remote servers and sessions (in production, use database)
_remote_servers: dict = {}
_appium_sessions: dict = {}


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
):
    """
    Add a remote Appium server configuration.
    """
    import uuid as uuid_module
    server_id = uuid_module.uuid4().hex
    tenant_key = str(current_user.tenant_id)
    
    if tenant_key not in _remote_servers:
        _remote_servers[tenant_key] = {}
    
    server = {
        "id": server_id,
        "name": payload.name,
        "host": payload.host,
        "port": payload.port,
        "path": payload.path,
        "username": payload.username,
        "password": payload.password,
        "status": "unknown",
        "last_connected": None,
        "device_count": 0,
    }
    
    _remote_servers[tenant_key][server_id] = server
    
    return RemoteServerResponse(**{k: v for k, v in server.items() if k not in ("username", "password")})


@router.get("/devices/remote-servers", response_model=List[RemoteServerResponse])
async def list_remote_servers(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    List all configured remote Appium servers.
    """
    tenant_key = str(current_user.tenant_id)
    servers = _remote_servers.get(tenant_key, {})
    
    return [
        RemoteServerResponse(**{k: v for k, v in s.items() if k not in ("username", "password")})
        for s in servers.values()
    ]


@router.delete("/devices/remote-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_remote_server(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Delete a remote Appium server configuration.
    """
    tenant_key = str(current_user.tenant_id)
    servers = _remote_servers.get(tenant_key, {})
    
    if server_id not in servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remote server not found",
        )
    
    del _remote_servers[tenant_key][server_id]


@router.post("/devices/remote-servers/{server_id}/refresh", response_model=ScanLocalDevicesResponse)
async def refresh_remote_devices(
    server_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Refresh/scan devices from a remote Appium server.
    First checks server status, then retrieves active sessions.
    """
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)
    servers = _remote_servers.get(tenant_key, {})
    
    if server_id not in servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Remote server not found",
        )
    
    server = servers[server_id]
    base_path = server['path'].rstrip('/') if server['path'] else ""
    base_url = f"http://{server['host']}:{server['port']}{base_path}"
    status_url = f"{base_url}/status"
    sessions_url = f"{base_url}/sessions"
    
    discovered_devices = []
    
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # First check server status
            async with session.get(status_url) as response:
                if response.status != 200:
                    server["status"] = "error"
                    return ScanLocalDevicesResponse(
                        devices=[],
                        count=0,
                        message=f"Server returned status {response.status}",
                    )
                
                status_data = await response.json()
                server_ready = status_data.get("value", {}).get("ready", False)
                server_version = status_data.get("value", {}).get("build", {}).get("version", "unknown")
                
                if not server_ready:
                    server["status"] = "not_ready"
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
            server["status"] = "connected"
            server["last_connected"] = datetime.utcnow()
            server["device_count"] = len(discovered_devices)
            server["server_version"] = server_version
            
    except aiohttp.ClientError as e:
        server["status"] = "error"
        return ScanLocalDevicesResponse(
            devices=[],
            count=0,
            message=f"Failed to connect to remote server: {str(e)}",
        )
    except Exception as e:
        server["status"] = "error"
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
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json={"capabilities": payload.capabilities}) as response:
                if response.status == 200:
                    data = await response.json()
                    session_id = data.get("value", {}).get("sessionId")
                    if session_id:
                        tenant_key = str(current_user.tenant_id)
                        if tenant_key not in _appium_sessions:
                            _appium_sessions[tenant_key] = {}
                        _appium_sessions[tenant_key][session_id] = {
                            "server_url": payload.server_url,
                            "capabilities": payload.capabilities,
                        }
                        return StartSessionResponse(
                            success=True,
                            session_id=session_id,
                            message="Session started successfully",
                        )
                error_data = await response.json()
                return StartSessionResponse(
                    success=False,
                    message=error_data.get("value", {}).get("error", "Failed to start session"),
                )
    except Exception as e:
        return StartSessionResponse(
            success=False,
            message=f"Connection error: {str(e)}",
        )


@router.post("/devices/session/{session_id}/page-source", response_model=PageSourceResponse)
async def get_page_source(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get page source from an active Appium session."""
    import aiohttp
    
    tenant_key = str(current_user.tenant_id)
    sessions = _appium_sessions.get(tenant_key, {})
    
    if session_id not in sessions:
        return PageSourceResponse(
            success=False,
            message="Session not found. Please start a new session.",
        )
    
    session_info = sessions[session_id]
    server_url = session_info["server_url"]
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            source_url = f"{server_url.rstrip('/')}/session/{session_id}/source"
            async with client.get(source_url) as response:
                if response.status != 200:
                    return PageSourceResponse(
                        success=False,
                        message="Failed to get page source",
                    )
                source_data = await response.json()
                page_source = source_data.get("value", "")
            
            screenshot_url = f"{server_url.rstrip('/')}/session/{session_id}/screenshot"
            async with client.get(screenshot_url) as response:
                screenshot_base64 = None
                if response.status == 200:
                    screenshot_data = await response.json()
                    screenshot_base64 = screenshot_data.get("value")
            
            return PageSourceResponse(
                success=True,
                source=page_source,
                screenshot=screenshot_base64,
                message="Page source retrieved successfully",
            )
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
    sessions = _appium_sessions.get(tenant_key, {})
    
    if session_id in sessions:
        session_info = sessions[session_id]
        server_url = session_info["server_url"]
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as client:
                url = f"{server_url.rstrip('/')}/session/{session_id}"
                async with client.delete(url):
                    pass
        except Exception:
            pass
        
        del _appium_sessions[tenant_key][session_id]


# =============================================================================
# Device Endpoints
# =============================================================================


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    pool_id: Optional[UUID] = Query(None),
):
    """List all devices for the tenant."""
    base_query = select(Device).where(
        Device.tenant_id == current_user.tenant_id,
        Device.deleted_at.is_(None),
    )

    if platform:
        base_query = base_query.where(Device.platform == platform)
    if status_filter:
        base_query = base_query.where(Device.status == status_filter)
    if pool_id:
        base_query = base_query.join(DevicePoolMember).where(
            DevicePoolMember.pool_id == pool_id
        )

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Get items
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


@router.post(
    "/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(
    payload: DeviceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Register a new device."""
    # Check if device with same UDID already exists
    result = await db.execute(
        select(Device).where(
            Device.tenant_id == current_user.tenant_id,
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
        tenant_id=current_user.tenant_id,
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
    await db.flush()
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
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

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
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    await db.flush()
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
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    device.deleted_at = datetime.utcnow()
    await db.flush()


@router.post("/devices/{device_id}/heartbeat", response_model=DeviceResponse)
async def device_heartbeat(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update device heartbeat timestamp."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    device.last_heartbeat = datetime.utcnow()
    if device.status == "offline":
        device.status = "available"

    await db.flush()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.post("/devices/{device_id}/reserve", response_model=DeviceResponse)
async def reserve_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Reserve a device for testing."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    if device.status != "available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device is not available (current status: {device.status})",
        )

    device.status = "busy"
    device.current_run_id = None  # Will be set when run starts
    await db.flush()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.post("/devices/{device_id}/release", response_model=DeviceResponse)
async def release_device(
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Release a device after testing."""
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    device.status = "available"
    device.current_run_id = None
    await db.flush()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


# =============================================================================
# Device Pool Endpoints
# =============================================================================


@router.get("/device-pools", response_model=DevicePoolListResponse)
async def list_device_pools(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all device pools for the tenant."""
    base_query = select(DevicePool).where(
        DevicePool.tenant_id == current_user.tenant_id,
        DevicePool.deleted_at.is_(None),
    )

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Get items
    query = (
        base_query.order_by(DevicePool.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    pools = result.scalars().all()

    return DevicePoolListResponse(
        items=[DevicePoolResponse.model_validate(p) for p in pools],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/device-pools",
    response_model=DevicePoolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_device_pool(
    payload: DevicePoolCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new device pool."""
    pool = DevicePool(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description,
        selection_strategy=payload.selection_strategy or "round_robin",
        platform_filter=payload.platform_filter,
        tag_filter=payload.tag_filter or [],
    )
    db.add(pool)
    await db.flush()
    await db.refresh(pool)
    return DevicePoolResponse.model_validate(pool)


@router.get("/device-pools/{pool_id}", response_model=DevicePoolResponse)
async def get_device_pool(
    pool_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a device pool by ID."""
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    return DevicePoolResponse.model_validate(pool)


@router.patch("/device-pools/{pool_id}", response_model=DevicePoolResponse)
async def update_device_pool(
    pool_id: UUID,
    payload: DevicePoolUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a device pool."""
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pool, field, value)

    await db.flush()
    await db.refresh(pool)
    return DevicePoolResponse.model_validate(pool)


@router.delete("/device-pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_pool(
    pool_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a device pool."""
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    pool.deleted_at = datetime.utcnow()
    await db.flush()


@router.post(
    "/device-pools/{pool_id}/devices/{device_id}",
    status_code=status.HTTP_201_CREATED,
)
async def add_device_to_pool(
    pool_id: UUID,
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Add a device to a pool."""
    # Verify pool exists
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    # Verify device exists
    result = await db.execute(
        select(Device).where(
            Device.id == str(device_id),
            Device.tenant_id == current_user.tenant_id,
            Device.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check if already in pool
    result = await db.execute(
        select(DevicePoolMember).where(
            DevicePoolMember.pool_id == pool_id,
            DevicePoolMember.device_id == device_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device already in pool",
        )

    # Add to pool
    member = DevicePoolMember(
        pool_id=pool_id,
        device_id=device_id,
        priority=0,
    )
    db.add(member)
    await db.flush()

    return {"message": "Device added to pool"}


@router.delete(
    "/device-pools/{pool_id}/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_device_from_pool(
    pool_id: UUID,
    device_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Remove a device from a pool."""
    result = await db.execute(
        select(DevicePoolMember).where(
            DevicePoolMember.pool_id == pool_id,
            DevicePoolMember.device_id == device_id,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not in pool",
        )

    await db.delete(member)
    await db.flush()


@router.get("/device-pools/{pool_id}/devices", response_model=DeviceListResponse)
async def list_pool_devices(
    pool_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all devices in a pool."""
    # Verify pool exists
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    base_query = (
        select(Device)
        .join(DevicePoolMember)
        .where(
            DevicePoolMember.pool_id == pool_id,
            Device.deleted_at.is_(None),
        )
    )

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query)

    # Get items
    query = (
        base_query.order_by(DevicePoolMember.priority.desc(), Device.name)
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


@router.post("/device-pools/{pool_id}/acquire", response_model=DeviceResponse)
async def acquire_device_from_pool(
    pool_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    platform: Optional[str] = Query(None),
):
    """Acquire an available device from the pool."""
    # Verify pool exists
    result = await db.execute(
        select(DevicePool).where(
            DevicePool.id == str(pool_id),
            DevicePool.tenant_id == current_user.tenant_id,
            DevicePool.deleted_at.is_(None),
        )
    )
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device pool not found",
        )

    # Find available device
    query = (
        select(Device)
        .join(DevicePoolMember)
        .where(
            DevicePoolMember.pool_id == pool_id,
            Device.status == "available",
            Device.deleted_at.is_(None),
        )
    )

    # Apply platform filter
    if platform:
        query = query.where(Device.platform == platform)
    elif pool.platform_filter:
        query = query.where(Device.platform == pool.platform_filter)

    # Order by selection strategy
    if pool.selection_strategy == "priority":
        query = query.order_by(DevicePoolMember.priority.desc())
    elif pool.selection_strategy == "least_used":
        query = query.order_by(Device.last_heartbeat.asc().nullsfirst())
    else:  # round_robin - just get first available
        query = query.order_by(Device.last_heartbeat.desc().nullslast())

    query = query.limit(1)
    result = await db.execute(query)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No available devices in pool",
        )

    # Reserve the device
    device.status = "busy"
    await db.flush()
    await db.refresh(device)

    return DeviceResponse.model_validate(device)
