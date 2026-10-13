"""K3 final inceleme düzeltmeleri."""
import re

from components.renderer import render_html
from core.antislop import lint_course
from core.composition_auto import resolve_project
from core.project import Project
from tests.test_composition_k3_classic import SPECS
from tests.test_composition_k3_model import TA


def _adaptive_with_stimulus():
    d = dict(SPECS[7], items=[dict(it, stimulus={"text_html": "<p>V</p>"}) for it in SPECS[7]["items"]])
    return TA.validate_python(d)


def test_adaptive_with_stimulus_keeps_title_before_exercise():
    s = _adaptive_with_stimulus()
    p = Project(id="p", title="t", composition="auto", screens=[s])
    assert resolve_project(p)[0].dom_order == "support-first"
    html = render_html(p, mode="package", runtime_js="")
    sec = re.search(r'<section class="screen".*?</section>', html, re.S).group(0)
    assert sec.index("screen-title") < sec.index("ap-check")


def _leak(stim_html, answer):
    s = TA.validate_python({"type": "mcq", "title": "q", "prompt_html": "<p>?</p>",
                            "stimulus": {"text_html": stim_html},
                            "options": [{"id": "a", "text_html": answer, "correct": True},
                                        {"id": "b", "text_html": "Başka"}]})
    return "stimulus_answer_leak" in {i.code for i in lint_course(Project(id="p", title="t", screens=[s]))}


def test_leak_turkish_dotted_capital_i():
    assert _leak("<p>Toplantı İSTANBUL ofisinde.</p>", "istanbul")
    assert _leak("<p>Toplantı istanbul ofisinde.</p>", "İstanbul")


def test_leak_turkish_dotless_i():
    assert _leak("<p>Su ILIK olmalı.</p>", "ılık")


def test_leak_html_entities():
    assert _leak("<p>Merkez New&nbsp;York.</p>", "New York")


def test_leak_still_word_bounded():
    assert not _leak("<p>İstanbullu müşteri aradı.</p>", "İstanbul")


def test_sorting_never_two_columns():
    spec = dict(SPECS[6], items=[{"id": f"{k}", "text_html": f"S{k}"} for k in range(8)])
    html = render_html(Project(id="p", title="t", composition="auto",
                               screens=[TA.validate_python(spec)]), mode="package", runtime_js="")
    assert 'data-many="1"' not in html
