"""SQLAlchemy 2.0 async engine, session factory, and declarative base.

Provides the async database connection for Azure PostgreSQL, replacing the
supabase-py PostgREST client for new features and migrated services.

Usage in routers::

    from app.database import get_db
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Item))
        return result.scalars().all()
"""

import logging
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection URL
# ---------------------------------------------------------------------------
# Expected format: postgresql+asyncpg://user:pass@host:port/dbname
# Falls back gracefully so the app can still start if DATABASE_URL is missing
# (existing supabase-py services remain functional).
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# ---------------------------------------------------------------------------
# Engine + Session Factory
# ---------------------------------------------------------------------------
engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None

if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=os.getenv("SQLALCHEMY_ECHO", "").lower() == "true",
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("SQLAlchemy async engine configured for Azure PostgreSQL")
else:
    logger.warning(
        "DATABASE_URL not set — SQLAlchemy features disabled. "
        "Existing supabase-py services will continue to work."
    )


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""

    pass


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for a single request.

    Commits on success, rolls back on exception, and always closes the session.
    """
    if async_session_factory is None:
        raise RuntimeError(
            "Database not configured. Set DATABASE_URL environment variable."
        )
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
