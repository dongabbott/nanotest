"""App package management service."""
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import AppPackage, Project
from app.integrations.aliyun.oss_client import get_oss_client
from app.services.package_parser import AppPackageParser, AppPackageInfo

logger = structlog.get_logger()


class PackageService:
    """Service for managing app packages."""
    
    # OSS 路径前缀
    PATH_PACKAGES = "packages"
    PATH_ICONS = "icons"
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.oss = get_oss_client()

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        name = Path(filename).name.replace("\x00", "")
        name = re.sub(r'[<>:"/\\\\|?*]+', "_", name).strip()
        if not name or name in {".", ".."}:
            return "package"
        return name[:200]

    @staticmethod
    def _resolve_storage_root() -> Path:
        root = Path(settings.app_package_storage_dir)
        if root.is_absolute():
            return root
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / root).resolve()

    def _build_local_package_path(self, tenant_id: str, project_id: str, package_id: str, filename: str) -> Path:
        root = self._resolve_storage_root()
        safe_filename = self._sanitize_filename(filename)
        return root / tenant_id / project_id / package_id / safe_filename

    def _write_local_copy(self, local_path: Path, file_data: bytes) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = local_path.with_name(f".{local_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp_path, "wb") as f:
                f.write(file_data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, local_path)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
    
    async def upload_package(
        self,
        project_id: str,
        tenant_id: str,
        filename: str,
        file_data: bytes,
        uploaded_by: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> AppPackage:
        """
        Upload and parse an app package.
        
        Args:
            project_id: Project ID to associate the package with
            tenant_id: Tenant ID
            filename: Original filename
            file_data: Raw file bytes
            uploaded_by: User ID who uploaded
            description: Optional description
            tags: Optional tags
            
        Returns:
            Created AppPackage model
        """
        # Verify project exists
        project = await self.db.get(Project, project_id)
        if not project or project.tenant_id != tenant_id:
            raise ValueError("Project not found or access denied")
        
        # Parse the package
        logger.info(f"Parsing package: {filename}")
        try:
            package_info = AppPackageParser.parse(file_data, filename)
        except Exception as e:
            logger.error(f"Failed to parse package: {e}")
            raise ValueError(f"Failed to parse package: {str(e)}")
        
        # Calculate file hash
        file_hash = AppPackageParser.calculate_hash(file_data)
        
        # Check for duplicate
        existing = await self._find_by_hash(tenant_id, file_hash)
        if existing:
            raise ValueError(f"Package already exists with ID: {existing.id}")
        
        # Generate object key - 简化路径: packages/{filename}
        package_id = str(uuid.uuid4())
        safe_filename = self._sanitize_filename(filename)
        simple_key = f"{self.PATH_PACKAGES}/{safe_filename}"

        local_path = self._build_local_package_path(tenant_id, project_id, package_id, safe_filename)
        try:
            self._write_local_copy(local_path, file_data)
        except Exception as e:
            raise ValueError(f"Failed to save local package copy: {str(e)}")
        
        # Upload to Aliyun OSS - 返回完整路径（包含 path 前缀）
        logger.info(f"Uploading package to Aliyun OSS: {simple_key}")
        content_type = "application/vnd.android.package-archive" if package_info.platform == "android" else "application/octet-stream"
        try:
            object_key = self.oss.upload_bytes(simple_key, file_data, content_type)
        except Exception as e:
            try:
                if local_path.exists():
                    local_path.unlink()
            except Exception:
                pass
            raise ValueError(f"Failed to upload package to OSS: {str(e)}")
        
        # Upload icon if available - 简化路径: icons/{filename}_icon.png
        icon_object_key = None
        if package_info.icon_data:
            icon_filename = Path(safe_filename).stem
            simple_icon_key = f"{self.PATH_ICONS}/{icon_filename}_icon.png"
            try:
                icon_object_key = self.oss.upload_bytes(simple_icon_key, package_info.icon_data, "image/png")
            except Exception as e:
                logger.warning(f"Failed to upload icon: {e}")
        
        # Create database record
        app_package = AppPackage(
            id=package_id,
            project_id=project_id,
            tenant_id=tenant_id,
            filename=filename,
            file_size=len(file_data),
            file_hash=file_hash,
            object_key=object_key,
            local_path=str(local_path),
            platform=package_info.platform,
            package_name=package_info.package_name,
            app_name=package_info.app_name,
            version_name=package_info.version_name,
            version_code=package_info.version_code,
            build_number=package_info.build_number,
            min_sdk_version=package_info.min_sdk_version,
            target_sdk_version=package_info.target_sdk_version,
            app_activity=package_info.app_activity,
            app_package=package_info.package_name if package_info.platform == "android" else None,
            bundle_id=package_info.package_name if package_info.platform == "ios" else None,
            minimum_os_version=package_info.minimum_os_version,
            supported_platforms=package_info.supported_platforms,
            permissions=package_info.permissions,
            icon_object_key=icon_object_key,
            extra_metadata=package_info.extra_metadata or {},
            description=description,
            tags=tags or [],
            uploaded_by=uploaded_by,
        )
        
        self.db.add(app_package)
        await self.db.commit()
        await self.db.refresh(app_package)
        
        logger.info(f"Package uploaded successfully: {package_id}")
        return app_package
    
    async def get_package(self, package_id: str, tenant_id: str) -> Optional[AppPackage]:
        """Get a package by ID."""
        result = await self.db.execute(
            select(AppPackage).where(
                and_(
                    AppPackage.id == package_id,
                    AppPackage.tenant_id == tenant_id,
                    AppPackage.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def list_packages(
        self,
        tenant_id: str,
        project_id: Optional[str] = None,
        platform: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AppPackage], int]:
        """List packages with filtering and pagination."""
        query = select(AppPackage).where(
            and_(
                AppPackage.tenant_id == tenant_id,
                AppPackage.deleted_at.is_(None),
            )
        )
        
        if project_id:
            query = query.where(AppPackage.project_id == project_id)
        if platform:
            query = query.where(AppPackage.platform == platform)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Paginate
        query = query.order_by(AppPackage.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        packages = list(result.scalars().all())
        
        return packages, total
    
    async def delete_package(self, package_id: str, tenant_id: str) -> bool:
        """Soft delete a package."""
        package = await self.get_package(package_id, tenant_id)
        if not package:
            return False
        
        package.deleted_at = datetime.utcnow()
        await self.db.commit()
        
        # Optionally delete from OSS (keep for now for audit)
        # self.oss.delete_object(package.object_key)
        
        return True
    
    async def update_package(
        self,
        package_id: str,
        tenant_id: str,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
    ) -> Optional[AppPackage]:
        """Update package metadata."""
        package = await self.get_package(package_id, tenant_id)
        if not package:
            return None
        
        if description is not None:
            package.description = description
        if tags is not None:
            package.tags = tags
        if status is not None:
            package.status = status
        
        await self.db.commit()
        await self.db.refresh(package)
        return package
    
    async def get_download_url(self, package_id: str, tenant_id: str) -> Optional[str]:
        """Get presigned download URL for a package."""
        package = await self.get_package(package_id, tenant_id)
        if not package:
            return None
        
        return self.oss.get_download_url(package.object_key, expires=3600)
    
    async def get_icon_url(self, package_id: str, tenant_id: str) -> Optional[str]:
        """Get presigned URL for package icon."""
        package = await self.get_package(package_id, tenant_id)
        if not package or not package.icon_object_key:
            return None
        
        return self.oss.get_download_url(package.icon_object_key, expires=3600)
    
    async def _find_by_hash(self, tenant_id: str, file_hash: str) -> Optional[AppPackage]:
        """Find package by file hash."""
        result = await self.db.execute(
            select(AppPackage).where(
                and_(
                    AppPackage.tenant_id == tenant_id,
                    AppPackage.file_hash == file_hash,
                    AppPackage.deleted_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_packages_by_package_name(
        self,
        tenant_id: str,
        package_name: str,
    ) -> list[AppPackage]:
        """Get all versions of a package by package name."""
        result = await self.db.execute(
            select(AppPackage).where(
                and_(
                    AppPackage.tenant_id == tenant_id,
                    AppPackage.package_name == package_name,
                    AppPackage.deleted_at.is_(None),
                )
            ).order_by(AppPackage.created_at.desc())
        )
        return list(result.scalars().all())
