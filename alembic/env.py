"""
GeneWeaver Alembic migration environment.

Supports asynchronous database connections and offline SQL generation.
Uses the existing application settings and SQLAlchemy metadata.
"""

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.models import Base

# Alembic Config object.
config = context.config

# Configure Python logging when an ini file is available.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing Base through app.models registers the alignment models
# in its metadata through the package exports.
target_metadata = Base.metadata


def get_database_url() -> str:
    """Return the configured database URL."""

    configured_url = config.get_main_option("sqlalchemy.url")

    if configured_url:
        return configured_url

    return get_settings().database_url


def run_migrations_offline() -> None:
    """Generate SQL migration statements without connecting to a database."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Run migrations using an established database connection."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an asynchronous engine and execute migrations."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""

    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
