"""Small cache abstraction: Redis when available, in-process TTL dict otherwise."""
import json
import logging
import threading
import time
from typing import Any

from app.core.config import get_settings

log = logging.getLogger(__name__)


class _MemoryBackend:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if item[0] < time.time():
                self._data.pop(key, None)
                return None
            return item[1]

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl, value)

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            exp, val = self._data.get(key, (time.time() + ttl, "0"))
            if exp < time.time():
                exp, val = time.time() + ttl, "0"
            new = int(val) + 1
            self._data[key] = (exp, str(new))
            return new

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for k in [k for k in self._data if k.startswith(prefix)]:
                self._data.pop(k, None)


class Cache:
    def __init__(self) -> None:
        self._redis = None
        self._memory = _MemoryBackend()
        url = get_settings().redis_url
        if url:
            try:
                import redis

                client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
                client.ping()
                self._redis = client
                log.info("Cache: using Redis at %s", url)
            except Exception as exc:  # pragma: no cover - depends on environment
                log.warning("Cache: Redis unavailable (%s); using in-memory cache", exc)

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

    def get_json(self, key: str) -> Any | None:
        raw = self._redis.get(key) if self._redis else self._memory.get(key)
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        raw = json.dumps(value, default=str)
        if self._redis:
            self._redis.set(key, raw, ex=ttl)
        else:
            self._memory.set(key, raw, ttl)

    def incr(self, key: str, ttl: int) -> int:
        if self._redis:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl, nx=True)
            return int(pipe.execute()[0])
        return self._memory.incr(key, ttl)

    def delete_prefix(self, prefix: str) -> None:
        if self._redis:
            for k in self._redis.scan_iter(f"{prefix}*"):
                self._redis.delete(k)
        else:
            self._memory.delete_prefix(prefix)


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


def invalidate_answer_cache() -> None:
    """Called whenever knowledge changes so cached answers never go stale."""
    get_cache().delete_prefix("answer:")
