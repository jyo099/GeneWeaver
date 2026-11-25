"""Redis-backed reference-genome chunk cache.

Redis is an optional performance layer. Cache failures are treated as
cache misses so callers can fall back to the authoritative genome store.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_CACHE_SCHEMA_VERSION = "v1"
_DEFAULT_TTL_SECONDS = 86_400
_MAX_TTL_SECONDS = 30 * 24 * 60 * 60


class RedisGenomeCache:
    """Cache immutable reference-genome sequence chunks in Redis."""

    def __init__(
        self,
        client: Redis,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        key_prefix: str = "geneweaver:reference",
    ) -> None:
        if not 1 <= ttl_seconds <= _MAX_TTL_SECONDS:
            raise ValueError(f"ttl_seconds must be between 1 and {_MAX_TTL_SECONDS}.")

        if not key_prefix or not key_prefix.strip():
            raise ValueError("key_prefix cannot be empty.")

        self._client = client
        self._ttl_seconds = ttl_seconds
        self._key_prefix = key_prefix.rstrip(":")

    @classmethod
    def from_url(
        cls,
        redis_url: str,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        key_prefix: str = "geneweaver:reference",
    ) -> RedisGenomeCache:
        """Create a cache using a Redis URL."""
        client = Redis.from_url(
            redis_url,
            encoding="utf-8",
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

    @classmethod
    def from_settings(cls) -> RedisGenomeCache:
        """Create a cache using the application's existing settings."""
        from app.core.config import get_settings

        settings = get_settings()
        return cls.from_url(settings.redis_url)

    @staticmethod
    def _digest(value: str) -> str:
        """Hash an identifier so arbitrary input cannot alter Redis keys."""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _key(
        self,
        genome_id: str,
        genome_version: str,
        chunk_index: int,
    ) -> str:
        if not genome_id or not genome_id.strip():
            raise ValueError("genome_id cannot be empty.")

        if not genome_version or not genome_version.strip():
            raise ValueError("genome_version cannot be empty.")

        if chunk_index < 0:
            raise ValueError("chunk_index cannot be negative.")

        genome_hash = self._digest(genome_id)
        version_hash = self._digest(genome_version)

        return (
            f"{self._key_prefix}:{_CACHE_SCHEMA_VERSION}:"
            f"{genome_hash}:{version_hash}:chunk:{chunk_index}"
        )

    def _pattern(self, genome_id: str, genome_version: str) -> str:
        """Build a pattern matching every chunk of one genome version."""
        if not genome_id or not genome_id.strip():
            raise ValueError("genome_id cannot be empty.")

        if not genome_version or not genome_version.strip():
            raise ValueError("genome_version cannot be empty.")

        return (
            f"{self._key_prefix}:{_CACHE_SCHEMA_VERSION}:"
            f"{self._digest(genome_id)}:"
            f"{self._digest(genome_version)}:chunk:*"
        )

    async def get_chunk(
        self,
        genome_id: str,
        genome_version: str,
        chunk_index: int,
    ) -> str | None:
        """Return a cached sequence chunk, or None on a cache miss."""
        key = self._key(genome_id, genome_version, chunk_index)

        try:
            payload = await self._client.get(key)
        except (RedisError, OSError, TimeoutError):
            logger.warning(
                "Redis read failed; treating genome cache as a miss.",
                exc_info=True,
            )
            return None

        if payload is None:
            return None

        try:
            decoded: Any = json.loads(payload)

            if not isinstance(decoded, dict):
                raise TypeError("Cached payload must be a JSON object.")

            if decoded.get("schema") != _CACHE_SCHEMA_VERSION:
                raise ValueError("Unsupported cached payload schema.")

            sequence = decoded.get("sequence")
            if not isinstance(sequence, str):
                raise TypeError("Cached sequence must be a string.")

            return sequence

        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Invalid genome cache payload; deleting corrupted entry.")
            try:
                await self._client.delete(key)
            except (RedisError, OSError, TimeoutError):
                logger.warning(
                    "Unable to delete corrupted genome cache entry.",
                    exc_info=True,
                )
            return None

    async def set_chunk(
        self,
        genome_id: str,
        genome_version: str,
        chunk_index: int,
        sequence: str,
        *,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store one immutable genome sequence chunk.

        Returns False if Redis is unavailable. Invalid input raises
        ValueError instead of silently accepting an invalid cache entry.
        """
        if not isinstance(sequence, str) or not sequence:
            raise ValueError("sequence must be a non-empty string.")

        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        if not 1 <= ttl <= _MAX_TTL_SECONDS:
            raise ValueError(f"ttl_seconds must be between 1 and {_MAX_TTL_SECONDS}.")

        key = self._key(genome_id, genome_version, chunk_index)
        payload = json.dumps(
            {
                "schema": _CACHE_SCHEMA_VERSION,
                "sequence": sequence,
            },
            separators=(",", ":"),
        )

        try:
            await self._client.set(key, payload, ex=ttl)
            return True
        except (RedisError, OSError, TimeoutError):
            logger.warning(
                "Redis write failed; genome data remains uncached.",
                exc_info=True,
            )
            return False

    async def invalidate_genome(
        self,
        genome_id: str,
        genome_version: str,
    ) -> int:
        """Delete all cached chunks for a specific genome version."""
        pattern = self._pattern(genome_id, genome_version)
        deleted = 0

        try:
            keys: AsyncIterator[str] = self._client.scan_iter(
                match=pattern,
                count=500,
            )

            batch: list[str] = []
            async for key in keys:
                batch.append(key)

                if len(batch) >= 500:
                    deleted += await self._client.delete(*batch)
                    batch.clear()

            if batch:
                deleted += await self._client.delete(*batch)

            return deleted

        except (RedisError, OSError, TimeoutError):
            logger.warning(
                "Redis genome invalidation failed.",
                exc_info=True,
            )
            return deleted

    async def health_check(self) -> bool:
        """Check whether Redis is reachable."""
        try:
            return bool(await self._client.ping())
        except (RedisError, OSError, TimeoutError):
            logger.warning(
                "Redis health check failed.",
                exc_info=True,
            )
            return False

    async def close(self) -> None:
        """Close the Redis connection pool."""
        try:
            await self._client.aclose()
        except (RedisError, OSError, TimeoutError):
            logger.warning(
                "Redis connection shutdown failed.",
                exc_info=True,
            )
