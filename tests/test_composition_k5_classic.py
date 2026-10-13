"""K5 — classic oyun/senaryo/gömülü bayt-aynı (gövde yardımcılarına çıkarma bunu bozmamalı)."""
import os

from pydantic import TypeAdapter

from components.renderer import render_html
from core.project import Project, Screen

TA = TypeAdapter(Screen)
FIX = os.path.join(os.path.dirname(__file__), "fixtures", "k5_types_classic.html")
SPECS = [
    {"type": "game", "id": "ga", "title": "GA", "intro_html": "<p>Giriş</p>",
     "nodes": [{"id": "n1", "content_html": "<p>Sahne 1</p>", "image_asset_id": "img",
                "image_alt": "Sahne", "choices": [
                    {"id": "c1", "text_html": "Seç A", "to": "n2", "feedback_html": "<p>Sonuç A</p>"},
                    {"id": "c2", "text_html": "Seç B", "to": "n2"}]},
               {"id": "n2", "content_html": "<p>Son</p>", "choices": []}]},
    {"type": "decision_scenario", "id": "ds", "title": "DS", "intro_html": "<p>Vaka</p>",
     "nodes": [{"id": "d1", "prompt_html": "<p>Ne yaparsın?</p>", "image_asset_id": "img",
                "image_alt": "Ofis", "choices": [
                    {"id": "x", "text_html": "Doğrula", "feedback_html": "<p>İyi</p>",
                    "score_delta": 10, "goto_node_id": "d2"},
                    {"id": "y", "text_html": "Tıkla", "feedback_html": "<p>Kötü</p>",
                     "score_delta": -5, "goto_node_id": "d2"}]},
               {"id": "d2", "prompt_html": "<p>Bitti</p>", "choices": [
                    {"id": "z", "text_html": "Tamam", "feedback_html": "<p>.</p>"},
                    {"id": "w", "text_html": "Tekrar", "feedback_html": "<p>..</p>"}]}]},
    {"type": "escape_room", "id": "er", "title": "ER", "intro_html": "<p>Kaç</p>", "lives": 3,
     "puzzles": [{"id": "p1", "prompt_html": "<p>2+2?</p>", "accepted": ["4"], "hint_html": "<p>İpucu</p>"},
                 {"id": "p2", "prompt_html": "<p>Başkent?</p>", "accepted": ["Ankara"]}]},
    {"type": "term_match_race", "id": "tm", "title": "TM", "prompt_html": "<p>Eşle</p>",
     "time_limit_sec": 60,
     "pairs": [{"id": "a", "term_html": "MFA", "definition_html": "Çok faktör"},
               {"id": "b", "term_html": "VPN", "definition_html": "Sanal ağ"}]},
    {"type": "branching", "id": "br", "title": "BR", "prompt_html": "<p>Hangi yol?</p>",
     "choices": [{"id": "l", "text_html": "Sol", "goto_screen_id": "ga"},
                 {"id": "r", "text_html": "Sağ", "goto_screen_id": "ds"}]},
    {"type": "embed_html", "id": "em", "title": "EM", "html_asset_id": "h"},
]


def _render():
    return render_html(Project(id="p", title="t", screens=[TA.validate_python(x) for x in SPECS]),
                       mode="preview", runtime_js="/*RT*/")


def test_classic_k5_types_byte_identical():
    with open(FIX, encoding="utf-8") as f:
        assert _render() == f.read(), "classic K5 çıktısı kilitten saptı"


def test_classic_branching_stimulus_above_prompt():
    st = {"text_html": "<p>VAKA</p>", "asset_id": "img", "alt": "ALT"}
    html = render_html(Project(id="p", title="t",
                               screens=[TA.validate_python(dict(SPECS[4], stimulus=st))]),
                       mode="package", runtime_js="")
    sec = html[html.index('data-screen-id="br"'):]
    sec = sec[:sec.index("</section>")]
    assert sec.index('class="stimulus') < sec.index('class="rich prompt"') and 'alt="ALT"' in sec
