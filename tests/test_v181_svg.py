"""v1.8.1 #178 — build_from_spec içinde SVG (base64'süz) + SVG temizliği (spec ve svg_to_asset)."""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server
from core.svg_safe import SvgError, clean

OK = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
EVIL = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<script>alert(1)</script><rect onclick="alert(2)" width="1" height="1"/>'
        '<a href="javascript:alert(3)"><text>x</text></a><image xlink:href="https://evil.example/x.png"/>'
        '<foreignObject><div>y</div></foreignObject><use href="#r"/></svg>')


def test_clean_removes_active_content_keeps_shapes():
    out = clean(EVIL)
    low = out.lower()
    for bad in ("<script", "onclick", "javascript:", "evil.example", "foreignobject"):
        assert bad not in low, bad
    assert "<rect" in out and 'href="#r"' in out


def test_clean_rejects_entities_and_non_svg():
    with pytest.raises(SvgError):
        clean('<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>')
    with pytest.raises(SvgError):
        clean("<html><body>no</body></html>")


async def _asset_bytes(pid, aid):
    p = await server._load(pid, await server._owner())
    ref = next(a for a in p.assets if a.id == aid)
    return ref, await server.SVC.store.get_asset_bytes(pid, aid)


async def test_build_from_spec_accepts_svg_assets():
    spec = {"title": "x", "assets": [{"id": "d1", "svg": EVIL}],
            "screens": [{"type": "content_slide", "title": "c", "media_asset_id": "d1", "media_alt": "d"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
    ref, data = await _asset_bytes(pid, "d1")
    assert ref.mime == "image/svg+xml" and ref.filename.endswith(".svg")
    assert b"<script" not in data.lower() and b"<rect" in data


@pytest.mark.parametrize("asset", [{"id": "d", "svg": OK, "source": "data:image/png;base64,AA=="},
                                   {"id": "d"}])
async def test_build_from_spec_needs_exactly_one_of_svg_source(asset):
    spec = {"title": "x", "assets": [asset], "screens": [{"type": "title_slide", "title": "t"}]}
    async with Client(server.mcp) as c:
        with pytest.raises(ToolError, match="invalid_spec"):
            await c.call_tool("build_from_spec", {"spec": spec})


async def test_svg_to_asset_is_cleaned_too():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
        ref = (await c.call_tool("svg_to_asset", {"project_id": pid, "svg_content": EVIL})).data
    _, data = await _asset_bytes(pid, ref.id)
    assert b"<script" not in data.lower() and b"onclick" not in data.lower()


_NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'


@pytest.mark.parametrize("payload, bad", [
    ('<a><set attributeName="href" to="javascript:alert(1)"/><text>x</text></a>', "javascript:"),
    ('<a><animate attributeName="xlink:href" values="javascript:alert(1)"/><text>x</text></a>', "javascript:"),
    ('<h:iframe xmlns:h="http://www.w3.org/1999/xhtml" srcdoc="&lt;script&gt;alert(1)&lt;/script&gt;"/>', "iframe"),
    ('<h:object xmlns:h="http://www.w3.org/1999/xhtml" data="javascript:alert(1)"/>', "object"),
    ('<h:meta xmlns:h="http://www.w3.org/1999/xhtml" http-equiv="refresh" content="0;url=x"/>', "refresh"),
    ('<style>@import url(https://evil.example/t.css);</style>', "evil.example"),
    ('<rect style="fill:url(https://evil.example/t)" width="1" height="1"/>', "evil.example"),
    ('<g xml:base="javascript:alert(1)"><rect width="1" height="1"/></g>', "javascript:"),
    ('<x:foo xmlns:x="urn:other" onclick="1"/>', "urn:other"),
])
def test_clean_blocks_review_bypasses(payload, bad):
    out = clean(f"<svg {_NS}>{payload}</svg>")
    assert bad not in out.lower(), out


def test_clean_keeps_safe_animation_and_local_style():
    out = clean(f'<svg {_NS}><rect id="r" style="fill:url(#g)" width="1" height="1">'
                '<animate attributeName="opacity" values="0;1" dur="1s"/></rect></svg>')
    assert "<animate" in out and "url(#g)" in out


async def test_invalid_svg_rejected_before_any_asset_is_stored(monkeypatch):
    # final inceleme I2: geçersiz SVG, önceki asset'ler depoya yazılmadan reddedilmeli (sahipsiz asset yok)
    calls = []
    orig = server.SVC.store.put_asset

    async def spy(pid, data, ref):
        calls.append(ref.id)
        return await orig(pid, data, ref)

    monkeypatch.setattr(server.SVC.store, "put_asset", spy)
    spec = {"title": "x", "assets": [{"id": "ok", "svg": OK},
                                     {"id": "bad", "svg": '<!DOCTYPE x [<!ENTITY a "b">]><svg/>'}],
            "screens": [{"type": "title_slide", "title": "t"}]}
    async with Client(server.mcp) as c:
        with pytest.raises(ToolError, match="invalid_svg"):
            await c.call_tool("build_from_spec", {"spec": spec})
    assert calls == []
