"""tests/test_exploration_slider.py — #141: exploration `input_kind="slider"`.

Yeni ekran tipi DEĞİL (tip enflasyonu yasağı 3.7) — mevcut `exploration`ın PARAMETRESİ;
`hotspot.mode` (#138) ve `labeled_diagram.mode` (#126) ile aynı presedan.

Kapsam:
- Model: varsayılanlar (0-100/1 = "kaç yüzde?") ve yapısal reddetmeler.
- Render: `<input type=range>` + görünür değer + ölçek uçları; birim değere girer.
- Taahhüt semantiği: kol `min_value`da başlar, değer OYNATILANA kadar saklanmaz.
- Bayt-parite: slider'sız kursta XPSLIDER_CSS/JS hiç basılmaz (koşullu üretim kapısı).
- Skorsuzluk korunur: slider da `exploration`dır — QUIZ_TYPES dışı, puan alanı yok.
- Anti-slop: kaba ölçek (`slider_range_too_coarse`).
"""
import pytest
from pydantic import ValidationError

from components.renderer import _uses_xp_slider, render_html
from core.antislop import lint_course
from core.project import (
    ExplorationScreen,
    Project,
    ThemeTokens,
    TitleSlide,
    new_project_id,
)


def _sl(**kw):
    args = dict(id="x1", title="Tahmin", prompt_html="<p>Kaç yüzde?</p>",
                input_kind="slider", store_key="tahmin")
    args.update(kw)
    return ExplorationScreen(**args)


def _proj(screens):
    return Project(id=new_project_id(), title="T", theme=ThemeTokens(), screens=screens)


def _html(screens):
    return render_html(_proj(screens), mode="preview", runtime_js="/*rt*/")


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def test_slider_defaults_are_a_percentage_scale():
    s = _sl()
    assert (s.min_value, s.max_value, s.step, s.unit) == (0.0, 100.0, 1.0, None)


def test_max_must_exceed_min():
    with pytest.raises(ValidationError, match="max_value"):
        _sl(min_value=10, max_value=5)


def test_step_must_be_positive():
    with pytest.raises(ValidationError, match="step"):
        _sl(step=0)


def test_step_cannot_exceed_the_range():
    """Tek konumlu ölçek slider değildir."""
    with pytest.raises(ValidationError, match="tek konumlu"):
        _sl(min_value=0, max_value=10, step=20)


def test_slider_constraints_do_not_touch_other_kinds():
    """text kipinde saçma min/max reddedilmemeli — alanlar slider'a ait."""
    s = ExplorationScreen(id="x2", title="T", prompt_html="<p>?</p>", store_key="k2",
                          min_value=10, max_value=5)
    assert s.input_kind == "text"


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def test_renders_a_native_range_with_scale_bounds():
    h = _html([_sl(min_value=1, max_value=5, step=1)])
    assert '<input class="xp-range" id="xp-x1-input" type="range" min="1" max="5" step="1"' in h
    assert 'value="1"' in h                      # kol min'de başlar
    assert '<span class="xp-value">1</span>' in h
    assert '<div class="xp-scale" aria-hidden="true"><span>1</span><span>5</span></div>' in h


def test_unit_appears_in_value_and_scale():
    h = _html([_sl(unit="%")])
    assert 'data-unit="%"' in h
    assert '<span class="xp-value">0 %</span>' in h
    assert "<span>100 %</span>" in h


def test_float_bounds_are_not_printed_as_dot_zero():
    h = _html([_sl(min_value=0.5, max_value=2.5, step=0.5)])
    assert 'min="0.5" max="2.5" step="0.5"' in h


def test_label_is_a_real_label_for_the_input():
    """text kipiyle AYNI yüzey: görünür <label for> — ad `title`a ya da placeholder'a bağlı değil."""
    h = _html([_sl()])
    assert '<label class="xp-label" for="xp-x1-input">' in h


# --------------------------------------------------------------------------- #
# Koşullu üretim — bayt-parite kapısı
# --------------------------------------------------------------------------- #
def test_uses_flag_only_fires_for_slider():
    assert _uses_xp_slider(_proj([_sl()]))
    assert not _uses_xp_slider(_proj([TitleSlide(id="t1", title="T")]))
    text_xp = ExplorationScreen(id="x3", title="T", prompt_html="<p>?</p>", store_key="k3")
    assert not _uses_xp_slider(_proj([text_xp]))


def test_slider_surface_absent_without_a_slider_screen():
    text_xp = ExplorationScreen(id="x3", title="T", prompt_html="<p>?</p>", store_key="k3")
    h = _html([TitleSlide(id="t1", title="T"), text_xp])
    for marker in (".xp-slider-row", ".xp-range{", 'data-kind="slider"', "xp-scale"):
        assert marker not in h, f"slider'sız kursta sızıntı: {marker}"


def test_text_kind_output_is_untouched_by_this_change():
    """Aynı ekran slider alanları AYARLANMIŞ hâlde de metin kipinde bayt-aynı üretmeli."""
    a = ExplorationScreen(id="x4", title="T", prompt_html="<p>?</p>", store_key="k4")
    b = ExplorationScreen(id="x4", title="T", prompt_html="<p>?</p>", store_key="k4",
                          min_value=3, max_value=9, step=2, unit="yıl")
    assert _html([a]) == _html([b])


# --------------------------------------------------------------------------- #
# Skorsuzluk — keşif sözleşmesi bozulmaz
# --------------------------------------------------------------------------- #
def test_slider_is_still_unscored():
    from core.project import QUIZ_TYPES
    s = _sl()
    assert s.type not in QUIZ_TYPES
    assert not hasattr(s, "points")


# --------------------------------------------------------------------------- #
# Anti-slop
# --------------------------------------------------------------------------- #
def test_lint_warns_on_a_scale_with_three_positions():
    issues = [i for i in lint_course(_proj([_sl(min_value=0, max_value=10, step=5)]))
              if i.code == "slider_range_too_coarse"]
    assert issues and issues[0].severity == "warn"
    assert "3 konum" in issues[0].message


def test_lint_quiet_for_a_real_scale():
    codes = [i.code for i in lint_course(_proj([_sl(min_value=1, max_value=5, step=1)]))]
    assert "slider_range_too_coarse" not in codes
