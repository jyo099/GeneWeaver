
"""Unit tests for GeneWeaver Hamming distance engine."""

import numpy as np
import pytest

from app.engine.device_manager import DeviceManager

from app.engine.hamming import (
    HammingDistanceEngine,
    InvalidSequenceError,
    SequenceLengthMismatchError,
    hamming_distance,
    batch_hamming_distance,
)


@pytest.fixture
def engine():
    """Create a CPU-backed Hamming distance engine."""

    manager = DeviceManager(backend="cpu")

    return HammingDistanceEngine(
        device_manager=manager
    )


def test_identical_sequences(engine):
    assert engine.compute(
        "ATGC",
        "ATGC",
    ) == 0


def test_single_mismatch(engine):
    assert engine.compute(
        "ATGC",
        "ATGA",
    ) == 1


def test_multiple_mismatches(engine):
    assert engine.compute(
        "ATGCAG",
        "ATACTG",
    ) == 2


def test_case_insensitive_comparison(engine):
    assert engine.compute(
        "atgc",
        "ATGC",
    ) == 0


def test_rna_uracil_normalized_to_thymine(engine):
    assert engine.compute(
        "AUGC",
        "ATGC",
    ) == 0


def test_ambiguous_symbols_are_compared_literally(engine):
    assert engine.compute(
        "ARN",
        "AGN",
    ) == 1


def test_empty_sequences(engine):
    assert engine.compute("", "") == 0


def test_unequal_sequence_lengths(engine):
    with pytest.raises(SequenceLengthMismatchError):
        engine.compute(
            "ATGC",
            "ATG",
        )


@pytest.mark.parametrize(
    "sequence",
    [
        "ATGX",
        "ATG1",
        "ATG-",
        "ATG ",
        "ATG*",
    ],
)
def test_invalid_dna_symbols(engine, sequence):
    with pytest.raises(InvalidSequenceError):
        engine.compute(
            sequence,
            sequence,
        )


def test_non_string_sequence(engine):
    with pytest.raises(InvalidSequenceError):
        engine.compute(
            "ATGC",
            None,
        )


def test_batch_hamming_distance(engine):
    query = "ATGC"

    targets = [
        "ATGC",
        "ATGA",
        "ATAA",
        "TTTT",
    ]

    result = engine.compute_batch(
        query,
        targets,
    )

    assert result == [0, 1, 2, 3]


def test_batch_with_empty_targets(engine):
    assert engine.compute_batch(
        "ATGC",
        [],
    ) == []


def test_batch_with_empty_sequences(engine):
    assert engine.compute_batch(
        "",
        ["", "", ""],
    ) == [0, 0, 0]


def test_batch_length_mismatch(engine):
    with pytest.raises(SequenceLengthMismatchError):
        engine.compute_batch(
            "ATGC",
            ["ATGC", "ATG"],
        )


def test_batch_invalid_target(engine):
    with pytest.raises(InvalidSequenceError):
        engine.compute_batch(
            "ATGC",
            ["ATGC", "ATGX"],
        )


def test_batch_rejects_single_string_as_targets(engine):
    with pytest.raises(InvalidSequenceError):
        engine.compute_batch(
            "ATGC",
            "ATGC",
        )


def test_convenience_function():
    assert hamming_distance(
        "ATGC",
        "ATGA",
        DeviceManager(backend="cpu"),
    ) == 1


def test_batch_convenience_function():
    result = batch_hamming_distance(
        "ATGC",
        ["ATGC", "ATGA", "TTTT"],
        DeviceManager(backend="cpu"),
    )

    assert result == [0, 1, 3]


def test_backend_array_module(engine):
    assert engine._xp is np


def test_large_batch(engine):
    query = "A" * 100

    targets = [
        "A" * 100,
        "C" + "A" * 99,
        "C" * 100,
        "A" * 99 + "G",
    ]

    assert engine.compute_batch(
        query,
        targets,
    ) == [0, 1, 100, 1]


def test_ambiguous_symbols_are_valid(engine):
    assert engine.compute(
        "ACGTRYSWKMBDHVN",
        "ACGTRYSWKMBDHVN",
    ) == 0
