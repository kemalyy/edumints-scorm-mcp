"""tests/test_schema_populate.py — şema cache tamlık kapısı + atomik doldurma.

Prod build hatası (ArtifactValidationError: imsmd_v1p2 lom ... strict wildcard) kök nedeni:
şema cache'i imscp + xml PRESENT ama imsmd_v1p2p4.xsd MISSING durumuna düşünce, lxml driver'ı
(imsmd import'u çözülmeden) yine de derliyor → her manifest'in HER ZAMAN yaydığı <lom> bloğu
strict wildcard'ı geçemiyor → BLOCKING conformance_error → build ölüyor. İki onset:
  (a) partial-fetch: imsmd (fetch sırasının SONU) tek seferlik patlar; driver zaten kopyalanmış,
      "populated mı?" kapısı yalnız driver.exists() baktığı için sonraki tüm çağrılar poisoned
      cache'i tam sayıyor.
  (b) stale-cache: kalıcı DATA_DIR volume'unda S7-öncesi (imsmd import'suz driver, imsmd dosyası
      yok) cache; her post-S7 build deterministik başarısız.

Uçtan uca lom→graceful davranışı ağ gerektiren gerçek imscp/imsmd şemalarıyla elle repro edildi
(bkz. bug raporu); bu suite AĞSIZ (conftest zorunluluğu) olduğundan tamlık-kapısı ve atomik-
doldurma mantığını doğrudan test eder — düzeltmenin poisoned durumu ULAŞILAMAZ kıldığını kanıtlar.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import core.schema_validate as sv

SCHEMAS = Path(sv.__file__).resolve().parent.parent / "runtime" / "schemas"


@pytest.fixture(autouse=True)
def _clear_schema_cache():
    sv._compiled_schema.cache_clear()
    yield
    sv._compiled_schema.cache_clear()


def _vendored(name: str) -> bytes:
    return (SCHEMAS / name).read_bytes()


def _adl_files() -> dict:
    return {x.name: x.read_bytes() for x in (SCHEMAS / "adl").glob("*.xsd")}


def _offline_root(files: dict, tmp_path: Path) -> str:
    """SCORM_SCHEMA_DIR kökü döndürür; files (relname→bytes) '12/' altına yazılır."""
    d = tmp_path / "off" / "12"
    d.mkdir(parents=True)
    for name, data in files.items():
        (d / name).write_bytes(data)
    return str(tmp_path / "off")


# --- Tamlık kapısı (_cache_complete) ------------------------------------------------

def test_cache_complete_false_when_imsmd_missing(tmp_path):
    """imscp/xml PRESENT ama imsmd MISSING → poisoned durum → kapı False vermeli."""
    files = {"driver_12.xsd": _vendored("driver_12.xsd"), **_adl_files(),
             "imscp_rootv1p1p2.xsd": b"<x/>", "ims_xml.xsd": b"<x/>", "xml.xsd": b"<x/>"}
    root = _offline_root(files, tmp_path)
    assert sv._cache_complete("1.2", Path(root) / "12") is False


def test_cache_complete_false_when_driver_stale(tmp_path):
    """S7-öncesi (vendored'dan farklı) driver → bayt uyuşmazlığı → kapı False (stale onset)."""
    files = {"driver_12.xsd": b"<xsd:schema/>", **_adl_files(),
             "imscp_rootv1p1p2.xsd": b"<x/>", "ims_xml.xsd": b"<x/>", "xml.xsd": b"<x/>",
             "imsmd_v1p2p4.xsd": b"<x/>"}
    root = _offline_root(files, tmp_path)
    assert sv._cache_complete("1.2", Path(root) / "12") is False


def test_cache_complete_true_when_all_present(tmp_path):
    files = {"driver_12.xsd": _vendored("driver_12.xsd"), **_adl_files(),
             "imscp_rootv1p1p2.xsd": b"<x/>", "ims_xml.xsd": b"<x/>", "xml.xsd": b"<x/>",
             "imsmd_v1p2p4.xsd": b"<x/>"}
    root = _offline_root(files, tmp_path)
    assert sv._cache_complete("1.2", Path(root) / "12") is True


# --- Davranış: eksik cache build'i BLOKLAMAZ --------------------------------------

def test_offline_incomplete_degrades_gracefully(tmp_path, monkeypatch):
    """imsmd eksik offline dir → validate → schema_unavailable (BLOCKING conformance_error DEĞİL)."""
    files = {"driver_12.xsd": _vendored("driver_12.xsd"), **_adl_files(),
             "imscp_rootv1p1p2.xsd": b"<x/>", "ims_xml.xsd": b"<x/>", "xml.xsd": b"<x/>"}
    root = _offline_root(files, tmp_path)
    monkeypatch.setenv("SCORM_SCHEMA_DIR", root)
    errs = sv.validate_manifest_xsd(b"<manifest/>", "1.2")
    assert len(errs) == 1 and errs[0].code == sv.SCHEMA_UNAVAILABLE


# --- Atomik doldurma: partial-fetch ASLA poisoned dir bırakmaz -----------------------

def test_partial_fetch_never_poisons_then_self_heals(tmp_path, monkeypatch):
    """Fetch modu: imsmd fetch'i patlarsa poisoned dir KALMAZ (None); sonraki tam fetch iyileşir."""
    monkeypatch.delenv("SCORM_SCHEMA_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    imsmd_url = sv._ims_sources()["12"]["imsmd_v1p2p4.xsd"]["url"]

    def fail_on_imsmd(self, url, *a, **k):
        if url == imsmd_url:
            raise RuntimeError("simulated imsmd fetch failure (last in loop)")
        m = MagicMock()
        m.content = b"<schema/>"
        return m

    with patch("httpx.Client.get", fail_on_imsmd):
        rd = sv._ensure_populated("1.2")
    assert rd is None, "eksik fetch None dönmeli (poisoned dir değil)"
    resolved = Path(tmp_path) / "scorm_schemas" / "12"
    assert not sv._cache_complete("1.2", resolved), "poisoned/partial cache kalıcı OLMAMALI"

    # Sonraki tam fetch (hepsi başarılı) → cache iyileşir, tam dir döner
    def all_ok(self, url, *a, **k):
        m = MagicMock()
        m.content = b"<schema/>"
        return m

    with patch("httpx.Client.get", all_ok):
        rd2 = sv._ensure_populated("1.2")
    assert rd2 is not None and sv._cache_complete("1.2", rd2)


def test_empty_ims_sources_degrades_not_certifies(tmp_path, monkeypatch):
    """ims_sources.json okunamaz/boş → gate IMS'siz cache'i TAM sertifikalamamalı → graceful None
    (aksi hâlde aynı lom hatası başka kapıdan geri gelir)."""
    monkeypatch.delenv("SCORM_SCHEMA_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sv, "_ims_sources", lambda: {})
    assert sv._ensure_populated("1.2") is None
