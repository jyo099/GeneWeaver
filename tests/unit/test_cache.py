"""Unit tests for the Redis reference-genome cache."""

import json

import pytest
from redis.exceptions import RedisError

from app.services.cache import RedisGenomeCache


class FakeRedis:
    """Small asynchronous Redis substitute for unit testing."""

    def __init__(self):
        self.data = {}
        self.ttls = {}
        self.fail_reads = False
        self.fail_writes = False
        self.fail_ping = False
        self.closed = False

    async def get(self, key):
        if self.fail_reads:
            raise RedisError("Redis unavailable")
        return self.data.get(key)

    async def set(self, key, value, ex=None):
        if self.fail_writes:
            raise RedisError("Redis unavailable")
        self.data[key] = value
        self.ttls[key] = ex
        return True

    async def delete(self, *keys):
        deleted = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                self.ttls.pop(key, None)
                deleted += 1
        return deleted

    async def scan_iter(self, match=None, count=500):
        del count
        import fnmatch

        for key in list(self.data):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def ping(self):
        if self.fail_ping:
            raise RedisError("Redis unavailable")
        return True

    async def aclose(self):
        self.closed = True


@pytest.fixture
def redis_client():
    return FakeRedis()


@pytest.fixture
def cache(redis_client):
    return RedisGenomeCache(
        redis_client,
        ttl_seconds=3600,
    )


@pytest.mark.asyncio
async def test_set_and_get_genome_chunk(cache):
    sequence = "ACGTACGTACGT"

    stored = await cache.set_chunk(
        "GRCh38",
        "release-1",
        0,
        sequence,
    )
    retrieved = await cache.get_chunk(
        "GRCh38",
        "release-1",
        0,
    )

    assert stored is True
    assert retrieved == sequence


@pytest.mark.asyncio
async def test_cache_miss_returns_none(cache):
    result = await cache.get_chunk(
        "GRCh38",
        "release-1",
        0,
    )

    assert result is None


@pytest.mark.asyncio
async def test_genome_versions_have_separate_cache_entries(cache):
    await cache.set_chunk("GRCh38", "release-1", 0, "AAAA")
    await cache.set_chunk("GRCh38", "release-2", 0, "CCCC")

    first = await cache.get_chunk("GRCh38", "release-1", 0)
    second = await cache.get_chunk("GRCh38", "release-2", 0)

    assert first == "AAAA"
    assert second == "CCCC"


@pytest.mark.asyncio
async def test_different_genomes_have_separate_cache_entries(cache):
    await cache.set_chunk("GRCh38", "release-1", 0, "AAAA")
    await cache.set_chunk("GRCh37", "release-1", 0, "CCCC")

    assert await cache.get_chunk("GRCh38", "release-1", 0) == "AAAA"
    assert await cache.get_chunk("GRCh37", "release-1", 0) == "CCCC"


@pytest.mark.asyncio
async def test_chunks_are_independent(cache):
    await cache.set_chunk("GRCh38", "release-1", 0, "AAAA")
    await cache.set_chunk("GRCh38", "release-1", 1, "CCCC")

    assert await cache.get_chunk("GRCh38", "release-1", 0) == "AAAA"
    assert await cache.get_chunk("GRCh38", "release-1", 1) == "CCCC"


@pytest.mark.asyncio
async def test_ttl_is_applied(redis_client, cache):
    await cache.set_chunk("GRCh38", "release-1", 0, "AAAA")

    key = next(iter(redis_client.data))
    assert redis_client.ttls[key] == 3600


@pytest.mark.asyncio
async def test_custom_ttl_is_applied(redis_client, cache):
    await cache.set_chunk(
        "GRCh38",
        "release-1",
        0,
        "AAAA",
        ttl_seconds=120,
    )

    key = next(iter(redis_client.data))
    assert redis_client.ttls[key] == 120


@pytest.mark.asyncio
async def test_invalid_ttl_is_rejected(cache):
    with pytest.raises(ValueError):
        await cache.set_chunk(
            "GRCh38",
            "release-1",
            0,
            "AAAA",
            ttl_seconds=0,
        )


@pytest.mark.asyncio
async def test_empty_sequence_is_rejected(cache):
    with pytest.raises(ValueError):
        await cache.set_chunk(
            "GRCh38",
            "release-1",
            0,
            "",
        )


@pytest.mark.asyncio
async def test_negative_chunk_index_is_rejected(cache):
    with pytest.raises(ValueError):
        await cache.get_chunk("GRCh38", "release-1", -1)


@pytest.mark.asyncio
async def test_empty_genome_id_is_rejected(cache):
    with pytest.raises(ValueError):
        await cache.get_chunk("", "release-1", 0)


@pytest.mark.asyncio
async def test_redis_read_failure_returns_cache_miss(cache, redis_client):
    redis_client.fail_reads = True

    result = await cache.get_chunk("GRCh38", "release-1", 0)

    assert result is None


@pytest.mark.asyncio
async def test_redis_write_failure_returns_false(cache, redis_client):
    redis_client.fail_writes = True

    result = await cache.set_chunk(
        "GRCh38",
        "release-1",
        0,
        "AAAA",
    )

    assert result is False


@pytest.mark.asyncio
async def test_invalid_payload_is_deleted(cache, redis_client):
    key = cache._key("GRCh38", "release-1", 0)
    redis_client.data[key] = json.dumps({"schema": "unknown", "sequence": "AAAA"})

    result = await cache.get_chunk("GRCh38", "release-1", 0)

    assert result is None
    assert key not in redis_client.data


@pytest.mark.asyncio
async def test_invalidate_one_genome_version(cache):
    await cache.set_chunk("GRCh38", "release-1", 0, "AAAA")
    await cache.set_chunk("GRCh38", "release-1", 1, "CCCC")
    await cache.set_chunk("GRCh38", "release-2", 0, "GGGG")
    await cache.set_chunk("GRCh37", "release-1", 0, "TTTT")

    deleted = await cache.invalidate_genome(
        "GRCh38",
        "release-1",
    )

    assert deleted == 2
    assert await cache.get_chunk("GRCh38", "release-1", 0) is None
    assert await cache.get_chunk("GRCh38", "release-2", 0) == "GGGG"
    assert await cache.get_chunk("GRCh37", "release-1", 0) == "TTTT"


@pytest.mark.asyncio
async def test_health_check(cache):
    assert await cache.health_check() is True


@pytest.mark.asyncio
async def test_health_check_handles_redis_failure(cache, redis_client):
    redis_client.fail_ping = True

    assert await cache.health_check() is False


@pytest.mark.asyncio
async def test_close_closes_redis_client(cache, redis_client):
    await cache.close()

    assert redis_client.closed is True


def test_invalid_default_ttl_is_rejected(redis_client):
    with pytest.raises(ValueError):
        RedisGenomeCache(redis_client, ttl_seconds=0)
