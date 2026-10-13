"""K3 — classic soru ekranları bayt-aynı (cevap-alanı yardımcılarına çıkarma bunu bozmamalı)."""
import os

from components.renderer import render_html
from core.project import Project
from tests.test_composition_k3_model import OPTS, TA

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "question_types_classic.html")
SPECS = [
    {"type": "mcq", "id": "m", "title": "M", "prompt_html": "<p>P</p>", "options": OPTS},
    {"type": "mcq", "id": "m2", "title": "M2", "prompt_html": "<p>P</p>", "multi_select": True,
     "options": [dict(o, feedback_html="<p>G</p>") for o in OPTS]},
    {"type": "true_false", "id": "t", "title": "T", "prompt_html": "<p>P</p>", "correct": True},
    {"type": "fill_blank", "id": "f", "title": "F", "prompt_html": "<p>P ___</p>",
     "blanks": [{"id": "b1", "accepted": ["x"]}]},
    {"type": "drag_drop", "id": "d", "title": "D", "prompt_html": "<p>P</p>",
     "items": [{"id": "i", "text_html": "I", "correct_target_id": "g"}],
     "targets": [{"id": "g", "label_html": "G"}]},
    {"type": "matching", "id": "x", "title": "X", "prompt_html": "<p>P</p>",
     "pairs": [{"id": "1", "left_html": "a", "right_html": "b"},
               {"id": "2", "left_html": "c", "right_html": "d"}]},
    {"type": "sorting", "id": "s", "title": "S", "prompt_html": "<p>P</p>",
     "items": [{"id": "1", "text_html": "a"}, {"id": "2", "text_html": "b"}]},
    {"type": "adaptive_practice", "id": "a", "title": "A", "adaptive": {"strategy": "elo"},
     "items": [{"id": f"i{k}", "prompt_html": "p", "options": OPTS} for k in range(4)]},
]


def _render():
    return render_html(Project(id="p", title="t", screens=[TA.validate_python(x) for x in SPECS]),
                       mode="preview", runtime_js="/*RT*/")


def test_classic_question_types_byte_identical():
    with open(FIX, encoding="utf-8") as f:
        assert _render() == f.read(), "classic soru çıktısı kilitten saptı"


def test_classic_stimulus_rendered_above_prompt():
    s = TA.validate_python(dict(SPECS[0], stimulus={"text_html": "<p>VAKA</p>", "asset_id": "img",
                                                    "alt": "ALT", "caption": "CAP"}))
    html = render_html(Project(id="p", title="t", screens=[s]), mode="package", runtime_js="")
    sec = html[html.index('<section class="screen"'):html.index("</section>")]
    assert sec.index('class="stimulus') < sec.index('class="rich prompt"')
    assert "VAKA" in sec and 'alt="ALT"' in sec and "CAP" in sec
    assert ".stimulus{" in html  # STIMULUS_CSS yalnız uyaran varsa


def test_classic_adaptive_item_stimulus_inside_item():
    d = dict(SPECS[7], items=[dict(it, stimulus={"text_html": "<p>OGE_VAKA</p>"})
                              for it in SPECS[7]["items"]])
    html = render_html(Project(id="p", title="t", screens=[TA.validate_python(d)]),
                       mode="package", runtime_js="")
    item = html[html.index('<div class="ap-item"'):]
    assert item.index("OGE_VAKA") < item.index("ap-prompt")


def test_no_stimulus_css_without_stimulus():
    assert ".stimulus{" not in _render()
