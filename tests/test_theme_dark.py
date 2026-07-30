"""tests/test_theme_dark.py — Faz 6b birimi 4: karanlık mod (Faz 5 token katmanı üstüne).

TASARIM KARARI (plan 7.3 — kozmetik eksen preset'lere ORTOGONAL):
karanlık mod ayrı bir preset DEĞİL, HER preset'in üstüne compose edilen overlay'dir
(themes/_dark-overlay.json → core/theme_dark.derive_dark_theme). Katman sırası:
  _tokens → preset → audience → kurs custom  (Faz 5, değişmedi — _load_theme)
  → [render anında, theme_mode != light ise] _dark-overlay + en-yakın-uyumlu mürekkep oturtma
Böylece kitle katmanı ve kurs custom'ı karanlıkta da görünür; preset kimliği (tipografi,
radius, motion, marka primary'si) korunur — nötr zeminler + durum renkleri overlay'den,
primary/focus preset'ten türetilip AA'ya EN YAKIN uyumlu değere oturtulur (deterministik).

theme_mode: "light" (varsayılan — BAYT PARİTESİ: mevcut kurs çıktısı değişmez) |
"dark" (:root doğrudan koyu değişkenler + color-scheme:dark) |
"auto" (aydınlık :root + @media (prefers-color-scheme: dark) bloğu — işletim sistemi seçer).
"""
import json
from pathlib import Path

import pytest

import server
from components.renderer import render_html
from core.project import ContentSlide, CourseSpec, Project, ThemeTokens, new_project_id
from core.theme_dark import derive_dark_theme
from tests.test_theme_contrast import contrast, shipped_presets


def _proj(mode=None, theme=None):
    kw = {}
    if mode is not None:
        kw["theme_mode"] = mode
    if theme is not None:
        kw["theme"] = theme
    return Project(id="proj_DARKMODE000000000000000000", title="t",
                   screens=[ContentSlide(id="c1", title="b", body_html="<p>x</p>")], **kw)


# --------------------------------------------------------------------------- #
# 1 — theme_mode alanı + varsayılan bayt paritesi
# --------------------------------------------------------------------------- #
def test_theme_mode_defaults_light_and_validates():
    assert Project(id=new_project_id(), title="t").theme_mode == "light"
    spec = CourseSpec.model_validate({"title": "t", "screens": [
        {"type": "content_slide", "id": "c", "title": "c", "body_html": "<p>x</p>"}]})
    assert spec.theme_mode == "light"
    spec_d = CourseSpec.model_validate({"title": "t", "theme_mode": "dark", "screens": [
        {"type": "content_slide", "id": "c", "title": "c", "body_html": "<p>x</p>"}]})
    assert spec_d.theme_mode == "dark"
    with pytest.raises(Exception):
        CourseSpec.model_validate({"title": "t", "theme_mode": "sepya", "screens": []})


def test_default_light_output_byte_identical():
    """Karanlık-mod ekseni varsayılanda SIFIR davranış değişikliği: theme_mode alanına hiç
    dokunmayan proje ile açıkça light olan proje bayt-bayt aynı çıktıyı üretir ve çıktıda
    karanlık-mod izi yoktur."""
    html_default = render_html(_proj(), mode="preview", runtime_js="/*rt*/")
    html_light = render_html(_proj(mode="light"), mode="preview", runtime_js="/*rt*/")
    assert html_default == html_light
    assert "prefers-color-scheme" not in html_default
    assert "color-scheme:dark" not in html_default


# --------------------------------------------------------------------------- #
# 2 — dark / auto emisyonu
# --------------------------------------------------------------------------- #
def test_dark_mode_emits_dark_vars_in_root():
    html = render_html(_proj(mode="dark"), mode="preview", runtime_js="/*rt*/")
    overlay = json.loads(Path("themes/_dark-overlay.json").read_text(encoding="utf-8"))
    assert f"--c-bg:{overlay['color']['bg']};" in html
    assert "color-scheme:dark" in html
    assert "prefers-color-scheme" not in html  # sabit koyu: medya sorgusu yok


def test_auto_mode_emits_light_root_plus_media_query_block():
    light = server._load_theme("default")
    html = render_html(_proj(mode="auto", theme=light), mode="preview", runtime_js="/*rt*/")
    overlay = json.loads(Path("themes/_dark-overlay.json").read_text(encoding="utf-8"))
    # :root aydınlık (varsayılan davranış korunur; JS gerekmez — saf CSS)
    assert f"--c-bg:{light.color.bg};" in html
    # medya bloğu koyu değişkenleri taşır
    assert "@media (prefers-color-scheme: dark)" in html
    assert f"--c-bg:{overlay['color']['bg']};" in html
    assert "color-scheme:dark" in html


def test_dark_mode_chart_vars_flow_from_overlay():
    from core.project import ChartDatum, DataChartScreen
    p = Project(id=new_project_id(), title="t", theme_mode="dark", screens=[
        DataChartScreen(id="d", title="d", chart_type="line",
                        data=[ChartDatum(label="A", value=1)])])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    overlay = json.loads(Path("themes/_dark-overlay.json").read_text(encoding="utf-8"))
    assert f"--chart-0:{overlay['color']['chart_series'][0]};" in html


# --------------------------------------------------------------------------- #
# 3 — derive_dark_theme: ortogonallik + en-yakın-uyum
# --------------------------------------------------------------------------- #
def test_derive_preserves_preset_identity_axes():
    """Kozmetik eksen ortogonal: koyu türev preset'in tipografisini/radius'unu/motion'ını
    ve adını KORUR; yalnız renk zeminleri + elevation değişir."""
    for preset in ("default", "playground", "academic"):
        light = server._load_theme(preset)
        dark = derive_dark_theme(light)
        assert dark.name == light.name  # mod ≠ kimlik (3.4)
        assert dark.typography == light.typography
        assert dark.radii == light.radii
        assert dark.motion == light.motion
        assert dark.color.bg != light.color.bg


def test_derive_is_nearest_compliant_no_change_when_already_passing():
    """'En yakın uyumlu' sözleşmesi: zaten koyu-zeminde AA geçen mürekkep DEĞİŞMEZ
    (dark preset'inin primary'si overlay zeminlerinde geçiyor → aynen kalmalı)."""
    dark_preset = server._load_theme("dark")
    derived = derive_dark_theme(dark_preset)
    assert derived.color.primary == dark_preset.color.primary


def test_derive_fits_light_preset_primary_to_dark_ground():
    """Aydınlık preset primary'si (koyu mürekkep) koyu zeminde 4.5:1'i tutturacak asgari
    beyaz karışımına oturtulur."""
    light = server._load_theme("default")  # primary #4f46e5 — koyu zeminde okunmaz
    dark = derive_dark_theme(light)
    assert contrast(dark.color.primary, dark.color.surface) >= 4.5 - 1e-9
    assert contrast(dark.color.primary, dark.color.bg) >= 4.5 - 1e-9
    assert dark.color.primary != light.color.primary


def test_derive_deterministic():
    light = server._load_theme("editorial")
    assert derive_dark_theme(light).model_dump() == derive_dark_theme(light).model_dump()


def test_every_preset_dark_variant_core_pairs_pass():
    """Kapı büyümesinin hızlı yerel aynası (tam matris test_theme_contrast'ta): her sevk
    edilen preset'in koyu türevi çekirdek çiftleri geçer."""
    for preset in shipped_presets():
        d = derive_dark_theme(server._load_theme(preset)).color
        assert contrast(d.text, d.bg) >= 4.5 - 1e-9, preset
        assert contrast(d.text, d.surface) >= 4.5 - 1e-9, preset
        assert contrast(d.primary, d.surface) >= 4.5 - 1e-9, preset
        assert contrast(d.primary_contrast, d.primary) >= 4.5 - 1e-9, preset
        assert contrast(d.focus_ring, d.surface) >= 3.0 - 1e-9, preset
        for i, ch in enumerate(d.chart_series):
            assert contrast(ch, d.surface) >= 3.0 - 1e-9, f"{preset} chart[{i}]"


def test_derive_composes_on_custom_inline_theme():
    """Overlay çözülmüş TEMA üstüne compose edilir → kurs custom'ı ve audience katmanı
    karanlıkta da görünür (katman sırası korunur; overlay ayrı bir preset değildir)."""
    custom = ThemeTokens.model_validate({"name": "default", "radii": {"md": "3px"}})
    merged = server._deep_merge_theme(server._load_theme("default"), custom)
    dark = derive_dark_theme(merged)
    assert dark.radii.md == "3px"
