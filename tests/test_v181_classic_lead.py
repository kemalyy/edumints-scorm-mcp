"""v1.8.1 #179 — classic projede kicker/lead sade gösterim (yalnız dolu ekranlar; boşlar bayt-aynı)."""
import re

from pydantic import TypeAdapter

from components.renderer import render_html
from core.antislop import lint_course
from core.project import Project, Screen

TA = TypeAdapter(Screen)
OPTS = [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]


def sec(d):
    html = render_html(Project(id="p", title="t", screens=[TA.validate_python(d)]),
                       mode="package", runtime_js="")
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0), html


def test_classic_shows_kicker_and_lead_around_title():
    s, html = sec({"type": "content_slide", "title": "Başlık", "kicker": "ADIM 1",
                   "lead": "Tek mesaj burada.", "body_html": "<p>gövde</p>"})
    k, h, ld = s.index("kicker-classic"), s.index('class="screen-title"'), s.index("lead-classic")
    assert k < h < ld and "ADIM 1" in s and "Tek mesaj burada." in s
    assert ".lead-classic{" in html  # CSS yalnız kullanılınca


def test_classic_title_slide_and_question():
    s, _ = sec({"type": "title_slide", "title": "Kurs", "lead": "Neden önemli?"})
    assert s.index('class="title-main"') < s.index("lead-classic")
    s, _ = sec({"type": "mcq", "title": "Soru", "lead": "Dikkat", "prompt_html": "<p>?</p>",
                "options": OPTS})
    assert s.index('class="screen-title"') < s.index("lead-classic") < s.index('class="rich prompt"')


def test_empty_screens_unchanged():
    s, html = sec({"type": "content_slide", "title": "Başlık", "body_html": "<p>gövde</p>"})
    assert "lead-classic" not in html and "kicker-classic" not in html


def test_info_message_updated():
    p = Project(id="p", title="t", screens=[TA.validate_python(
        {"type": "content_slide", "title": "a", "lead": "x"})])
    msg = next(i.message for i in lint_course(p) if i.code == "composition_ignored_classic")
    assert "sade" in msg
