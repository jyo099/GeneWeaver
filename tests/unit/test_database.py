"""
Unit tests for GeneWeaver asynchronous database infrastructure.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    close_database,
    create_database_engine,
    create_session_factory,
    get_db,
    get_engine,
    initialize_database,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# --------------------------------------------------
# Engine tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_create_database_engine():
    """Test asynchronous database engine creation."""

    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        assert engine is not None

        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))

            assert result.scalar_one() == 1

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_database_engine_empty_url():
    """Reject an empty database URL."""

    with pytest.raises(
        ValueError,
        match="Database URL cannot be empty",
    ):
        create_database_engine("")


# --------------------------------------------------
# Session factory tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_factory():
    """Test asynchronous session factory creation."""

    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            assert isinstance(session, AsyncSession)

            result = await session.execute(text("SELECT 1"))

            assert result.scalar_one() == 1

    finally:
        await engine.dispose()


# --------------------------------------------------
# Database initialization tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_database():
    """Test database initialization."""

    await initialize_database(TEST_DATABASE_URL)

    try:
        engine = get_engine()

        assert engine is not None

        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))

            assert result.scalar_one() == 1

    finally:
        await close_database()


@pytest.mark.asyncio
async def test_database_double_initialization():
    """Prevent accidental database reinitialization."""

    await initialize_database(TEST_DATABASE_URL)

    try:
        with pytest.raises(
            RuntimeError,
            match="Database is already initialized",
        ):
            await initialize_database(TEST_DATABASE_URL)

    finally:
        await close_database()


# --------------------------------------------------
# FastAPI dependency tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_get_db_dependency():
    """Test database session dependency."""

    await initialize_database(TEST_DATABASE_URL)

    try:
        database_generator = get_db()

        session = await anext(database_generator)

        try:
            assert isinstance(session, AsyncSession)

            result = await session.execute(text("SELECT 1"))

            assert result.scalar_one() == 1

        finally:
            await database_generator.aclose()

    finally:
        await close_database()


# --------------------------------------------------
# Database cleanup tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_close_database():
    """Test database connection cleanup."""

    await initialize_database(TEST_DATABASE_URL)

    await close_database()

    with pytest.raises(
        RuntimeError,
        match="Database is not initialized",
    ):
        get_engine()


@pytest.mark.asyncio
async def test_close_database_without_initialization():
    """Closing an uninitialized database should be safe."""

    await close_database()

    assert True


@pytest.mark.asyncio
async def test_get_engine_without_initialization():
    """Reject engine access before initialization."""

    with pytest.raises(
        RuntimeError,
        match="Database is not initialized",
    ):
        get_engine()


# --------------------------------------------------
# Additional Database Reliability Tests
# --------------------------------------------------


@pytest.mark.asyncio
async def test_get_db_without_initialization():
    """Reject database session access before initialization."""

    with pytest.raises(
        RuntimeError,
        match="Database session factory is not initialized",
    ):
        await anext(get_db())


@pytest.mark.asyncio
async def test_failed_initialization_does_not_publish_engine():
    """Ensure failed initialization does not publish resources."""

    invalid_url = "sqlite+aiosqlite:///invalid/path/database.db"

    with pytest.raises(OperationalError):
        await initialize_database(invalid_url)

    with pytest.raises(
        RuntimeError,
        match="Database is not initialized",
    ):
        get_engine()


@pytest.mark.asyncio
async def test_database_echo_configuration():
    """Verify SQL query logging configuration."""

    engine = create_database_engine(
        TEST_DATABASE_URL,
        echo=True,
    )

    try:
        assert engine.echo is True

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_database_session_closes_after_dependency():
    """Verify database transactions are cleaned up after dependency cleanup."""

    await initialize_database(TEST_DATABASE_URL)

    try:
        database_generator = get_db()
        session = await anext(database_generator)

        assert isinstance(session, AsyncSession)

        # Start a transaction.
        await session.execute(text("SELECT 1"))
        assert session.in_transaction()

        # Close the dependency generator.
        await database_generator.aclose()

        # The session transaction should now be cleaned up.
        assert not session.in_transaction()

    finally:
        await close_database()
