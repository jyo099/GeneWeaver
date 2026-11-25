
# Reference Genome Cache

GeneWeaver uses Redis as an optional cache for immutable reference-genome
sequence chunks.

## Cache identity

Each entry is identified by:

- Genome identifier
- Exact reference dataset version
- Chunk index
- Cache schema version

A different genome version always produces a different cache key.

## Usage

```python
from app.services.cache import RedisGenomeCache

cache = RedisGenomeCache.from_settings()

try:
    sequence = await cache.get_chunk(
        genome_id="GRCh38",
        genome_version="release-1",
        chunk_index=0,
    )

    if sequence is None:
        # Load the authoritative sequence chunk from the genome store.
        sequence = await genome_store.load_chunk(
            genome_id="GRCh38",
            version="release-1",
            chunk_index=0,
        )

        await cache.set_chunk(
            genome_id="GRCh38",
            genome_version="release-1",
            chunk_index=0,
            sequence=sequence,
        )
finally:
    await cache.close()
```

The `genome_store` above represents the authoritative genome storage
service. It must be implemented by the reference-genome management
milestone; the cache must never become the authoritative source.

## Invalidation

When a reference dataset version is retired or its cached entries must
be removed:

```python
deleted = await cache.invalidate_genome(
    genome_id="GRCh38",
    genome_version="release-1",
)
```

Only the specified genome and version are invalidated.

## Failure behavior

Redis connection failures are treated as cache misses for reads and
unsuccessful cache writes. Callers must continue using the authoritative
genome store.

Malformed cache entries are deleted and treated as misses.

## Operational notes

- Default TTL: 24 hours.
- Maximum configurable TTL: 30 days.
- Cache keys contain SHA-256 hashes of genome identifiers and versions.
- Sequence chunks are stored independently.
- Redis must be monitored and protected by network access controls.
- Never store authentication secrets or sensitive user data in genome keys.
- Cache schema changes require a schema-version update.
