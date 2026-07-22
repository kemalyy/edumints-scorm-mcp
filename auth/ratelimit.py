"""auth/ratelimit.py — basit in-process token-bucket rate limiter (W9 P0).

Redis/harici bağımlılık yok — tek-node deployment varsayımıyla process-içi dict. Principal
(owner.id) başına ayrı bucket. Thread-safe değil (asyncio tek event-loop'ta çağrılıyor, GIL
altında basit dict/float operasyonları için yeterli — ThreadPoolExecutor build worker'ları
buraya dokunmuyor, yalnız _owner() çağrısı, o da event loop'ta)."""
from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, capacity: int, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True
