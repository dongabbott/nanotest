"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Any, Optional

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
    llm_provider: str = "doubao"  # doubao|qwen

    # Volcengine Doubao / Ark (OpenAI-compatible)
    doubao_api_key: Optional[str] = None
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_chat_model: str = "doubao-seed-2-0-pro-260215"
    doubao_embedding_model: str = "doubao-embedding-vision-251215"

    # Aliyun Qwen / DashScope compatible-mode
    qwen_api_key: Optional[str] = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_chat_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v3"

    # Effective provider settings resolved from llm_provider
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_chat_model: str = ""
    llm_embedding_model: str = ""
    llm_embedding_dimensions: int = 1536
    ai_analysis_timeout: int = 120
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    app_package_storage_dir: str = "storage/app_packages"

    def model_post_init(self, __context: Any) -> None:
        """Resolve active provider settings."""
        provider = (self.llm_provider or "doubao").strip().lower()

        provider_map = {
            "doubao": {
                "api_key": self.doubao_api_key,
                "base_url": self.doubao_base_url,
                "chat_model": self.doubao_chat_model,
                "embedding_model": self.doubao_embedding_model,
            },
            "qwen": {
                "api_key": self.qwen_api_key,
                "base_url": self.qwen_base_url,
                "chat_model": self.qwen_chat_model,
                "embedding_model": self.qwen_embedding_model,
            },
        }

        resolved = provider_map.get(provider, provider_map["doubao"])
        self.llm_provider = provider if provider in provider_map else "doubao"
        self.llm_api_key = resolved["api_key"]
        self.llm_base_url = resolved["base_url"]
        self.llm_chat_model = resolved["chat_model"]
        self.llm_embedding_model = resolved["embedding_model"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
