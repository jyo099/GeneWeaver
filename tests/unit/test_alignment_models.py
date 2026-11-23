"""Unit tests for GeneWeaver alignment database models."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import AlignmentJob, AlignmentResult, Base


@pytest.fixture
async def db_session():
    """Create an isolated in-memory database for each test."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


def create_alignment_job(**overrides):
    """Create a valid alignment job with optional field overrides."""

    values = {
        "guide_sequence": "GAGTCCGAGCAGAAGAAGAA",
        "pam_type": "NGG",
        "reference_genome": "GRCh38",
        "reference_dataset_version": "GRCh38.p14",
        "reference_dataset_checksum": "sha256:example-checksum",
        "algorithm_name": "geneweaver-off-target",
        "algorithm_version": "0.1.0",
        "compute_backend": "cpu",
        "parameters": {
            "max_mismatches": 3,
            "scoring_method": "hamming",
        },
    }

    values.update(overrides)
    return AlignmentJob(**values)


def create_alignment_result(**overrides):
    """Create a valid alignment result with optional field overrides."""

    values = {
        "chromosome": "chr1",
        "start_position": 100,
        "end_position": 120,
        "strand": "+",
        "target_sequence": "GAGTCCGAGCAGAAGAAGAA",
        "pam_sequence": "AGG",
        "mismatch_count": 1,
        "mismatch_positions": [5],
        "score": 0.85,
        "score_components": {
            "mismatch_penalty": 0.15,
        },
        "result_metadata": {
            "source": "unit-test",
        },
    }

    values.update(overrides)
    return AlignmentResult(**values)


@pytest.mark.asyncio
async def test_alignment_job_can_be_persisted(db_session):
    """Verify that an alignment job is persisted correctly."""

    job = create_alignment_job()

    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    assert isinstance(job.id, uuid.UUID)
    assert job.status == "pending"
    assert job.progress == 0
    assert job.guide_sequence == "GAGTCCGAGCAGAAGAAGAA"
    assert job.reference_genome == "GRCh38"
    assert job.algorithm_version == "0.1.0"
    assert job.created_at is not None
    assert job.updated_at is not None


@pytest.mark.asyncio
async def test_alignment_result_belongs_to_job(db_session):
    """Verify the one-to-many job/result relationship."""

    job = create_alignment_job()
    result = create_alignment_result()

    job.results.append(result)

    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(result)

    assert isinstance(result.id, uuid.UUID)
    assert result.job_id == job.id
    assert result.chromosome == "chr1"
    assert result.start_position == 100
    assert result.end_position == 120
    assert result.strand == "+"
    assert result.mismatch_count == 1
    assert result.mismatch_positions == [5]


@pytest.mark.asyncio
async def test_alignment_job_can_be_retrieved(db_session):
    """Verify that a stored job can be retrieved by its UUID."""

    job = create_alignment_job()

    db_session.add(job)
    await db_session.commit()

    statement = select(AlignmentJob).where(AlignmentJob.id == job.id)

    stored_job = await db_session.scalar(statement)

    assert stored_job is not None
    assert stored_job.id == job.id
    assert stored_job.reference_dataset_version == "GRCh38.p14"


@pytest.mark.asyncio
async def test_alignment_job_rejects_invalid_status(db_session):
    """Verify that unsupported job statuses are rejected."""

    job = create_alignment_job(status="unknown")

    db_session.add(job)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_alignment_job_rejects_invalid_progress(db_session):
    """Verify that progress must remain between zero and one hundred."""

    job = create_alignment_job(progress=101)

    db_session.add(job)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_alignment_result_rejects_invalid_coordinates(db_session):
    """Verify that genomic intervals must have a valid coordinate range."""

    job = create_alignment_job()
    db_session.add(job)
    await db_session.flush()

    result = create_alignment_result(
        job_id=job.id,
        start_position=200,
        end_position=100,
    )

    db_session.add(result)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_alignment_result_rejects_invalid_strand(db_session):
    """Verify that only positive and negative strands are accepted."""

    job = create_alignment_job()
    db_session.add(job)
    await db_session.flush()

    result = create_alignment_result(
        job_id=job.id,
        strand="?",
    )

    db_session.add(result)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_alignment_result_rejects_negative_mismatch_count(db_session):
    """Verify that mismatch counts cannot be negative."""

    job = create_alignment_job()
    db_session.add(job)
    await db_session.flush()

    result = create_alignment_result(
        job_id=job.id,
        mismatch_count=-1,
    )

    db_session.add(result)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_deleting_job_deletes_its_results(db_session):
    """Verify that deleting a job also deletes its child results."""

    job = create_alignment_job()
    job.results.append(create_alignment_result())
    job.results.append(
        create_alignment_result(
            chromosome="chr2",
            start_position=300,
            end_position=320,
        )
    )

    db_session.add(job)
    await db_session.commit()

    job_id = job.id

    await db_session.delete(job)
    await db_session.commit()

    remaining_results = await db_session.scalars(
        select(AlignmentResult).where(AlignmentResult.job_id == job_id)
    )

    assert list(remaining_results) == []
