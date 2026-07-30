"""tests/test_media_provenance.py — Faz 3 kabul #11: PROVENANCE.json pakete gömülür.

  - scenario_compile: dolu slot varlıkları spec.assets'e data: URI olarak enjekte edilir
    (asset id KORUNUR → ekran referansları geçerli kalır); spec.media_provenance dolu
    slot başına tek kayıt taşır.
  - compile_and_build zinciri: SCORM zip'inde assets/PROVENANCE.json + varlık dosyası.
  - GERİYE UYUM (bayt-parite sınıfı): düz build_from_spec kursu PROVENANCE.json KAZANMAZ
    (dosya yok, manifest'te kayıt yok).
"""

import base64
import io
import json
import os
import zipfile

import pytest
from fastmcp import Client

from tests.test_media_federation import PNG_1PX
from tests.test_media_tools import PNG_URI, _make_scenario

PLAIN_SPEC = {
    "title": "Düz Kurs",
    "screens": [
        {"type": "content_slide", "id": "s1", "title": "Giriş", "body_html": "<p>metin</p>"},
        {"type": "summary", "id": "s2", "title": "Özet"},
    ],
}


async def _zip_bytes(download_url: str) -> bytes:
    import server
    token = download_url.rstrip("/").split("/")[-1]
    meta = await server.SVC.store.get_package_by_token(token)
    assert meta is not None
    with open(os.path.join(server.SETTINGS.data_dir, meta.rel_path), "rb") as f:
        return f.read()


async def _filled_scenario(c):
    sid = await _make_scenario(c, slots=[
        {"slot_id": "hucre_zari", "role": "aciklayici", "kind": "image",
         "spec": "Hücre zarı diyagramı"}])
    r = await c.call_tool("fill_media_slot", {
        "scenario_id": sid, "page_id": "p1", "slot_id": "hucre_zari",
        "source": PNG_URI, "alt_text": "hücre zarı",
        "provenance": {"source": "openverse", "license_note": "CC0"}})
    return sid, r.data["asset_id"]


# --------------------------------------------------------------------------- #
# compile: assets data-URI enjeksiyonu + media_provenance
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_compile_injects_assets_and_provenance():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid, aid = await _filled_scenario(c)
        r = await c.call_tool("scenario_compile", {"scenario_id": sid})
        spec = r.data["spec"]
        # varlık data: URI olarak, id KORUNARAK enjekte edildi
        assert len(spec["assets"]) == 1
        a = spec["assets"][0]
        assert a["id"] == aid
        assert a["source"].startswith("data:image/png;base64,")
        assert base64.b64decode(a["source"].split(",", 1)[1]) == PNG_1PX
        # ekran alanı aynı id'ye referans veriyor
        scr = next(s for s in spec["screens"] if s["id"] == "p1")
        assert scr["media_asset_id"] == aid
        # provenance kayıtları (kabul #11 kaynağı)
        recs = spec["media_provenance"]
        assert len(recs) == 1
        assert recs[0]["slot_id"] == "hucre_zari"
        assert recs[0]["asset_id"] == aid
        assert recs[0]["provenance"]["source"] == "openverse"
        assert recs[0]["provenance"]["generated_at"]


@pytest.mark.asyncio
async def test_compile_without_filled_slots_has_no_provenance_key():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c)  # slot var ama BOŞ
        r = await c.call_tool("scenario_compile", {"scenario_id": sid})
        assert "media_provenance" not in r.data["spec"]
        assert not r.data["spec"].get("assets")


# --------------------------------------------------------------------------- #
# kabul #11 — zip: assets/PROVENANCE.json (dolu slot başına bir kayıt)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_compile_and_build_zip_contains_provenance_json():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid, aid = await _filled_scenario(c)
        r = await c.call_tool("scenario_compile",
                              {"scenario_id": sid, "compile_and_build": True})
        build = r.data["build"]
        assert build["status"] == "done", build
        raw = await _zip_bytes(build["download_url"])
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = set(zf.namelist())
    assert "assets/PROVENANCE.json" in names
    recs = json.loads(zf.read("assets/PROVENANCE.json").decode("utf-8"))
    assert len(recs) == 1  # dolu slot başına TEK kayıt
    assert recs[0]["slot_id"] == "hucre_zari"
    assert recs[0]["asset_id"] == aid
    assert recs[0]["provenance"]["source"] == "openverse"
    # varlık dosyası da pakette
    assert any(n.startswith("assets/") and n.endswith(".png") for n in names)
    # manifest PROVENANCE.json'u dosya listesinde taşıyor
    manifest = zf.read("imsmanifest.xml").decode("utf-8")
    assert "assets/PROVENANCE.json" in manifest


# --------------------------------------------------------------------------- #
# geriye uyum — düz build PROVENANCE.json KAZANMAZ (bayt-parite sınıfı)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_plain_build_has_no_provenance_file():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": PLAIN_SPEC})
        assert res.data.status == "done"
        raw = await _zip_bytes(res.data.download_url)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert "assets/PROVENANCE.json" not in set(zf.namelist())
    assert "PROVENANCE" not in zf.read("imsmanifest.xml").decode("utf-8")


@pytest.mark.asyncio
async def test_media_provenance_field_backward_compatible_default():
    """Eski projeler/spec'ler alan olmadan doğrulanır (additive)."""
    from core.project import CourseSpec, Project
    assert CourseSpec.model_validate(PLAIN_SPEC).media_provenance == []
    p = Project(id="proj_x", title="T", owner_key_id="k")
    assert p.media_provenance == []
