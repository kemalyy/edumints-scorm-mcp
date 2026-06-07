"""core/integrations/base.py — Provenance modeli ve temel adaptör arayüzü (AGENTS.md §9, §11)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, Optional, Any

from pydantic import BaseModel, Field, field_validator

ALLOWED_SOURCES = ("ai-generated", "cc0", "public-domain", "own", "local")

class Provenance(BaseModel):
    """Her ikili medya varlığı için telif/kaynak kaydı."""
    source: Literal["ai-generated", "cc0", "public-domain", "own", "local"]
    license: str
    url: Optional[str] = None
    author: Optional[str] = None
    retrieved_at: Optional[str] = None  # YYYY-MM-DD
    license_url: Optional[str] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"İzin verilmeyen kaynak: {v}. Yalnızca {ALLOWED_SOURCES} kabul edilir.")
        return v

def validate_provenance(asset_manifest: dict[str, Any]) -> None:
    """
    Pakete giren tüm assetlerin geçerli bir provenance kaydı olup olmadığını denetler.
    Eksik veya geçersizse ValueError fırlatır.
    """
    for asset_path, provenance_data in asset_manifest.items():
        try:
            if not provenance_data:
                raise ValueError(f"Asset için provenance eksik: {asset_path}")
            Provenance.model_validate(provenance_data)
        except Exception as e:
            raise ValueError(f"Geçersiz provenance ({asset_path}): {e}") from e

class ProvenanceAdapter(ABC):
    """Dış kaynaklardan görsel/medya arama ve çekme için soyut temel sınıf."""

    @abstractmethod
    async def fetch(self, query: str, **kwargs) -> tuple[Optional[bytes], Optional[Provenance]]:
        """
        Dış kaynaktan veri çeker.
        (veri, provenance) döndürür. Sonuç yoksa (None, None).
        """
        pass
