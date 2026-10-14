"""v1.8.1 — hafif preview (#177), alt alanı yönlendirmesi + image_compare alt (#176), sızıntı mesajı (#174)."""
import json
import re

import pytest
from fastmcp import Client
from pydantic import TypeAdapter

import server
from components.renderer import render_html
from core.antislop import lint_course
from core.project import Project, Screen

TA = TypeAdapter(Screen)


async def _pid(c):
    pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
    for i in range(6):
        await c.call_tool("add_screen", {"project_id": pid, "screen": {
            "type": "content_slide", "title": f"Ekran {i}", "body_html": "<p>" + "metin " * 80 + "</p>"}})
    return pid


async def test_preview_default_is_light():
    async with Client(server.mcp) as c:
        pid = await _pid(c)
        res = await c.call_tool("preview", {"project_id": pid})
    d = res.structured_content
    assert d.get("inline_html") in (None, "")
    assert d["hosted_url"].startswith("http") and d["size_bytes"] > 100_000
    assert "compositions" in d and "composition_questions" in d
    assert len(json.dumps(d)) < 20_000


async def test_preview_include_html():
    async with Client(server.mcp) as c:
        pid = await _pid(c)
        res = await c.call_tool("preview", {"project_id": pid, "include_html": True})
    d = res.structured_content
    assert d["inline_html"].startswith("<!DOCTYPE html>") and d["size_bytes"] == len(d["inline_html"].encode())


@pytest.mark.parametrize("screen, field", [
    ({"type": "hotspot", "title": "h", "prompt_html": "<p>bul</p>", "image_asset_id": "i",
      "regions": [{"id": "r", "shape": "rect", "coords": [1, 1, 5, 5]}]}, "image_alt"),
    ({"type": "flashcards", "title": "f", "cards": [{"front_html": "a", "back_html": "b",
                                                     "front_asset_id": "i"}]}, "front_alt"),
    ({"type": "content_slide", "title": "c", "media_asset_id": "i"}, "media_alt"),
    ({"type": "content_slide", "title": "c", "blocks": [{"asset_id": "i"}]}, "caption"),
    ({"type": "image_compare", "title": "ic", "before_asset_id": "i", "after_asset_id": "j"}, "before_alt"),
])
def test_missing_alt_message_names_target_field(screen, field):
    p = Project(id="p", title="t", screens=[TA.validate_python(screen)])
    msgs = [i.message for i in lint_course(p) if i.code == "missing_alt_text"]
    assert msgs and any(f"→ `{field}`" in m for m in msgs), msgs


def _ic_html(**kw):
    s = TA.validate_python({"type": "image_compare", "id": "ic", "title": "ic",
                            "before_asset_id": "i", "after_asset_id": "j", **kw})
    return render_html(Project(id="p", title="t", screens=[s]), mode="package", runtime_js="")


def test_image_compare_alt_fields_render_and_default_unchanged():
    html = _ic_html(before_alt="Gerçek giriş sayfası", after_alt="Sahte giriş sayfası")
    assert 'alt="Gerçek giriş sayfası"' in html and 'alt="Sahte giriş sayfası"' in html
    base = _ic_html(before_label="Önce", after_label="Sonra")
    assert 'alt="Önce"' in base and 'alt="Sonra"' in base  # alt verilmezse bugünkü davranış


def test_leak_message_shows_original_text():
    s = TA.validate_python({
        "type": "mcq", "title": "q", "prompt_html": "<p>?</p>",
        "stimulus": {"text_html": "<p>Tedarikçiyi kayıtlı telefon numarasından arayıp faturayı teyit etmek gerekir.</p>"},
        "options": [{"id": "a", "text_html": "Tedarikçiyi kayıtlı telefon numarasından arayıp faturayı teyit etmek",
                     "correct": True}, {"id": "b", "text_html": "Bağlantıyı aç"}]})
    msg = next(i.message for i in lint_course(Project(id="p", title="t", screens=[s]))
               if i.code == "stimulus_answer_leak")
    assert "kayıtlı telefon numarasından" in msg and not re.search(r"kayitli|numarasindan", msg)
