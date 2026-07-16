from __future__ import annotations

import copy
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCacheStore:
    def __init__(self, max_entries: int = 256) -> None:
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired_keys = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)

    def get(self, key: str):
        with self._lock:
            self._purge_expired_locked()
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return copy.deepcopy(entry.value)

    def set(self, key: str, value, ttl_seconds: int) -> None:
        with self._lock:
            self._purge_expired_locked()
            self._entries[key] = CacheEntry(
                value=copy.deepcopy(value),
                expires_at=time.time() + ttl_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict:
        with self._lock:
            self._purge_expired_locked()
            return {
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
            }


_CACHE = TTLCacheStore(max_entries=512)
_REQUEST_CACHE_LOCAL = threading.local()


def make_cache_key(namespace: str, payload) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{namespace}:{blob}"


def cached_call(
    *,
    namespace: str,
    payload,
    ttl_seconds: int,
    bypass: bool,
    producer: Callable[[], T],
) -> T:
    key = make_cache_key(namespace, payload)
    if not bypass:
        cached = _CACHE.get(key)
        if cached is not None:
            _record_request_cache_event(f"{namespace}:hit")
            return cached
    _record_request_cache_event(f"{namespace}:miss")
    value = producer()
    _CACHE.set(key, value, ttl_seconds)
    return copy.deepcopy(value)


def clear_cache() -> None:
    _CACHE.clear()


def get_cache_stats() -> dict:
    return _CACHE.stats()


def reset_request_cache_events() -> None:
    _REQUEST_CACHE_LOCAL.events = []


def get_request_cache_events() -> list[str]:
    return list(getattr(_REQUEST_CACHE_LOCAL, "events", []))


def _record_request_cache_event(event: str) -> None:
    current = list(getattr(_REQUEST_CACHE_LOCAL, "events", []))
    current.append(event)
    _REQUEST_CACHE_LOCAL.events = current
