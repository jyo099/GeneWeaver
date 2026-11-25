"""Redis-backed reference genome cache for GeneWeaver."""

from __future__ import annotations

import logging
from urllib.parse import quote

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 86_400
DEFAULT_KEY_PREFIX = "geneweaver"


class ReferenceGenomeCache:
    """Cache reference genome sequences using versioned Redis keys.

    Redis failures are treated as cache misses or unsuccessful writes.
    This keeps cache availability independent from alignment availability.
    """

    def __init__(
        self,
        client: Redis,
        *,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        if not key_prefix.strip():
            raise ValueError("key_prefix cannot be empty")

        self._client = client
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix.strip().rstrip(":")

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> ReferenceGenomeCache:
        """Create a cache backed by an asynchronous Redis client."""
        if not redis_url.strip():
            raise ValueError("redis_url cannot be empty")

        client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        return cls(
            client,
            ttl_seconds=ttl_seconds,
            key_prefix=key_prefix,
        )

    def _build_key(self, genome_id: str, dataset_version: str) -> str:
        """Build a collision-safe key scoped to a genome dataset version."""
        if not genome_id.strip():
            raise ValueError("genome_id cannot be empty")

        if not dataset_version.strip():
            raise ValueError("dataset_version cannot be empty")

        safe_genome_id = quote(genome_id.strip(), safe="")
        safe_version = quote(dataset_version.strip(), safe="")

        return (
            f"{self._key_prefix}:reference-genome:" f"{safe_genome_id}:{safe_version}"
        )

    async def get_reference_genome(
        self,
        genome_id: str,
        dataset_version: str,
    ) -> str | None:
        """Retrieve a cached sequence, or return None on a cache miss."""
        key = self._build_key(genome_id, dataset_version)

        try:
            return await self._client.get(key)
        except RedisError:
            logger.warning(
                "Redis read failed for reference genome cache key %s",
                key,
                exc_info=True,
            )
            return None

    async def set_reference_genome(
        self,
        genome_id: str,
        dataset_version: str,
        sequence: str,
        *,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store a reference sequence with an expiration time."""
        if not isinstance(sequence, str) or not sequence:
            raise ValueError("sequence must be a non-empty string")

        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        key = self._build_key(genome_id, dataset_version)

        try:
            await self._client.set(key, sequence, ex=ttl)
            return True
        except RedisError:
            logger.warning(
                "Redis write failed for reference genome cache key %s",
                key,
                exc_info=True,
            )
            return False

    async def delete_reference_genome(
        self,
        genome_id: str,
        dataset_version: str,
    ) -> bool:
        """Delete one version of a cached reference genome."""
        key = self._build_key(genome_id, dataset_version)

        try:
            return bool(await self._client.delete(key))
        except RedisError:
            logger.warning(
                "Redis delete failed for reference genome cache key %s",
                key,
                exc_info=True,
            )
            return False

    async def close(self) -> None:
        """Close the underlying asynchronous Redis connection pool."""
        try:
            await self._client.aclose()
        except RedisError:
            logger.warning("Failed to close Redis cache connection", exc_info=True)
