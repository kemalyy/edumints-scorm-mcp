"""tests/conftest.py — test ortamı (server import'undan ÖNCE env ayarlar)."""

import os
import tempfile

# server.py SETTINGS'i import anında okur → env'i burada, import'tan önce kur.
_TMP = tempfile.mkdtemp(prefix="scorm-test-")
os.environ.setdefault("SCORM_AUTH_ENABLED", "0")
os.environ.setdefault("DATA_DIR", _TMP)
os.environ.setdefault("DB_PATH", os.path.join(_TMP, "scorm.db"))
os.environ.setdefault("PUBLIC_BASE_URL", "https://mcp.test/scorm")
os.environ.setdefault("BUILD_SYNC_TIMEOUT_SEC", "20")
# Sonsuz TTL-cleaner arka-plan task'ini testte başlatma (CI'da pytest teardown hang'ini önler).
os.environ.setdefault("SCORM_NO_TTL_CLEANER", "1")
# W9 P0 rate limiter: test ortamında tüm tool çağrıları tek anonim principal'a (key_local)
# yazılır — paket büyüdükçe 60/dk global bucket'ı tüketip alakasız testleri kırmasın diye
# limiti pratikte devre dışı bırak (ölçüm: mevcut paket ~45 çağrı, %75 doluluk). Rate-limit
# testleri kendi RateLimiter örneğini monkeypatch'lediğinden bundan etkilenmez.
os.environ.setdefault("RATE_LIMIT_PER_MIN", "100000")
# Testler AĞSIZ olmalı: XSD şema fetch'i (imsglobal) CI'da yavaş/asılı kalabilir. SCORM_SCHEMA_DIR'i
# şemasız bir dizine işaret ettir → _ensure_populated None → conformance testi graceful skip eder.
# (XSD doğrulamasını gerçek koşmak için bu env'i unset edip ağa izin ver.)
os.environ.setdefault("SCORM_SCHEMA_DIR", os.path.join(_TMP, "no_schemas"))

import pytest  # noqa: E402

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")


@pytest.fixture
def examples_dir() -> str:
    return EXAMPLES


_EXIT_STATUS = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _EXIT_STATUS["code"] = int(exitstatus)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Süreci kesin sonlandır (özet/rapor BASILDIKTAN sonra — unconfigure en son hook'tur).
    Sebep: testler bitip rapor yazıldıktan sonra, arka-plan thread'leri (ThreadPoolExecutor /
    aiosqlite / fastmcp) bazı ortamlarda (GitHub Actions ubuntu) süreç çıkışını bloklayıp
    'orphan pytest' olarak askıda bırakıyordu → CI 6h timeout'a takılıyordu. Burada os._exit
    güvenli: tüm raporlama tamamlandı."""
    import os as _os
    import sys as _sys
    _sys.stdout.flush()
    _sys.stderr.flush()
    _os._exit(_EXIT_STATUS["code"])
