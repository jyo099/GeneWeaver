
"""Unit tests for GeneWeaver off-target scoring engine."""

import pytest

from app.engine.device_manager import DeviceManager

from app.engine.hamming import (
    InvalidSequenceError,
    SequenceLengthMismatchError,
)

from app.engine.off_target import (
    OffTargetScoringEngine,
    InvalidScoringConfigurationError,
    score_off_target,
    batch_score_off_targets,
)


@pytest.fixture
def engine():
    """Create a CPU-backed off-target scoring engine."""

    return OffTargetScoringEngine(
        device_manager=DeviceManager(backend="cpu"),
    )


def test_exact_match(engine):
    result = engine.score("ATGC", "ATGC")

    assert result.mismatch_count == 0
    assert result.sequence_length == 4
    assert result.similarity_percent == 100.0
    assert result.mismatch_positions == ()
    assert result.is_candidate is None


def test_single_mismatch(engine):
    result = engine.score("ATGC", "ATGA")

    assert result.mismatch_count == 1
    assert result.similarity_percent == 75.0
    assert result.mismatch_positions == (3,)


def test_multiple_mismatches(engine):
    result = engine.score("ATGCAG", "ATACTG")

    assert result.mismatch_count == 2
    assert result.similarity_percent == pytest.approx(66.67, abs=0.01)
    assert result.mismatch_positions == (2, 4)


def test_case_insensitive_scoring(engine):
    result = engine.score("atgc", "ATGC")

    assert result.mismatch_count == 0
    assert result.similarity_percent == 100.0


def test_uracil_normalized_to_thymine(engine):
    result = engine.score("AUGC", "ATGC")

    assert result.mismatch_count == 0
    assert result.target_sequence == "ATGC"


def test_candidate_within_threshold():
    engine = OffTargetScoringEngine(
        device_manager=DeviceManager(backend="cpu"),
        max_mismatches=2,
    )

    result = engine.score("ATGC", "ATGA")

    assert result.mismatch_count == 1
    assert result.is_candidate is True


def test_candidate_outside_threshold():
    engine = OffTargetScoringEngine(
        device_manager=DeviceManager(backend="cpu"),
        max_mismatches=1,
    )

    result = engine.score("ATGC", "TTTT")

    assert result.mismatch_count == 3
    assert result.is_candidate is False


def test_zero_mismatch_threshold():
    engine = OffTargetScoringEngine(
        device_manager=DeviceManager(backend="cpu"),
        max_mismatches=0,
    )

    exact_match = engine.score("ATGC", "ATGC")
    mismatch = engine.score("ATGC", "ATGA")

    assert exact_match.is_candidate is True
    assert mismatch.is_candidate is False


def test_candidate_classification_disabled(engine):
    result = engine.score("ATGC", "ATGA")

    assert result.is_candidate is None
    assert result.max_mismatches is None


def test_batch_scoring(engine):
    results = engine.score_batch(
        "ATGC",
        [
            "ATGC",
            "ATGA",
            "ATAA",
            "TTTT",
        ],
    )

    assert [result.mismatch_count for result in results] == [
        0, 1, 2, 3
    ]

    assert [
        result.similarity_percent for result in results
    ] == [
        100.0, 75.0, 50.0, 25.0
    ]


def test_batch_preserves_target_order(engine):
    targets = ["TTTT", "ATGC", "ATGA"]

    results = engine.score_batch("ATGC", targets)

    assert [
        result.target_sequence for result in results
    ] == targets


def test_batch_candidate_classification():
    engine = OffTargetScoringEngine(
        device_manager=DeviceManager(backend="cpu"),
        max_mismatches=1,
    )

    results = engine.score_batch(
        "ATGC",
        ["ATGC", "ATGA", "TTTT"],
    )

    assert [result.is_candidate for result in results] == [
        True, True, False
    ]


def test_empty_batch(engine):
    assert engine.score_batch("ATGC", []) == []


def test_empty_query_rejected(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score("", "ATGC")


def test_empty_target_rejected(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score("ATGC", "")


def test_invalid_query_rejected(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score("ATGX", "ATGC")


def test_invalid_target_rejected(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score("ATGC", "ATGX")


def test_unequal_lengths_rejected(engine):
    with pytest.raises(SequenceLengthMismatchError):
        engine.score("ATGC", "ATG")


def test_batch_unequal_lengths_rejected(engine):
    with pytest.raises(SequenceLengthMismatchError):
        engine.score_batch(
            "ATGC",
            ["ATGC", "ATG"],
        )


def test_batch_invalid_target_rejected(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score_batch(
            "ATGC",
            ["ATGC", "ATGX"],
        )


def test_batch_rejects_single_string(engine):
    with pytest.raises(InvalidSequenceError):
        engine.score_batch("ATGC", "ATGC")


@pytest.mark.parametrize(
    "threshold",
    [-1, 1.5, True, "2"],
)
def test_invalid_mismatch_threshold(threshold):
    with pytest.raises(InvalidScoringConfigurationError):
        OffTargetScoringEngine(
            device_manager=DeviceManager(backend="cpu"),
            max_mismatches=threshold,
        )


def test_mismatch_rate(engine):
    result = engine.score("ATGC", "ATGA")

    assert result.mismatch_rate == pytest.approx(0.25)


def test_single_scoring_convenience_function():
    result = score_off_target(
        "ATGC",
        "ATGA",
        max_mismatches=1,
        device_manager=DeviceManager(backend="cpu"),
    )

    assert result.mismatch_count == 1
    assert result.is_candidate is True


def test_batch_scoring_convenience_function():
    results = batch_score_off_targets(
        "ATGC",
        ["ATGC", "ATGA", "TTTT"],
        max_mismatches=1,
        device_manager=DeviceManager(backend="cpu"),
    )

    assert [result.mismatch_count for result in results] == [
        0, 1, 3
    ]


def test_ambiguous_symbols_are_compared_literally(engine):
    result = engine.score("ARN", "AGN")

    assert result.mismatch_count == 1
    assert result.mismatch_positions == (1,)


def test_result_contains_normalized_target(engine):
    result = engine.score("AUGC", "atgc")

    assert result.target_sequence == "ATGC"
