"""core/integrations/generative_svg.py — Basit telifsiz inline-SVG üretici."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from .base import Provenance, ProvenanceAdapter

class GenerativeSVGAdapter(ProvenanceAdapter):
    """
    Basit geometrik SVG'ler üreten adaptör (Ağ kullanımı yok).
    Query'ye göre deterministik renk ve şekil üretir.
    """

    async def fetch(self, query: str, **kwargs) -> tuple[Optional[bytes], Optional[Provenance]]:
        """
        Query'yi hash'leyerek basit bir SVG ikonu döner.
        """
        try:
            # Deterministik renk seçimi
            h = hashlib.md5(query.encode()).hexdigest()
            color = f"#{h[:6]}"
            bg_color = f"#{h[6:12]}"
            
            # Basit bir SVG şablonu (Kare içinde daire/şekil)
            svg = f"""<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
                <rect width="100" height="100" fill="{bg_color}" />
                <circle cx="50" cy="50" r="40" fill="{color}" stroke="white" stroke-width="2" />
                <text x="50" y="55" font-family="Arial" font-size="12" fill="white" text-anchor="middle">{query[:10]}</text>
            </svg>"""
            
            content = svg.encode("utf-8")
            
            provenance = Provenance(
                source="ai-generated",
                license="CC0",
                author="GenerativeSVGAdapter",
                retrieved_at=datetime.now().strftime("%Y-%m-%d"),
                url=None,
                license_url=None
            )
            
            return content, provenance

        except Exception:
            return None, None
