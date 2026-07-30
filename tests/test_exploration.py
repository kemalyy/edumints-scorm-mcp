"""tests/test_exploration.py — F2 (#113): exploration ekran tipi (keşif — girdi saklama + geri oynatma).

Kabul kriterleri (issue #113):
- Öğrenen girdisi SAKLANIR (suspend v2 zarf kuyruğu `xp` haritası — vitest: tests/js/scorm.test.js)
- Sonraki ekranlar `<span data-exploration-ref="store_key">` ile girdiyi GERİ OYNATIR
  ("senin tahminin şuydu" atfı — 5e-inquiry kanıt kaynağı 1)
- Skorsuz (A4 skorsuz-erken-deneme istisnasının teknik karşılığı) — skor state'ine yazmaz
- suspend_data bütçesi: değer 500 karakterde kırpılır; 1.2'de tahmin modeli WARN üretir

Tasarım kararları (bu dosya belgeler):
- exploration QUIZ_TYPES'ta DEĞİL: puan alanı yok; keşif/deneme ekranı — denemeyi puanlamak
  keşfi tahmin-yarışına çevirir (Z3).
- store_key makine-dostu ([a-z0-9_-]) ve kurs genelinde TEKİL (core/validator.py SERT hata):
  geri-oynatma referansının tek adresidir, çakışma sessiz veri karışması olurdu.
- Geri oynatma HER ZAMAN textContent enjeksiyonudur (innerHTML ASLA — XSS); sanitize
  data-exploration-ref'i span'da korur (dar allowlist genişletmesi).
- E1: _EVIDENCE_CONTENT_TYPES üyesi — koşulsuz kanıt-taşıyabilir (K1 tür 2: öğrenenin KENDİ
  ürettiği artefakt). Doğası gereği görsel DEĞİL (_INHERENTLY_VISUAL_TYPES dışı).
"""

from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from components.renderer import _course_config, render_html, sanitize
from core.project import (
    ContentSlide,
    ExplorationScreen,
    Project,
    QUIZ_TYPES,
    Choice,
    ScreenType,
    new_project_id,
)
from core.validator import validate_project

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _choices():
    return [Choice(id="a", text_html="Yüzer"), Choice(id="b", text_html="Batar")]


def _xp(**kw):
    d = dict(id="xp1", title="Dene: kütleyi değiştir", store_key="kesif_tahmin",
             prompt_html="<p>Önce tahmin et, sonra dene.</p>")
    d.update(kw)
    return ExplorationScreen(**d)


def _proj(screens, **kw):
    return Project(id=new_project_id(), title="K", screens=screens, **kw)


# --------------------------------------------------------------------------- #
# Model doğrulama
# --------------------------------------------------------------------------- #
def test_model_defaults_and_discriminator():
    s = _xp()
    assert s.type == ScreenType.exploration
    assert s.input_kind == "text"
    assert s.choices is None and s.placeholder is None and s.min_length is None
    # discriminated union üzerinden de çözülmeli
    p = Project.model_validate({
        "id": new_project_id(), "title": "K",
        "screens": [{"type": "exploration", "title": "Dene", "store_key": "k1",
                     "prompt_html": "<p>?</p>"}],
    })
    assert p.screens[0].type == ScreenType.exploration


@pytest.mark.parametrize("bad", ["", "Büyük", "boşluk var", "ÜST", "a.b", "k/e", "türkçe-ı"])
def test_model_rejects_bad_store_key(bad):
    with pytest.raises(PydanticValidationError):
        _xp(store_key=bad)


@pytest.mark.parametrize("ok", ["k1", "kesif_tahmin", "t-2", "a" * 64])
def test_model_accepts_machine_friendly_store_key(ok):
    assert _xp(store_key=ok).store_key == ok


@pytest.mark.parametrize("kind", ["choice", "prediction"])
def test_model_choice_kinds_require_choices(kind):
    with pytest.raises(PydanticValidationError):
        _xp(input_kind=kind)                      # choices yok
    with pytest.raises(PydanticValidationError):
        _xp(input_kind=kind, choices=_choices()[:1])   # tek seçenek yetmez
    s = _xp(input_kind=kind, choices=_choices())
    assert len(s.choices) == 2


def test_model_rejects_unknown_input_kind():
    with pytest.raises(PydanticValidationError):
        _xp(input_kind="slider")


def test_not_scorable_no_points_field():
    """İssue: skorsuz (formatif) — puan alanı tanımsız, QUIZ_TYPES dışı."""
    s = _xp()
    assert ScreenType.exploration not in QUIZ_TYPES
    assert "points" not in type(s).model_fields


# --------------------------------------------------------------------------- #
# Validator — store_key kurs genelinde TEKİL (çakışma = SERT hata)
# --------------------------------------------------------------------------- #
def test_duplicate_store_key_is_hard_error():
    p = _proj([_xp(id="x1", store_key="ayni"), _xp(id="x2", store_key="ayni")])
    errors = validate_project(p)
    assert any("store_key" in e.message and "ayni" in e.message for e in errors)


def test_unique_store_keys_pass():
    p = _proj([_xp(id="x1", store_key="k1"), _xp(id="x2", store_key="k2")])
    assert [e for e in validate_project(p) if "store_key" in e.message] == []


# --------------------------------------------------------------------------- #
# Sanitize — geri-oynatma span'ı allowlist'ten sağ çıkar (dar genişletme)
# --------------------------------------------------------------------------- #
def test_sanitize_keeps_exploration_ref_attr():
    out = sanitize('<p>Tahminin: <span data-exploration-ref="kesif_tahmin">—</span></p>')
    assert 'data-exploration-ref="kesif_tahmin"' in out


def test_sanitize_still_strips_other_data_attrs_and_tags():
    out = sanitize('<span data-foo="x" data-exploration-ref="k">y</span><script>hack()</script>')
    assert "data-foo" not in out and "<script" not in out
    assert 'data-exploration-ref="k"' in out


def test_sanitize_ref_only_on_span():
    """Genişletme DAR: data-exploration-ref yalnız span'a tanındı (div vb. taşımaz)."""
    out = sanitize('<div data-exploration-ref="k">y</div>')
    assert "data-exploration-ref" not in out


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def _html(screens):
    return render_html(_proj(screens), mode="preview", runtime_js="/*rt*/")


def test_render_text_kind_textarea_with_label():
    html = _html([_xp(placeholder="Gözlemini yaz")])
    assert 'data-type="exploration"' in html
    assert 'data-exploration' in html and 'data-store-key="kesif_tahmin"' in html
    assert 'data-kind="text"' in html
    assert '<textarea class="xp-text" id="xp-xp1-input"' in html
    assert 'placeholder="Gözlemini yaz"' in html
    assert '<label class="xp-label" for="xp-xp1-input">' in html
    assert "Önce tahmin et" in html


def test_render_min_length_hint():
    html = _html([_xp(min_length=40)])
    assert 'data-min="40"' in html and 'minlength="40"' in html
    assert "40" in html  # ipucu metni sayıyı taşır


def test_render_choice_kind_radiogroup():
    html = _html([_xp(input_kind="choice", choices=_choices())])
    assert 'data-kind="choice"' in html
    assert 'role="radiogroup"' in html and 'aria-labelledby="xp-xp1-prompt"' in html
    assert html.count('type="radio" name="xp-xp1"') == 2
    assert "Yüzer" in html and "Batar" in html
    assert "<textarea" not in html.split('data-exploration')[1].split("</section>")[0]


def test_render_prediction_kind_marked():
    html = _html([_xp(input_kind="prediction", choices=_choices())])
    assert 'data-kind="prediction"' in html


def test_render_unscored_chip_and_saved_status():
    html = _html([_xp()])
    assert 'class="xp-unscored ui-chip"' in html
    assert 'class="xp-saved ui-chip"' in html and 'aria-live="polite"' in html


def test_render_replay_ref_survives_in_later_screen():
    """Sonraki ekranda referans mekanizması: yazarın span'ı render çıktısında aynen durur."""
    later = ContentSlide(id="c1", title="Açıkla",
                         body_html='<p>Senin tahminin şuydu: '
                                   '<span data-exploration-ref="kesif_tahmin"></span></p>')
    html = _html([_xp(), later])
    assert 'data-exploration-ref="kesif_tahmin"' in html


def test_render_deterministic():
    p = _proj([_xp(input_kind="choice", choices=_choices())])
    a = render_html(p, mode="preview", runtime_js="/*rt*/")
    b = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert a == b


def test_config_unscored_no_feedback_reveal_none():
    """Skorsuzluk: skor state'ine yazacak HİÇBİR config alanı üretilmez."""
    p = _proj([_xp()])
    cfg = _course_config(p)
    assert cfg["total_points"] == 0
    item = cfg["screens"][0]
    assert item["is_quiz"] is False
    assert "points" not in item and "feedback" not in item
    assert item["reveal"] == "none"  # kendi etkileşimi var — timeline reveal'a girmez


# --------------------------------------------------------------------------- #
# E1 — kanıt-kaynağı sayımı (lint): öğrenenin KENDİ artefaktı (K1 tür 2)
# --------------------------------------------------------------------------- #
def test_evidentiary_set_membership():
    from core.antislop import _EVIDENCE_CONTENT_TYPES, _is_evidentiary_target
    assert ScreenType.exploration in _EVIDENCE_CONTENT_TYPES
    p = _proj([_xp()])
    assert _is_evidentiary_target(p.screens[0], p) is True


def test_scored_question_bound_to_exploration_passes_lint():
    from core.antislop import lint_course
    mcq = {
        "type": "mcq", "id": "q1", "title": "Skorlu soru", "points": 10,
        "prompt_html": "<p>?</p>", "evidence_screen_ids": ["xp1"],
        "options": [{"id": "a", "text_html": "A", "correct": True},
                    {"id": "b", "text_html": "B"}],
        "feedback": {"correct_html": "<p>Kendi denemende gördüğün desen.</p>",
                     "incorrect_html": "<p>Keşif ekranındaki denemene dön.</p>"},
    }
    p = _proj([_xp(), Project.model_validate(
        {"id": new_project_id(), "title": "x", "screens": [mcq]}).screens[0]])
    codes = {i.code for i in lint_course(p)}
    assert "unbound_scored_question" not in codes
    assert "evidence_target_not_evidentiary" not in codes
    assert "evidence_screen_missing" not in codes


def test_visual_budget_membership():
    from core.antislop import _INHERENTLY_VISUAL_TYPES, _has_visual
    assert ScreenType.exploration not in _INHERENTLY_VISUAL_TYPES  # doğası metin/seçim
    p = _proj([_xp()])
    assert _has_visual(p.screens[0]) is False


# --------------------------------------------------------------------------- #
# Suspend bütçesi — maliyet modeli (500 kırpma sınırı × keşif sayısı)
# --------------------------------------------------------------------------- #
def test_suspend_estimate_counts_explorations():
    from core.antislop import estimate_suspend_size
    base = _proj([ContentSlide(id="c1", title="t", body_html="<p>x</p>")])
    with_xp = _proj([ContentSlide(id="c1", title="t", body_html="<p>x</p>"),
                     _xp(id="x1", store_key="anahtar_bir")])
    delta = estimate_suspend_size(with_xp) - estimate_suspend_size(base)
    # kötü-durum: değer tavanı (500) + anahtar + JSON zarf payı
    assert delta >= 500 + len("anahtar_bir")


def test_many_explorations_warn_on_scorm12_budget():
    from core.antislop import lint_course
    screens = [_xp(id=f"x{i}", store_key=f"kesif_{i}") for i in range(8)]  # 8×500 > 3500 bütçesi
    p = _proj(screens, scorm_version="1.2")
    codes = {i.code for i in lint_course(p)}
    assert "SUSPEND_OVERFLOW" in codes                      # Faz 4-ek: bütçe aşımı projeksiyonu
    # 2004 hedefinde aynı kurs uyarmaz (64KB bütçe)
    p2 = _proj(list(screens), scorm_version="2004")
    assert not {"SUSPEND_OVERFLOW", "suspend_size_risk"} & {i.code for i in lint_course(p2)}


# --------------------------------------------------------------------------- #
# Runtime köprüsü — saklama/geri-oynatma JS'i pakete gömülü (mantık vitest'te)
# --------------------------------------------------------------------------- #
def test_bind_and_resolve_shipped_in_engine_js():
    html = _html([_xp()])
    assert "bindExploration" in html
    assert "resolveExplorationRefs" in html
    # geri-oynatma XSS-güvenli: textContent enjeksiyonu, innerHTML değil
    assert "textContent" in html


def test_codec_helpers_in_scormrt_bundle():
    """setExploration/getExploration window.SCORMRT bundle'ında (tek-kaynak scorm.js)."""
    from core.engine_bundle import load_scorm_bundle
    b = load_scorm_bundle()
    assert "setExploration" in b and "getExploration" in b and "EXPLORATION_VALUE_MAX" in b


# --------------------------------------------------------------------------- #
# i18n — kabuk dizgeleri tr/en
# --------------------------------------------------------------------------- #
def test_fixture_course_is_lint_clean():
    """İssue kabul kriteri: örnek fikstür kurs mevcut ve lint'ten temiz (5e mini-döngü)."""
    import json as _json
    from core.antislop import lint_course
    from core.project import CourseSpec
    raw = _json.loads((EXAMPLES / "exploration-5e.tr.json").read_text(encoding="utf-8"))
    spec = CourseSpec.model_validate(raw)
    p = Project(id=new_project_id(), title=spec.title, language=spec.language,
                scorm_version=spec.scorm_version, tracking=spec.tracking,
                screens=spec.screens)
    assert validate_project(p) == [], [e.message for e in validate_project(p)]
    issues = lint_course(p)
    assert issues == [], [f"{i.code}: {i.path}" for i in issues]
    # üç girdi türü de temsil ediliyor; geri-oynatma referansı sonraki ekranda mevcut
    kinds = {s.input_kind for s in p.screens if s.type == ScreenType.exploration}
    assert kinds == {"text", "choice", "prediction"}
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert html.count('data-type="exploration"') == 3
    assert "data-exploration-ref=" in html


def test_i18n_labels_localized():
    from components import i18n
    p_tr = _proj([_xp()])
    p_en = Project(id=new_project_id(), title="K", language="en", screens=p_tr.screens)
    html_tr = render_html(p_tr, mode="preview", runtime_js="/*rt*/")
    html_en = render_html(p_en, mode="preview", runtime_js="/*rt*/")
    assert i18n.t("tr", "xp_input_label") in html_tr
    assert i18n.t("en", "xp_input_label") in html_en
    assert i18n.t("en", "xp_input_label") != "xp_input_label"  # anahtar tanımlı
    # boş-değer yer tutucusu runtime tablosunda gömülü (tr: "henüz cevaplamadın")
    assert i18n.t("tr", "xp_not_answered") in html_tr
    assert i18n.t("en", "xp_not_answered") in html_en
    assert i18n.t("en", "xp_not_answered") != "xp_not_answered"
