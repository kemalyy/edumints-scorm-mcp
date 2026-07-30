"""tests/test_layout_lint.py — Faz 6b (ölçüm raporu birimi 2): dar düzen lint'i MEDIA_NO_CAPTION.

Rapor kararı (docs/research/2026-07-30-layout-split-attention-measurement.md §5):
- Genel SPLIT_ATTENTION lint'i ÖLÇÜMLE gerekçelendirilemedi (6/39, heterojen desenler,
  mekanik vekiller ölçülen vakaların hiçbirini yakalamıyor) → YAZILMADI.
- Yerine iki dar iş: (1) render düzeltmesi (tests/test_charts.py) ve (2) bu dosyanın
  konusu MEDIA_NO_CAPTION: content_slide `blocks` içinde caption'sız görsel bloğu +
  ekranın >80 kelimelik düz yazısı → WARN. Bugün 0 isabet (ölçüm doğruladı — mevcut
  yazarlık captionlı); geleceğe korkuluk, yanlış-pozitifsiz.
- CHART_VALUES_UNREADABLE lint OLARAK YAZILMADI: birim-1 düzeltmesi etiketleri koşulsuz
  ürettiği için spec-düzeyi lint ölü kod olurdu — nihai biçimi test-düzeyi render
  değişmezidir (tests/test_charts.py::test_chart_values_unreadable_invariant).
"""
from core.antislop import STRICT_PROMOTED_CODES, lint_course, lint_errors
from core.project import ContentBlock, ContentSlide, Project, new_project_id

# 90 kelime — >80 eşiğinin üstünde (uzun okuma protokolü senaryosu: rapor §3 desen 1'in
# gelecekteki blocks'lu benzeri).
_LONG = "<p>" + " ".join(f"kelime{i}" for i in range(90)) + "</p>"
_SHORT = "<p>" + " ".join(f"kelime{i}" for i in range(20)) + "</p>"


def _proj(*screens):
    return Project(id=new_project_id(), title="t", screens=list(screens))


def _codes(p):
    return [i.code for i in lint_course(p)]


def test_warns_on_uncaptioned_image_block_with_long_body():
    p = _proj(ContentSlide(id="c1", title="t", blocks=[
        ContentBlock(html=_LONG),
        ContentBlock(asset_id="a1"),  # caption yok
    ]))
    issues = [i for i in lint_course(p) if i.code == "MEDIA_NO_CAPTION"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "blocks[1]" in issues[0].path


def test_no_warn_when_caption_present():
    p = _proj(ContentSlide(id="c1", title="t", blocks=[
        ContentBlock(html=_LONG),
        ContentBlock(asset_id="a1", caption="Figürün yorumu görselin bitişiğinde."),
    ]))
    assert "MEDIA_NO_CAPTION" not in _codes(p)


def test_no_warn_when_body_short():
    """Eşik korkuluğu: kısa gövde (<= 80 kelime) yorumu zaten taşıyamaz sayılmaz —
    dekoratif/kompakt slaytları cezalandırma (yanlış-pozitifsizlik raporun şartı)."""
    p = _proj(ContentSlide(id="c1", title="t", blocks=[
        ContentBlock(html=_SHORT),
        ContentBlock(asset_id="a1"),
    ]))
    assert "MEDIA_NO_CAPTION" not in _codes(p)


def test_word_count_spans_all_html_blocks():
    """Gövde ölçüsü ekranın DÜZYAZI toplamıdır: blocks'lu slaytta renderer body_html yerine
    html bloklarını basar → sayım html bloklarının toplamı üzerinden (41+41 > 80)."""
    half = "<p>" + " ".join(f"k{i}" for i in range(41)) + "</p>"
    p = _proj(ContentSlide(id="c1", title="t", blocks=[
        ContentBlock(html=half),
        ContentBlock(asset_id="a1"),
        ContentBlock(html=half),
    ]))
    assert "MEDIA_NO_CAPTION" in _codes(p)


def test_body_html_counted_when_no_html_blocks():
    """blocks yalnız görsel taşıyorsa düzyazı body_html'dedir (renderer blocks'u basar ama
    yazarlıkta gövde metni body_html'de kalmış olabilir — kelime sayımı ikisini de görür)."""
    p = _proj(ContentSlide(id="c1", title="t", body_html=_LONG, blocks=[
        ContentBlock(asset_id="a1"),
    ]))
    assert "MEDIA_NO_CAPTION" in _codes(p)


def test_media_asset_slide_out_of_scope():
    """Kapsam blocks'tur (rapor §5.2): eski yol media_asset_id + layout'ta caption alanı hiç
    yok — orada uyarı basmak yazara çıkış yolu göstermeden ceza olurdu (media_alt ayrıca
    missing_alt_text'in işi)."""
    p = _proj(ContentSlide(id="c1", title="t", body_html=_LONG,
                           media_asset_id="a1", media_alt="alt"))
    assert "MEDIA_NO_CAPTION" not in _codes(p)


def test_strict_promoted_and_default_advisory():
    """E1 emsali: kalite WARN'ı varsayılanda danışsal, strict'te bloklar (SP-5)."""
    assert "MEDIA_NO_CAPTION" in STRICT_PROMOTED_CODES
    p = _proj(ContentSlide(id="c1", title="t", blocks=[
        ContentBlock(html=_LONG),
        ContentBlock(asset_id="a1"),
    ]))
    default_codes = [i.code for i in lint_errors(p)]
    assert "MEDIA_NO_CAPTION" not in default_codes  # varsayılan davranış değişmedi
    strict_codes = [i.code for i in lint_errors(p, strict=True)]
    assert "MEDIA_NO_CAPTION" in strict_codes


def test_generic_split_attention_lint_intentionally_absent():
    """Rapor §5 kararının kilidi: genel SPLIT_ATTENTION lint'i ölçümle gerekçelendirilemedi
    ve YAZILMADI. Bu test, kod tabanına raporsuz/ölçümsüz genel lint sızmasını yakalar."""
    import core.antislop as antislop
    src = open(antislop.__file__, encoding="utf-8").read()
    assert "SPLIT_ATTENTION" not in src
