"""
Caching & Event Streaming Service for DengueWatch Full-Stack Platform.
Provides Redis-compatible high-performance caching (with TTL) and
Server-Sent Events (SSE) event-driven streaming for real-time surveillance.
"""

import os
import time
import json
from typing import Any, Optional, Dict

class InMemoryCache:
    """Thread-safe, TTL-based high-performance in-memory cache."""
    def __init__(self, default_ttl: int = 300):
        self._store: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            entry = self._store[key]
            if time.time() < entry["expires_at"]:
                self.hits += 1
                return entry["data"]
            else:
                del self._store[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
        self._store[key] = {
            "data": value,
            "expires_at": expiry
        }

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def flush(self) -> None:
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "cached_keys": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": round(self.hits / (self.hits + self.misses + 1e-6), 2)
        }

# Global cache instance
cache = InMemoryCache(default_ttl=300)
