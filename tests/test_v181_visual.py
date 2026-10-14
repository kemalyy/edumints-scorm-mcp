"""v1.8.1 G2 (#169) — tek görsel tespiti: vaka görselleri ve {{asset}} gömmeleri de görsel sayılır."""
import pytest
from pydantic import TypeAdapter

from core.antislop import _has_visual, lint_course, lint_errors
from core.project import Project, Screen

TA = TypeAdapter(Screen)
OPTS = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]


def S(d):
    return TA.validate_python(d)


@pytest.mark.parametrize("d", [
    {"type": "content_slide", "title": "t", "media_asset_id": "i"},
    {"type": "content_slide", "title": "t", "blocks": [{"asset_id": "i"}]},
    {"type": "mcq", "title": "t", "prompt_html": "p", "options": OPTS,
     "stimulus": {"asset_id": "i", "alt": "a"}},
    {"type": "poll", "title": "t", "prompt_html": "p",
     "options": [{"id": "a", "text_html": "a"}, {"id": "b", "text_html": "b"}],
     "stimulus": {"asset_id": "i", "alt": "a"}},
    {"type": "adaptive_practice", "title": "t", "adaptive": {"strategy": "elo"},
     "items": [{"id": f"q{k}", "prompt_html": "p", "options": OPTS,
                "stimulus": {"asset_id": "i", "alt": "a"} if k == 2 else None} for k in range(4)]},
    {"type": "content_slide", "title": "t", "body_html": "<p>Bak: {{asset:i}}</p>"},
    {"type": "mcq", "title": "t", "prompt_html": "<p>{{asset:i}} nedir?</p>", "options": OPTS},
], ids=["media", "blocks", "mcq-stimulus", "poll-stimulus", "adaptive-item-stimulus",
        "asset-embed-body", "asset-embed-prompt"])
def test_visual_fields_count(d):
    assert _has_visual(S(d))


def test_text_only_stimulus_is_not_visual():
    assert not _has_visual(S({"type": "mcq", "title": "t", "prompt_html": "p", "options": OPTS,
                              "stimulus": {"text_html": "<p>vaka</p>"}}))


def test_report_sequence_no_text_only_run_even_strict():
    sc = [S({"type": "fill_blank", "id": "f", "title": "F", "prompt_html": "<p>x ___</p>",
             "blanks": [{"id": "b", "accepted": ["y"]}], "stimulus": {"text_html": "<p>v</p>"}}),
          S({"type": "true_false", "id": "t", "title": "T", "prompt_html": "<p>x</p>", "correct": True,
             "stimulus": {"text_html": "<p>v</p>"}}),
          S({"type": "mcq", "id": "m1", "title": "M", "prompt_html": "<p>x</p>", "options": OPTS}),
          S({"type": "mcq", "id": "m2", "title": "M", "prompt_html": "<p>x</p>", "options": OPTS,
             "stimulus": {"asset_id": "img", "alt": "a", "text_html": "<p>v</p>"}}),
          S({"type": "poll", "id": "p", "title": "P", "prompt_html": "<p>x</p>",
             "options": [{"id": "a", "text_html": "a"}, {"id": "b", "text_html": "b"}],
             "stimulus": {"text_html": "<p>v</p>"}})]
    p = Project(id="p", title="t", composition="auto", screens=sc)
    assert "text_only_run" not in {i.code for i in lint_course(p)}
    assert "text_only_run" not in {i.code for i in lint_errors(p, strict=True)}
