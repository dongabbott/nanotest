"""MinIO client integration for object storage."""
import io
from datetime import timedelta
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class MinioClient:
    """MinIO client wrapper for object storage operations."""

    def __init__(self):
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        """Ensure required buckets exist."""
        buckets = [
            settings.minio_bucket_screenshots,
            settings.minio_bucket_reports,
            settings.minio_bucket_logs,
        ]
        for bucket in buckets:
            try:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
            except S3Error as e:
                # Log but don't fail - bucket might already exist
                print(f"Warning: Could not create bucket {bucket}: {e}")

    def upload_file(
        self,
        bucket: str,
        object_name: str,
        file_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file to MinIO."""
        self._client.fput_object(
            bucket,
            object_name,
            file_path,
            content_type=content_type,
        )
        return object_name

    def upload_bytes(
        self,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes data to MinIO."""
        self._client.put_object(
            bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def download_file(self, bucket: str, object_name: str, file_path: str) -> str:
        """Download a file from MinIO."""
        self._client.fget_object(bucket, object_name, file_path)
        return file_path

    def download_bytes(self, bucket: str, object_name: str) -> bytes:
        """Download bytes data from MinIO."""
        response = self._client.get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_presigned_upload_url(
        self,
        bucket: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Get a presigned URL for uploading."""
        return self._client.presigned_put_object(
            bucket,
            object_name,
            expires=expires,
        )

    def get_presigned_download_url(
        self,
        bucket: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Get a presigned URL for downloading."""
        return self._client.presigned_get_object(
            bucket,
            object_name,
            expires=expires,
        )

    def delete_object(self, bucket: str, object_name: str) -> None:
        """Delete an object from MinIO."""
        self._client.remove_object(bucket, object_name)

    def object_exists(self, bucket: str, object_name: str) -> bool:
        """Check if an object exists."""
        try:
            self._client.stat_object(bucket, object_name)
            return True
        except S3Error:
            return False


# Singleton instance
_minio_client: Optional[MinioClient] = None


def get_minio_client() -> MinioClient:
    """Get the MinIO client singleton."""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinioClient()
    return _minio_client
