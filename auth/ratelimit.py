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
        # v1.9.1: kova temizliği — bir kovanın dolma süresi geçtikçe ara ara (bellek büyümez)
        last_sweep = getattr(self, "_last_sweep", None)
        if last_sweep is None:
            self._last_sweep = now
        elif self.refill_per_sec > 0 and now - last_sweep >= self.capacity / self.refill_per_sec:
            self._sweep(now)
            self._last_sweep = now
        tokens, last = self._buckets.get(key, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - 1.0, now)
        return True

    def _sweep(self, now: float) -> None:
        """Dolmuş (= varsayılan durumla aynı) kovaları sil: silmek davranışı değiştirmez, bellek büyümez."""
        if self.refill_per_sec <= 0:
            return
        full_after = self.capacity / self.refill_per_sec
        for k in [k for k, (_, last) in self._buckets.items() if now - last >= full_after]:
            del self._buckets[k]
