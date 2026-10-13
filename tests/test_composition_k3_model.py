import pytest
from fastmcp import Client
from pydantic import TypeAdapter, ValidationError

import server
from core.project import CompositionDefaults, Project, Screen, Stimulus
from core.validator import validate_project

TA = TypeAdapter(Screen)
OPTS = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]


def test_stimulus_needs_asset_or_text_and_forbids_extra():
    assert Stimulus(text_html="<p>Vaka</p>").text_html
    assert Stimulus(asset_id="x", alt="a").asset_id
    with pytest.raises(ValidationError):
        Stimulus(caption="yalnız alt yazı")
    with pytest.raises(ValidationError):
        Stimulus(text_html="x", colour="red")


@pytest.mark.parametrize("t,extra", [
    ("mcq", {"prompt_html": "p", "options": OPTS}),
    ("true_false", {"prompt_html": "p", "correct": True}),
    ("fill_blank", {"prompt_html": "p ___", "blanks": [{"id": "b1", "accepted": ["x"]}]}),
    ("drag_drop", {"prompt_html": "p", "items": [{"id": "i", "text_html": "i",
                   "correct_target_id": "t"}], "targets": [{"id": "t", "label_html": "t"}]}),
    ("matching", {"prompt_html": "p", "pairs": [{"id": "1", "left_html": "a", "right_html": "b"},
                                                {"id": "2", "left_html": "c", "right_html": "d"}]}),
    ("sorting", {"prompt_html": "p", "items": [{"id": "1", "text_html": "a"},
                                               {"id": "2", "text_html": "b"}]}),
])
def test_question_types_accept_stimulus(t, extra):
    s = TA.validate_python({"type": t, "title": "q", "stimulus": {"text_html": "<p>V</p>"}, **extra})
    assert s.stimulus.text_html == "<p>V</p>"


def test_adaptive_item_takes_stimulus():
    s = TA.validate_python({"type": "adaptive_practice", "title": "a",
                            "adaptive": {"strategy": "elo"}, "items": [
        {"id": f"i{k}", "prompt_html": "p", "options": OPTS, "stimulus": {"text_html": "V"}}
        for k in range(4)]})
    assert s.items[0].stimulus.text_html == "V"


def test_question_default_is_unset():
    assert CompositionDefaults().question is None


def test_validator_rejects_dangling_stimulus_asset():
    s = TA.validate_python({"type": "mcq", "title": "q", "prompt_html": "p", "options": OPTS,
                            "stimulus": {"asset_id": "nope", "alt": "x"}})
    errs = validate_project(Project(id="p", title="t", screens=[s]))
    assert any("nope" in e.message for e in errs)


async def test_set_composition_question():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "x"})).data.project_id
        await c.call_tool("set_composition", {"project_id": pid, "mode": "auto",
                                              "question": "split"})
    p = await server._load(pid, await server._owner())
    assert p.composition_defaults.question == "split"
    assert p.composition_defaults.visual is None  # yalnız question cevaplandı: visual hâlâ sorulacak
