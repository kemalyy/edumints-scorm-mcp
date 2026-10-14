"""v1.8.1 — yazma-anı doğrulaması (#170), update_screen ezmeyi korur (#168), hata kodları (#171)."""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import TypeAdapter

import server
from core.composition import CompositionError, resolve_spec
from core.composition_auto import summary
from core.project import Project, Screen

TA = TypeAdapter(Screen)
OPTS = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]
HS = {"type": "hotspot", "id": "h", "title": "H", "prompt_html": "<p>bul</p>", "image_asset_id": "i",
      "image_alt": "x", "regions": [{"id": "r", "shape": "rect", "coords": [1, 1, 5, 5]}]}
MCQ = {"type": "mcq", "id": "m", "title": "M", "prompt_html": "<p>?</p>", "options": OPTS}


async def _load(pid):
    return await server._load(pid, await server._owner())


async def _project(c, *screens):
    pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
    for s in screens:
        await c.call_tool("add_screen", {"project_id": pid, "screen": s})
    return pid


def _screen(p, sid):
    return next(s for s in p.screens if s.id == sid)


# --- #171 hata kodları -------------------------------------------------------------------------
def test_not_applicable_vs_unknown_codes():
    with pytest.raises(CompositionError) as e:
        resolve_spec("hero-focal", "mcq")
    assert e.value.code == "composition_not_applicable"
    assert "question-column" in str(e.value)  # tipe uyan desenler önerilir
    with pytest.raises(CompositionError) as e:
        resolve_spec("nope", "mcq")
    assert e.value.code == "composition_unknown"


# --- #168 update_screen ezmeyi korur ------------------------------------------------------------
async def test_update_screen_keeps_override_when_key_absent():
    async with Client(server.mcp) as c:
        pid = await _project(c, HS)
        await c.call_tool("set_screen_composition", {"project_id": pid, "screen_id": "h",
                                                     "composition": "visual-stack"})
        await c.call_tool("update_screen", {"project_id": pid, "screen_id": "h",
                                            "screen": dict(HS, image_alt="yeni alt")})
    s = _screen(await _load(pid), "h")
    assert s.composition == "visual-stack" and s.image_alt == "yeni alt"


async def test_update_screen_null_clears_and_value_replaces():
    async with Client(server.mcp) as c:
        pid = await _project(c, HS)
        await c.call_tool("set_screen_composition", {"project_id": pid, "screen_id": "h",
                                                     "composition": "visual-stack"})
        await c.call_tool("update_screen", {"project_id": pid, "screen_id": "h",
                                            "screen": dict(HS, composition=None)})
        assert _screen(await _load(pid), "h").composition is None
        await c.call_tool("update_screen", {"project_id": pid, "screen_id": "h",
                                            "screen": dict(HS, composition="split-thirds")})
        assert _screen(await _load(pid), "h").composition == "split-thirds"


async def test_update_screen_type_change_does_not_carry_override():
    async with Client(server.mcp) as c:
        pid = await _project(c, HS)
        await c.call_tool("set_screen_composition", {"project_id": pid, "screen_id": "h",
                                                     "composition": "visual-stack"})
        await c.call_tool("update_screen", {"project_id": pid, "screen_id": "h",
                                            "screen": dict(MCQ, id="h")})
    assert _screen(await _load(pid), "h").composition is None


# --- #170 yazma-anı doğrulaması --------------------------------------------------------------------
@pytest.mark.parametrize("bad, code", [
    (dict(MCQ, composition="hero-focal"), "composition_not_applicable"),
    (dict(MCQ, composition="nope"), "composition_unknown"),
    (dict(MCQ, stimulus={"asset_id": "i"}), "stimulus_without_alt"),
])
async def test_writes_reject_invalid_screen(bad, code):
    async with Client(server.mcp) as c:
        pid = await _project(c, MCQ)
        before = (await _load(pid)).model_dump_json()
        with pytest.raises(ToolError, match=code):
            await c.call_tool("update_screen", {"project_id": pid, "screen_id": "m", "screen": bad})
        with pytest.raises(ToolError, match=code):
            await c.call_tool("add_screen", {"project_id": pid, "screen": dict(bad, id="m2")})
        assert (await _load(pid)).model_dump_json() == before  # proje değişmedi


async def test_build_from_spec_rejects_invalid_screen():
    spec = {"title": "x", "screens": [MCQ, dict(MCQ, id="m2", composition="hero-focal")]}
    async with Client(server.mcp) as c:
        with pytest.raises(ToolError, match="composition_not_applicable"):
            await c.call_tool("build_from_spec", {"spec": spec})


# --- #170 lint: geçersiz kayıt düşmez, komşu sabit ------------------------------------------------
def test_invalid_composition_kept_with_fallback_and_neighbour_stable():
    def proj(bad):
        sc = [TA.validate_python(dict(MCQ, id=f"m{i}")) for i in range(5)]
        if bad:
            sc[2] = TA.validate_python(dict(MCQ, id="m2", composition="hero-focal"))
        return Project(id="p", title="t", composition="auto", screens=sc)
    good, bad = summary(proj(False)), summary(proj(True))
    assert len(bad) == 5
    rec = next(r for r in bad if r["screen_id"] == "m2")
    assert rec["error"] == "composition_not_applicable" and rec["fallback"] == "question-column"
    assert [r["preset"] for r in bad if r["screen_id"] != "m2"] == \
           [r["preset"] for r in good if r["screen_id"] != "m2"]
