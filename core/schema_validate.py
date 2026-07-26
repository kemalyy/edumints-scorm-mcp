"""core/schema_validate.py — imsmanifest.xml'i resmi SCORM XSD'lerine karşı doğrular (Faz 1).

Tasarım:
- **ADL şemaları vendor** (`runtime/schemas/adl/`, kamu malı) + ince **driver** XSD'ler.
- **IMS/W3C şemaları vendor EDİLMEZ** (lisans) → runtime'da imsglobal.org/w3.org'dan **FETCH + cache**
  (`runtime/schemas/ims_sources.json`'daki URL + sha256 ile). **Offline override:** `SCORM_SCHEMA_DIR`
  ayarlıysa tüm şemalar oradan okunur, hiç fetch yapılmaz (hava-boşluklu kurulum).
- **Doğrulama tamamen DİSKTEN, ağa çıkmadan** yapılır (`no_network=True` + mutlak `xml.xsd` import'u
  yerele yeniden yazılır). Ağ yalnız cache'i ilk doldururken kullanılır.
- Şema yoksa/fetch başarısızsa **graceful degrade**: `schema_unavailable` UYARISI döner (sessiz geçmez),
  paket build'i bloklanmaz.

XSD doğrulaması DESTEKLEYİCİ bir iç kontroldür; conformance'ın **gating** kanıtı SCORM Cloud'dur
(bkz. docs/CONFORMANCE.md).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from .project import ValidationError

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "runtime" / "schemas"
_ADL_DIR = _SCHEMAS_DIR / "adl"
_DRIVER = {"1.2": "driver_12.xsd", "2004": "driver_2004.xsd"}
_VER_KEY = {"1.2": "12", "2004": "2004"}
# Bazı IMS şemaları (ör. imsmd_v1p2p4.xsd) xml.xsd'yi "/2001/03/xml.xsd" varyantıyla import eder;
# ikisi de aynı yerel "xml.xsd" cache dosyasına yeniden yazılır (S7 / 2.3).
_W3_XML_RE = re.compile(r"http://www\.w3\.org/2001(?:/03)?/xml\.xsd")

SCHEMA_UNAVAILABLE = "schema_unavailable"   # UYARI kodu (build'i bloklamaz)
CONFORMANCE_ERROR = "conformance_error"     # gerçek XSD ihlali


def _cache_root() -> Path:
    override = os.environ.get("SCORM_SCHEMA_DIR")
    if override:
        return Path(override)
    base = os.environ.get("DATA_DIR") or tempfile.gettempdir()
    return Path(base) / "scorm_schemas"


def _resolved_dir(version: str) -> Path:
    return _cache_root() / _VER_KEY[version]


def _ims_sources() -> dict:
    try:
        return json.loads((_SCHEMAS_DIR / "ims_sources.json").read_text("utf-8")).get("schemas", {})
    except Exception:
        return {}


def _ensure_populated(version: str) -> Path | None:
    """Çözümlenmiş şema dizinini (ADL + driver + fetched IMS) hazırlar. Hazırsa yolu, değilse None."""
    rd = _resolved_dir(version)
    driver = rd / _DRIVER[version]
    if driver.exists():               # offline override ya da önceki cache
        return rd
    # offline override ayarlıysa ama driver yoksa → kullanıcı eksik yerleştirmiş; fetch deneme
    if os.environ.get("SCORM_SCHEMA_DIR"):
        return None
    try:
        rd.mkdir(parents=True, exist_ok=True)
        # vendored ADL + driver (flat kopya)
        for x in _ADL_DIR.glob("*.xsd"):
            shutil.copy2(x, rd / x.name)
        shutil.copy2(_SCHEMAS_DIR / _DRIVER[version], driver)
        # IMS/W3C fetch (yalnız cache doldururken ağ)
        import httpx
        srcs = _ims_sources().get(_VER_KEY[version], {})
        # Sıkı timeout: CI/ağ erişilemezse hızlı fail → graceful schema_unavailable (asılı kalma yok).
        _to = httpx.Timeout(20.0, connect=8.0)
        with httpx.Client(timeout=_to, follow_redirects=True) as c:
            for fn, info in srcs.items():
                data = c.get(info["url"]).content
                want = info.get("sha256")
                if want and hashlib.sha256(data).hexdigest() != want:
                    # integrity yumuşak: uyumsuzlukta yine yaz ama işaretle (standart şemalar dondurulmuş)
                    (rd / "INTEGRITY_MISMATCH.txt").write_text(
                        f"{fn}: beklenen {want}\n", encoding="utf-8")
                text = _W3_XML_RE.sub("xml.xsd", data.decode("utf-8", "ignore"))
                (rd / fn).write_text(text, encoding="utf-8")
        return rd if driver.exists() else None
    except Exception:
        # ağ yok / fetch hata → graceful degrade
        return None


@lru_cache(maxsize=4)
def _compiled_schema(version: str):
    rd = _ensure_populated(version)
    if rd is None:
        return None
    try:
        from lxml import etree
        parser = etree.XMLParser(no_network=True)          # ağa ASLA çıkma
        return etree.XMLSchema(etree.parse(str(rd / _DRIVER[version]), parser))
    except Exception:
        return None


def validate_manifest_xsd(manifest_bytes: bytes, scorm_version: str) -> list[ValidationError]:
    """imsmanifest.xml → resmi XSD doğrulaması. Gerçek ihlal → conformance_error; şema yoksa →
    schema_unavailable UYARISI (build'i bloklamaz). Tamamen offline (no_network)."""
    if scorm_version not in _DRIVER:
        return []
    schema = _compiled_schema(scorm_version)
    if schema is None:
        return [ValidationError(
            code=SCHEMA_UNAVAILABLE,
            message=("SCORM XSD şemaları indirilemedi/bulunamadı — yalnız yapısal kontrol yapıldı. "
                     "Çevrimdışı kullanım için SCORM_SCHEMA_DIR ayarlayın."),
            path="imsmanifest.xml")]
    from lxml import etree
    try:
        doc = etree.fromstring(manifest_bytes)
    except Exception as e:  # noqa: BLE001
        return [ValidationError(code=CONFORMANCE_ERROR,
                                message=f"imsmanifest.xml ayrıştırılamadı: {e}", path="imsmanifest.xml")]
    if schema.validate(doc):
        return []
    out: list[ValidationError] = []
    for e in list(schema.error_log)[:20]:
        out.append(ValidationError(code=CONFORMANCE_ERROR,
                                   message=re.sub(r"\s+", " ", e.message)[:240],
                                   path=f"imsmanifest.xml:{e.line}"))
    return out
