"""
GeneWeaver - Genomic Sequence Parser.

Supports FASTA and FASTQ sequence ingestion,
nucleotide validation, and quality score extraction.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal

from Bio import SeqIO

SequenceFormat = Literal["fasta", "fastq"]
MoleculeType = Literal["DNA", "RNA"]

DNA_ALPHABET = set("ACGTRYSWKMBDHVN")
RNA_ALPHABET = set("ACGURYSWKMBDHVN")

FORMAT_EXTENSIONS = {
    ".fa": "fasta",
    ".fasta": "fasta",
    ".fna": "fasta",
    ".fq": "fastq",
    ".fastq": "fastq",
}


class SequenceParseError(Exception):
    """Base exception for sequence parsing errors."""


class UnsupportedSequenceFormatError(SequenceParseError):
    """Raised when the input format is unsupported."""


class InvalidNucleotideError(SequenceParseError):
    """Raised when a sequence contains invalid nucleotides."""


class EmptySequenceError(SequenceParseError):
    """Raised when a sequence is empty."""


class SequenceTooLongError(SequenceParseError):
    """Raised when a sequence exceeds the configured limit."""


@dataclass(frozen=True, slots=True)
class ParsedSequence:
    """Structured representation of a genomic sequence."""

    sequence_id: str
    description: str
    sequence: str
    molecule_type: MoleculeType
    file_format: SequenceFormat
    quality_scores: tuple[int, ...] | None = None

    @property
    def length(self) -> int:
        """Return nucleotide sequence length."""
        return len(self.sequence)


def detect_format(file_path: str | Path) -> SequenceFormat:
    """Detect FASTA or FASTQ format using file extension."""

    extension = Path(file_path).suffix.lower()

    detected = FORMAT_EXTENSIONS.get(extension)

    if detected is None:
        raise UnsupportedSequenceFormatError(
            f"Unsupported sequence file extension: {extension}"
        )

    return detected  # type: ignore[return-value]


def validate_sequence(
    sequence: str,
    molecule_type: MoleculeType,
    max_sequence_length: int = 10_000_000,
) -> str:
    """
    Validate and normalize a DNA or RNA sequence.

    Returns an uppercase sequence.
    """

    normalized = sequence.upper()

    if not normalized:
        raise EmptySequenceError("Sequence cannot be empty.")

    if len(normalized) > max_sequence_length:
        raise SequenceTooLongError(
            f"Sequence length {len(normalized)} exceeds "
            f"the maximum allowed length {max_sequence_length}."
        )

    allowed_bases = DNA_ALPHABET if molecule_type == "DNA" else RNA_ALPHABET

    invalid_bases = sorted(set(normalized) - allowed_bases)

    if invalid_bases:
        raise InvalidNucleotideError(
            f"Invalid {molecule_type} nucleotide symbols: "
            f"{', '.join(invalid_bases)}"
        )

    return normalized


def _parse_handle(
    handle: IO[str],
    file_format: SequenceFormat,
    molecule_type: MoleculeType,
    max_sequence_length: int,
) -> Iterator[ParsedSequence]:
    """Parse a text stream incrementally."""

    record_count = 0

    try:
        for record in SeqIO.parse(handle, file_format):

            sequence = validate_sequence(
                str(record.seq),
                molecule_type,
                max_sequence_length,
            )

            quality_scores = None

            if file_format == "fastq":
                scores = record.letter_annotations.get("phred_quality")

                if scores is None:
                    raise SequenceParseError(
                        f"Missing FASTQ quality scores for " f"record {record.id}."
                    )

                if len(scores) != len(sequence):
                    raise SequenceParseError(
                        f"Quality score length mismatch for " f"record {record.id}."
                    )

                quality_scores = tuple(scores)

            record_count += 1

            yield ParsedSequence(
                sequence_id=record.id,
                description=record.description,
                sequence=sequence,
                molecule_type=molecule_type,
                file_format=file_format,
                quality_scores=quality_scores,
            )

    except SequenceParseError:
        raise

    except (ValueError, IndexError) as exc:
        raise SequenceParseError(f"Unable to parse {file_format} input: {exc}") from exc

    if record_count == 0:
        raise SequenceParseError("The input file contains no valid sequence records.")


def parse_sequences(
    source: str | Path | IO[str],
    file_format: SequenceFormat | Literal["auto"] = "auto",
    molecule_type: MoleculeType = "DNA",
    max_sequence_length: int = 10_000_000,
) -> Iterator[ParsedSequence]:
    """
    Parse genomic sequences from a file or open text stream.

    Parameters
    ----------
    source:
        File path or an already-open text stream.
    file_format:
        FASTA, FASTQ, or auto-detection from the file extension.
        An explicit format is required for file-like streams.
    molecule_type:
        DNA or RNA.
    max_sequence_length:
        Maximum allowed length for an individual sequence.

    Yields
    ------
    ParsedSequence:
        Validated sequence records, one at a time.

    Notes
    -----
    File paths are opened and closed internally.
    Caller-provided streams remain open.
    """

    if molecule_type not in ("DNA", "RNA"):
        raise ValueError("molecule_type must be either DNA or RNA.")

    if max_sequence_length <= 0:
        raise ValueError("max_sequence_length must be greater than zero.")

    if file_format == "auto":
        if hasattr(source, "read"):
            raise UnsupportedSequenceFormatError(
                "Specify file_format when using a file-like stream."
            )

        resolved_format = detect_format(source)

    else:
        resolved_format = file_format

    if resolved_format not in ("fasta", "fastq"):
        raise UnsupportedSequenceFormatError(
            f"Unsupported sequence format: {resolved_format}"
        )

    if hasattr(source, "read"):
        yield from _parse_handle(
            source,
            resolved_format,
            molecule_type,
            max_sequence_length,
        )

    else:
        path = Path(source)

        if not path.exists():
            raise FileNotFoundError(f"Sequence file not found: {path}")

        if not path.is_file():
            raise SequenceParseError(f"Sequence source is not a file: {path}")

        try:
            with path.open(
                "r",
                encoding="utf-8",
                newline=None,
            ) as handle:
                yield from _parse_handle(
                    handle,
                    resolved_format,
                    molecule_type,
                    max_sequence_length,
                )

        except UnicodeDecodeError as exc:
            raise SequenceParseError(
                "Sequence file must contain valid UTF-8 text."
            ) from exc
