"""tests/test_worked_example.py — F1 (#112): worked_example ekran tipi.

Kabul kriterleri (issue #112):
- Şema + render testleri (adım listesi: eylem + gerekçe + ops. artefakt)
- Soluklaştırma (fading) 3 düzey: full / partial / problem_only — fikstürle test
- Öz-açıklama alanı SKORSUZ (skora katkısı yok — testle doğrulanır)
- E1 kanıt-kaynağı sayımına dahil (lint testi)
- Örnek fikstür kurs lint'ten temiz geçer

Tasarım kararları (bu dosya belgeler):
- worked_example QUIZ_TYPES'ta DEĞİL: puan alanı yok, kanıt/öğretim ekranı (4cid
  `gorev_tam_destek`/`gorev_soluklastirma` fazlarının taşıyıcısı — skorlanamaz).
- E1: _EVIDENCE_CONTENT_TYPES üyesi — koşulsuz kanıt-taşıyabilir (K1 tür 1: çözümlü örnek;
  adımların eylem+gerekçe çifti artefaktın kendisidir, görsel şart değil).
- Görsel bütçe: _INHERENTLY_VISUAL_TYPES üyesi DEĞİL — artefakt opsiyonel; yalnız
  artifact_asset_id taşıyan adım varsa görsel sayılır (content_slide.blocks paraleli).
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from components.renderer import _course_config, render_html
from core.antislop import (
    _EVIDENCE_CONTENT_TYPES,
    _has_visual,
    _is_evidentiary_target,
    lint_course,
)
from core.project import (
    Project,
    QUIZ_TYPES,
    ScreenType,
    WEStep,
    WorkedExampleScreen,
    new_project_id,
)

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _steps(n=2, artifact=False):
    return [
        WEStep(
            action_html=f"<p>Eylem {i}: sorguyu kur</p>",
            rationale_html=f"<p>Gerekçe {i}: filtre satır sayısını belirler</p>",
            **({"artifact_asset_id": f"a{i}", "artifact_caption": f"Adım {i} çıktısı"}
               if artifact else {}),
        )
        for i in range(n)
    ]


def _we(**kw):
    d = dict(id="we1", title="Çözümlü örnek: Mart raporu", steps=_steps())
    d.update(kw)
    return WorkedExampleScreen(**d)


def _proj(screens, **kw):
    return Project(id=new_project_id(), title="K", screens=screens, **kw)


def _html(screens):
    return render_html(_proj(screens), mode="preview", runtime_js="/*rt*/")


# --------------------------------------------------------------------------- #
# Model doğrulama
# --------------------------------------------------------------------------- #
def test_model_defaults_and_discriminator():
    s = _we()
    assert s.type == ScreenType.worked_example
    assert s.fading == "full"
    assert s.intro_html is None and s.self_explanation_prompt_html is None
    # discriminated union üzerinden de çözülmeli
    p = Project.model_validate({
        "id": new_project_id(), "title": "K",
        "screens": [{"type": "worked_example", "title": "Ç", "steps": [
            {"action_html": "<p>a</p>", "rationale_html": "<p>r</p>"},
            {"action_html": "<p>b</p>", "rationale_html": "<p>s</p>"},
        ]}],
    })
    assert p.screens[0].type == ScreenType.worked_example


def test_model_requires_min_two_steps():
    with pytest.raises(ValidationError):
        _we(steps=_steps(1))


def test_model_rejects_unknown_fading():
    with pytest.raises(ValidationError):
        _we(fading="yari")


def test_not_scorable_no_points_field():
    """İssue: puan YOK — kanıt/öğretim ekranı. QUIZ_TYPES dışı, points alanı tanımsız."""
    s = _we()
    assert ScreenType.worked_example not in QUIZ_TYPES
    assert "points" not in type(s).model_fields


# --------------------------------------------------------------------------- #
# Render — 3 fading düzeyi
# --------------------------------------------------------------------------- #
def test_render_full_shows_everything():
    html = _html([_we(fading="full", intro_html="<p>Görev: Mart raporu</p>")])
    assert 'data-type="worked_example"' in html
    assert 'data-fading="full"' in html
    assert "Eylem 0" in html and "Gerekçe 0" in html and "Gerekçe 1" in html
    # full: gizli gerekçe/adım gövdesi ve reveal butonu YOK (markup'ta; ENGINE_JS her zaman gömülü)
    assert 'class="we-reveal' not in html
    assert 'aria-controls="we-' not in html
    assert "Görev: Mart raporu" in html


def test_render_partial_hides_rationales_behind_buttons():
    html = _html([_we(fading="partial")])
    assert 'data-fading="partial"' in html
    # gerekçeler markup'ta var ama hidden; adım başına aria-expanded'lı buton
    assert html.count('class="we-rationale rich" id="we-we1-r') == 2
    assert 'id="we-we1-r0" hidden' in html
    assert html.count('aria-expanded="false"') >= 2
    assert 'aria-controls="we-we1-r0"' in html
    # eylemler görünür (gizli değil)
    assert "Eylem 0" in html


def test_render_problem_only_hides_step_bodies():
    html = _html([_we(fading="problem_only")])
    assert 'data-fading="problem_only"' in html
    assert 'id="we-we1-b0" hidden' in html and 'id="we-we1-b1" hidden' in html
    assert 'aria-controls="we-we1-b0"' in html
    assert html.count('aria-expanded="false"') >= 2


def test_render_artifact_figure_with_caption():
    html = _html([_we(steps=_steps(artifact=True))])
    assert 'data-asset="a0"' in html and "Adım 0 çıktısı" in html
    assert '<figure class="we-artifact">' in html


def test_render_self_explanation_unscored():
    """Öz-açıklama: serbest metin alanı render edilir, skora HİÇ katkısı yok."""
    p = _proj([_we(self_explanation_prompt_html="<p>Neden GROUP BY?</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "we-selfexp-text" in html and "Neden GROUP BY?" in html
    cfg = _course_config(p)
    assert cfg["total_points"] == 0
    item = cfg["screens"][0]
    assert item["is_quiz"] is False
    assert "points" not in item and "feedback" not in item


def test_render_deterministic():
    p = _proj([_we(fading="partial", steps=_steps(artifact=True))])
    a = render_html(p, mode="preview", runtime_js="/*rt*/")
    b = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert a == b


def test_render_no_timeline_reveal_interference():
    """Kendi progresif-açılımı var → timeline reveal'a girmez (reveal='none')."""
    p = _proj([_we()])
    assert _course_config(p)["screens"][0]["reveal"] == "none"


def test_bind_function_shipped_in_engine_js():
    html = _html([_we(fading="partial")])
    assert "bindWorkedExample" in html


def test_reduced_motion_css_present():
    html = _html([_we()])
    assert "prefers-reduced-motion" in html  # kabuk CSS'i saygı duyar


# --------------------------------------------------------------------------- #
# i18n — kabuk dizgeleri _T ile çözülür (tr/en)
# --------------------------------------------------------------------------- #
def test_i18n_reveal_labels_localized():
    p_tr = _proj([_we(fading="partial", self_explanation_prompt_html="<p>?</p>")])
    p_en = Project(id=new_project_id(), title="K", language="en", screens=p_tr.screens)
    html_tr = render_html(p_tr, mode="preview", runtime_js="/*rt*/")
    html_en = render_html(p_en, mode="preview", runtime_js="/*rt*/")
    from components import i18n
    assert i18n.t("tr", "we_show_rationale") in html_tr
    assert i18n.t("en", "we_show_rationale") in html_en
    assert i18n.t("en", "we_show_rationale") != "we_show_rationale"  # anahtar tanımlı


# --------------------------------------------------------------------------- #
# E1 — kanıt-kaynağı sayımı (lint)
# --------------------------------------------------------------------------- #
def test_evidentiary_set_membership():
    assert ScreenType.worked_example in _EVIDENCE_CONTENT_TYPES
    p = _proj([_we()])
    assert _is_evidentiary_target(p.screens[0], p) is True


def test_scored_question_bound_to_worked_example_passes_lint():
    mcq = {
        "type": "mcq", "id": "q1", "title": "Skorlu tam görev", "points": 10,
        "prompt_html": "<p>?</p>", "evidence_screen_ids": ["we1"],
        "options": [{"id": "a", "text_html": "A", "correct": True},
                    {"id": "b", "text_html": "B"}],
        "feedback": {"correct_html": "<p>Örnekteki 2. adım deseni.</p>",
                     "incorrect_html": "<p>Çözümlü örneğin 2. adımına dön.</p>"},
    }
    p = _proj([_we(), Project.model_validate(
        {"id": new_project_id(), "title": "x", "screens": [mcq]}).screens[0]])
    codes = {i.code for i in lint_course(p)}
    assert "unbound_scored_question" not in codes
    assert "evidence_target_not_evidentiary" not in codes
    assert "evidence_screen_missing" not in codes


# --------------------------------------------------------------------------- #
# Görsel bütçe + alt-text
# --------------------------------------------------------------------------- #
def test_visual_budget_membership():
    from core.antislop import _INHERENTLY_VISUAL_TYPES
    assert ScreenType.worked_example not in _INHERENTLY_VISUAL_TYPES  # artefakt opsiyonel
    p = _proj([_we()])
    assert _has_visual(p.screens[0]) is False
    p2 = _proj([_we(steps=_steps(artifact=True))])
    assert _has_visual(p2.screens[0]) is True


def test_artifact_without_caption_warns_missing_alt():
    steps = _steps(artifact=True)
    steps[0].artifact_caption = None
    p = _proj([_we(steps=steps)])
    issues = [i for i in lint_course(p) if i.code == "missing_alt_text"]
    assert len(issues) == 1 and "steps[0]" in issues[0].path


def test_blank_rationale_warns():
    """İssue: her adım eylem + GEREKÇE — boş gerekçe pedagojik koku (WARN, kırmaz)."""
    steps = _steps()
    steps[1].rationale_html = "  "
    p = _proj([_we(steps=steps)])
    issues = [i for i in lint_course(p) if i.code == "step_without_rationale"]
    assert len(issues) == 1 and "steps[1]" in issues[0].path
    assert issues[0].severity == "warn"


# --------------------------------------------------------------------------- #
# Fikstür kurs — lint'ten temiz (issue kabul kriteri)
# --------------------------------------------------------------------------- #
def test_fixture_course_is_lint_clean():
    from core.project import CourseSpec
    raw = json.loads((EXAMPLES / "worked-example-4cid.tr.json").read_text(encoding="utf-8"))
    spec = CourseSpec.model_validate(raw)
    p = Project(id=new_project_id(), title=spec.title, language=spec.language,
                scorm_version=spec.scorm_version, tracking=spec.tracking,
                screens=spec.screens)
    issues = lint_course(p)
    assert issues == [], [f"{i.code}: {i.path}" for i in issues]
    # 3 fading düzeyi fikstürde temsil ediliyor
    fadings = {s.fading for s in p.screens if s.type == ScreenType.worked_example}
    assert fadings == {"full", "partial", "problem_only"}
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert html.count('data-type="worked_example"') == 3
