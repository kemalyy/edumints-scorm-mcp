"""tests/test_media_tools.py — Faz 3 MCP araçları: fill_media_slot (39.) + match_media_manifest (40.).

Kabul kanıtları:
  #9  sha256 içerik-dedup: aynı bayt → aynı asset id, TEK depolama
  #10 yerel-import negatif testi: sunucu araçları dosya sistemi TARAMAZ (şemada path alanı yok;
      kaynakta os.listdir/scandir/glob/iterdir/walk yok)
  A11Y_NO_TEXT_ALT sert hata (kanıt rolü; audio/video için transcript de)
  kind ↔ sniff MIME uyuşmazlığı sert hata
  provenance verildiği gibi saklanır + generated_at sunucu damgası
"""

import base64

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

from tests.test_media_federation import PNG_1PX

PNG_URI = "data:image/png;base64," + base64.b64encode(PNG_1PX).decode()
MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 32
MP3_URI = "data:audio/mpeg;base64," + base64.b64encode(MP3_BYTES).decode()


async def _make_scenario(c, slots=None, extra_pages=None):
    r = await c.call_tool("create_scenario", {
        "title": "Hücre", "outline": [
            {"id": "u1", "kind": "unit", "title": "Ünite",
             "objective": {"id": "obj_u1", "description": "hedef"}}]})
    sid = r.data["scenario_id"]
    slots = slots if slots is not None else [
        {"slot_id": "hucre_zari", "role": "aciklayici", "kind": "image",
         "spec": "Hücre zarı diyagramı"}]
    await c.call_tool("scenario_upsert_page", {
        "scenario_id": sid,
        "page": {"id": "p1", "node_id": "u1", "title": "Giriş",
                 "screen_type": "content_slide", "media_slots": slots}})
    for pg in extra_pages or []:
        await c.call_tool("scenario_upsert_page", {"scenario_id": sid, "page": pg})
    return sid


async def _get_doc(sid):
    import server
    return await server.SVC.store.get_scenario(sid, "key_local")


# --------------------------------------------------------------------------- #
# fill_media_slot — mutlu yol + provenance damgası
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fill_media_slot_happy_path_and_provenance_stamp():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c)
        r = await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "hucre_zari",
            "source": PNG_URI, "alt_text": "hücre zarı diyagramı",
            "provenance": {"source": "openverse", "tool": "search_images",
                           "license_note": "CC0"}})
        assert r.data["asset_id"].startswith("asset_")
        assert r.data["deduped"] is False
        assert r.data["mime"] == "image/png"

        doc = await _get_doc(sid)
        slot = doc.pages[0].media_slots[0]
        assert slot.asset_id == r.data["asset_id"]
        assert slot.a11y.alt_text == "hücre zarı diyagramı"
        # provenance verildiği gibi + generated_at sunucu damgası
        assert slot.provenance["source"] == "openverse"
        assert slot.provenance["license_note"] == "CC0"
        assert slot.provenance["generated_at"]
        # varlık senaryo evinde (paralel assets listesi)
        assert [a.id for a in doc.assets] == [r.data["asset_id"]]
        assert doc.assets[0].mime == "image/png"
        # bayt gerçekten store'da (scenario_id ad-alanı)
        data = await server.SVC.store.get_asset_bytes(sid, r.data["asset_id"])
        assert data == PNG_1PX


@pytest.mark.asyncio
async def test_fill_media_slot_given_generated_at_preserved():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c)
        await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "hucre_zari",
            "source": PNG_URI, "alt_text": "alt",
            "provenance": {"source": "upload",
                           "generated_at": "2026-01-01T00:00:00+00:00"}})
        doc = await _get_doc(sid)
        assert doc.pages[0].media_slots[0].provenance["generated_at"] == \
            "2026-01-01T00:00:00+00:00"


# --------------------------------------------------------------------------- #
# kabul #9 — sha256 içerik-dedup: aynı bayt → aynı id, tek depolama
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fill_dedup_same_bytes_single_asset_id():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "s1", "role": "aciklayici", "kind": "image", "spec": "görsel 1"},
            {"slot_id": "s2", "role": "aciklayici", "kind": "image", "spec": "görsel 2"},
        ])
        r1 = await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "s1", "source": PNG_URI})
        r2 = await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "s2", "source": PNG_URI})
        assert r1.data["asset_id"] == r2.data["asset_id"]  # aynı bayt → aynı id
        assert r1.data["deduped"] is False
        assert r2.data["deduped"] is True
        doc = await _get_doc(sid)
        assert len(doc.assets) == 1  # tek AssetRef → tek depolama, çift kayıt yok
        # dosya sisteminde de tek dosya
        from pathlib import Path
        adir = Path(server.SETTINGS.data_dir) / "assets" / sid
        assert len(list(adir.iterdir())) == 1


# --------------------------------------------------------------------------- #
# kind ↔ sniff MIME uyuşmazlığı — sert hata
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fill_kind_mime_mismatch_hard_error():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "ses", "role": "aciklayici", "kind": "audio", "spec": "anlatım"}])
        with pytest.raises(MCPToolError, match="kind_mime_mismatch"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "p1", "slot_id": "ses",
                "source": PNG_URI})  # PNG baytı, audio slotu
        doc = await _get_doc(sid)
        assert doc.pages[0].media_slots[0].asset_id is None  # slot değişmedi
        assert doc.assets == []                              # varlık da eklenmedi


@pytest.mark.asyncio
async def test_fill_declared_mime_lies_sniff_wins():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "ses", "role": "aciklayici", "kind": "audio", "spec": "anlatım"}])
        # data URI başlığı audio DİYOR ama baytlar PNG — sniff kazanır, sert hata
        lying = "data:audio/mpeg;base64," + base64.b64encode(PNG_1PX).decode()
        with pytest.raises(MCPToolError, match="kind_mime_mismatch"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "p1", "slot_id": "ses", "source": lying})


# --------------------------------------------------------------------------- #
# A11Y_NO_TEXT_ALT — kanıt rolü sert kapı (3.5/3.8)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fill_kanit_without_alt_text_hard_error():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "kanit_gorsel", "role": "kanit", "kind": "image",
             "spec": "işaretli mikroskop görüntüsü"}])
        with pytest.raises(MCPToolError, match="A11Y_NO_TEXT_ALT"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "p1", "slot_id": "kanit_gorsel",
                "source": PNG_URI})  # alt_text yok
        doc = await _get_doc(sid)
        assert doc.pages[0].media_slots[0].asset_id is None
        assert doc.assets == []


@pytest.mark.asyncio
async def test_fill_kanit_audio_requires_transcript_too():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "kanit_ses", "role": "kanit", "kind": "audio",
             "spec": "uzman anlatımı"}])
        with pytest.raises(MCPToolError, match="A11Y_NO_TEXT_ALT"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "p1", "slot_id": "kanit_ses",
                "source": MP3_URI, "alt_text": "uzman anlatımı"})  # transcript yok
        # transcript verilince geçer
        r = await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "kanit_ses",
            "source": MP3_URI, "alt_text": "uzman anlatımı",
            "transcript_html": "<p>transkript metni</p>"})
        assert r.data["asset_id"].startswith("asset_")
        doc = await _get_doc(sid)
        assert doc.pages[0].media_slots[0].a11y.transcript_html == "<p>transkript metni</p>"


@pytest.mark.asyncio
async def test_fill_kanit_alt_text_may_preexist_on_slot():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "kanit_gorsel", "role": "kanit", "kind": "image",
             "spec": "artefakt", "a11y": {"alt_text": "önceden yazılmış alt"}}])
        r = await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "kanit_gorsel",
            "source": PNG_URI})  # alt_text parametresiz — slottaki yeter
        assert r.data["asset_id"].startswith("asset_")


# --------------------------------------------------------------------------- #
# not_found yolları
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_fill_not_found_errors():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c)
        with pytest.raises(MCPToolError, match="not_found"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": "scn_YOK", "page_id": "p1", "slot_id": "hucre_zari",
                "source": PNG_URI})
        with pytest.raises(MCPToolError, match="not_found"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "pYOK", "slot_id": "hucre_zari",
                "source": PNG_URI})
        with pytest.raises(MCPToolError, match="not_found"):
            await c.call_tool("fill_media_slot", {
                "scenario_id": sid, "page_id": "p1", "slot_id": "yok_slot",
                "source": PNG_URI})


# --------------------------------------------------------------------------- #
# match_media_manifest — yalnız metadata; dedup bayrağı; deterministik
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_match_media_manifest_tool_proposals():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "hucre_zari", "role": "aciklayici", "kind": "image",
             "spec": "Hücre zarı diyagramı"},
            {"slot_id": "mitoz_anlatim", "role": "aciklayici", "kind": "audio",
             "spec": "Mitoz seslendirme"}])
        r = await c.call_tool("match_media_manifest", {
            "scenario_id": sid, "files": [
                {"name": "hucre-zari.png", "size": 6000, "sha256": "c" * 64,
                 "mime": "image/png"},
                {"name": "alakasiz.pdf", "size": 100, "sha256": "d" * 64,
                 "mime": "application/pdf"}]})
        props = {p["slot_id"]: p for p in r.data["proposals"]}
        assert props["hucre_zari"]["proposed"] == "hucre-zari.png"
        assert props["mitoz_anlatim"]["candidates"] == []
        assert r.data["unmatched_files"] == ["alakasiz.pdf"]


@pytest.mark.asyncio
async def test_match_media_manifest_flags_already_ingested():
    import server
    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        sid = await _make_scenario(c, slots=[
            {"slot_id": "s1", "role": "aciklayici", "kind": "image", "spec": "görsel 1"},
            {"slot_id": "s2", "role": "aciklayici", "kind": "image", "spec": "görsel 2"}])
        await c.call_tool("fill_media_slot", {
            "scenario_id": sid, "page_id": "p1", "slot_id": "s1", "source": PNG_URI})
        import hashlib
        r = await c.call_tool("match_media_manifest", {
            "scenario_id": sid, "files": [
                {"name": "gorsel-2.png", "size": len(PNG_1PX),
                 "sha256": hashlib.sha256(PNG_1PX).hexdigest(), "mime": "image/png"}]})
        props = {p["slot_id"]: p for p in r.data["proposals"]}
        cand = props["s2"]["candidates"][0]
        assert any("dedup" in x for x in cand["reasons"])


# --------------------------------------------------------------------------- #
# kabul #10 — NEGATİF test: sunucu dosya sistemi TARAMAZ
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_match_media_manifest_schema_has_no_path_field():
    """Araç şeması yerel yol kabul ETMEZ — dizin erişimi API yüzeyinde bile yok."""
    import inspect

    import server
    tool = await server.mcp.get_tool("match_media_manifest")
    schema = tool.parameters  # FastMCP tool JSON şeması
    prop_names = set(schema.get("properties", {}))
    assert prop_names == {"scenario_id", "files"}
    forbidden = {"path", "folder", "dir", "directory", "glob"}
    assert not (prop_names & forbidden)
    # files öğeleri de yol taşımaz: yalnız metadata alanları
    sig = inspect.signature(tool.fn)
    assert "path" not in sig.parameters


def test_no_directory_scanning_in_server_media_paths():
    """Kaynak kanıtı (grep): Faz 3 sunucu yolu hiçbir dizin-tarama çağrısı içermez.
    (server.py'deki THEMES_DIR.glob Faz 3 ÖNCESİ tema keşfidir; bu test Faz 3 modülü +
    iki yeni aracın kaynağını denetler.)"""
    import inspect
    from pathlib import Path

    import server
    from core import media_federation

    core_src = Path(media_federation.__file__).read_text(encoding="utf-8")
    tool_src = inspect.getsource(server.fill_media_slot) + \
        inspect.getsource(server.match_media_manifest)
    for src in (core_src, tool_src):
        for banned in ("os.listdir", "os.scandir", "os.walk", ".iterdir(",
                       ".glob(", ".rglob(", "glob.glob"):
            assert banned not in src, f"dizin tarama çağrısı bulundu: {banned}"
