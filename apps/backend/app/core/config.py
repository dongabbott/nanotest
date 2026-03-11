"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional, Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
    
    # Object Storage (Aliyun OSS)
    oss_sts_token_url: Optional[str] = "https://admin.shiguangxiaowu.cn/rhea/users/file_store_token"
    oss_url_scheme: Optional[str] = "https://alicn.timehutcdn.cn"
    
    # Appium
    appium_server_url: str = "http://localhost:4723"
    appium_session_timeout: int = 300
    
    # AI/LLM
    llm_provider: str = "openai"  # openai|doubao|ark|other(openai-compatible)

    # Volcengine Ark (Doubao) OpenAI-compatible settings
    ark_api_key: Optional[str] = "1b783983-5e9b-4321-9921-ad4ac5b41dda"
    ark_base_url: Optional[str] = "https://ark.cn-beijing.volces.com/api/v3"  # e.g. https://ark.cn-beijing.volces.com/api/v3
    ark_model: Optional[str] = "doubao-seed-2-0-pro-260215"  # e.g. doubao-seed-2-0-pro-260215

    # OpenAI-compatible settings (used by the SDK client)
    llm_base_url: Optional[str] = None  # if set, used as OpenAI-compatible base_url

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-vision-preview"
    ai_analysis_timeout: int = 120
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    app_package_storage_dir: str = "storage/app_packages"

    def model_post_init(self, __context: Any) -> None:
        """Derive effective OpenAI-compatible config from Ark/OpenAI env vars.

        Priority:
        - If OPENAI_* explicitly provided, use them.
        - Else if ARK_* provided, map to effective OPENAI_* and base_url.
        - Else keep defaults.
        """
        if not self.openai_api_key and self.ark_api_key:
            self.openai_api_key = self.ark_api_key
        if (not self.llm_base_url) and self.ark_base_url:
            self.llm_base_url = self.ark_base_url
        if (self.openai_model == "gpt-4-vision-preview") and self.ark_model:
            self.openai_model = self.ark_model


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
