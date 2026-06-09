"""auth/keys.py — Çoklu API-key doğrulama + kota (CONTRACTS.md §4, §6).

Anahtarlar SQLite'ta sha256 hash olarak tutulur (ham anahtar saklanmaz). Her anahtarın
kotası (max proje, max toplam MB) ve opsiyonel son kullanma tarihi vardır.
"""

from __future__ import annotations

from datetime import timezone

from core.project import utcnow
from core.store import ApiKey, Store

from .errors import ToolError


async def verify_key(store: Store, raw_key: str | None) -> ApiKey:
    if not raw_key:
        raise ToolError("unauthorized", "API anahtarı gerekli (Authorization: Bearer ...)")
    key = await store.get_key(raw_key)
    if key is None:
        raise ToolError("unauthorized", "Geçersiz API anahtarı")
    if key.disabled:
        raise ToolError("unauthorized", "API anahtarı devre dışı")
    if key.expires_at is not None:
        exp = key.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < utcnow():
            raise ToolError("unauthorized", "API anahtarının süresi dolmuş")
    await store.touch_key(key.id)
    return key


async def enforce_project_quota(store: Store, key: ApiKey) -> None:
    count = await store.count_projects(key.id)
    if count >= key.max_projects:
        raise ToolError(
            "quota_exceeded",
            f"Proje kotası aşıldı ({count}/{key.max_projects})",
            {"limit": key.max_projects, "current": count},
        )


async def enforce_size_quota(store: Store, key: ApiKey, add_bytes: int) -> None:
    current = await store.total_bytes(key.id)
    limit = key.max_total_mb * 1024 * 1024
    if current + add_bytes > limit:
        raise ToolError(
            "quota_exceeded",
            f"Boyut kotası aşıldı ({(current + add_bytes) // (1024*1024)}MB / {key.max_total_mb}MB)",
            {"limit_mb": key.max_total_mb},
        )


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
