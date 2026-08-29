"""tests/test_hotspot_v2.py — #138: hotspot v2 (keşif kipi + bölge rozeti + bölgeye özel
gerekçe + hepsini-bul).

Hepsi mevcut tipin PARAMETRESİ, yeni ekran tipi DEĞİL (tip enflasyonu yasağı 3.7) —
`labeled_diagram.mode="display"` (#126) ile aynı presedan.

Kapsam:
- Model: `mode` / `require_all` / `HotspotRegion.feedback_html` varsayılanları ve enum.
- a11y kısıt #8: erişilebilir ad artık `title`'a bağlı DEĞİL — her bölgede `aria-label`,
  etiketsizken jenerik i18n adına düşer; `label_html` markup'ı düz metne indirgenir.
- Quiz kipi geriye uyum: varsayılan hotspot çıktısı davranışsal olarak korunur, keşif
  yüzeyinden (rozet/panel/ipucu) hiçbir iz taşımaz.
- Keşif kipi: `_quiz_shell` KULLANILMAZ (kontrol butonu/feedback yok), skorlanmaz.
- Skor semantiği: explore `total_points` dışı, `is_quiz=false`, manifest'te skorlu sayılmaz.
- Koşullu üretim: kullanmayan kursta HOTSPOT2_CSS/JS hiç basılmaz (bayt-parite kapısı).
- Validator: `require_all` yalnız keşif kipinde.
- Anti-slop: içeriksiz keşif + etiketsiz bölge uyarıları.
"""
import pytest
from pydantic import ValidationError

from components.renderer import _course_config, _plain, _r_hotspot, _uses_hotspot2, render_html
from core.antislop import _is_evidentiary_target, _is_scored, lint_course
from core.manifest import _has_scored_content
from core.project import (
    HotspotRegion,
    HotspotScreen,
    Project,
    ThemeTokens,
    is_explore_hotspot,
    is_unscored_view,
    new_project_id,
)
from core.validator import validate_project


def _regions(n=2, **kw):
    return [
        HotspotRegion(id=f"r{i + 1}", shape="rect", coords=[10.0 * i, 10.0, 40.0, 40.0], **kw)
        for i in range(n)
    ]


def _hs(**kw):
    args = dict(id="hs1", title="Motor parçaları", prompt_html="<p>Karbüratörü bul.</p>",
                image_asset_id="img1", image_alt="motor şeması", regions=_regions())
    args.update(kw)
    return HotspotScreen(**args)


def _proj(screens):
    return Project(id=new_project_id(), title="T", theme=ThemeTokens(), screens=screens)


def _html(screen):
    return render_html(_proj([screen]), mode="preview", runtime_js="/*rt*/")


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_mode_defaults_to_quiz():
    s = _hs()
    assert s.mode == "quiz"
    assert s.require_all is False
    assert is_explore_hotspot(s) is False
    assert is_unscored_view(s) is False


def test_mode_accepts_explore():
    s = _hs(mode="explore")
    assert is_explore_hotspot(s) is True
    assert is_unscored_view(s) is True


def test_mode_rejects_unknown():
    with pytest.raises(ValidationError):
        _hs(mode="reveal")  # yalnız "quiz"|"explore"


def test_region_feedback_defaults_to_none():
    assert _hs().regions[0].feedback_html is None


# --------------------------------------------------------------------------- #
# a11y kısıt #8 — erişilebilir ad
# --------------------------------------------------------------------------- #
def test_every_region_has_aria_label_even_without_label_html():
    """Kısıt #8'in özü: ad `title`'a VE yazarın etiket vermesine bağlı olmamalı."""
    html = _r_hotspot(_hs())
    assert html.count("aria-label=") == 2
    assert 'aria-label="Bölge 1"' in html
    assert 'aria-label="Bölge 2"' in html


def test_label_html_markup_is_flattened_for_aria_label():
    """`aria-label` markup kabul etmez — ham <b> ekran okuyucuda harfi harfine okunur."""
    s = _hs(regions=[HotspotRegion(id="r1", shape="rect", coords=[0.0, 0.0, 10.0, 10.0],
                                   label_html="<b>Karbüratör</b>&nbsp;(üst)")])
    html = _r_hotspot(s)
    assert 'aria-label="Karbüratör (üst)"' in html
    assert "aria-label=\"<b>" not in html


def test_plain_strips_tags_and_entities():
    assert _plain("<p>Bir <em>iki</em>  üç</p>") == "Bir iki üç"
    assert _plain("a &amp; b") == "a & b"
    assert _plain(None) == ""


def test_badge_only_when_labelled_in_quiz_mode():
    """Etiketsiz quiz hotspot'unun GÖRÜNÜMÜ değişmemeli (geriye uyum 3.3)."""
    assert "hs-num" not in _r_hotspot(_hs())
    labelled = _hs(regions=_regions(1, label_html="Karbüratör"))
    assert "hs-num" in _r_hotspot(labelled)


def test_badge_always_present_in_explore_mode():
    """Keşifte bölge tıklanabilir olduğu görünmeli — etiket olmasa bile rozet basılır."""
    assert _r_hotspot(_hs(mode="explore")).count("hs-num") == 2


def test_empty_title_attribute_is_not_emitted():
    assert 'title=""' not in _r_hotspot(_hs())


# --------------------------------------------------------------------------- #
# Quiz kipi — geriye uyum
# --------------------------------------------------------------------------- #
def test_quiz_mode_keeps_check_button_and_has_no_explore_surface():
    html = _r_hotspot(_hs())
    assert "btn-check" in html
    for marker in ("hs-explore", "hs-hint", "hs-progress", "aria-expanded"):
        assert marker not in html


def test_quiz_mode_renders_region_feedback_hidden():
    """Gerekçe cevaptan ÖNCE görünmez; runtime seçilen bölgeninkini açar."""
    s = _hs(regions=_regions(1, feedback_html="<p>Yakıtı hava ile karıştırır.</p>"))
    html = _r_hotspot(s)
    assert 'data-note="r1"' in html
    assert "hidden" in html
    assert "Yakıtı hava ile karıştırır" in html


def test_quiz_mode_without_feedback_emits_no_notes_wrapper():
    assert "hs-notes" not in _r_hotspot(_hs())


# --------------------------------------------------------------------------- #
# Keşif kipi
# --------------------------------------------------------------------------- #
def test_explore_mode_has_no_quiz_shell():
    html = _r_hotspot(_hs(mode="explore"))
    assert "btn-check" not in html
    assert 'class="feedback"' not in html


def test_explore_mode_notes_are_live_region_and_hidden():
    s = _hs(mode="explore", regions=_regions(1, label_html="Karbüratör",
                                             feedback_html="<p>Yakıt-hava karışımı.</p>"))
    html = _r_hotspot(s)
    assert 'aria-live="polite"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="hsn-hs1-r1"' in html
    assert 'id="hsn-hs1-r1"' in html


def test_explore_stage_is_a_named_group():
    assert 'role="group" aria-label="motor şeması"' in _r_hotspot(_hs(mode="explore"))


def test_require_all_emits_progress_counter():
    html = _r_hotspot(_hs(mode="explore", require_all=True))
    assert 'data-require-all="1"' in html
    assert 'class="hs-progress"' in html
    assert "0</span>/2" in html


def test_explore_without_require_all_has_no_progress():
    assert "hs-progress" not in _r_hotspot(_hs(mode="explore"))


# --------------------------------------------------------------------------- #
# Skor semantiği
# --------------------------------------------------------------------------- #
def test_explore_is_outside_total_points_and_not_quiz():
    cfg = _course_config(_proj([_hs(mode="explore", points=25)]))
    assert cfg["total_points"] == 0
    item = cfg["screens"][0]
    assert item["is_quiz"] is False
    assert "points" not in item
    assert "correct" not in item


def test_quiz_mode_still_scores():
    cfg = _course_config(_proj([_hs(points=25)]))
    assert cfg["total_points"] == 25
    assert cfg["screens"][0]["is_quiz"] is True


def test_explore_alone_is_not_scored_content_for_manifest():
    """Skorsuz kurs masteryscore/completionThreshold almamalı (mastery regresyonu)."""
    assert _has_scored_content(_proj([_hs(mode="explore")])) is False
    assert _has_scored_content(_proj([_hs()])) is True


def test_explore_is_not_summative_but_is_evidentiary():
    s = _hs(mode="explore", points=10)
    p = _proj([s])
    assert _is_scored(s, p) is False
    assert _is_evidentiary_target(s, p) is True


# --------------------------------------------------------------------------- #
# Koşullu üretim — bayt-parite kapısı
# --------------------------------------------------------------------------- #
def test_plain_hotspot_course_gets_no_hotspot2_block():
    assert _uses_hotspot2(_proj([_hs()])) is False
    html = _html(_hs())
    # ENGINE_JS'teki guard yorumu "HOTSPOT2_JS" der; aranan şey KOŞULLU BLOĞUN kendisidir.
    assert "__HS_REQUIRE_ALL__=gate" not in html
    assert ".hs-num{" not in html
    assert "hs-num" not in html


@pytest.mark.parametrize("screen", [
    _hs(mode="explore"),
    _hs(require_all=True, mode="explore"),
    _hs(regions=_regions(1, label_html="Karbüratör")),
    _hs(regions=_regions(1, feedback_html="<p>x</p>")),
])
def test_hotspot2_block_is_emitted_when_surface_used(screen):
    assert _uses_hotspot2(_proj([screen])) is True
    assert "__HS_REQUIRE_ALL__=gate" in _html(screen)


# --------------------------------------------------------------------------- #
# Validator
# --------------------------------------------------------------------------- #
def test_require_all_rejected_in_quiz_mode():
    errs = validate_project(_proj([_hs(require_all=True)]))
    assert any("require_all" in e.path for e in errs)


def test_require_all_accepted_in_explore_mode():
    errs = validate_project(_proj([_hs(mode="explore", require_all=True,
                                       regions=_regions(2, label_html="Etiket"))]))
    assert not any("require_all" in e.path for e in errs)


# --------------------------------------------------------------------------- #
# Anti-slop
# --------------------------------------------------------------------------- #
def test_lint_warns_on_explore_without_content():
    codes = [i.code for i in lint_course(_proj([_hs(mode="explore")]))]
    assert "hotspot_explore_without_content" in codes


def test_lint_quiet_when_explore_has_content():
    p = _proj([_hs(mode="explore", regions=_regions(2, label_html="Etiket"))])
    codes = [i.code for i in lint_course(p)]
    assert "hotspot_explore_without_content" not in codes
    assert "hotspot_region_without_label" not in codes


def test_lint_warns_on_region_without_label():
    codes = [i.code for i in lint_course(_proj([_hs()]))]
    assert codes.count("hotspot_region_without_label") == 2
