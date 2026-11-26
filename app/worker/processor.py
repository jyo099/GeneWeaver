"""Scientific alignment processor interface for background jobs."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alignment import AlignmentJob


class AlignmentProcessorError(RuntimeError):
    """Base exception for alignment processor failures."""


class AlignmentProcessorUnavailableError(AlignmentProcessorError):
    """Raised when no genome-wide alignment processor is configured."""


class AlignmentProcessor(Protocol):
    """Interface implemented by a scientific alignment processor."""

    async def process(
        self,
        job: AlignmentJob,
        session: AsyncSession,
    ) -> None:
        """
        Execute an alignment job.

        Implementations must persist scientifically validated results
        using the supplied database session.

        The worker marks the job completed only after this method returns
        successfully.
        """


class UnavailableAlignmentProcessor:
    """
    Safe default processor.

    The current GeneWeaver engine provides sequence-based off-target
    comparison, but does not yet provide reference-genome searching.
    This processor prevents unsupported jobs from being marked completed.
    """

    async def process(
        self,
        job: AlignmentJob,
        session: AsyncSession,
    ) -> None:
        """Reject jobs until a real genome-wide processor is available."""

        raise AlignmentProcessorUnavailableError(
            "Genome-wide alignment is not available yet. "
            "GeneWeaver currently provides sequence-based off-target "
            "scoring, but a reference-genome alignment processor has "
            "not been configured. No alignment results were generated."
        )


def get_alignment_processor() -> AlignmentProcessor:
    """Return the configured alignment processor."""

    return UnavailableAlignmentProcessor()
