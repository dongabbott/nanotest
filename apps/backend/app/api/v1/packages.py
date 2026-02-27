"""App package management API endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.domain.models import User
from app.schemas.schemas import (
    AppPackageDownloadResponse,
    AppPackageIconResponse,
    AppPackageListResponse,
    AppPackageResponse,
    AppPackageUpdate,
    AppPackageUploadResponse,
    ErrorResponse,
)
from app.services.package_service import PackageService

router = APIRouter(prefix="/packages", tags=["Packages"])

# Max file size: 500MB
MAX_FILE_SIZE = 500 * 1024 * 1024


@router.post(
    "/upload",
    response_model=AppPackageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or parsing error"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
    summary="Upload app package",
    description="Upload an Android APK or iOS IPA file. The file will be parsed to extract metadata.",
)
async def upload_package(
    file: UploadFile = File(..., description="APK or IPA file to upload"),
    project_id: UUID = Form(..., description="Project ID to associate the package with"),
    description: Optional[str] = Form(None, description="Optional description"),
    tags: Optional[str] = Form(None, description="Comma-separated tags"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and parse an Android APK or iOS IPA file.
    
    The system will automatically extract:
    - **Android APK**: Package name, version, app activity, permissions, SDK versions, etc.
    - **iOS IPA**: Bundle ID, version, build number, minimum OS version, supported platforms, etc.
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".apk") or filename_lower.endswith(".ipa")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .apk and .ipa files are supported",
        )
    
    # Read file content
    file_data = await file.read()
    
    # Check file size
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )
    
    # Parse tags
    tag_list = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Upload and parse
    service = PackageService(db)
    try:
        package = await service.upload_package(
            project_id=str(project_id),
            tenant_id=current_user.tenant_id,
            filename=file.filename,
            file_data=file_data,
            uploaded_by=current_user.id,
            description=description,
            tags=tag_list,
        )
        return AppPackageUploadResponse.from_package(package)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=AppPackageListResponse,
    summary="List packages",
    description="List all packages with optional filtering by project or platform.",
)
async def list_packages(
    project_id: Optional[UUID] = Query(None, description="Filter by project ID"),
    platform: Optional[str] = Query(None, pattern="^(android|ios)$", description="Filter by platform"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all packages for the current tenant."""
    service = PackageService(db)
    packages, total = await service.list_packages(
        tenant_id=current_user.tenant_id,
        project_id=str(project_id) if project_id else None,
        platform=platform,
        page=page,
        page_size=page_size,
    )
    
    return AppPackageListResponse(
        items=[AppPackageResponse.from_package(p) for p in packages],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{package_id}",
    response_model=AppPackageResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get package details",
    description="Get detailed information about a specific package.",
)
async def get_package(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get package details by ID."""
    service = PackageService(db)
    package = await service.get_package(str(package_id), current_user.tenant_id)
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    
    return AppPackageResponse.from_package(package)


@router.patch(
    "/{package_id}",
    response_model=AppPackageResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Update package",
    description="Update package metadata (description, tags, status).",
)
async def update_package(
    package_id: UUID,
    update_data: AppPackageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update package metadata."""
    service = PackageService(db)
    package = await service.update_package(
        package_id=str(package_id),
        tenant_id=current_user.tenant_id,
        description=update_data.description,
        tags=update_data.tags,
        status=update_data.status,
    )
    
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    
    return AppPackageResponse.from_package(package)


@router.delete(
    "/{package_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete package",
    description="Soft delete a package.",
)
async def delete_package(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a package (soft delete)."""
    service = PackageService(db)
    deleted = await service.delete_package(str(package_id), current_user.tenant_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )


@router.get(
    "/{package_id}/download",
    response_model=AppPackageDownloadResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get download URL",
    description="Get a presigned URL to download the package file.",
)
async def get_download_url(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned download URL for a package."""
    service = PackageService(db)
    download_url = await service.get_download_url(str(package_id), current_user.tenant_id)
    
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    
    return AppPackageDownloadResponse(download_url=download_url, expires_in=3600)


@router.get(
    "/{package_id}/icon",
    response_model=AppPackageIconResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get icon URL",
    description="Get a presigned URL to download the package icon.",
)
async def get_icon_url(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get presigned URL for package icon."""
    service = PackageService(db)
    
    # First check if package exists
    package = await service.get_package(str(package_id), current_user.tenant_id)
    if not package:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )
    
    icon_url = await service.get_icon_url(str(package_id), current_user.tenant_id)
    return AppPackageIconResponse(icon_url=icon_url, expires_in=3600)


@router.get(
    "/by-name/{package_name:path}",
    response_model=AppPackageListResponse,
    summary="Get packages by name",
    description="Get all versions of a package by package name (bundle ID / package name).",
)
async def get_packages_by_name(
    package_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all versions of a package by package name."""
    service = PackageService(db)
    packages = await service.get_packages_by_package_name(
        tenant_id=current_user.tenant_id,
        package_name=package_name,
    )
    
    return AppPackageListResponse(
        items=[AppPackageResponse.from_package(p) for p in packages],
        total=len(packages),
        page=1,
        page_size=len(packages),
    )
