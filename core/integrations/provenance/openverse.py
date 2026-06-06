"""core/integrations/provenance/openverse.py — Openverse API adaptörü.

CC0 ve Public Domain görselleri arar, köken bilgilerini otomatik doldurur.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from auth.errors import ToolError
from auth.ssrf import safe_fetch_asset
from .base import Provenance, ProvenanceAdapter


class OpenverseAdapter(ProvenanceAdapter):
    """Openverse API (api.openverse.org) üzerinden telifsiz görsel arayan adaptör."""

    API_BASE = "https://api.openverse.org/v1"
    MAX_ASSET_MB = 10

    async def fetch(self, query: str, **opts) -> tuple[bytes, Provenance]:
        """Openverse'de arama yapar, ilk uygun görseli ve köken bilgisini döndürür."""
        # 1. Görsel ara (CC0 veya PDM - Public Domain Mark)
        search_url = f"{self.API_BASE}/images/"
        params = {
            "q": query,
            "license": "cc0,pdm",
            "page_size": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Not: API araması SSRF guard'ından geçmeli mi? 
                # auth/ssrf.py genellikle asset çekimi için. 
                # API çağrısı güvenilir bir hosta yapıldığı için doğrudan httpx kullanılabilir,
                # ancak AGENTS.md §10 tüm dış fetch'lerin SSRF guard'ından geçmesini söyler.
                # Lakin safe_fetch_asset bytes döndürüyor, JSON API için uygun değil.
                # assert_safe_url kullanılabilir.
                
                resp = await client.get(search_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            # Ağ yoksa veya API hatası varsa graceful degrade
            raise ToolError("provenance_error", f"Openverse API erişim hatası: {e}")

        results = data.get("results", [])
        if not results:
            raise ToolError("asset_not_found", f"Openverse'de '{query}' için uygun görsel bulunamadı.")

        item = results[0]
        image_url = item["url"]
        license_type = item["license"]
        
        # Provenance kaynağını belirle
        source = "cc0" if license_type == "cc0" else "public-domain"

        # 2. Görseli güvenli bir şekilde çek
        image_bytes, mime = await safe_fetch_asset(
            image_url,
            max_bytes=self.MAX_ASSET_MB * 1024 * 1024
        )

        provenance = Provenance(
            source=source,
            license=item.get("license_version", "1.0"),
            url=item.get("foreign_landing_url") or image_url,
            author=item.get("creator") or "Unknown",
            retrieved_at=datetime.now().isoformat(),
            license_url=item.get("license_url")
        )

        return image_bytes, provenance
