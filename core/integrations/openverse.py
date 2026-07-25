"""core/integrations/openverse.py — Openverse API entegrasyonu (SSRF korumalı)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx

from auth.ssrf import assert_safe_url, safe_fetch_asset
from .base import Provenance, ProvenanceAdapter

logger = logging.getLogger(__name__)

OPENVERSE_API_BASE = "https://api.openverse.org/v1"

class OpenverseAdapter(ProvenanceAdapter):
    """Openverse (CC0/PD) görsel arama adaptörü."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def fetch(self, query: str, **kwargs) -> tuple[Optional[bytes], Optional[Provenance]]:
        """
        Openverse üzerinden CC0/Public Domain görsel arar ve en üstteki sonucu döner.
        Graceful degrade: Hata durumunda (None, None) döner.
        """
        try:
            # 1. API Araması
            # Sadece CC0 ve Public Domain (pdm) lisanslarını istiyoruz.
            search_url = f"{OPENVERSE_API_BASE}/images/?q={quote(query)}&license=cc0,pdm&page_size=1"
            
            # SSRF Guard: API URL'sini doğrula
            assert_safe_url(search_url)

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"Openverse API hatası: {resp.status_code}")
                    return None, None
                
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return None, None
                
                img_data = results[0]
                img_url = img_data.get("url")
                if not img_url:
                    return None, None

            # 2. Görseli Güvenli Şekilde Çek
            # safe_fetch_asset zaten assert_safe_url çağrısı yapar ve mime/boyut kontrolü sağlar.
            content, mime = await safe_fetch_asset(img_url, max_bytes=5 * 1024 * 1024) # 5MB limit

            # 3. Provenance Kaydı Oluştur
            provenance = Provenance(
                source="cc0" if img_data.get("license") == "cc0" else "public-domain",
                license=img_data.get("license", "cc0").upper(),
                url=img_url,
                author=img_data.get("creator"),
                retrieved_at=datetime.now().strftime("%Y-%m-%d"),
                license_url=img_data.get("license_url")
            )

            return content, provenance

        except Exception as e:
            logger.error(f"Openverse fetch hatası (sessiz): {e}")
            return None, None

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Openverse üzerinden CC0/Public Domain görsel ADAY listesi döner — İNDİRME YAPMAZ.
        Her öğe: {title, url, thumb_url?, width?, height?, license, license_url?, creator?,
        source_page?}. Graceful degrade: hata/boş durumda [] döner (mevcut fetch() felsefesi).
        """
        try:
            search_url = f"{OPENVERSE_API_BASE}/images/?q={quote(query)}&license=cc0,pdm&page_size={limit}"

            # SSRF Guard: API URL'sini doğrula
            assert_safe_url(search_url)

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(f"Openverse arama API hatası: {resp.status_code}")
                    return []

                data = resp.json()
                results = data.get("results", [])

            items: list[dict] = []
            for img_data in results:
                img_url = img_data.get("url")
                if not img_url:
                    continue
                license_value = img_data.get("license")
                if not license_value or str(license_value).lower() not in ("cc0", "pdm"):
                    # Lisans eksik VEYA CC0/PD ailesi dışında → öğeyi ATLA. Sorgu filtresine ek
                    # per-item savunma (Wikimedia simetrisi); yanlış etiketleme riskini kapatır.
                    continue
                items.append({
                    "title": img_data.get("title") or "",
                    "url": img_url,
                    "thumb_url": img_data.get("thumbnail"),
                    "width": img_data.get("width"),
                    "height": img_data.get("height"),
                    "license": license_value.upper(),
                    "license_url": img_data.get("license_url"),
                    "creator": img_data.get("creator"),
                    "source_page": img_data.get("foreign_landing_url"),
                })
            return items

        except Exception as e:
            logger.warning(f"Openverse search hatası (sessiz): {e}")
            return []
