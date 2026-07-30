"""tests/test_charts.py — Faz 6b (ölçüm raporu birimi 1): data_chart okunabilirlik sözleşmesi.

Gerekçe (docs/research/2026-07-30-layout-split-attention-measurement.md §3 desen 3, §5 madde 1):
ölçülen 6 split-attention ekranının 2'si YAZARLIK hatası değil RENDER açığıydı — çizgi grafik
y-ekseni ölçeği ve değer etiketi hiç üretmiyordu (üretimden Playwright ile teyitli: dc_satis'te
yalnız ay adları basılıyor, 100→108 değerleri ekranın hiçbir yerinde yok). Bu dosya o açığı
KALICI sözleşmeye bağlar:

  1. line: y-ekseni + sayısal tick etiketleri + ilk/son nokta değer etiketi ZORUNLU.
  2. bar: değer etiketleri (çubuk üstü) mevcut davranış — regresyona kilitli.
  3. pie: legend her dilim için ham değer + yüzde taşır.
  4. Seri renkleri tema token'ından akar (var(--chart-N, <fallback>)) — sabit hex'e dönüş
     regresyondur (rapor §4.1: sabit #2563eb premium koyu zeminde 3.19:1).
  5. Deterministik çıktı + RTL-güvenli metin çapaları (sayısal eksen metni direction=ltr).

CHART_VALUES_UNREADABLE'ın NİHAİ BİÇİMİ (rapor §5 madde 2'deki geçici lint yerine):
unit-1 düzeltmesi etiketleri KOŞULSUZ ürettiği için spec-düzeyi lint yapısal olarak ölü koddu
(spec'te etiketleri kapatan hiçbir alan yok; lint hiçbir kursta tetiklenemezdi). Bunun yerine
denetim TEST-DÜZEYİ DEĞİŞMEZ olarak buradadır: `test_chart_values_unreadable_invariant`
kanıt-hedefi olan çizgi grafiğin render'ında değer etiketlerinin varlığını doğrular — gelecekte
bir regresyon/konfig etiketleri kaldırırsa bu test kırmızıya döner (kapı render katmanında,
yazarlık katmanında değil).
"""
import re

from components.renderer import _build_chart_svg, render_html
from core.project import ChartDatum, Choice, ContentSlide, DataChartScreen, MCQScreen, Project, new_project_id


def _line_screen(**kw):
    return DataChartScreen(
        id="dc", title="Satış", chart_type="line",
        data=[ChartDatum(label="Oca", value=100), ChartDatum(label="Şub", value=104),
              ChartDatum(label="Mar", value=101), ChartDatum(label="Haz", value=108)],
        **kw,
    )


def _svg_texts(svg: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<text[^>]*>(.*?)</text>", svg)]


# --------------------------------------------------------------------------- #
# 1 — line: y-ekseni + tick + ilk/son değer etiketi (raporun ölçtüğü açık)
# --------------------------------------------------------------------------- #
def test_line_chart_has_y_axis_with_tick_labels():
    svg = _build_chart_svg(_line_screen())
    # y-ekseni çizgisi (dikey) mevcut
    assert 'class="chart-axis-y"' in svg
    # sayısal tick etiketleri: 0 ve vmax'ı kapsayan en az 3 sayı
    ticks = [t for t in _svg_texts(svg) if re.fullmatch(r"-?\d+(\.\d+)?", t)]
    assert len(ticks) >= 3, f"y-ekseni tick etiketi yok/az: {ticks}"
    assert "0" in ticks


def test_line_chart_labels_first_and_last_point_values():
    svg = _build_chart_svg(_line_screen())
    texts = _svg_texts(svg)
    # dc_satis senaryosu: 100→108 GÖRSELİN ÜZERİNDE okunabilir olmalı (rapor §2 grafik-dedektifi)
    assert "100" in texts, "ilk nokta değer etiketi yok"
    assert "108" in texts, "son nokta değer etiketi yok"


def test_line_chart_x_labels_preserved():
    svg = _build_chart_svg(_line_screen())
    texts = _svg_texts(svg)
    for lbl in ("Oca", "Şub", "Mar", "Haz"):
        assert lbl in texts


def test_line_chart_numeric_texts_are_rtl_safe():
    """Sayısal eksen/değer metinleri direction=ltr taşır: RTL belgede (dir=rtl) text-anchor
    end/start çapaları ters çözülür ve sayılar grafiğin içine taşardı."""
    svg = _build_chart_svg(_line_screen())
    y_ticks = re.findall(r'<text[^>]*class="chart-tick"[^>]*>', svg)
    assert y_ticks, "chart-tick sınıflı y etiketi yok"
    for t in y_ticks:
        assert 'direction="ltr"' in t


def test_line_chart_single_point_no_crash_and_labeled():
    s = DataChartScreen(id="d1", title="t", chart_type="line",
                        data=[ChartDatum(label="X", value=42)])
    svg = _build_chart_svg(s)
    assert "42" in _svg_texts(svg)


# --------------------------------------------------------------------------- #
# 2 — bar/pie: değer etiketleri (bar mevcuttu — kilit; pie'a ham değer eklendi)
# --------------------------------------------------------------------------- #
def test_bar_chart_value_labels_locked():
    s = DataChartScreen(id="d2", title="t", chart_type="bar",
                        data=[ChartDatum(label="2023", value=13), ChartDatum(label="2024", value=9)])
    svg = _build_chart_svg(s)
    texts = _svg_texts(svg)
    assert "13" in texts and "9" in texts  # çubuk-üstü değerler (rapor §2 multipack veri_agri)


def test_pie_legend_carries_raw_value_and_percent():
    s = DataChartScreen(id="d3", title="t", chart_type="pie",
                        data=[ChartDatum(label="A", value=30), ChartDatum(label="B", value=70)])
    svg = _build_chart_svg(s)
    # ham değer + yüzde birlikte: "A (30 · 30%)" — orta nokta entity olarak basılır
    assert "30 &#183; 30%" in svg and "70 &#183; 70%" in svg


# --------------------------------------------------------------------------- #
# 3 — tema-token renkleri (rapor §4.1: sabit hex → token)
# --------------------------------------------------------------------------- #
def test_chart_series_colors_flow_from_tokens_with_fallback():
    for ctype in ("bar", "line", "pie"):
        s = DataChartScreen(id="d4", title="t", chart_type=ctype,
                            data=[ChartDatum(label="A", value=3), ChartDatum(label="B", value=5)])
        svg = _build_chart_svg(s)
        assert "var(--chart-0," in svg, f"{ctype}: seri rengi token'dan akmıyor"
        # sabit hex'e çıplak dönüş yok: her hex bir var() fallback'i içinde olmalı
        for m in re.finditer(r'(?:fill|stroke)="(#[0-9a-fA-F]{6})"', svg):
            raise AssertionError(f"{ctype}: token'suz sabit renk {m.group(1)}")


def test_chart_css_vars_emitted_only_for_chart_courses():
    """--chart-N değişkenleri YALNIZ data_chart içeren kursa basılır (3.3 bayt-parite:
    grafiksiz kursların çıktısı değişmez)."""
    base = dict(title="t", screens=[ContentSlide(id="c1", title="c", body_html="<p>x</p>")])
    p_plain = Project(id=new_project_id(), **base)
    html_plain = render_html(p_plain, mode="preview", runtime_js="/*rt*/")
    assert "--chart-0:" not in html_plain
    p_chart = Project(id=new_project_id(), title="t", screens=[
        ContentSlide(id="c1", title="c", body_html="<p>x</p>"),
        DataChartScreen(id="d", title="d", chart_type="line",
                        data=[ChartDatum(label="A", value=1)])])
    html_chart = render_html(p_chart, mode="preview", runtime_js="/*rt*/")
    assert "--chart-0:" in html_chart and "--chart-7:" in html_chart


# --------------------------------------------------------------------------- #
# 4 — determinizm
# --------------------------------------------------------------------------- #
def test_chart_svg_is_deterministic():
    for ctype in ("bar", "line", "pie"):
        s = DataChartScreen(id="d5", title="t", chart_type=ctype,
                            data=[ChartDatum(label="A", value=3), ChartDatum(label="B", value=5),
                                  ChartDatum(label="C", value=2)])
        assert _build_chart_svg(s) == _build_chart_svg(s)


# --------------------------------------------------------------------------- #
# 5 — CHART_VALUES_UNREADABLE nihai biçimi: test-düzeyi değişmez (docstring'de gerekçe)
# --------------------------------------------------------------------------- #
def test_chart_values_unreadable_invariant():
    """Kanıt hedefi (evidence_screen_ids) olan skorlu ekranın işaret ettiği line data_chart,
    render'da SAYISAL değer etiketleri taşımak ZORUNDA. Rapor §5.2'nin geçici linti yerine
    kalıcı render-değişmezi: lint spec'e bakar, açık render'da — spec'te etiketleri kapatan
    alan olmadığından lint hiçbir kursta tetiklenemezdi (ölü kod). Bu test regresyon kapısıdır."""
    p = Project(id=new_project_id(), title="t", screens=[
        _line_screen(),
        MCQScreen(id="q1", title="q", prompt_html="<p>İlk ve son ay?</p>", points=10,
                  evidence_screen_ids=["dc"],
                  options=[Choice(id="a", text_html="100→108", correct=True),
                           Choice(id="b", text_html="90→95")]),
    ])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    chart = re.search(r'<svg[^>]*class="chart-svg"[^>]*>.*?</svg>', html, re.S)
    assert chart, "chart SVG render edilmedi"
    texts = _svg_texts(chart.group(0))
    assert "100" in texts and "108" in texts, (
        "CHART_VALUES_UNREADABLE: kanıt-hedefi çizgi grafik değer etiketi basmıyor — "
        "render regresyonu (bkz. docstring)")
