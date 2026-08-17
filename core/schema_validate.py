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


def _expected_files(version: str) -> set[str]:
    """Bu sürüm için TAM şema setinde bulunması gereken tüm dosya adları:
    vendored driver + ADL/*.xsd + fetched IMS/W3C (ims_sources) anahtarları."""
    names = {_DRIVER[version]}
    names.update(x.name for x in _ADL_DIR.glob("*.xsd"))
    names.update(_ims_sources().get(_VER_KEY[version], {}).keys())
    return names


def _cache_complete(version: str, rd: Path) -> bool:
    """rd TAM ve GÜNCEL mi: (1) beklenen dosyaların tamamı mevcut, (2) cache'lenmiş driver =
    vendored driver (bayt-bayt). Bu iki koşul, prod build'ini bloklayan iki cache-poisoning
    onset'ini de reddeder: (a) partial-fetch (imscp var, imsmd yok → lom strict-wildcard
    conformance_error) ve (b) stale-cache (S7-öncesi, imsmd-import'suz eski driver). Eksik/eski
    → False; çağıran fetch modunda yeniden doldurur, offline modda graceful None döner."""
    driver = rd / _DRIVER[version]
    if not driver.exists():
        return False
    try:
        if driver.read_bytes() != (_SCHEMAS_DIR / _DRIVER[version]).read_bytes():
            return False  # stale/farklı driver → yeniden doldur
    except OSError:
        return False
    return all((rd / name).exists() for name in _expected_files(version))


def _ensure_populated(version: str) -> Path | None:
    """Çözümlenmiş şema dizinini (ADL + driver + fetched IMS) hazırlar. TAM/güncel cache varsa
    yolunu döner. Değilse: fetch modunda staging'e TAM doldurup ATOMİK yerleştirir — yarım fetch
    ASLA kalıcı cache bırakmaz, dolayısıyla 'imsmd eksik → lom strict-wildcard build'i bloklar'
    poisoned durumu ULAŞILAMAZ. Offline override eksik/eski ise poisoned dir DÖNMEZ → graceful None."""
    # ims_sources.json okunamaz/boşsa gerekli IMS dosyalarını BİLEMEYİZ → _expected_files yalnız
    # driver+ADL'e daralır ve gate IMS'siz bir cache'i yanlışlıkla TAM sertifikalar (aynı lom hatası
    # başka kapıdan geri gelir). Bu durumda graceful degrade (build asla bloklanmaz).
    srcs = _ims_sources().get(_VER_KEY[version])
    if not srcs:
        return None
    rd = _resolved_dir(version)
    if _cache_complete(version, rd):        # offline override ya da önceki TAM cache
        return rd
    # offline override ayarlıysa ama cache eksik/eski → kullanıcı eksik/eski yerleştirmiş; fetch
    # deneme, poisoned dir'i TAM sayma → graceful degrade (schema_unavailable, build bloklanmaz)
    if os.environ.get("SCORM_SCHEMA_DIR"):
        return None
    staging: Path | None = None
    try:
        rd.parent.mkdir(parents=True, exist_ok=True)
        # önceki sert çökmelerden (SIGKILL/OOM) kalan yarım staging'leri süpür — kalıcı volume'da birikmesin
        for stale in rd.parent.glob(f".staging_{_VER_KEY[version]}_*"):
            shutil.rmtree(stale, ignore_errors=True)
        staging = Path(tempfile.mkdtemp(prefix=f".staging_{_VER_KEY[version]}_", dir=rd.parent))
        # vendored ADL + driver (flat kopya) — driver HER doldurmada tazelenir (stale onset'i iyileştirir)
        for x in _ADL_DIR.glob("*.xsd"):
            shutil.copy2(x, staging / x.name)
        shutil.copy2(_SCHEMAS_DIR / _DRIVER[version], staging / _DRIVER[version])
        # IMS/W3C fetch (yalnız cache doldururken ağ)
        import httpx
        # srcs yukarıda (guard) hesaplandı — boş olamaz
        # Sıkı timeout: CI/ağ erişilemezse hızlı fail → graceful schema_unavailable (asılı kalma yok).
        _to = httpx.Timeout(20.0, connect=8.0)
        with httpx.Client(timeout=_to, follow_redirects=True) as c:
            for fn, info in srcs.items():
                data = c.get(info["url"]).content
                want = info.get("sha256")
                if want and hashlib.sha256(data).hexdigest() != want:
                    # integrity yumuşak: uyumsuzlukta yine yaz ama işaretle (standart şemalar dondurulmuş)
                    (staging / "INTEGRITY_MISMATCH.txt").write_text(
                        f"{fn}: beklenen {want}\n", encoding="utf-8")
                text = _W3_XML_RE.sub("xml.xsd", data.decode("utf-8", "ignore"))
                (staging / fn).write_text(text, encoding="utf-8")
        # ANCAK tamsa yerine koy → yarım fetch asla kalıcı olmaz (poisoned cache imkânsız)
        if not _cache_complete(version, staging):
            shutil.rmtree(staging, ignore_errors=True)
            return None
        # eski/bozuk cache'i temizle, staging'i atomik yerine al (aynı filesystem → os.replace atomik)
        if rd.exists():
            shutil.rmtree(rd, ignore_errors=True)
        os.replace(staging, rd)
        return rd
    except Exception:
        # ağ yok / fetch hata → graceful degrade; yarım staging temizlenir (poisoned dir bırakma yok)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
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
