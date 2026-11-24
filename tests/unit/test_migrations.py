"""Tests for GeneWeaver Alembic database migrations."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from alembic import command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def create_alembic_config(database_path: Path) -> Config:
    """Create an Alembic configuration for an isolated test database."""

    config = Config(str(ALEMBIC_INI))

    config.set_main_option(
        "script_location",
        str(PROJECT_ROOT / "alembic"),
    )

    database_url = URL.create(
        drivername="sqlite+aiosqlite",
        database=str(database_path),
    )

    config.set_main_option(
        "sqlalchemy.url",
        str(database_url).replace("%", "%%"),
    )

    return config


@pytest.fixture
def migration_database(tmp_path: Path):
    """Provide an isolated SQLite database and Alembic configuration."""

    database_path = tmp_path / "geneweaver_migrations.db"
    config = create_alembic_config(database_path)

    yield config, database_path


def test_upgrade_creates_alignment_tables(migration_database):
    """Verify that upgrading to head creates the expected schema."""

    config, database_path = migration_database

    command.upgrade(config, "head")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        assert "alignment_jobs" in tables
        assert "alignment_results" in tables

        job_columns = {
            column["name"] for column in inspector.get_columns("alignment_jobs")
        }

        assert "guide_sequence" in job_columns
        assert "reference_genome" in job_columns
        assert "algorithm_version" in job_columns
        assert "status" in job_columns

        result_columns = {
            column["name"] for column in inspector.get_columns("alignment_results")
        }

        assert "job_id" in result_columns
        assert "chromosome" in result_columns
        assert "start_position" in result_columns
        assert "mismatch_count" in result_columns

    finally:
        engine.dispose()


def test_upgrade_creates_expected_indexes(migration_database):
    """Verify that important query indexes are created."""

    config, database_path = migration_database

    command.upgrade(config, "head")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    try:
        inspector = inspect(engine)

        job_indexes = {
            index["name"] for index in inspector.get_indexes("alignment_jobs")
        }

        result_indexes = {
            index["name"] for index in inspector.get_indexes("alignment_results")
        }

        assert "ix_alignment_jobs_status_created_at" in job_indexes
        assert "ix_alignment_jobs_reference_genome" in job_indexes

        assert "ix_alignment_results_job_id" in result_indexes
        assert "ix_alignment_results_chromosome_position" in result_indexes
        assert "ix_alignment_results_mismatch_count" in result_indexes

    finally:
        engine.dispose()


def test_upgrade_creates_cascade_foreign_key(migration_database):
    """Verify that alignment results reference their parent job."""

    config, database_path = migration_database

    command.upgrade(config, "head")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    try:
        inspector = inspect(engine)
        foreign_keys = inspector.get_foreign_keys("alignment_results")

        job_foreign_key = next(
            foreign_key
            for foreign_key in foreign_keys
            if foreign_key["constrained_columns"] == ["job_id"]
        )

        assert job_foreign_key["referred_table"] == "alignment_jobs"
        assert job_foreign_key["referred_columns"] == ["id"]
        assert job_foreign_key["options"]["ondelete"] == "CASCADE"

    finally:
        engine.dispose()


def test_downgrade_removes_alignment_tables(migration_database):
    """Verify that downgrading to base removes the application schema."""

    config, database_path = migration_database

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        assert "alignment_jobs" not in tables
        assert "alignment_results" not in tables

        # Alembic retains its version table after downgrade.
        assert "alembic_version" in tables

        with engine.connect() as connection:
            version_rows = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchall()

            assert version_rows == []

    finally:
        engine.dispose()


def test_upgrade_is_idempotent(migration_database):
    """Verify that upgrading an already upgraded database is safe."""

    config, database_path = migration_database

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
    )

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        assert "alignment_jobs" in tables
        assert "alignment_results" in tables

    finally:
        engine.dispose()
