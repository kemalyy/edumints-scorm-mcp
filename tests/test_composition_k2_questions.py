"""K2 — üretim-anı kompozisyon soruları (deterministik)."""
from fastmcp import Client

import server
from core.composition_questions import build_questions
from core.project import (CompositionDefaults, HotspotRegion, HotspotScreen, Project,
                          TitleSlide)


def HS(i, words=5, comp=None):
    return HotspotScreen(id=f"h{i}", title=f"H{i}", composition=comp,
                         prompt_html="<p>" + " ".join(["k"] * words) + "</p>",
                         image_asset_id="img",
                         regions=[HotspotRegion(id="r", shape="rect", coords=[1, 1, 5, 5])])


def P(*s, comp="auto", defaults=None):
    return Project(id="p", title="t", composition=comp, screens=list(s),
                   composition_defaults=defaults)


def ids(qs):
    return [q["id"] for q in qs]


def test_course_question_needs_three_k2_screens_and_unset_defaults():
    assert "visual_layout" not in ids(build_questions(P(HS(1), HS(2))))
    q = build_questions(P(HS(1), HS(2), HS(3)))[0]
    assert q["id"] == "visual_layout" and q["scope"] == "course" and q["default"] == "auto"
    assert [o["value"] for o in q["options"]] == ["stack", "split", "auto"]
    assert q["apply"] == {"tool": "set_composition", "args": {"mode": "auto", "visual": "$value"}}
    assert "visual_layout" not in ids(build_questions(
        P(HS(1), HS(2), HS(3), defaults=CompositionDefaults(visual="auto"))))


def test_screen_questions_only_in_borderline_band_max_three():
    qs = build_questions(P(HS(1, 23), HS(2, 37), HS(3, 22), HS(4, 38), HS(5, 30), HS(6, 30),
                           defaults=CompositionDefaults(visual="auto")))
    assert ids(qs) == ["screen:h1", "screen:h2", "screen:h5"]
    q = qs[0]
    assert q["scope"] == "screen" and q["screen_id"] == "h1"
    assert [o["value"] for o in q["options"]] == ["visual-stack", "split-thirds"]
    assert q["default"] == "visual-stack"
    assert q["apply"] == {"tool": "set_screen_composition",
                          "args": {"screen_id": "h1", "composition": "$value"}}


def test_no_screen_question_when_explicit_or_preference_set():
    assert build_questions(P(HS(1, 30, comp="visual-stack"),
                             defaults=CompositionDefaults(visual="auto"))) == []
    assert build_questions(P(HS(1, 30), defaults=CompositionDefaults(visual="split"))) == []


def test_classic_and_non_k2_produce_nothing():
    assert build_questions(P(HS(1), HS(2), HS(3), comp="classic")) == []
    assert build_questions(P(TitleSlide(title="t"), TitleSlide(title="u"),
                             TitleSlide(title="v"))) == []


async def test_lint_and_preview_return_questions():
    png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
           "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    hs = {"type": "hotspot", "title": "H", "prompt_html": "<p>Bul</p>", "image_asset_id": "img",
          "regions": [{"id": "r", "shape": "rect", "coords": [1, 1, 5, 5]}]}
    spec = {"title": "x", "assets": [{"id": "img", "filename": "i.png", "source": png}],
            "screens": [dict(hs, id=f"h{i}") for i in range(3)]}
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("build_from_spec", {"spec": spec})).data.project_id
        lint = (await c.call_tool("lint_course", {"project_id": pid})).data
        prev = (await c.call_tool("preview", {"project_id": pid})).data
    assert lint["composition_questions"][0]["id"] == "visual_layout"
    assert prev.composition_questions[0]["id"] == "visual_layout"
