"""Database connection and session management."""
from __future__ import annotations
import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool, NullPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Check if using SQLite (for local development)
is_sqlite = settings.database_url.startswith("sqlite")

if is_sqlite:
    # SQLite configuration for async
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # PostgreSQL configuration
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def _create_celery_engine():
    """Create a short-lived engine for Celery tasks.

    Celery on Windows uses ``asyncio.run()`` which creates a **new** event loop
    on every call and closes it afterwards.  A long-lived engine with a
    connection pool (QueuePool / NullPool backed by asyncpg) keeps references
    to the *previous* loop, causing ``RuntimeError: Event loop is closed``.

    Using ``NullPool`` ensures every connection is created fresh and
    discarded after use, so there are no stale references.
    """
    if is_sqlite:
        return create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        poolclass=NullPool,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database tables (for SQLite dev mode)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from contextlib import asynccontextmanager


@asynccontextmanager
async def celery_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for Celery tasks.

    Creates a **fresh** engine (NullPool) every call so that asyncpg
    connections are never bound to a stale event loop.

    Usage inside a Celery task::

        async def _execute():
            async with celery_session() as db:
                ...
    """
    eng = _create_celery_engine()
    factory = async_sessionmaker(
        eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    # Dispose of all connections so nothing leaks to the next event loop
    await eng.dispose()
