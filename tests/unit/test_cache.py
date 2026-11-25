"""Unit tests for the Redis reference genome cache."""

from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import RedisError

from app.services.cache import ReferenceGenomeCache


@pytest.fixture
def redis_client():
    """Provide an isolated asynchronous Redis mock."""
    client = AsyncMock()
    return client


@pytest.fixture
def cache(redis_client):
    """Create a cache using the mocked Redis client."""
    return ReferenceGenomeCache(
        redis_client,
        ttl_seconds=3600,
    )


@pytest.mark.asyncio
async def test_cache_hit_returns_reference_sequence(cache, redis_client):
    redis_client.get.return_value = "ACGTACGT"

    result = await cache.get_reference_genome("GRCh38", "v1")

    assert result == "ACGTACGT"
    redis_client.get.assert_awaited_once_with("geneweaver:reference-genome:GRCh38:v1")


@pytest.mark.asyncio
async def test_cache_miss_returns_none(cache, redis_client):
    redis_client.get.return_value = None

    result = await cache.get_reference_genome("GRCh38", "v1")

    assert result is None


@pytest.mark.asyncio
async def test_set_reference_genome_uses_default_ttl(cache, redis_client):
    result = await cache.set_reference_genome(
        "GRCh38",
        "v1",
        "ACGTACGT",
    )

    assert result is True
    redis_client.set.assert_awaited_once_with(
        "geneweaver:reference-genome:GRCh38:v1",
        "ACGTACGT",
        ex=3600,
    )


@pytest.mark.asyncio
async def test_set_reference_genome_supports_custom_ttl(
    cache,
    redis_client,
):
    result = await cache.set_reference_genome(
        "GRCh38",
        "v1",
        "ACGT",
        ttl_seconds=120,
    )

    assert result is True
    assert redis_client.set.await_args.kwargs["ex"] == 120


@pytest.mark.asyncio
async def test_dataset_versions_use_separate_cache_keys(
    cache,
    redis_client,
):
    await cache.get_reference_genome("GRCh38", "v1")
    await cache.get_reference_genome("GRCh38", "v2")

    assert redis_client.get.await_args_list[0].args[0].endswith(":v1")
    assert redis_client.get.await_args_list[1].args[0].endswith(":v2")


@pytest.mark.asyncio
async def test_genome_identifiers_are_escaped(cache, redis_client):
    await cache.get_reference_genome("reference/a", "release 1")

    redis_client.get.assert_awaited_once_with(
        "geneweaver:reference-genome:reference%2Fa:release%201"
    )


@pytest.mark.asyncio
async def test_redis_read_failure_fails_open(cache, redis_client):
    redis_client.get.side_effect = RedisError("Redis unavailable")

    result = await cache.get_reference_genome("GRCh38", "v1")

    assert result is None


@pytest.mark.asyncio
async def test_redis_write_failure_does_not_break_processing(
    cache,
    redis_client,
):
    redis_client.set.side_effect = RedisError("Redis unavailable")

    result = await cache.set_reference_genome(
        "GRCh38",
        "v1",
        "ACGT",
    )

    assert result is False


@pytest.mark.asyncio
async def test_delete_reference_genome(cache, redis_client):
    redis_client.delete.return_value = 1

    result = await cache.delete_reference_genome("GRCh38", "v1")

    assert result is True
    redis_client.delete.assert_awaited_once_with(
        "geneweaver:reference-genome:GRCh38:v1"
    )


@pytest.mark.asyncio
async def test_delete_missing_key_returns_false(cache, redis_client):
    redis_client.delete.return_value = 0

    result = await cache.delete_reference_genome("GRCh38", "v1")

    assert result is False


@pytest.mark.asyncio
async def test_redis_delete_failure_fails_open(cache, redis_client):
    redis_client.delete.side_effect = RedisError("Redis unavailable")

    result = await cache.delete_reference_genome("GRCh38", "v1")

    assert result is False


@pytest.mark.asyncio
async def test_close_closes_redis_client(cache, redis_client):
    await cache.close()

    redis_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_from_url_creates_async_redis_client(redis_client):
    with patch(
        "app.services.cache.Redis.from_url",
        return_value=redis_client,
    ) as redis_factory:
        cache = ReferenceGenomeCache.from_url(
            "redis://localhost:6379/0",
            ttl_seconds=600,
        )

    redis_factory.assert_called_once_with(
        "redis://localhost:6379/0",
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )
    assert cache._client is redis_client


def test_rejects_non_positive_default_ttl(redis_client):
    with pytest.raises(ValueError, match="ttl_seconds"):
        ReferenceGenomeCache(redis_client, ttl_seconds=0)


def test_rejects_empty_key_prefix(redis_client):
    with pytest.raises(ValueError, match="key_prefix"):
        ReferenceGenomeCache(redis_client, key_prefix=" ")


@pytest.mark.asyncio
async def test_rejects_empty_sequence(cache):
    with pytest.raises(ValueError, match="sequence"):
        await cache.set_reference_genome("GRCh38", "v1", "")


@pytest.mark.asyncio
async def test_rejects_non_positive_custom_ttl(cache):
    with pytest.raises(ValueError, match="ttl_seconds"):
        await cache.set_reference_genome(
            "GRCh38",
            "v1",
            "ACGT",
            ttl_seconds=0,
        )


@pytest.mark.asyncio
async def test_rejects_empty_genome_identifier(cache):
    with pytest.raises(ValueError, match="genome_id"):
        await cache.get_reference_genome(" ", "v1")


@pytest.mark.asyncio
async def test_rejects_empty_dataset_version(cache):
    with pytest.raises(ValueError, match="dataset_version"):
        await cache.get_reference_genome("GRCh38", " ")
