"""K2 final review düzeltmeleri — tercih vs monotonluk, ekran kompozisyonu setter'ı, kontrol sırası,
centered'ın K2'den çıkarılması."""
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError as MCPToolError

import server
from components.renderer import render_html
from core.antislop import lint_course
from core.composition import CompositionError, resolve_spec
from core.composition_auto import resolve_project
from core.composition_questions import build_questions
from core.project import (CompositionDefaults, HotspotRegion, HotspotScreen,
                          LabeledDiagramScreen, Project)


def HS(i, **kw):
    kw.setdefault("prompt_html", "<p>Bul</p>")
    return HotspotScreen(id=f"h{i}", title=f"H{i}", image_asset_id="img",
                         regions=[HotspotRegion(id="r", shape="rect", coords=[1, 1, 5, 5])], **kw)


def P(*s, defaults=None):
    return Project(id="p", title="t", composition="auto", screens=list(s),
                   composition_defaults=defaults)


@pytest.mark.parametrize("visual,preset", [("stack", "visual-stack"), ("split", "split-thirds")])
def test_preference_is_honoured_on_every_screen(visual, preset):
    out = resolve_project(P(*[HS(i) for i in range(8)],
                            defaults=CompositionDefaults(visual=visual)))
    assert [r.preset for r in out] == [preset] * 8


def test_split_preference_alternates_mirror():
    out = resolve_project(P(*[HS(i) for i in range(4)], defaults=CompositionDefaults(visual="split")))
    assert [r.mirror for r in out] == [False, True, False, True]


def test_no_monotony_warning_for_preference_driven_runs():
    p = P(*[HS(i) for i in range(6)], defaults=CompositionDefaults(visual="stack"))
    assert "composition_monotony" not in {i.code for i in lint_course(p)}


def test_centered_no_longer_applies_to_k2():
    with pytest.raises(CompositionError):
        resolve_spec("centered", "hotspot")


def _section(html):
    return html[html.index('<section class="screen"'):html.index("</section>")]


def test_quiz_controls_come_after_inputs():
    lab = LabeledDiagramScreen.model_validate({
        "id": "l", "title": "L", "image_asset_id": "img",
        "labels": [{"id": "a", "x": 1, "y": 1, "text": "A"}, {"id": "b", "x": 5, "y": 5, "text": "B"}]})
    for s, anchor in ((HS(1), "hotspot-stage"), (lab, "ld-select")):
        sec = _section(render_html(P(s), mode="package", runtime_js=""))
        assert sec.rindex(anchor) < sec.index("btn-check") < sec.index('class="feedback"'), anchor


def test_screen_question_applies_through_dedicated_tool():
    qs = build_questions(P(HS(1, prompt_html="<p>" + " ".join(["k"] * 30) + "</p>"),
                           defaults=CompositionDefaults()))
    assert qs[0]["apply"] == {"tool": "set_screen_composition",
                              "args": {"screen_id": "h1", "composition": "$value"}}


async def test_set_screen_composition_keeps_other_fields_and_validates():
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
           "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    spec = {"title": "x", "assets": [{"id": "img", "filename": "i.png", "source": png}],
            "screens": [{"type": "hotspot", "id": "h1", "title": "H", "lead": "KALSIN",
                         "prompt_html": "<p>Bul</p>", "image_asset_id": "img",
                         "regions": [{"id": "r", "shape": "rect", "coords": [1, 1, 5, 5],
                                      "feedback_html": "<p>GEREKCE</p>"}]}]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
        await c.call_tool("set_screen_composition",
                          {"project_id": pid, "screen_id": "h1", "composition": "split-thirds"})
        with pytest.raises(MCPToolError):
            await c.call_tool("set_screen_composition",
                              {"project_id": pid, "screen_id": "h1", "composition": "nope"})
    p = await server._load(pid, await server._owner())
    s = p.screens[0]
    assert s.composition == "split-thirds" and s.lead == "KALSIN"
    assert s.regions[0].feedback_html == "<p>GEREKCE</p>"
