
# GeneWeaver Database Models

## Overview

GeneWeaver uses SQLAlchemy models to persist alignment jobs and
their genomic alignment results.

The models are defined in:

- `app/models/alignment.py`
- `app/models/database.py`

The shared declarative base is defined in `database.py`.

## AlignmentJob

The `alignment_jobs` table stores submitted alignment jobs.

Important fields:

| Field | Purpose |
|---|---|
| id | Unique UUID for the job |
| guide_sequence | Submitted guide sequence |
| pam_type | PAM type used for the search |
| reference_genome | Reference genome identifier |
| reference_dataset_version | Exact reference dataset version |
| reference_dataset_checksum | Optional dataset checksum |
| algorithm_name | Alignment algorithm identifier |
| algorithm_version | Algorithm version |
| compute_backend | CPU or GPU execution backend |
| parameters | JSON configuration used for the run |
| status | Job lifecycle status |
| progress | Job progress from 0 to 100 |
| error_message | Failure details, if applicable |
| created_at | Job creation time |
| started_at | Job start time |
| completed_at | Job completion time |
| updated_at | Last update time |

Supported statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

Progress must be between 0 and 100.

## AlignmentResult

The `alignment_results` table stores individual genomic matches.

Important fields:

| Field | Purpose |
|---|---|
| id | Unique UUID for the result |
| job_id | Parent alignment job |
| chromosome | Chromosome or reference contig |
| start_position | Inclusive genomic start coordinate |
| end_position | Exclusive genomic end coordinate |
| strand | Positive or negative strand |
| target_sequence | Matched target sequence |
| pam_sequence | Observed PAM sequence |
| mismatch_count | Number of mismatches |
| mismatch_positions | JSON array of mismatch positions |
| score | Algorithm-specific screening score |
| score_components | Optional score breakdown |
| result_metadata | Additional result metadata |
| created_at | Result creation time |

## Coordinate convention

Genomic coordinates use a zero-based, half-open interval:

- `start_position` is included.
- `end_position` is excluded.
- `end_position` must be greater than `start_position`.

For example, a result with start 100 and end 120 represents
20 bases: positions 100 through 119.

The alignment engine and API must use this convention consistently.
Convert coordinates explicitly when importing data that uses a
different convention.

## Reproducibility

Each job records:

- Reference genome identifier.
- Reference dataset version.
- Optional reference dataset checksum.
- Algorithm name and version.
- Compute backend.
- Algorithm parameters.

These fields help identify the computational context in which
a result was produced.

The checksum should be populated from the actual reference dataset
when available. Do not use a placeholder checksum in production.

## Scientific interpretation

The `score` field represents an algorithm-specific screening score.

It must not be presented as a clinically validated probability
or as a guarantee of biological activity.

Mismatch counts, mismatch positions, strand, PAM sequence,
and reference coordinates should be retained for traceability.

## Relationships

One alignment job can contain multiple alignment results.

Deleting an alignment job also deletes its associated results.

## Database migrations

This commit defines SQLAlchemy models only.

Database schema creation and updates for deployed environments
must be handled through Alembic migrations in Commit 10.

Do not use `Base.metadata.create_all()` as a production migration
strategy.
