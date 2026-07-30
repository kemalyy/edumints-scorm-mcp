"""tests/test_labeled_diagram_callout.py — #126: labeled_diagram SALT-GÖSTERİM (callout) modu.

Split-attention "exhibit" deseninin kalıcı çözümü (ölçüm raporu §5.3): mevcut
`labeled_diagram`'a PARAMETRE (`mode`), yeni ekran tipi DEĞİL (tip enflasyonu yasağı 3.7).

Kapsam:
- Model doğrulama: `mode` enum + varsayılan "quiz".
- Renderer callout markup: statik kutular, leader line, koordinatlar, a11y, etkileşim YOK.
- Quiz modu BAYT-BAYT değişmez (geriye uyum 3.3).
- Skor semantiği: display total_points dışı, is_quiz=false.
- Kanıt (E1): display kanıt-taşıyabilir hedef; skorlu soru ona bağlanabilir.
- Ölçülen exhibit örneği (okuma protokolü görsel üstüne taşınır) regresyonu.
"""
import pytest
from pydantic import ValidationError

from components.renderer import _course_config, _r_labeled_diagram, render_html
from core.antislop import _explicit_evidence_ok, _is_evidentiary_target, _is_scored
from core.project import (
    Choice,
    DiagramLabel,
    LabeledDiagramScreen,
    MCQScreen,
    Project,
    is_display_diagram,
    new_project_id,
)


def _labels(n=2):
    return [DiagramLabel(id=chr(97 + i), text=f"Etiket {i + 1}", x=200 + i * 200, y=300 + i * 100)
            for i in range(n)]


def _diagram(mode=None, **kw):
    args = dict(id="ld1", title="Diyagram", image_asset_id="img1", image_alt="şema",
                labels=_labels(), **kw)
    if mode is not None:
        args["mode"] = mode
    return LabeledDiagramScreen(**args)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_mode_defaults_to_quiz():
    assert _diagram().mode == "quiz"
    assert is_display_diagram(_diagram()) is False


def test_mode_accepts_display():
    s = _diagram(mode="display")
    assert s.mode == "display"
    assert is_display_diagram(s) is True


def test_mode_rejects_unknown():
    with pytest.raises(ValidationError):
        _diagram(mode="callout")  # yalnız "quiz"|"display"


# --------------------------------------------------------------------------- #
# Renderer — quiz modu BAYT-BAYT korunur (geriye uyum 3.3)
# --------------------------------------------------------------------------- #
def test_quiz_mode_byte_identical_default_vs_explicit():
    """Alanın eklenmesi + varsayılan, çıktıyı bayt-bayt değiştirmez."""
    assert _r_labeled_diagram(_diagram()) == _r_labeled_diagram(_diagram(mode="quiz"))


def test_quiz_mode_still_interactive():
    html = _r_labeled_diagram(_diagram())
    assert 'class="ld-select"' in html          # select UI
    assert 'class="ld-pin"' in html             # etkileşimli işaretçi
    assert 'class="btn btn-check"' in html       # kontrol butonu
    assert 'class="feedback"' in html
    assert "ld-display" not in html
    assert "ld-callout" not in html


# --------------------------------------------------------------------------- #
# Renderer — display (callout) modu
# --------------------------------------------------------------------------- #
def test_display_mode_static_callouts_with_coords():
    html = _r_labeled_diagram(_diagram(mode="display"))
    assert 'class="labeled-diagram ld-display"' in html
    # her etiket için statik callout kutusu + koordinat (pin ile aynı % matematiği)
    assert html.count('class="ld-callout"') == 2
    assert "left:20.00%;top:30.00%" in html
    assert "left:40.00%;top:40.00%" in html
    # yorum metni görsel üstünde gerçek DOM metni (tooltip DEĞİL)
    assert ">Etiket 1<" in html and ">Etiket 2<" in html
    assert 'class="ld-callout-text"' in html
    assert 'class="ld-leader"' in html            # leader line


def test_display_mode_no_interactive_handlers():
    html = _r_labeled_diagram(_diagram(mode="display"))
    assert "ld-select" not in html                # select yok
    assert "btn-check" not in html                # kontrol butonu yok
    assert '<select' not in html
    assert 'class="feedback"' not in html          # feedback alanı yok
    assert "ld-row" not in html


def test_display_mode_a11y_text_not_tooltip():
    html = _r_labeled_diagram(_diagram(mode="display"))
    # metin title tooltip'e gömülmez; num dekoratif (aria-hidden), stage etiketli grup
    assert 'title=' not in html.split('<div class="labeled-diagram')[1]
    assert 'aria-hidden="true"' in html            # num + leader dekoratif
    assert 'role="group"' in html
    assert 'aria-label=' in html


def test_display_mode_uses_gated_tokens_only():
    """Callout renkleri yalnız AA-gated token'dan akar (matris deltası 0)."""
    html = render_html(Project(id=new_project_id(), title="t", screens=[_diagram(mode="display")]),
                       mode="preview", runtime_js="/*rt*/")
    assert ".ld-callout-text{background:var(--c-surface-alt);color:var(--c-text)" in html
    assert ".ld-callout-num{" in html and "background:var(--c-primary)" in html


# --------------------------------------------------------------------------- #
# Skor semantiği — display skorlanmaz
# --------------------------------------------------------------------------- #
def _config(screens):
    p = Project(id=new_project_id(), title="t", scorm_version="2004", screens=screens)
    return _course_config(p)


def test_display_not_scored_not_quiz_in_config():
    cfg = _config([_diagram(mode="display")])
    assert cfg["total_points"] == 0
    item = cfg["screens"][0]
    assert item["is_quiz"] is False
    assert "points" not in item
    assert "feedback" not in item


def test_quiz_diagram_still_scored_in_config():
    cfg = _config([_diagram()])  # quiz vars.
    assert cfg["total_points"] == 15
    item = cfg["screens"][0]
    assert item["is_quiz"] is True
    assert item["points"] == 15


# --------------------------------------------------------------------------- #
# Kanıt (E1) — display kanıt-taşıyabilir hedef
# --------------------------------------------------------------------------- #
def test_display_is_evidentiary_and_unscored():
    p = Project(id=new_project_id(), title="t", screens=[_diagram(mode="display")])
    s = p.screens[0]
    assert _is_scored(s, p) is False
    assert _is_evidentiary_target(s, p) is True


def test_scored_question_can_bind_to_display_diagram():
    disp = _diagram(mode="display")
    disp.id = "exhibit"
    q = MCQScreen(id="q1", title="Soru", prompt_html="<p>?</p>", points=10,
                  evidence_screen_ids=["exhibit"],
                  options=[Choice(id="a", text_html="A", correct=True),
                           Choice(id="b", text_html="B")])
    p = Project(id=new_project_id(), title="t", screens=[disp, q])
    by_id = {s.id: s for s in p.screens}
    assert _explicit_evidence_ok(q, p, by_id) is True


# --------------------------------------------------------------------------- #
# Ölçülen exhibit deseni — okuma protokolü görsel ÜSTÜNE taşınır (regresyon)
# --------------------------------------------------------------------------- #
def test_exhibit_reading_protocol_lives_on_image():
    """spot-the-phish/c_email deseni: 4 maddelik okuma protokolü artık görsel altındaki
    düzyazıda DEĞİL, e-posta mockup'ının ÜSTÜNDE statik callout olarak (göz gidiş-gelişi yok)."""
    protocol = ["Gönderen satırı sahte mi?", "Ton aciliyet dayatıyor mu?",
                "Butonun gerçek hedefi ne?", "Ek güvenli mi?"]
    s = LabeledDiagramScreen(
        id="c_email", title="Bu e-postayı incele", image_asset_id="email_mock",
        image_alt="şüpheli e-posta ekran görüntüsü", mode="display",
        labels=[DiagramLabel(id=f"p{i}", text=t, x=150, y=150 + i * 180)
                for i, t in enumerate(protocol)])
    p = Project(id=new_project_id(), title="phish", screens=[s])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    for t in protocol:                       # her protokol maddesi görsel üstü callout'ta
        assert t in html
    assert 'class="ld-callout-text"' in html
    assert _is_scored(s, p) is False         # skorlanmaz içerik
    assert _is_evidentiary_target(s, p) is True  # ama kanıt-taşıyabilir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
