import time
from typing import Any

import aiosqlite
import pytest

from app.services.session_categorized_cache_service import SessionCategorizedCacheService


class FakeRedis:
    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._strings: dict[str, str] = {}
        self._zsets: dict[str, dict[str, float]] = {}
        self._expires: dict[str, int] = {}
        self._expire_calls: list[tuple[str, int]] = []

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._lists:
                count += 1
                self._lists.pop(key, None)
            if key in self._hashes:
                count += 1
                self._hashes.pop(key, None)
            if key in self._strings:
                count += 1
                self._strings.pop(key, None)
            if key in self._zsets:
                count += 1
                self._zsets.pop(key, None)
            self._expires.pop(key, None)
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        self._expires[key] = seconds
        self._expire_calls.append((key, seconds))
        return True

    def expire_calls_for_key(self, key: str) -> list[int]:
        return [s for k, s in self._expire_calls if k == key]

    async def rpush(self, key: str, *values: str) -> int:
        self._lists.setdefault(key, []).extend(values)
        return len(self._lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self._lists.get(key, [])
        if not values:
            return []
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        values = self._lists.get(key, [])
        if not values:
            self._lists[key] = []
            return True

        if start < 0:
            start = max(0, len(values) + start)
        if end < 0:
            end = len(values) + end

        self._lists[key] = values[start : end + 1]
        return True

    async def set(self, key: str, value: str) -> bool:
        self._strings[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._strings.get(key)

    async def hset(self, key: str, field: str | None = None, value: str | None = None, mapping: dict[str, str] | None = None) -> int:  # noqa: E501
        h = self._hashes.setdefault(key, {})
        n = 0
        if mapping is not None:
            for k, v in mapping.items():
                if h.get(k) != v:
                    n += 1
                h[k] = v
        elif field is not None and value is not None:
            if h.get(field) != value:
                n += 1
            h[field] = value
        return n

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def hmget(self, key: str, *fields: str) -> list[str | None]:
        h = self._hashes.get(key, {})
        return [h.get(f) for f in fields]

    async def hdel(self, key: str, *fields: str) -> int:
        h = self._hashes.get(key, {})
        n = 0
        for f in fields:
            if f in h:
                n += 1
                h.pop(f, None)
        return n

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        z = self._zsets.setdefault(key, {})
        n = 0
        for member, score in mapping.items():
            if member not in z:
                n += 1
            z[member] = float(score)
        return n

    async def zrevrange(self, key: str, start: int, end: int) -> list[str]:
        z = self._zsets.get(key, {})
        items = sorted(z.items(), key=lambda kv: kv[1], reverse=True)
        members = [m for m, _ in items]
        if end == -1:
            return members[start:]
        return members[start : end + 1]

    async def zrem(self, key: str, *members: str) -> int:
        z = self._zsets.get(key, {})
        n = 0
        for m in members:
            if m in z:
                n += 1
                z.pop(m, None)
        return n


async def _create_service(tmp_path, timeline_max_items: int = 20) -> SessionCategorizedCacheService:
    db_path = tmp_path / "categorized_cache.db"
    service = SessionCategorizedCacheService(
        redis_url="redis://unused",
        sqlite_path=str(db_path),
        ttl_seconds=111,
        timeline_max_items=timeline_max_items,
        cleanup_interval_seconds=9999,
        redis_key_prefix="cache",
    )
    service._redis = FakeRedis()  # noqa: SLF001
    service._db = await aiosqlite.connect(str(db_path))  # noqa: SLF001
    await service._ensure_schema()  # noqa: SLF001
    return service


@pytest.mark.asyncio
async def test_append_event_and_list_resources(tmp_path) -> None:
    service = await _create_service(tmp_path)

    await service.append_event(session_id="s1", category="image_result", resource="r1", payload={"a": 1})
    resources = await service.list_resources(session_id="s1")
    assert resources == ["r1"]


@pytest.mark.asyncio
async def test_timeline_order_and_trim(tmp_path) -> None:
    service = await _create_service(tmp_path, timeline_max_items=2)

    await service.append_event(session_id="s1", category="scene_analysis", resource="r1", payload={"i": 1})
    await service.append_event(session_id="s1", category="scene_analysis", resource="r2", payload={"i": 2})
    await service.append_event(session_id="s1", category="scene_analysis", resource="r3", payload={"i": 3})

    timeline = await service.get_timeline(session_id="s1", category="scene_analysis")
    assert [e["payload"]["i"] for e in timeline] == [2, 3]


@pytest.mark.asyncio
async def test_get_resource_category_last_and_categories(tmp_path) -> None:
    service = await _create_service(tmp_path)

    await service.append_event(session_id="s1", category="image_result", resource="r1", payload={"v": 1})
    await service.append_event(session_id="s1", category="scene_analysis", resource="r1", payload={"v": 2})

    last = await service.get_resource_category_last(session_id="s1", category="scene_analysis", resource="r1")
    assert last is not None
    assert last["payload"]["v"] == 2

    cats = await service.get_resource_categories(session_id="s1", resource="r1")
    assert set(cats.keys()) == {"image_result", "scene_analysis"}


@pytest.mark.asyncio
async def test_ttl_refresh_on_append_and_read(tmp_path) -> None:
    service = await _create_service(tmp_path)
    fake: FakeRedis = service._redis  # type: ignore[assignment]

    await service.append_event(session_id="s1", category="reply", resource="r1", payload={"x": 1})
    await service.get_timeline(session_id="s1", category="reply")

    timeline_key = "cache:s:s1:c:reply:timeline"
    assert fake.expire_calls_for_key(timeline_key)


@pytest.mark.asyncio
async def test_sqlite_fallback_loads_timeline(tmp_path) -> None:
    service1 = await _create_service(tmp_path)
    await service1.append_event(session_id="s1", category="reply", resource="r1", payload={"x": 1})

    service2 = SessionCategorizedCacheService(
        redis_url="redis://unused",
        sqlite_path=service1._sqlite_path,  # noqa: SLF001
        ttl_seconds=111,
        timeline_max_items=20,
        cleanup_interval_seconds=9999,
        redis_key_prefix="cache",
    )
    service2._redis = FakeRedis()  # noqa: SLF001
    service2._db = await aiosqlite.connect(service1._sqlite_path)  # noqa: SLF001
    await service2._ensure_schema()  # noqa: SLF001

    timeline = await service2.get_timeline(session_id="s1", category="reply")
    assert len(timeline) == 1
    assert timeline[0]["payload"]["x"] == 1


@pytest.mark.asyncio
async def test_metrics_increment(tmp_path) -> None:
    service = await _create_service(tmp_path)

    await service.append_event(session_id="s1", category="reply", resource="r1", payload={"x": 1})
    await service.get_timeline(session_id="s1", category="reply")
    await service.list_resources(session_id="s1")

    stats = service.stats()
    assert stats["append_event_calls"] == 1
    assert stats["get_timeline_calls"] == 1
    assert stats["list_resources_calls"] == 1
