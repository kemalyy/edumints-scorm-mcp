"""v1.8.1 #175 — kompozisyonlu her ekranda başlık (kicker + başlık) DOM'da ilk içerik öğesi."""
import re

import pytest
from pydantic import TypeAdapter

from components.renderer import render_html
from core.composition_auto import summary
from core.project import Project, Screen
from tests.visual.generate_fixtures import collect_screens

TA = TypeAdapter(Screen)
SAMPLES = collect_screens()
STIM = {"text_html": "<p>VAKA metni burada.</p>", "asset_id": "i", "alt": "vaka görseli"}
# içerik taşıyan ilk öğe (dekoratif aria-hidden svg/ikon hariç)
_CONTENT = re.compile(r'<(?:p|h1|h2|h3|img|figure|button|select|input|textarea|iframe|ol|ul|table|'
                      r'video|div class="(?:rich|stimulus|ap-|scen-|game-|esc-|term-|tmr-|chart|hotspot))')


def _section(d, extra=None):
    s = TA.validate_python(dict(d, kicker="ÜST ETİKET", **(extra or {})))
    html = render_html(Project(id="p", title="t", composition="auto", screens=[s]),
                       mode="package", runtime_js="")
    return re.search(r'<section class="screen".*?</section>', html, re.S).group(0)


@pytest.mark.parametrize("t", sorted(SAMPLES))
def test_title_is_first_content(t):
    screen = {k: v for k, v in SAMPLES[t][0].items() if k not in ("composition", "lead", "kicker")}
    sec = _section(screen)
    m = _CONTENT.search(sec[sec.index("comp-grid") if "comp-grid" in sec else 0:])
    assert m, t
    first = sec[sec.index("comp-grid"):][m.start():m.start() + 60] if "comp-grid" in sec else ""
    assert 'class="kicker"' in first or "screen-title" in first or "title-main" in first or \
        t == "summary", (t, first)


@pytest.mark.parametrize("t", ["mcq", "true_false", "poll", "branching"])
def test_stimulus_screen_order_title_case_prompt(t):
    screen = {k: v for k, v in SAMPLES[t][0].items() if k not in ("composition", "lead", "kicker")}
    sec = _section(screen, {"stimulus": STIM, "composition": "split-thirds"})
    i_title, i_case = sec.index("screen-title"), sec.index("VAKA metni")
    i_prompt = sec.index('class="rich prompt"')
    assert i_title < i_case < i_prompt


def test_title_slot_sits_above_support_and_focal_spans_title_row():
    d = {"type": "content_slide", "id": "c", "title": "Başlık", "media_asset_id": "i",
         "media_alt": "a", "body_html": "<p>gövde</p>", "composition": "split-thirds"}
    sec = _section(d)
    title = re.search(r'class="slot slot-title" style="grid-area:(\d+) / (\d+) / (\d+) / (\d+)"', sec)
    sup = re.search(r'class="slot slot-support" style="grid-area:(\d+) / (\d+) / (\d+) / (\d+)"', sec)
    foc = re.search(r'class="slot slot-focal" style="grid-area:(\d+) / (\d+) / (\d+) / (\d+)"', sec)
    assert title and sup and foc
    t, s, f = [tuple(map(int, m.groups())) for m in (title, sup, foc)]
    assert t[0] + 1 == s[0] and t[1] == s[1] and t[3] == s[3]  # başlık destek sütununun üstünde
    assert f[0] == t[0] and f[2] == s[2]                        # odak başlık satırını da kaplar
    assert sec.index("slot-title") < sec.index("slot-focal") < sec.index("slot-support")
    assert "--comp-rows:auto 1fr 1fr 1fr" in sec


def test_statement_title_row_inserted_before_support():
    d = {"type": "content_slide", "id": "c", "title": "Başlık", "lead": "%91",
         "body_html": "<p>kısa</p>", "composition": "statement"}
    sec = _section(d)
    t = tuple(map(int, re.search(r'slot-title" style="grid-area:(\d+) / (\d+) / (\d+) / (\d+)"', sec).groups()))
    f = tuple(map(int, re.search(r'slot-focal" style="grid-area:(\d+) / (\d+) / (\d+) / (\d+)"', sec).groups()))
    assert f[2] <= t[0]  # odak (büyük lead) başlık satırıyla çakışmaz


def test_summary_dom_order_starts_with_title():
    s = TA.validate_python({"type": "content_slide", "id": "c", "title": "a", "media_asset_id": "i"})
    assert summary(Project(id="p", title="t", composition="auto", screens=[s]))[0]["dom_order"][0] == "title"


def test_single_area_title_slide_keeps_title_in_panel():
    # hero-focal: tek alan (support) — başlık zaten ilk; ayrılmaz (arka plan üstünde okunur panelde kalır)
    d = {"type": "title_slide", "id": "t", "title": "Gelen kutunda bir tuzak var", "lead": "Bul, tıklama.",
         "background_asset_id": "i", "composition": "hero-focal"}
    sec = _section(d)
    assert "slot-title" not in sec
    sup = sec[sec.index("slot-support"):]
    assert "title-main" in sup and "Bul, tıklama." in sup


def test_four_row_tracks_only_with_title_row():
    # final inceleme M2: başlık satırı eklenmeyen (destek-önce) ızgarada boş 4. satır + gap olmamalı
    from components.templates import COMPOSITION_CSS
    css = re.sub(r"\s+", " ", COMPOSITION_CSS)
    for rule in re.finditer(r"([^{}]*)\{[^{}]*grid-template-rows:auto auto auto auto", css):
        sel = rule.group(1)
        if "stimulus" in sel:  # vakalı visual-stack: odak (vaka) önce → başlık her zaman ayrılır
            continue
        assert "[data-title]" in sel, sel
