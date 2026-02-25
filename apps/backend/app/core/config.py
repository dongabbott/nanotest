"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = "AI Mobile Test Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # API
    api_v1_prefix: str = "/api/v1"
    api_base_url: str = "http://localhost:8000"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    algorithm: str = "HS256"
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nanotest"
    database_echo: bool = False
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "nanotest"  # 默认 bucket
    minio_bucket_screenshots: str = "screenshots"
    minio_bucket_reports: str = "reports"
    minio_bucket_logs: str = "logs"
    minio_secure: bool = False
    
    # Appium
    appium_server_url: str = "http://localhost:4723"
    appium_session_timeout: int = 300
    
    # AI/LLM
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-vision-preview"
    ai_analysis_timeout: int = 60
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    app_package_storage_dir: str = "storage/app_packages"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
