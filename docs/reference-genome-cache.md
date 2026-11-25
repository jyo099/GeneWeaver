
# Reference Genome Cache

GeneWeaver uses Redis as an optional performance layer for reference-genome
sequences. PostgreSQL and the reference-data source remain authoritative.

## Installation

Install the existing cache dependency group:

```powershell
pip install -e ".[cache,dev]"
```

The cache group includes Redis and Celery. This commit uses Redis; Celery
will be integrated in the background-worker milestone.

## Configuration

Set the Redis connection URL through the existing `GW_` environment prefix:

```env
GW_REDIS_URL=redis://localhost:6379/0
```

The default cache expiration is 86,400 seconds (24 hours). It can be
overridden per write.

## Usage

```python
from app.core.config import get_settings
from app.services.cache import ReferenceGenomeCache


cache = ReferenceGenomeCache.from_url(
    get_settings().redis_url,
    ttl_seconds=86_400,
)

try:
    sequence = await cache.get_reference_genome(
        genome_id="GRCh38",
        dataset_version="2026.1",
    )

    if sequence is None:
        # Load the sequence from the authoritative reference-data source.
        sequence = await reference_repository.load_sequence(
            genome_id="GRCh38",
            dataset_version="2026.1",
        )

        await cache.set_reference_genome(
            genome_id="GRCh38",
            dataset_version="2026.1",
            sequence=sequence,
        )
finally:
    await cache.close()
```

`reference_repository` above represents the application's authoritative
reference-data loader; it is not introduced by this cache commit.

## Cache key strategy

Keys follow this structure:

```text
geneweaver:reference-genome:{genome_id}:{dataset_version}
```

The genome identifier and dataset version are URL-escaped before being
placed in the key. Including the dataset version prevents a newer reference
dataset from accidentally reading an older cached sequence.

## Failure behavior

- Cache hit: return the cached sequence.
- Cache miss: return `None`; the caller loads the authoritative sequence.
- Redis read failure: log a warning and return `None`.
- Redis write/delete failure: log a warning and return `False`.
- Cache expiration: Redis automatically expires the entry.

Redis is an optimization, not the source of truth. Callers must always be
able to load reference data without a cache hit.

## Tests

Run the cache tests without a Redis server:

```powershell
pytest tests/unit/test_cache.py -v
```

Run the complete suite:

```powershell
pytest -v
```
