import io
import json
import os
import zipfile
import pytest
from fastmcp import Client
import server

def _spec(name: str) -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "games", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)

async def _build_and_get_zip(spec: dict) -> bytes:
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        assert res.data.status == "done", f"build status: {res.data.status}"
        assert res.data.download_url
        token = res.data.download_url.rstrip("/").split("/")[-1]
    meta = await server.SVC.store.get_package_by_token(token)
    assert meta is not None
    zpath = os.path.join(server.SETTINGS.data_dir, meta.rel_path)
    with open(zpath, "rb") as f:
        return f.read()

@pytest.mark.asyncio
async def test_phishing_decision_builds():
    spec = _spec("phishing-decision.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="decision_scenario"' in index

@pytest.mark.asyncio
async def test_customer_deescalation_builds():
    spec = _spec("customer-deescalation.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="decision_scenario"' in index


# --- W3b: kompozisyonel `game` ekranı (engine bundle + primitif + kural + dallanan düğüm) ---
@pytest.mark.asyncio
async def test_clinic_triage_game_builds():
    """case_sim şablonu: score+lives+hints kompozisyonu, dallanan klinik karar düğümleri."""
    spec = _spec("clinic-triage-game.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="game"' in index
    # oyun motoru bundle'ı YALNIZ game ekranı varsa inline edilir (bundle'a-özgü token) + köprü
    assert "/* engine/rng.js */" in index
    assert "window.SCORMGame = __E" in index
    assert "function bindGame" in index
    # config'te oyun mantığı (mekanik specs + kural + düğüm-mantığı) serileşmiş olmalı
    assert '"game":' in index and '"mechanics"' in index


@pytest.mark.asyncio
async def test_escape_cipher_game_builds():
    """escape_room şablonu: timer(a11y)+lives+hints+score, kilitli oda zinciri."""
    spec = _spec("escape-cipher-game.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="game"' in index
    assert "/* engine/rng.js */" in index and "window.SCORMGame = __E" in index
    # a11y süre kontrolleri (WCAG 2.2.1): uzat + kapat butonları render edilmeli
    assert "game-timer-extend" in index and "game-timer-off" in index
    # W5b — bu örnek cmi5 telemetri açık: xapi config + forwarder + xapi modülü inline
    assert '"xapi"' in index and "var XAPI=(function" in index and "/* engine/xapi.js */" in index


# --- W4b: adaptif pratik (Elo/BKT tahminci → ZPD zorluk seçimi) ---
@pytest.mark.asyncio
async def test_adaptive_statistics_builds():
    """adaptive_practice: Elo tahminci, öğe bankası + zorluklar; engine bundle inline."""
    spec = _spec("adaptive-statistics.tr.json")
    raw = await _build_and_get_zip(spec)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "index.html" in names
    assert "imsmanifest.xml" in names
    index = zf.read("index.html").decode("utf-8")
    assert 'data-type="adaptive_practice"' in index
    assert "/* engine/adaptive.js */" in index and "window.SCORMGame = __E" in index
    assert "function bindAdaptive" in index
    # config: tahminci spec + öğe zorlukları serileşmeli
    assert '"adaptive":' in index and '"difficulty"' in index
