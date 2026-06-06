"""core/integrations/provenance/base.py — Telifsiz medya köken şeması ve arayüzü.

AGENTS.md §11 ve §9 uyarınca her ikili asset için köken kaydı zorunludur.
İzinli kaynaklar: ai-generated, cc0, public-domain, own, local.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from auth.errors import ToolError

ALLOWED_SOURCES = ["ai-generated", "cc0", "public-domain", "own", "local"]
SourceType = Literal["ai-generated", "cc0", "public-domain", "own", "local"]


class Provenance(BaseModel):
    """Asset köken (provenance) bilgisi."""

    source: SourceType
    license: str
    url: str | None = None
    author: str | None = ""
    retrieved_at: str  # ISO 8601 formatı önerilir
    license_url: str | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"Geçersiz kaynak: {v}. İzin verilenler: {ALLOWED_SOURCES}")
        return v


def validate_provenance(asset_manifest: dict[str, Provenance | dict]) -> None:
    """Asset manifestindeki tüm kayıtların geçerli köken bilgilerine sahip olduğunu doğrular.

    Geçersiz bir kaynak veya eksik bilgi durumunda ToolError fırlatır.
    """
    for asset_path, prov_data in asset_manifest.items():
        try:
            if isinstance(prov_data, dict):
                Provenance(**prov_data)
            elif isinstance(prov_data, Provenance):
                # Pydantic model ise zaten validate edilmiştir ama yine de kontrol
                pass
            else:
                raise ToolError(
                    "provenance_error", f"Asset {asset_path} için geçersiz köken veri tipi"
                )
        except Exception as e:
            raise ToolError("provenance_error", f"Asset {asset_path} köken doğrulaması başarısız: {e}")


class ProvenanceAdapter(ABC):
    """Dış kaynaklardan asset ve köken bilgisi çeken adaptörler için taban sınıf."""

    @abstractmethod
    async def fetch(self, query_or_path: str, **opts) -> tuple[bytes, Provenance]:
        """Belirtilen sorgu veya yoldan asset verisini ve köken bilgisini çeker."""
