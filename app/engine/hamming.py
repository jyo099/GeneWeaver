
"""Vectorized Hamming distance engine for GeneWeaver."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.engine.device_manager import DeviceManager


# Standard DNA IUPAC nucleotide symbols.
VALID_DNA_SYMBOLS = frozenset(
    "ACGTRYSWKMBDHVN"
)

DNA_NORMALIZATION = str.maketrans({
    "U": "T",
})


class HammingDistanceError(ValueError):
    """Base exception for Hamming distance validation errors."""


class InvalidSequenceError(HammingDistanceError):
    """Raised when a sequence contains invalid DNA symbols."""


class SequenceLengthMismatchError(HammingDistanceError):
    """Raised when sequences have different lengths."""


class HammingDistanceEngine:
    """
    Calculate Hamming distances using CPU or GPU vectorization.

    The supplied DeviceManager determines whether NumPy or CuPy
    performs the calculations.

    Ambiguous IUPAC symbols are compared literally.
    U is normalized to T before comparison.
    """

    def __init__(
        self,
        device_manager: DeviceManager | None = None,
    ) -> None:
        self.device_manager = (
            device_manager
            if device_manager is not None
            else DeviceManager(backend="auto")
        )

        self._xp = self.device_manager.array_module

    @staticmethod
    def normalize_sequence(sequence: str) -> str:
        """
        Normalize and validate a DNA sequence.

        Normalization:
        - Convert lowercase to uppercase.
        - Convert U to T.
        - Preserve valid IUPAC DNA ambiguity symbols.

        Whitespace is not silently removed.
        """

        if not isinstance(sequence, str):
            raise InvalidSequenceError(
                "DNA sequence must be a string."
            )

        normalized = sequence.upper().translate(
            DNA_NORMALIZATION
        )

        for position, symbol in enumerate(normalized):
            if symbol not in VALID_DNA_SYMBOLS:
                raise InvalidSequenceError(
                    f"Invalid DNA symbol '{symbol}' "
                    f"at position {position}."
                )

        return normalized

    @staticmethod
    def _validate_equal_lengths(
        first: str,
        second: str,
    ) -> None:
        """Ensure two sequences have identical lengths."""

        if len(first) != len(second):
            raise SequenceLengthMismatchError(
                "Hamming distance requires sequences of equal "
                f"length. Received {len(first)} and "
                f"{len(second)}."
            )

    def compute(
        self,
        sequence_a: str,
        sequence_b: str,
    ) -> int:
        """
        Calculate Hamming distance between two DNA sequences.

        Returns
        -------
        int
            Number of positions containing different symbols.
        """

        first = self.normalize_sequence(sequence_a)
        second = self.normalize_sequence(sequence_b)

        self._validate_equal_lengths(first, second)

        if not first:
            return 0

        # Convert ASCII nucleotide symbols to numerical arrays.
        first_array = np.frombuffer(
            first.encode("ascii"),
            dtype=np.uint8,
        )

        second_array = np.frombuffer(
            second.encode("ascii"),
            dtype=np.uint8,
        )

        # Transfer arrays to the selected compute backend.
        first_array = self._xp.asarray(first_array)
        second_array = self._xp.asarray(second_array)

        # Vectorized element-wise comparison.
        mismatch_count = self._xp.count_nonzero(
            first_array != second_array
        )

        self.device_manager.synchronize()

        return int(mismatch_count.item())

    def compute_batch(
        self,
        query: str,
        targets: Sequence[str],
    ) -> list[int]:
        """
        Calculate distances between one query and many targets.

        All target sequences must have the same length as the query.

        Returns
        -------
        list[int]
            Hamming distances in the original target order.
        """

        normalized_query = self.normalize_sequence(query)

        if isinstance(targets, (str, bytes)):
            raise InvalidSequenceError(
                "Targets must be a sequence of DNA strings, "
                "not a single string."
            )

        normalized_targets = [
            self.normalize_sequence(target)
            for target in targets
        ]

        if not normalized_targets:
            return []

        query_length = len(normalized_query)

        for index, target in enumerate(normalized_targets):
            if len(target) != query_length:
                raise SequenceLengthMismatchError(
                    f"Target at index {index} has length "
                    f"{len(target)}; expected {query_length}."
                )

        if query_length == 0:
            return [0] * len(normalized_targets)

        # Encode the query once.
        query_array = np.frombuffer(
            normalized_query.encode("ascii"),
            dtype=np.uint8,
        )

        # Build a contiguous matrix of target sequences.
        target_matrix = np.frombuffer(
            b"".join(
                target.encode("ascii")
                for target in normalized_targets
            ),
            dtype=np.uint8,
        ).reshape(
            len(normalized_targets),
            query_length,
        )

        # Move data to CPU or GPU backend.
        query_array = self._xp.asarray(query_array)
        target_matrix = self._xp.asarray(target_matrix)

        # Broadcast query across all target rows.
        mismatch_matrix = (
            target_matrix != query_array[None, :]
        )

        # Count mismatches independently for each target.
        distances = self._xp.count_nonzero(
            mismatch_matrix,
            axis=1,
        )

        self.device_manager.synchronize()

        # Convert backend result to ordinary Python integers.
        if hasattr(distances, "get"):
            distances = distances.get()

        return [int(value) for value in distances.tolist()]


def hamming_distance(
    sequence_a: str,
    sequence_b: str,
    device_manager: DeviceManager | None = None,
) -> int:
    """Convenience function for calculating one distance."""

    engine = HammingDistanceEngine(device_manager)

    return engine.compute(sequence_a, sequence_b)


def batch_hamming_distance(
    query: str,
    targets: Sequence[str],
    device_manager: DeviceManager | None = None,
) -> list[int]:
    """Convenience function for calculating multiple distances."""

    engine = HammingDistanceEngine(device_manager)

    return engine.compute_batch(query, targets)
