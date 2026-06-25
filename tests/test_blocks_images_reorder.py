"""tests/test_blocks_images_reorder.py — P1–P6 authoring-surface eklentileri.

P1 content_slide blocks[] · P3 accordion/tabs per-item görsel · P4 flashcard/timeline görsel ·
P5 data: URI <img> · P6 {{asset:id}} interpolasyonu · P2 reorder_screens · validator per-item ref.
"""

import pytest

from core.project import (
    Project, new_project_id,
    ContentSlide, ContentBlock,
    AccordionScreen, AccordionItem, TabsScreen, TabItem,
    FlashcardsScreen, Flashcard, TimelineScreen, TimelineEvent,
    AssetRef,
)
from core.validator import validate_project
from components.renderer import render_html, sanitize

from fastmcp import Client
import server

PNG_1x1 = ("data:image/png;base64,"
           "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def _asset(aid: str) -> AssetRef:
    return AssetRef(id=aid, filename=f"{aid}.png", mime="image/png",
                    size_bytes=10, sha256="x" * 64, rel_path=f"assets/{aid}.png")


def _render(project: Project) -> str:
    return render_html(project, mode="package", runtime_js="/*rt*/")


# ---------------- P1: content_slide blocks[] ----------------
def test_p1_content_blocks_render_in_order():
    p = Project(id=new_project_id(), title="Blocks", assets=[_asset("g1")],
                screens=[ContentSlide(id="s1", title="Akış", blocks=[
                    ContentBlock(html="<p>Adım 1</p>"),
                    ContentBlock(asset_id="g1", caption="Görsel 1"),
                    ContentBlock(html="<p>Adım 2</p>"),
                ])])
    h = _render(p)
    assert 'class="content-blocks' in h        # gerçek blok konteyneri (CSS sınıf adı değil)
    assert "Adım 1" in h and "Adım 2" in h
    assert 'data-asset="g1"' in h          # blok görseli placeholder
    assert "Görsel 1" in h                  # caption
    # blok sırası korunmalı: Adım 1 < görsel < Adım 2
    assert h.index("Adım 1") < h.index('data-asset="g1"') < h.index("Adım 2")


def test_p1_body_html_optional_when_blocks_used():
    # body_html artık zorunlu değil (blocks-only spec geçerli olmalı)
    s = ContentSlide(id="s1", title="T", blocks=[ContentBlock(html="<p>x</p>")])
    assert s.body_html == ""


def test_p1_backward_compat_plain_content_slide():
    p = Project(id=new_project_id(), title="Eski",
                screens=[ContentSlide(id="s1", title="T", body_html="<p>klasik</p>")])
    h = _render(p)
    assert "klasik" in h and 'class="content-blocks' not in h


# ---------------- P3: accordion / tabs per-item görsel ----------------
def test_p3_accordion_tabs_item_images():
    p = Project(id=new_project_id(), title="A", assets=[_asset("a1"), _asset("t1")], screens=[
        AccordionScreen(id="s1", title="Acc", items=[
            AccordionItem(title="P1", body_html="<p>b</p>", image_asset_id="a1")]),
        TabsScreen(id="s2", title="Tabs", tabs=[
            TabItem(label="L1", body_html="<p>b</p>", image_asset_id="t1")]),
    ])
    h = _render(p)
    assert 'data-asset="a1"' in h
    assert 'data-asset="t1"' in h


# ---------------- P4: flashcard / timeline görsel ----------------
def test_p4_flashcard_timeline_images():
    p = Project(id=new_project_id(), title="F", assets=[_asset("f1"), _asset("f2"), _asset("e1")], screens=[
        FlashcardsScreen(id="s1", title="FC", cards=[
            Flashcard(front_html="<p>ön</p>", back_html="<p>arka</p>",
                      front_asset_id="f1", back_asset_id="f2")]),
        TimelineScreen(id="s2", title="TL", events=[
            TimelineEvent(date="1", title="E", body_html="<p>b</p>", image_asset_id="e1")]),
    ])
    h = _render(p)
    for aid in ("f1", "f2", "e1"):
        assert f'data-asset="{aid}"' in h


# ---------------- P5: data: URI <img> ----------------
def test_p5_data_uri_img_survives_sanitize():
    out = sanitize(f'<p>x</p><img src="{PNG_1x1}" alt="i">')
    assert "data:image/png;base64," in out          # data: URI strip EDİLMEDİ
    assert "<img" in out


def test_p5_script_still_stripped():
    out = sanitize('<p>ok</p><script>alert(1)</script>')
    assert "ok" in out and "<script" not in out and "alert(1)" not in out


# ---------------- P6: {{asset:id}} interpolasyonu ----------------
def test_p6_asset_token_interpolation():
    p = Project(id=new_project_id(), title="Interp", assets=[_asset("g9")],
                screens=[ContentSlide(id="s1", title="T",
                         body_html="<p>Önce {{asset:g9}} sonra</p>")])
    h = _render(p)
    assert 'data-asset="g9"' in h
    assert "{{asset:g9}}" not in h                  # token değiştirildi


# ---------------- validator: per-item bilinmeyen asset ----------------
def test_validator_flags_unknown_per_item_asset():
    p = Project(id=new_project_id(), title="V",
                screens=[AccordionScreen(id="s1", title="A", items=[
                    AccordionItem(title="P", body_html="<p>b</p>", image_asset_id="yok")])])
    errs = validate_project(p)
    assert any("yok" in e.message for e in errs)


# ---------------- P2: reorder_screens (MCP tool) ----------------
@pytest.mark.asyncio
async def test_p2_reorder_screens():
    async with Client(server.mcp) as c:
        proj = await c.call_tool("create_project", {"title": "R"})
        pid = proj.data.project_id
        ids = []
        for t in ("A", "B", "C"):
            r = await c.call_tool("add_screen", {"project_id": pid,
                                  "screen": {"type": "content_slide", "title": t, "body_html": "<p>x</p>"}})
            ids.append(r.data.screen_id)
        # ters sıraya diz
        await c.call_tool("reorder_screens", {"project_id": pid, "screen_ids_in_order": list(reversed(ids))})
        listed = await c.call_tool("list_screens", {"project_id": pid})
        assert [s.id for s in listed.data.screens] == list(reversed(ids))
        # eksik liste → hata
        with pytest.raises(Exception):
            await c.call_tool("reorder_screens", {"project_id": pid, "screen_ids_in_order": ids[:2]})


def test_inline_svg_stripped_but_img_kept():
    # inline <svg> body_html'den temizlenir (LMS uyumu); <img> korunur → asset yolu doğru çözüm
    out = sanitize('<p>ok</p><svg viewBox="0 0 10 10"><rect/></svg><img src="https://x/a.svg">')
    assert "ok" in out and "<svg" not in out and "<img" in out


@pytest.mark.asyncio
async def test_svg_to_asset_and_content_slide():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"><rect width="100" height="50"/></svg>'
    async with Client(server.mcp) as c:
        proj = await c.call_tool("create_project", {"title": "SVG"})
        pid = proj.data.project_id
        a = await c.call_tool("svg_to_asset", {"project_id": pid, "svg_content": svg, "filename": "d.svg"})
        assert a.data.mime == "image/svg+xml" and a.data.filename.endswith(".svg")
        await c.call_tool("add_screen", {"project_id": pid, "screen": {
            "type": "content_slide", "title": "D", "layout": "text_media",
            "media_asset_id": a.data.id, "body_html": "<p>x</p>"}})
        v = await c.call_tool("validate_package", {"project_id": pid})
        assert v.data.ok, v.data.errors
        with pytest.raises(Exception):
            await c.call_tool("svg_to_asset", {"project_id": pid, "svg_content": "düz metin, svg değil"})


def test_block_width_renders_inline_style():
    p = Project(id=new_project_id(), title="W", assets=[_asset("g1")],
                screens=[ContentSlide(id="s1", title="T", blocks=[
                    ContentBlock(asset_id="g1", caption="c", width="60%")])])
    h = _render(p)
    assert "width:60%" in h and 'data-asset="g1"' in h


@pytest.mark.asyncio
async def test_auto_tts_graceful_when_piper_absent():
    """auto_tts:true Piper yoksa build'i KIRMAMALI (sessiz atlama); auto_tts:false → narration set edilmez."""
    spec = {"title": "TTS", "auto_tts": True,
            "screens": [{"type": "content_slide", "title": "T", "body_html": "<p>x</p>",
                         "narration_text": "Merhaba dünya"}]}
    async with Client(server.mcp) as c:
        r = await c.call_tool("build_from_spec", {"spec": spec})
        v = await c.call_tool("validate_package", {"project_id": r.data.project_id})
        assert v.data.ok, v.data.errors   # Piper olsun olmasın build geçerli kalır


@pytest.mark.asyncio
async def test_e2e_build_from_spec_with_new_media_fields():
    """build_from_spec dict girdisi yeni alanları (blocks + per-item görsel + data-URI asset) kabul
    edip geçerli paket üretmeli."""
    spec = {
        "title": "AI Okuryazarligi",
        "assets": [{"id": "g1", "filename": "g1.png", "source": PNG_1x1}],
        "screens": [
            {"type": "content_slide", "title": "Akis", "blocks": [
                {"html": "<p>Adim 1</p>"},
                {"asset_id": "g1", "caption": "Veri"},
                {"html": "<p>Adim 2</p>"}]},
            {"type": "accordion", "title": "Acc", "items": [
                {"title": "P", "body_html": "<p>b</p>", "image_asset_id": "g1"}]},
            {"type": "flashcards", "title": "FC", "cards": [
                {"front_html": "<p>on</p>", "back_html": "<p>arka</p>", "front_asset_id": "g1"}]},
        ],
    }
    async with Client(server.mcp) as c:
        r = await c.call_tool("build_from_spec", {"spec": spec})
        pid = r.data.project_id
        v = await c.call_tool("validate_package", {"project_id": pid})
        assert v.data.ok, v.data.errors


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
