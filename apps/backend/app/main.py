"""Main FastAPI application entry point."""
import sys
import asyncio

# Windows compatibility: use WindowsSelectorEventLoopPolicy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db, is_sqlite
from app.schemas.schemas import HealthResponse


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def create_dev_data():
    """Create development test data."""
    from app.core.database import AsyncSessionLocal
    from app.core.security import get_password_hash
    from app.domain.models import Tenant, User
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as session:
        # Check if test user exists
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        if result.scalar_one_or_none():
            logger.info("Dev user already exists")
            return
        
        # Create test tenant
        tenant = Tenant(name="Dev Tenant", status="active")
        session.add(tenant)
        await session.flush()
        
        # Create test user
        user = User(
            tenant_id=tenant.id,
            email="admin@example.com",
            name="Admin User",
            hashed_password=get_password_hash("admin123"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        logger.info("Created dev user: admin@example.com / admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting application", version=settings.app_version)
    
    # Initialize database for SQLite dev mode
    if is_sqlite:
        logger.info("SQLite mode: initializing database tables...")
        await init_db()
        await create_dev_data()
    
    yield
    logger.info("Shutting down application")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-driven Mobile Automation Testing Platform",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    # TODO: Add actual health checks for database and redis
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        database="connected",
        redis="connected",
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.api_v1_prefix}/docs",
    }
