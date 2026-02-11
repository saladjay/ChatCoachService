import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Sequence
from typing import Any

import aiosqlite
import redis.asyncio as redis


logger = logging.getLogger(__name__)


class SessionCategorizedCacheService:
    def __init__(
        self,
        *,
        redis_url: str,
        sqlite_path: str,
        ttl_seconds: int,
        timeline_max_items: int,
        cleanup_interval_seconds: int,
        redis_key_prefix: str,
    ) -> None:
        self._redis_url = redis_url
        self._sqlite_path = sqlite_path
        self._ttl_seconds = ttl_seconds
        self._timeline_max_items = timeline_max_items
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._redis_key_prefix = redis_key_prefix.rstrip(":")

        self._redis: redis.Redis | None = None
        self._db: aiosqlite.Connection | None = None

        self._stop_event = asyncio.Event()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._db_lock = asyncio.Lock()

        self._metrics: dict[str, int] = {
            "start_calls": 0,
            "stop_calls": 0,
            "append_event_calls": 0,
            "get_timeline_calls": 0,
            "get_resource_categories_calls": 0,
            "get_resource_category_last_calls": 0,
            "list_resources_calls": 0,
            "sqlite_fallback_loads": 0,
            "recovered_sessions": 0,
            "cleanup_runs": 0,
            "cleaned_sessions": 0,
        }

    def stats(self) -> dict[str, int]:
        return dict(self._metrics)

    def _resource_key(self, resource: str) -> str:
        return hashlib.sha1(resource.encode("utf-8")).hexdigest()[:16]

    def _key_resources_zset(self, session_id: str) -> str:
        return f"{self._redis_key_prefix}:s:{session_id}:resources"

    def _key_resources_map(self, session_id: str) -> str:
        return f"{self._redis_key_prefix}:s:{session_id}:resources:map"

    def _key_timeline(self, session_id: str, category: str) -> str:
        return f"{self._redis_key_prefix}:s:{session_id}:c:{category}:timeline"

    def _key_last(self, session_id: str, resource_key: str, category: str) -> str:
        return f"{self._redis_key_prefix}:s:{session_id}:r:{resource_key}:c:{category}:last"

    def _key_resource_cats(self, session_id: str, resource_key: str) -> str:
        return f"{self._redis_key_prefix}:s:{session_id}:r:{resource_key}:cats"

    async def start(self) -> None:
        self._metrics["start_calls"] += 1
        if self._redis is not None or self._db is not None:
            return

        self._stop_event.clear()

        self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()

        self._db = await aiosqlite.connect(self._sqlite_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._ensure_schema()

        await self._recover_to_redis()

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(
            "SessionCategorizedCacheService started (redis_url=%s, sqlite_path=%s, ttl=%s, timeline_max_items=%s)",
            self._redis_url,
            self._sqlite_path,
            self._ttl_seconds,
            self._timeline_max_items,
        )

    async def stop(self) -> None:
        self._metrics["stop_calls"] += 1
        self._stop_event.set()

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._db is not None:
            await self._db.close()
            self._db = None

        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

        logger.info("SessionCategorizedCacheService stopped")

    async def append_event(self, *, session_id: str, category: str, resource: str, payload: dict[str, Any], scene:str="") -> None:
        # Convert scene to string if it's not already (handles int scene IDs)
        scene_str = str(scene) if scene else ""
        session_id_with_scene = f"{session_id}_{scene_str}"
        
        from app.core.config import settings
        if settings.debug_config.log_cache_operations:
            logger.error(f"===== APPEND_EVENT SCENE DEBUG =====")
            logger.error(f"Original scene: '{scene}' (type: {type(scene).__name__})")
            logger.error(f"Converted scene_str: '{scene_str}'")
            logger.error(f"Final session_id: '{session_id_with_scene}'")
            logger.error(f"Category: {category}, Resource: {resource[:50]}...")
            logger.error(f"===== END APPEND_EVENT SCENE DEBUG =====")
        
        self._metrics["append_event_calls"] += 1
        redis_client = self._require_redis()
        now = int(time.time())
        resource_key = self._resource_key(resource)

        event = {
            "ts": now,
            "resource_key": resource_key,
            "category": category,
            "payload": payload,
        }
        event_str = json.dumps(event, ensure_ascii=False, separators=(",", ":"))

        zset_key = self._key_resources_zset(session_id_with_scene)
        map_key = self._key_resources_map(session_id_with_scene)
        await redis_client.zadd(zset_key, {resource_key: now})
        await redis_client.hset(map_key, resource_key, resource)

        timeline_key = self._key_timeline(session_id_with_scene, category)
        await redis_client.rpush(timeline_key, event_str)
        if self._timeline_max_items > 0:
            await redis_client.ltrim(timeline_key, -self._timeline_max_items, -1)

        last_key = self._key_last(session_id_with_scene, resource_key, category)
        if settings.debug_config.log_cache_operations:
            logger.error(f"===== REDIS SET DEBUG =====")
            logger.error(f"Setting last_key: {last_key}")
            logger.error(f"Event strategy: {payload.get('_strategy')}, model: {payload.get('_model')}")
            logger.error(f"===== END REDIS SET DEBUG =====")
        await redis_client.set(last_key, event_str)
        
        # Log cache update for debugging
        strategy = payload.get('_strategy', 'unknown') if isinstance(payload, dict) else 'unknown'
        model = payload.get('_model', 'unknown') if isinstance(payload, dict) else 'unknown'
        logger.debug(f"Cache updated: session={session_id_with_scene}, resource={resource_key}, category={category}, strategy={strategy}, model={model}")

        cats_key = self._key_resource_cats(session_id_with_scene, resource_key)
        await redis_client.hset(cats_key, category, event_str)

        await self._refresh_ttl(
            session_id=session_id_with_scene,
            category=category,
            resource_key=resource_key,
            keys=[zset_key, map_key, timeline_key, last_key, cats_key],
        )

        await self._persist_event(
            session_id=session_id_with_scene,
            category=category,
            resource=resource,
            resource_key=resource_key,
            ts=now,
            payload_str=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        )

    async def get_timeline(self, *, session_id: str, category: str, scene:str="") -> list[dict[str, Any]]:
        # Convert scene to string if it's not already (handles int scene IDs)
        scene_str = str(scene) if scene else ""
        session_id_with_scene = f"{session_id}_{scene_str}"
        
        self._metrics["get_timeline_calls"] += 1
        redis_client = self._require_redis()
        timeline_key = self._key_timeline(session_id_with_scene, category)

        values: Sequence[str] | None = await redis_client.lrange(timeline_key, 0, -1)
        if not values:
            self._metrics["sqlite_fallback_loads"] += 1
            await self._load_timeline_from_sqlite(session_id=session_id_with_scene, category=category)
            values = await redis_client.lrange(timeline_key, 0, -1)

        if not values:
            return []

        await redis_client.expire(timeline_key, self._ttl_seconds)
        await self._touch_session(session_id=session_id_with_scene, now=int(time.time()))

        result: list[dict[str, Any]] = []
        for v in values:
            result.append(json.loads(v))
        return result

    async def get_resource_categories(self, *, session_id: str, resource: str, scene:str="") -> dict[str, dict[str, Any]]:
        # Convert scene to string if it's not already (handles int scene IDs)
        scene_str = str(scene) if scene else ""
        session_id_with_scene = f"{session_id}_{scene_str}"
        
        self._metrics["get_resource_categories_calls"] += 1
        redis_client = self._require_redis()
        now = int(time.time())
        resource_key = self._resource_key(resource)

        cats_key = self._key_resource_cats(session_id_with_scene, resource_key)
        data = await redis_client.hgetall(cats_key)
        if not data:
            self._metrics["sqlite_fallback_loads"] += 1
            await self._load_resource_indexes_from_sqlite(session_id=session_id_with_scene, resource_key=resource_key)
            data = await redis_client.hgetall(cats_key)

        keys_to_refresh = [
            self._key_resources_zset(session_id_with_scene),
            self._key_resources_map(session_id_with_scene),
            cats_key,
        ]
        await self._refresh_ttl(session_id=session_id_with_scene, resource_key=resource_key, keys=keys_to_refresh)
        await self._touch_session(session_id=session_id_with_scene, now=now)

        result: dict[str, dict[str, Any]] = {}
        for category, event_str in data.items():
            result[category] = json.loads(event_str)
        return result

    async def get_resource_category_last(
        self, *, session_id: str, category: str, resource: str, scene:str=""
    ) -> dict[str, Any] | None:
        # Convert scene to string if it's not already (handles int scene IDs)
        scene_str = str(scene) if scene else ""
        session_id_with_scene = f"{session_id}_{scene_str}"
        
        from app.core.config import settings
        if settings.debug_config.log_cache_operations:
            logger.error(f"===== GET_RESOURCE_CATEGORY_LAST SCENE DEBUG =====")
            logger.error(f"Original scene: '{scene}' (type: {type(scene).__name__})")
            logger.error(f"Converted scene_str: '{scene_str}'")
            logger.error(f"Final session_id: '{session_id_with_scene}'")
            logger.error(f"Category: {category}, Resource: {resource[:50]}...")
            logger.error(f"===== END GET_RESOURCE_CATEGORY_LAST SCENE DEBUG =====")
        
        self._metrics["get_resource_category_last_calls"] += 1
        redis_client = self._require_redis()
        now = int(time.time())
        resource_key = self._resource_key(resource)

        last_key = self._key_last(session_id_with_scene, resource_key, category)
        if settings.debug_config.log_cache_operations:
            logger.error(f"===== REDIS GET DEBUG =====")
            logger.error(f"Getting last_key: {last_key}")
        value = await redis_client.get(last_key)
        if settings.debug_config.log_cache_operations:
            logger.error(f"Redis returned value: {value[:200] if value else None}...")
            logger.error(f"===== END REDIS GET DEBUG =====")
        
        if value is None:
            self._metrics["sqlite_fallback_loads"] += 1
            await self._load_resource_indexes_from_sqlite(session_id=session_id_with_scene, resource_key=resource_key)
            value = await redis_client.get(last_key)

        keys_to_refresh = [
            self._key_resources_zset(session_id_with_scene),
            self._key_resources_map(session_id_with_scene),
            last_key,
            self._key_resource_cats(session_id_with_scene, resource_key),
        ]
        await self._refresh_ttl(session_id=session_id_with_scene, resource_key=resource_key, category=category, keys=keys_to_refresh)
        await self._touch_session(session_id=session_id_with_scene, now=now)

        if value is None:
            return None
        
        result = json.loads(value)
        if settings.debug_config.log_cache_operations:
            logger.error(f"===== PARSED RESULT DEBUG =====")
            logger.error(f"Parsed result keys: {result.keys() if isinstance(result, dict) else 'not a dict'}")
            if isinstance(result, dict) and 'payload' in result:
                payload = result.get('payload', {})
                logger.error(f"Payload _strategy: {payload.get('_strategy')}, _model: {payload.get('_model')}")
            logger.error(f"===== END PARSED RESULT DEBUG =====")
        return result

    async def list_resources(self, *, session_id: str, limit: int = 100, scene:str="") -> list[str]:
        # Convert scene to string if it's not already (handles int scene IDs)
        scene_str = str(scene) if scene else ""
        session_id_with_scene = f"{session_id}_{scene_str}"
        
        self._metrics["list_resources_calls"] += 1
        redis_client = self._require_redis()
        now = int(time.time())

        zset_key = self._key_resources_zset(session_id_with_scene)
        map_key = self._key_resources_map(session_id_with_scene)

        resource_keys = await redis_client.zrevrange(zset_key, 0, max(0, limit - 1))
        if not resource_keys:
            self._metrics["sqlite_fallback_loads"] += 1
            await self._load_resources_from_sqlite(session_id=session_id_with_scene)
            resource_keys = await redis_client.zrevrange(zset_key, 0, max(0, limit - 1))

        if not resource_keys:
            return []

        values = await redis_client.hmget(map_key, *resource_keys)
        await self._refresh_ttl(session_id=session_id_with_scene, keys=[zset_key, map_key])
        await self._touch_session(session_id=session_id_with_scene, now=now)

        return [v for v in values if isinstance(v, str) and v]

    def _require_redis(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("SessionCategorizedCacheService is not started")
        return self._redis

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SessionCategorizedCacheService is not started")
        return self._db

    async def _ensure_schema(self) -> None:
        db = self._require_db()
        async with self._db_lock:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_sessions (
                    session_id TEXT PRIMARY KEY,
                    last_active_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_resources (
                    session_id TEXT NOT NULL,
                    resource_key TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    last_active_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(session_id, resource_key)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    resource_key TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_events_session_category_id ON cache_events(session_id, category, id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_events_session_resource_category_id ON cache_events(session_id, resource_key, category, id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_sessions_last_active_at ON cache_sessions(last_active_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_resources_last_active_at ON cache_resources(last_active_at)"
            )
            await db.commit()

    async def _touch_session(self, *, session_id: str, now: int) -> None:
        db = self._require_db()
        async with self._db_lock:
            await db.execute(
                """
                INSERT INTO cache_sessions(session_id, last_active_at, created_at)
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET last_active_at=excluded.last_active_at
                """,
                (session_id, now, now),
            )
            await db.commit()

    async def _persist_event(
        self,
        *,
        session_id: str,
        category: str,
        resource: str,
        resource_key: str,
        ts: int,
        payload_str: str,
    ) -> None:
        db = self._require_db()
        async with self._db_lock:
            await db.execute(
                """
                INSERT INTO cache_sessions(session_id, last_active_at, created_at)
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET last_active_at=excluded.last_active_at
                """,
                (session_id, ts, ts),
            )
            await db.execute(
                """
                INSERT INTO cache_resources(session_id, resource_key, resource, last_active_at, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(session_id, resource_key) DO UPDATE SET
                    resource=excluded.resource,
                    last_active_at=excluded.last_active_at
                """,
                (session_id, resource_key, resource, ts, ts),
            )
            await db.execute(
                "INSERT INTO cache_events(session_id, category, resource_key, ts, payload) VALUES(?, ?, ?, ?, ?)",
                (session_id, category, resource_key, ts, payload_str),
            )

            if self._timeline_max_items > 0:
                await db.execute(
                    """
                    DELETE FROM cache_events
                    WHERE id NOT IN (
                        SELECT id FROM cache_events
                        WHERE session_id = ? AND category = ?
                        ORDER BY id DESC
                        LIMIT ?
                    )
                      AND session_id = ? AND category = ?
                    """,
                    (session_id, category, self._timeline_max_items, session_id, category),
                )

            await db.commit()

    async def _recover_to_redis(self) -> None:
        redis_client = self._require_redis()
        db = self._require_db()
        now = int(time.time())
        threshold = now - self._ttl_seconds

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT session_id, last_active_at FROM cache_sessions WHERE last_active_at >= ?",
                (threshold,),
            )
            sessions = await cursor.fetchall()

        for session_id, last_active_at in sessions:
            remaining_ttl = max(1, self._ttl_seconds - (now - int(last_active_at)))
            await self._recover_one_session_to_redis(session_id=str(session_id), remaining_ttl=remaining_ttl)
            self._metrics["recovered_sessions"] += 1

        logger.info("SessionCategorizedCacheService recovered sessions=%s", len(sessions))

        # Refresh TTL for recovered keys is handled per-session.
        await redis_client.ping()

    async def _recover_one_session_to_redis(self, *, session_id: str, remaining_ttl: int) -> None:
        redis_client = self._require_redis()
        db = self._require_db()

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT resource_key, resource, last_active_at FROM cache_resources WHERE session_id = ? ORDER BY last_active_at DESC",
                (session_id,),
            )
            rows = await cursor.fetchall()

        zset_key = self._key_resources_zset(session_id)
        map_key = self._key_resources_map(session_id)
        await redis_client.delete(zset_key)
        await redis_client.delete(map_key)

        if rows:
            zadd_payload: dict[str, float] = {}
            hmset_payload: dict[str, str] = {}
            for resource_key, resource, last_active_at in rows:
                zadd_payload[str(resource_key)] = float(int(last_active_at))
                hmset_payload[str(resource_key)] = str(resource)

            await redis_client.zadd(zset_key, zadd_payload)
            await redis_client.hset(map_key, mapping=hmset_payload)

        await redis_client.expire(zset_key, remaining_ttl)
        await redis_client.expire(map_key, remaining_ttl)

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT DISTINCT category FROM cache_events WHERE session_id = ?",
                (session_id,),
            )
            categories = [str(r[0]) for r in await cursor.fetchall()]

        for category in categories:
            await self._recover_one_timeline_to_redis(
                session_id=session_id,
                category=category,
                remaining_ttl=remaining_ttl,
            )


    async def _recover_one_timeline_to_redis(self, *, session_id: str, category: str, remaining_ttl: int) -> None:
        redis_client = self._require_redis()
        db = self._require_db()

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT resource_key, ts, payload FROM cache_events WHERE session_id = ? AND category = ? ORDER BY id ASC",
                (session_id, category),
            )
            rows = await cursor.fetchall()

        timeline_key = self._key_timeline(session_id, category)
        await redis_client.delete(timeline_key)

        if rows:
            events: list[str] = []
            last_per_resource: dict[str, str] = {}
            for resource_key, ts, payload_str in rows:
                event = {
                    "ts": int(ts),
                    "resource_key": str(resource_key),
                    "category": category,
                    "payload": json.loads(payload_str),
                }
                event_str = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                events.append(event_str)
                last_per_resource[str(resource_key)] = event_str

            await redis_client.rpush(timeline_key, *events)
            if self._timeline_max_items > 0:
                await redis_client.ltrim(timeline_key, -self._timeline_max_items, -1)

            # Rebuild S3/S4 from last_per_resource
            for resource_key, event_str in last_per_resource.items():
                last_key = self._key_last(session_id, resource_key, category)
                cats_key = self._key_resource_cats(session_id, resource_key)
                await redis_client.set(last_key, event_str)
                await redis_client.hset(cats_key, category, event_str)
                await redis_client.expire(last_key, remaining_ttl)
                await redis_client.expire(cats_key, remaining_ttl)

        await redis_client.expire(timeline_key, remaining_ttl)

    async def _load_resources_from_sqlite(self, *, session_id: str) -> None:
        db = self._require_db()
        redis_client = self._require_redis()

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT resource_key, resource, last_active_at FROM cache_resources WHERE session_id = ? ORDER BY last_active_at DESC",
                (session_id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            return

        zset_key = self._key_resources_zset(session_id)
        map_key = self._key_resources_map(session_id)

        zadd_payload: dict[str, float] = {}
        hmset_payload: dict[str, str] = {}
        for resource_key, resource, last_active_at in rows:
            zadd_payload[str(resource_key)] = float(int(last_active_at))
            hmset_payload[str(resource_key)] = str(resource)

        await redis_client.zadd(zset_key, zadd_payload)
        await redis_client.hset(map_key, mapping=hmset_payload)

    async def _load_timeline_from_sqlite(self, *, session_id: str, category: str) -> None:
        db = self._require_db()
        redis_client = self._require_redis()

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT resource_key, ts, payload FROM cache_events WHERE session_id = ? AND category = ? ORDER BY id ASC",
                (session_id, category),
            )
            rows = await cursor.fetchall()

        if not rows:
            return

        timeline_key = self._key_timeline(session_id, category)
        await redis_client.delete(timeline_key)

        last_per_resource: dict[str, str] = {}
        events: list[str] = []
        for resource_key, ts, payload_str in rows:
            event = {
                "ts": int(ts),
                "resource_key": str(resource_key),
                "category": category,
                "payload": json.loads(payload_str),
            }
            event_str = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            events.append(event_str)
            last_per_resource[str(resource_key)] = event_str

        await redis_client.rpush(timeline_key, *events)
        if self._timeline_max_items > 0:
            await redis_client.ltrim(timeline_key, -self._timeline_max_items, -1)

        for resource_key, event_str in last_per_resource.items():
            last_key = self._key_last(session_id, resource_key, category)
            cats_key = self._key_resource_cats(session_id, resource_key)
            await redis_client.set(last_key, event_str)
            await redis_client.hset(cats_key, category, event_str)

    async def _load_resource_indexes_from_sqlite(self, *, session_id: str, resource_key: str) -> None:
        db = self._require_db()
        redis_client = self._require_redis()

        async with self._db_lock:
            cursor = await db.execute(
                """
                SELECT category, ts, payload
                FROM cache_events
                WHERE session_id = ? AND resource_key = ?
                ORDER BY id ASC
                """,
                (session_id, resource_key),
            )
            rows = await cursor.fetchall()

        if not rows:
            return

        latest: dict[str, str] = {}
        for category, ts, payload_str in rows:
            event = {
                "ts": int(ts),
                "resource_key": resource_key,
                "category": str(category),
                "payload": json.loads(payload_str),
            }
            event_str = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            latest[str(category)] = event_str

        cats_key = self._key_resource_cats(session_id, resource_key)
        await redis_client.hset(cats_key, mapping=latest)

        for category, event_str in latest.items():
            last_key = self._key_last(session_id, resource_key, category)
            await redis_client.set(last_key, event_str)

    async def _refresh_ttl(
        self,
        *,
        session_id: str,
        keys: list[str],
        category: str | None = None,
        resource_key: str | None = None,
    ) -> None:
        redis_client = self._require_redis()
        for key in keys:
            await redis_client.expire(key, self._ttl_seconds)

    async def _cleanup_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._cleanup_interval_seconds)
            except TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            await self._cleanup_expired_sessions()

    async def _cleanup_expired_sessions(self) -> None:
        self._metrics["cleanup_runs"] += 1
        db = self._require_db()
        threshold = int(time.time()) - self._ttl_seconds

        async with self._db_lock:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM cache_sessions WHERE last_active_at < ?",
                (threshold,),
            )
            row = await cursor.fetchone()
            count = int(row[0]) if row else 0

            await db.execute("DELETE FROM cache_sessions WHERE last_active_at < ?", (threshold,))
            await db.execute("DELETE FROM cache_resources WHERE last_active_at < ?", (threshold,))

            await db.execute(
                """
                DELETE FROM cache_events
                WHERE session_id NOT IN (SELECT session_id FROM cache_sessions)
                """
            )
            await db.commit()

        if count:
            self._metrics["cleaned_sessions"] += count
            logger.info("SessionCategorizedCacheService cleaned expired sessions=%s", count)

    async def clear_by_session(self, session_id: str) -> None:
        redis_client = self._require_redis()

        await redis_client.delete(self._key_resources_zset(session_id))
        await redis_client.delete(self._key_resources_map(session_id))

        db = self._require_db()
        async with self._db_lock:
            await db.execute("DELETE FROM cache_events WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM cache_resources WHERE session_id = ?", (session_id,))
            await db.execute("DELETE FROM cache_sessions WHERE session_id = ?", (session_id,))
            await db.commit()

    async def clear_resource(self, *, session_id: str, resource: str) -> None:
        redis_client = self._require_redis()
        resource_key = self._resource_key(resource)

        await redis_client.zrem(self._key_resources_zset(session_id), resource_key)
        await redis_client.hdel(self._key_resources_map(session_id), resource_key)
        await redis_client.delete(self._key_resource_cats(session_id, resource_key))

        db = self._require_db()
        async with self._db_lock:
            await db.execute(
                "DELETE FROM cache_resources WHERE session_id = ? AND resource_key = ?",
                (session_id, resource_key),
            )
            await db.execute(
                "DELETE FROM cache_events WHERE session_id = ? AND resource_key = ?",
                (session_id, resource_key),
            )
            await db.commit()
