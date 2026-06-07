"""core/integrations/wikimedia.py — Wikimedia Commons API entegrasyonu (SSRF korumalı)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx

from auth.ssrf import assert_safe_url, safe_fetch_asset
from .base import Provenance, ProvenanceAdapter

logger = logging.getLogger(__name__)

WIKIMEDIA_API_BASE = "https://commons.wikimedia.org/w/api.php"

class WikimediaAdapter(ProvenanceAdapter):
    """Wikimedia Commons (CC0/PD) görsel arama adaptörü."""

    async def fetch(self, query: str, **kwargs) -> tuple[Optional[bytes], Optional[Provenance]]:
        """
        Wikimedia Commons üzerinden CC0/Public Domain görsel arar.
        Graceful degrade: Hata durumunda (None, None) döner.
        """
        try:
            # 1. API Araması (Generator search)
            # iiprop=url|extmetadata ile URL ve lisans bilgisini alıyoruz.
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"File:{query}",
                "gsrnamespace": 6,  # File namespace
                "gsrlimit": 5,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|UsageTerms|Artist",
            }
            
            query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
            search_url = f"{WIKIMEDIA_API_BASE}?{query_string}"
            
            assert_safe_url(search_url)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    logger.warning(f"Wikimedia API hatası: {resp.status_code}")
                    return None, None
                
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                
                for page_id, page_data in pages.items():
                    imageinfo = page_data.get("imageinfo", [])
                    if not imageinfo:
                        continue
                    
                    info = imageinfo[0]
                    metadata = info.get("extmetadata", {})
                    
                    license_name = metadata.get("LicenseShortName", {}).get("value", "").lower()
                    
                    # Yalnızca CC0 ve Public Domain kabul edilir.
                    source = None
                    if license_name in ("cc0", "pd", "public domain"):
                        source = "cc0" if license_name == "cc0" else "public-domain"
                    else:
                        # Bazı durumlarda UsageTerms daha açıklayıcı olabilir.
                        usage_terms = metadata.get("UsageTerms", {}).get("value", "").lower()
                        if "public domain" in usage_terms:
                            source = "public-domain"
                        elif "cc0" in usage_terms:
                            source = "cc0"
                    
                    if not source:
                        continue
                        
                    img_url = info.get("url")
                    if not img_url:
                        continue

                    # 2. Görseli Güvenli Şekilde Çek
                    content, mime = await safe_fetch_asset(img_url, max_bytes=5 * 1024 * 1024)
                    
                    # 3. Provenance Kaydı
                    provenance = Provenance(
                        source=source,
                        license=license_name.upper() or "PD",
                        url=img_url,
                        author=metadata.get("Artist", {}).get("value"),
                        retrieved_at=datetime.now().strftime("%Y-%m-%d"),
                        license_url=info.get("descriptionurl") # Detay sayfası
                    )
                    
                    return content, provenance

                return None, None

        except Exception as e:
            logger.error(f"Wikimedia fetch hatası (sessiz): {e}")
            return None, None
