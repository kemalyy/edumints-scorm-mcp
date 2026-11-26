"""auth/keys.py — Çoklu API-key doğrulama + kota (CONTRACTS.md §4, §6).

Anahtarlar SQLite'ta sha256 hash olarak tutulur (ham anahtar saklanmaz). Her anahtarın
kotası (max proje, max toplam MB) ve opsiyonel son kullanma tarihi vardır.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
from datetime import timezone

from core.project import utcnow
from core.store import ApiKey, Store

from .errors import ToolError


def key_rejection(key: ApiKey | None) -> str | None:
    """v1.9.1 — anahtar geçerliliğinin TEK doğruluk kaynağı: MCP (ApiKeyVerifier) ve özel HTTP
    rotaları (verify_key) aynı kuralı uygular. Geçerliyse None, değilse ret gerekçesi."""
    if key is None:
        return "Geçersiz API anahtarı"
    if key.disabled:
        return "API anahtarı devre dışı"
    if key.expires_at is not None:
        exp = key.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < utcnow():
            return "API anahtarının süresi dolmuş"
    return None


async def verify_key(store: Store, raw_key: str | None) -> ApiKey:
    if not raw_key:
        raise ToolError("unauthorized", "API anahtarı gerekli (Authorization: Bearer ...)")
    key = await store.get_key(raw_key)
    reason = key_rejection(key)
    if reason:
        raise ToolError("unauthorized", reason)
    await store.touch_key(key.id)
    return key


# v1.9.1 — atomik kota: principal başına kilit altında "okunan kullanım + bekleyen rezervasyonlar +
# istenen" kontrol edilir ve istenen miktar REZERVE edilir. Rezervasyon, çağrı kapsamı (araç çağrısı;
# `reservation_scope`) bitince serbest kalır — o noktada yazma DB'ye işlenmiştir. Tek-node varsayımı
# (süreç içi); çoklu replica'da DB düzeyi rezervasyon gerekir (KNOWN-LIMITATIONS).
_quota_locks: dict[tuple[int, str], asyncio.Lock] = {}
_reserved: dict[str, list[int]] = {}  # principal → [bekleyen bayt, bekleyen proje]
_scope: contextvars.ContextVar[list | None] = contextvars.ContextVar("quota_scope", default=None)


def _lock(pid: str) -> asyncio.Lock:
    # event loop'a bağlı (asyncio.Lock döngüler arası paylaşılamaz)
    return _quota_locks.setdefault((id(asyncio.get_running_loop()), pid), asyncio.Lock())


@contextlib.contextmanager
def reservation_scope():
    """Bir araç çağrısı boyunca alınan rezervasyonları toplar; çıkışta hepsini bırakır."""
    held: list[tuple[str, int, int]] = []
    token = _scope.set(held)
    try:
        yield
    finally:
        _scope.reset(token)
        for pid, b, n in held:
            r = _reserved.get(pid)
            if r:
                r[0] -= b
                r[1] -= n
                if r[0] <= 0 and r[1] <= 0:
                    _reserved.pop(pid, None)


def _reserve(pid: str, add_bytes: int, add_projects: int) -> None:
    held = _scope.get()
    if held is None:  # kapsam dışı çağrı (ör. doğrudan iç kullanım): yalnız kilitli kontrol
        return
    r = _reserved.setdefault(pid, [0, 0])
    r[0] += add_bytes
    r[1] += add_projects
    held.append((pid, add_bytes, add_projects))


async def enforce_project_quota(store: Store, key: ApiKey) -> None:
    lock = _lock(key.id)
    async with lock:
        count = await store.count_projects(key.id) + _reserved.get(key.id, [0, 0])[1]
        if count >= key.max_projects:
            raise ToolError(
                "quota_exceeded",
                f"Proje kotası aşıldı ({count}/{key.max_projects})",
                {"limit": key.max_projects, "current": count},
            )
        _reserve(key.id, 0, 1)


async def enforce_size_quota(store: Store, key: ApiKey, add_bytes: int) -> None:
    lock = _lock(key.id)
    async with lock:
        current = await store.total_bytes(key.id) + _reserved.get(key.id, [0, 0])[0]
        limit = key.max_total_mb * 1024 * 1024
        if current + add_bytes > limit:
            raise ToolError(
                "quota_exceeded",
                f"Boyut kotası aşıldı ({(current + add_bytes) // (1024*1024)}MB / {key.max_total_mb}MB)",
                {"limit_mb": key.max_total_mb},
            )
        _reserve(key.id, max(add_bytes, 0), 0)


def parse_bearer(headers: dict[str, str]) -> str | None:
    """Authorization: Bearer <key> → raw key. Header isimleri küçük harfe normalize varsayılır."""
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth:
        # bazı bağlayıcılar özel header kullanır
        return headers.get("x-api-key") or headers.get("X-API-Key")
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return auth.strip() or None
