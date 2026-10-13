"""K4 — classic içerik etkileşimleri bayt-aynı (gövde yardımcılarına çıkarma bunu bozmamalı)."""
import os

from pydantic import TypeAdapter

from components.renderer import render_html
from core.project import Project, Screen

TA = TypeAdapter(Screen)
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "content_types_classic.html")
SPECS = [
    {"type": "accordion", "id": "ac", "title": "AC", "prompt_html": "<p>P</p>",
     "items": [{"title": "A1", "body_html": "<p>B1</p>"},
               {"title": "A2", "body_html": "<p>B2</p>", "image_asset_id": "img", "image_alt": "IA"}]},
    {"type": "tabs", "id": "tb", "title": "TB", "prompt_html": "<p>P</p>",
     "tabs": [{"label": "T1", "body_html": "<p>X1</p>"}, {"label": "T2", "body_html": "<p>X2</p>"},
              {"label": "T3", "body_html": "<p>X3</p>"}]},
    {"type": "flashcards", "id": "fc", "title": "FC",
     "cards": [{"front_html": "F1", "back_html": "K1"}, {"front_html": "F2", "back_html": "K2"}]},
    {"type": "timeline", "id": "tl", "title": "TL",
     "events": [{"date": "2020", "title": "E1", "body_html": "<p>D1</p>"},
                {"date": "2021", "title": "E2"}]},
    {"type": "summary", "id": "su", "title": "SU", "body_html": "<p>Bitti</p>", "show_score": True},
    {"type": "results_breakdown", "id": "rb", "title": "RB", "body_html": "<p>G</p>",
     "sections": [{"title": "S1", "screen_ids": ["ac"], "advice_html": "<p>Tekrar</p>"}]},
    {"type": "poll", "id": "po", "title": "PO", "prompt_html": "<p>Ne düşünüyorsun?</p>",
     "options": [{"id": "o1", "text_html": "Evet"}, {"id": "o2", "text_html": "Hayır"}],
     "allow_text": True, "reflection_html": "<p>Teşekkürler</p>"},
    {"type": "worked_example", "id": "we", "title": "WE", "intro_html": "<p>Giriş</p>",
     "fading": "partial", "self_explanation_prompt_html": "<p>Neden?</p>",
     "steps": [{"action_html": "<p>A1</p>", "rationale_html": "<p>R1</p>"},
               {"action_html": "<p>A2</p>", "rationale_html": "<p>R2</p>"}]},
    {"type": "exploration", "id": "xp", "title": "XP", "prompt_html": "<p>Tahmin et</p>",
     "input_kind": "text", "store_key": "guess1", "min_length": 5},
]


def _render():
    return render_html(Project(id="p", title="t", screens=[TA.validate_python(x) for x in SPECS]),
                       mode="preview", runtime_js="/*RT*/")


def test_classic_content_types_byte_identical():
    with open(FIX, encoding="utf-8") as f:
        assert _render() == f.read(), "classic içerik etkileşimi çıktısı kilitten saptı"


def _sec(html, sid):
    i = html.index(f'data-screen-id="{sid}"')
    return html[i:html.index("</section>", i)]


def test_classic_poll_and_exploration_stimulus_above_prompt():
    st = {"text_html": "<p>VAKA</p>", "asset_id": "img", "alt": "ALT"}
    p = Project(id="p", title="t", screens=[TA.validate_python(dict(SPECS[6], stimulus=st)),
                                            TA.validate_python(dict(SPECS[8], stimulus=st))])
    html = render_html(p, mode="package", runtime_js="")
    for sid in ("po", "xp"):
        sec = _sec(html, sid)
        assert sec.index('class="stimulus') < sec.index('class="rich prompt"')
        assert "VAKA" in sec and 'alt="ALT"' in sec
