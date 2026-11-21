
"""Interpretable sequence-based off-target scoring for GeneWeaver."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.engine.device_manager import DeviceManager
from app.engine.hamming import (
    HammingDistanceEngine,
    InvalidSequenceError,
    SequenceLengthMismatchError,
)


class OffTargetScoringError(ValueError):
    """Base exception for off-target scoring errors."""


class InvalidScoringConfigurationError(OffTargetScoringError):
    """Raised when scoring configuration is invalid."""


@dataclass(frozen=True, slots=True)
class OffTargetResult:
    """
    Sequence-based off-target comparison result.

    similarity_percent is a sequence similarity metric, not a
    probability of biological editing activity.

    mismatch_positions are zero-based positions in the normalized
    query and target sequences.
    """

    target_sequence: str
    mismatch_count: int
    sequence_length: int
    similarity_percent: float
    mismatch_positions: tuple[int, ...]
    max_mismatches: int | None
    is_candidate: bool | None

    @property
    def mismatch_rate(self) -> float:
        """Return the fraction of positions that differ."""

        if self.sequence_length == 0:
            return 0.0

        return self.mismatch_count / self.sequence_length


class OffTargetScoringEngine:
    """
    Score potential off-target sequences using exact-symbol Hamming
    distance.

    Candidate classification is optional. When max_mismatches is
    provided, targets within that mismatch threshold are marked
    as candidates.

    This baseline engine does not model PAM compatibility, strand,
    bulges, mismatch-position weights, or biological editing
    probabilities.
    """

    def __init__(
        self,
        device_manager: DeviceManager | None = None,
        max_mismatches: int | None = None,
    ) -> None:
        if max_mismatches is not None:
            if (
                isinstance(max_mismatches, bool)
                or not isinstance(max_mismatches, int)
                or max_mismatches < 0
            ):
                raise InvalidScoringConfigurationError(
                    "max_mismatches must be a non-negative integer "
                    "or None."
                )

        self.max_mismatches = max_mismatches

        self._hamming_engine = HammingDistanceEngine(
            device_manager=device_manager
        )

    @staticmethod
    def _validate_non_empty_sequence(
        sequence: str,
        field_name: str,
    ) -> str:
        """Normalize and validate a non-empty DNA sequence."""

        normalized = HammingDistanceEngine.normalize_sequence(
            sequence
        )

        if not normalized:
            raise InvalidSequenceError(
                f"{field_name} cannot be empty."
            )

        return normalized

    @staticmethod
    def _get_mismatch_positions(
        query: str,
        target: str,
    ) -> tuple[int, ...]:
        """Return zero-based positions containing mismatches."""

        return tuple(
            index
            for index, (query_base, target_base)
            in enumerate(zip(query, target))
            if query_base != target_base
        )

    def score(
        self,
        query: str,
        target: str,
    ) -> OffTargetResult:
        """Score one target sequence against a query sequence."""

        normalized_query = self._validate_non_empty_sequence(
            query,
            "Query sequence",
        )

        normalized_target = self._validate_non_empty_sequence(
            target,
            "Target sequence",
        )

        if len(normalized_query) != len(normalized_target):
            raise SequenceLengthMismatchError(
                "Off-target scoring requires equal-length "
                f"sequences. Received {len(normalized_query)} "
                f"and {len(normalized_target)}."
            )

        mismatch_count = self._hamming_engine.compute(
            normalized_query,
            normalized_target,
        )

        mismatch_positions = self._get_mismatch_positions(
            normalized_query,
            normalized_target,
        )

        sequence_length = len(normalized_query)

        similarity_percent = (
            (sequence_length - mismatch_count)
            / sequence_length
        ) * 100.0

        is_candidate = (
            mismatch_count <= self.max_mismatches
            if self.max_mismatches is not None
            else None
        )

        return OffTargetResult(
            target_sequence=normalized_target,
            mismatch_count=mismatch_count,
            sequence_length=sequence_length,
            similarity_percent=round(
                similarity_percent,
                2,
            ),
            mismatch_positions=mismatch_positions,
            max_mismatches=self.max_mismatches,
            is_candidate=is_candidate,
        )

    def score_batch(
        self,
        query: str,
        targets: Sequence[str],
    ) -> list[OffTargetResult]:
        """
        Score multiple target sequences against one query.

        Results retain the same order as the supplied targets.
        """

        normalized_query = self._validate_non_empty_sequence(
            query,
            "Query sequence",
        )

        if isinstance(targets, (str, bytes)):
            raise InvalidSequenceError(
                "Targets must be a collection of DNA strings, "
                "not a single string."
            )

        normalized_targets = [
            self._validate_non_empty_sequence(
                target,
                f"Target at index {index}",
            )
            for index, target in enumerate(targets)
        ]

        if not normalized_targets:
            return []

        # Validate lengths before performing batch computation.
        for index, target in enumerate(normalized_targets):
            if len(target) != len(normalized_query):
                raise SequenceLengthMismatchError(
                    f"Target at index {index} has length "
                    f"{len(target)}; expected "
                    f"{len(normalized_query)}."
                )

        mismatch_counts = self._hamming_engine.compute_batch(
            normalized_query,
            normalized_targets,
        )

        results: list[OffTargetResult] = []

        for target, mismatch_count in zip(
            normalized_targets,
            mismatch_counts,
        ):
            mismatch_positions = self._get_mismatch_positions(
                normalized_query,
                target,
            )

            sequence_length = len(normalized_query)

            similarity_percent = (
                (sequence_length - mismatch_count)
                / sequence_length
            ) * 100.0

            is_candidate = (
                mismatch_count <= self.max_mismatches
                if self.max_mismatches is not None
                else None
            )

            results.append(
                OffTargetResult(
                    target_sequence=target,
                    mismatch_count=mismatch_count,
                    sequence_length=sequence_length,
                    similarity_percent=round(
                        similarity_percent,
                        2,
                    ),
                    mismatch_positions=mismatch_positions,
                    max_mismatches=self.max_mismatches,
                    is_candidate=is_candidate,
                )
            )

        return results


def score_off_target(
    query: str,
    target: str,
    max_mismatches: int | None = None,
    device_manager: DeviceManager | None = None,
) -> OffTargetResult:
    """Convenience function for scoring one target."""

    engine = OffTargetScoringEngine(
        device_manager=device_manager,
        max_mismatches=max_mismatches,
    )

    return engine.score(query, target)


def batch_score_off_targets(
    query: str,
    targets: Sequence[str],
    max_mismatches: int | None = None,
    device_manager: DeviceManager | None = None,
) -> list[OffTargetResult]:
    """Convenience function for scoring multiple targets."""

    engine = OffTargetScoringEngine(
        device_manager=device_manager,
        max_mismatches=max_mismatches,
    )

    return engine.score_batch(query, targets)
