"""K1 — sunucu: yeni projeler auto + mint; list_compositions/set_composition; kompozisyon
hataları build'i bloklar. Classic + "default" tema bayt-aynı yolu korur."""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

import server


async def _project(pid):
    owner = await server._owner()
    return await server._load(pid, owner)


async def test_create_project_is_auto_with_mint():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
    p = await _project(pid)
    assert p.composition == "auto" and p.theme.name == "mint"


async def test_create_project_classic_keeps_default_theme():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project",
                                 {"title": "x", "composition": "classic"})).data.project_id
    p = await _project(pid)
    assert p.composition == "classic" and p.theme.name == "default"


async def test_build_from_spec_auto_and_explicit_theme_respected():
    spec = {"title": "x", "theme": "style-minimal",
            "screens": [{"type": "content_slide", "title": "a", "body_html": "<p>b</p>"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
    p = await _project(pid)
    assert p.composition == "auto" and p.theme.name == "style-minimal"


async def test_build_from_spec_default_theme_becomes_mint_only_when_auto():
    base = {"title": "x", "screens": [{"type": "title_slide", "title": "a"}]}
    async with Client(server.mcp) as c:
        auto = (await c.call_tool("build_from_spec", {"spec": base})).data.project_id
        classic = (await c.call_tool("build_from_spec",
                                     {"spec": {**base, "composition": "classic"}})).data.project_id
    assert (await _project(auto)).theme.name == "mint"
    assert (await _project(classic)).theme.name == "default"


async def test_list_compositions():
    async with Client(server.mcp) as c:
        out = (await c.call_tool("list_compositions", {})).data
    assert out["count"] == 7
    assert {x["name"] for x in out["compositions"]} >= {"centered", "split-thirds"}


async def test_set_composition_roundtrip():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project",
                                 {"title": "x", "composition": "classic"})).data.project_id
        await c.call_tool("set_composition", {"project_id": pid, "mode": "auto"})
    assert (await _project(pid)).composition == "auto"


async def test_invalid_composition_blocks_build():
    spec = {"title": "x", "screens": [{"type": "content_slide", "title": "a",
                                       "composition": "nope"}]}
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as e:
            await c.call_tool("build_from_spec", {"spec": spec})
    assert "composition_unknown" in str(e.value) or "nope" in str(e.value)


async def test_lint_and_preview_expose_composition_summary():
    spec = {"title": "x", "screens": [{"type": "content_slide", "id": "c1", "title": "a",
                                       "body_html": "<p>b</p>"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
        lint = (await c.call_tool("lint_course", {"project_id": pid})).data
        prev = (await c.call_tool("preview", {"project_id": pid})).data
    assert lint["compositions"][0]["screen_id"] == "c1"
    assert prev.compositions[0]["preset"] == "centered"


async def test_lint_clean_ignores_info():
    spec = {"title": "x", "composition": "classic",
            "screens": [{"type": "content_slide", "title": "a", "lead": "L"}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
        lint = (await c.call_tool("lint_course", {"project_id": pid})).data
    assert any(i["code"] == "composition_ignored_classic" for i in lint["issues"])
    assert lint["error_count"] == 0
