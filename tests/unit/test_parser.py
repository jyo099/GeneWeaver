"""Unit tests for GeneWeaver sequence parser."""

from io import StringIO

import pytest

from app.engine.parser import (
    EmptySequenceError,
    InvalidNucleotideError,
    SequenceParseError,
    SequenceTooLongError,
    UnsupportedSequenceFormatError,
    detect_format,
    parse_sequences,
    validate_sequence,
)


def test_parse_single_fasta(tmp_path):
    """Test parsing one FASTA record."""

    fasta = tmp_path / "sample.fasta"

    fasta.write_text(
        ">gene_001 Human reference\nATGCGTACGT\n",
        encoding="utf-8",
    )

    records = list(parse_sequences(fasta))

    assert len(records) == 1
    assert records[0].sequence_id == "gene_001"
    assert records[0].sequence == "ATGCGTACGT"
    assert records[0].molecule_type == "DNA"
    assert records[0].file_format == "fasta"


def test_parse_multiple_fasta_records(tmp_path):
    """Test reading multiple FASTA records."""

    fasta = tmp_path / "multiple.fa"

    fasta.write_text(
        ">gene_001\nATGC\n>gene_002\nGCTA\n",
        encoding="utf-8",
    )

    records = list(parse_sequences(fasta))

    assert len(records) == 2
    assert records[0].sequence == "ATGC"
    assert records[1].sequence == "GCTA"


def test_parse_fastq_and_quality_scores(tmp_path):
    """Test FASTQ sequence and quality extraction."""

    fastq = tmp_path / "reads.fastq"

    fastq.write_text(
        "@read_001 sample\nATGCGT\n+\nIIIIII\n",
        encoding="utf-8",
    )

    records = list(parse_sequences(fastq))

    assert len(records) == 1
    assert records[0].sequence == "ATGCGT"
    assert records[0].quality_scores == (40, 40, 40, 40, 40, 40)


def test_detect_fasta_format():
    assert detect_format("reference.fasta") == "fasta"
    assert detect_format("reference.fna") == "fasta"


def test_detect_fastq_format():
    assert detect_format("reads.fastq") == "fastq"
    assert detect_format("reads.fq") == "fastq"


def test_unsupported_file_extension():
    with pytest.raises(UnsupportedSequenceFormatError):
        detect_format("sequence.txt")


def test_invalid_dna_sequence():
    with pytest.raises(InvalidNucleotideError):
        validate_sequence("ATGX123", "DNA")


def test_invalid_rna_sequence():
    with pytest.raises(InvalidNucleotideError):
        validate_sequence("AUGTX", "RNA")


def test_empty_sequence():
    with pytest.raises(EmptySequenceError):
        validate_sequence("", "DNA")


def test_sequence_length_limit():
    with pytest.raises(SequenceTooLongError):
        validate_sequence(
            "ATGCGT",
            "DNA",
            max_sequence_length=4,
        )


def test_valid_iupac_dna_sequence():
    sequence = validate_sequence(
        "ACGTRYSWKMBDHVN",
        "DNA",
    )

    assert sequence == "ACGTRYSWKMBDHVN"


def test_valid_rna_sequence():
    sequence = validate_sequence(
        "AUGCRYSWKMBDHVN",
        "RNA",
    )

    assert sequence == "AUGCRYSWKMBDHVN"


def test_empty_fasta_file(tmp_path):
    """Reject files without sequence records."""

    fasta = tmp_path / "empty.fasta"
    fasta.write_text("", encoding="utf-8")

    with pytest.raises(SequenceParseError):
        list(parse_sequences(fasta))


def test_file_like_stream():
    """Test parsing an already-open text stream."""

    content = StringIO(">gene_001\nATGC\n")

    records = list(
        parse_sequences(
            content,
            file_format="fasta",
        )
    )

    assert records[0].sequence == "ATGC"
    assert not content.closed


def test_file_like_requires_explicit_format():
    """Require an explicit format for text streams."""

    content = StringIO(">gene_001\nATGC\n")

    with pytest.raises(UnsupportedSequenceFormatError):
        list(parse_sequences(content))


def test_missing_file():
    """Reject nonexistent sequence files."""

    with pytest.raises(FileNotFoundError):
        list(parse_sequences("missing_genome.fasta"))
