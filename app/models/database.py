"""
GeneWeaver - Asynchronous Database Infrastructure.

Provides:
- SQLAlchemy declarative base.
- Asynchronous PostgreSQL engine.
- Asynchronous session factory.
- FastAPI database dependency.
- Database initialization and cleanup.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("geneweaver.database")


# --------------------------------------------------
# Declarative Base
# --------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all GeneWeaver database models."""


# --------------------------------------------------
# Database Resources
# --------------------------------------------------

_engine: AsyncEngine | None = None

_session_factory: async_sessionmaker[AsyncSession] | None = None


# --------------------------------------------------
# Engine Creation
# --------------------------------------------------


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
) -> AsyncEngine:
    """Create an asynchronous SQLAlchemy engine."""

    if not database_url or not database_url.strip():
        raise ValueError("Database URL cannot be empty.")

    return create_async_engine(
        database_url.strip(),
        echo=echo,
        pool_pre_ping=True,
    )


# --------------------------------------------------
# Session Factory
# --------------------------------------------------


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create an asynchronous database session factory."""

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# --------------------------------------------------
# Database Initialization
# --------------------------------------------------


async def initialize_database(
    database_url: str,
    *,
    echo: bool = False,
) -> None:
    """
    Initialize database infrastructure.

    Verify database connectivity before publishing
    the engine and session factory.
    """

    global _engine
    global _session_factory

    if _engine is not None:
        raise RuntimeError("Database is already initialized.")

    engine = create_database_engine(
        database_url,
        echo=echo,
    )

    try:
        session_factory = create_session_factory(engine)

        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    except BaseException:
        # Attempt cleanup without hiding the original error.
        try:
            await engine.dispose()
        except Exception:
            logger.exception(
                "Failed to dispose database engine after initialization failure."
            )

        raise

    # Publish resources only after successful connectivity check.
    _engine = engine
    _session_factory = session_factory

    logger.info("Database engine initialized successfully.")


# --------------------------------------------------
# Database Access
# --------------------------------------------------


def get_engine() -> AsyncEngine:
    """Return the initialized database engine."""

    if _engine is None:
        raise RuntimeError("Database is not initialized.")

    return _engine


# --------------------------------------------------
# FastAPI Database Dependency
# --------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous database session to FastAPI.

    The session is automatically closed after use.
    """

    if _session_factory is None:
        raise RuntimeError("Database session factory is not initialized.")

    async with _session_factory() as session:
        yield session


# --------------------------------------------------
# Database Shutdown
# --------------------------------------------------


async def close_database() -> None:
    """
    Dispose of database resources during application shutdown.

    Retain global references if disposal fails.
    """

    global _engine
    global _session_factory

    engine = _engine

    if engine is None:
        _session_factory = None
        return

    await engine.dispose()

    if _engine is engine:
        _engine = None
        _session_factory = None

    logger.info("Database engine disposed successfully.")
