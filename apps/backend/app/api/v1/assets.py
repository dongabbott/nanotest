"""Assets API endpoints for file upload/download with presigned URLs."""
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.domain.models import User

router = APIRouter(prefix="/assets", tags=["Assets"])


# ============ Request/Response Models ============

class PresignUploadRequest(BaseModel):
    """Request for presigned upload URL."""
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the file")
    file_size: Optional[int] = Field(None, description="File size in bytes")


class PresignUploadResponse(BaseModel):
    """Response with presigned upload URL."""
    upload_url: str
    object_key: str
    expires_at: datetime
    fields: dict = Field(default_factory=dict, description="Form fields for POST upload")


class PresignDownloadRequest(BaseModel):
    """Request for presigned download URL."""
    object_key: str = Field(..., description="Object key in storage")


class PresignDownloadResponse(BaseModel):
    """Response with presigned download URL."""
    download_url: str
    expires_at: datetime


class AssetMetadata(BaseModel):
    """Asset metadata."""
    object_key: str
    filename: str
    content_type: str
    file_size: Optional[int]
    uploaded_at: Optional[datetime]
    checksum: Optional[str]


# ============ MinIO/S3 Client Helper ============

def get_minio_client():
    """Get MinIO client instance."""
    try:
        from minio import Minio
        
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        return client
    except ImportError:
        return None
    except Exception:
        return None


def generate_object_key(tenant_id: str, category: str, filename: str) -> str:
    """Generate a unique object key for storage."""
    timestamp = datetime.utcnow().strftime("%Y/%m/%d")
    unique_id = uuid.uuid4().hex[:8]
    safe_filename = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    return f"{tenant_id}/{category}/{timestamp}/{unique_id}_{safe_filename}"


# ============ Endpoints ============

@router.post("/presign-upload", response_model=PresignUploadResponse)
async def get_presigned_upload_url(
    request: PresignUploadRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Get a presigned URL for uploading a file.
    
    The client should use this URL to upload the file directly to storage,
    bypassing the API server for better performance.
    """
    client = get_minio_client()
    
    # Generate unique object key
    object_key = generate_object_key(
        str(current_user.tenant_id),
        "uploads",
        request.filename
    )
    
    expires = timedelta(hours=1)
    expires_at = datetime.utcnow() + expires
    
    if client:
        try:
            # Ensure bucket exists
            bucket = settings.MINIO_BUCKET
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
            
            # Generate presigned PUT URL
            upload_url = client.presigned_put_object(
                bucket,
                object_key,
                expires=expires,
            )
            
            return PresignUploadResponse(
                upload_url=upload_url,
                object_key=object_key,
                expires_at=expires_at,
                fields={},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Storage service unavailable: {str(e)}",
            )
    else:
        # Fallback: return local upload endpoint
        upload_url = f"{settings.API_BASE_URL}/api/v1/assets/upload/{object_key}"
        return PresignUploadResponse(
            upload_url=upload_url,
            object_key=object_key,
            expires_at=expires_at,
            fields={"fallback": "true"},
        )


@router.post("/presign-download", response_model=PresignDownloadResponse)
async def get_presigned_download_url(
    request: PresignDownloadRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """
    Get a presigned URL for downloading a file.
    
    The URL is valid for a limited time and can be used to download
    the file directly from storage.
    """
    # Verify user has access to the object (basic tenant check)
    tenant_prefix = str(current_user.tenant_id)
    if not request.object_key.startswith(tenant_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this object",
        )
    
    client = get_minio_client()
    expires = timedelta(hours=1)
    expires_at = datetime.utcnow() + expires
    
    if client:
        try:
            download_url = client.presigned_get_object(
                settings.MINIO_BUCKET,
                request.object_key,
                expires=expires,
            )
            
            return PresignDownloadResponse(
                download_url=download_url,
                expires_at=expires_at,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Storage service unavailable: {str(e)}",
            )
    else:
        # Fallback: return local download endpoint
        download_url = f"{settings.API_BASE_URL}/api/v1/assets/download/{request.object_key}"
        return PresignDownloadResponse(
            download_url=download_url,
            expires_at=expires_at,
        )


@router.get("/metadata/{object_key:path}", response_model=AssetMetadata)
async def get_asset_metadata(
    object_key: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get metadata for an asset."""
    # Verify access
    tenant_prefix = str(current_user.tenant_id)
    if not object_key.startswith(tenant_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this object",
        )
    
    client = get_minio_client()
    
    if client:
        try:
            stat = client.stat_object(settings.MINIO_BUCKET, object_key)
            
            # Extract filename from object key
            filename = object_key.split("/")[-1]
            if "_" in filename:
                filename = "_".join(filename.split("_")[1:])
            
            return AssetMetadata(
                object_key=object_key,
                filename=filename,
                content_type=stat.content_type or "application/octet-stream",
                file_size=stat.size,
                uploaded_at=stat.last_modified,
                checksum=stat.etag,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Object not found",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        )


@router.delete("/{object_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    object_key: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Delete an asset from storage."""
    # Verify access
    tenant_prefix = str(current_user.tenant_id)
    if not object_key.startswith(tenant_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this object",
        )
    
    client = get_minio_client()
    
    if client:
        try:
            client.remove_object(settings.MINIO_BUCKET, object_key)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete object: {str(e)}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        )


@router.post("/screenshots/batch-upload")
async def batch_upload_screenshots(
    current_user: Annotated[User, Depends(get_current_active_user)],
    count: int = 10,
):
    """
    Get multiple presigned URLs for batch screenshot upload.
    
    Useful for uploading multiple screenshots at once during test execution.
    """
    if count > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 URLs per request",
        )
    
    urls = []
    for i in range(count):
        object_key = generate_object_key(
            str(current_user.tenant_id),
            "screenshots",
            f"screenshot_{i}.png"
        )
        
        client = get_minio_client()
        expires = timedelta(hours=1)
        expires_at = datetime.utcnow() + expires
        
        if client:
            try:
                upload_url = client.presigned_put_object(
                    settings.MINIO_BUCKET,
                    object_key,
                    expires=expires,
                )
                urls.append({
                    "upload_url": upload_url,
                    "object_key": object_key,
                    "expires_at": expires_at.isoformat(),
                })
            except Exception:
                pass
        else:
            upload_url = f"{settings.API_BASE_URL}/api/v1/assets/upload/{object_key}"
            urls.append({
                "upload_url": upload_url,
                "object_key": object_key,
                "expires_at": expires_at.isoformat(),
            })
    
    return {"urls": urls, "count": len(urls)}
