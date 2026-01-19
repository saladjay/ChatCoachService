"""SQLAlchemy async session configuration.

This module provides:
- Async engine creation
- Async session factory
- Session dependency for FastAPI
- Database initialization utilities
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.db.models import Base


# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
    future=True,
)

# Create async session factory
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.
    
    Yields:
        AsyncSession: An async SQLAlchemy session.
        
    Example:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for getting a database session outside of FastAPI.
    
    Useful for background tasks or testing.
    
    Example:
        async with get_session_context() as session:
            result = await session.execute(select(Item))
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize the database by creating all tables.
    
    Should be called during application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close the database engine.
    
    Should be called during application shutdown.
    """
    await engine.dispose()
