"""tests/test_i18n.py — I1 (oynatıcı kabuğu dizge tablosu) + I2 (RTL).

Kapatılan boşluklar:
  I1 — kabuk sabit kodlanmış Türkçeydi; `project.language` yalnız <html lang>'i besliyordu.
       lang="de" bildiren sayfanın etiketleri Türkçe kalıyordu → WCAG 3.1.1/3.1.2 ihlali.
  I2 — hiçbir yerde `dir` yoktu, CSS fiziksel özellikler kullanıyordu → RTL pazarları kapalı.

Buradaki en önemli test `test_no_hardcoded_turkish_ui_strings`: geriye dönüşü engeller.
"""

import io
import re
import tokenize
from pathlib import Path

import pytest

from components import i18n
from components.renderer import render_html
from core.project import (
    Choice,
    ContentSlide,
    MCQScreen,
    Project,
    TrueFalseScreen,
    new_project_id,
)

REPO = Path(__file__).resolve().parent.parent
TR_CHARS = "ışğüöçİŞĞÜÖÇı"


def _proj(lang: str, screens=None) -> Project:
    return Project(id=new_project_id(), title="T", language=lang,
                   screens=screens or [ContentSlide(id="c", title="x", body_html="<p>y</p>")])


def _html(lang: str, screens=None) -> str:
    return render_html(_proj(lang, screens), mode="preview", runtime_js="/*rt*/")


# --------------------------------------------------------------------------- #
# Dizge tablosu
# --------------------------------------------------------------------------- #
def test_tr_and_en_have_identical_key_sets():
    """`en` referans tablodur; bakımlı her dil onunla aynı anahtar kümesine sahip olmalı."""
    en_keys = set(i18n.STRINGS["en"])
    for loc in i18n.supported():
        missing = en_keys - set(i18n.STRINGS[loc])
        extra = set(i18n.STRINGS[loc]) - en_keys
        assert not missing, f"{loc} eksik anahtar: {sorted(missing)}"
        assert not extra, f"{loc} fazla anahtar (en'de yok): {sorted(extra)}"


def test_no_empty_translations():
    for loc in i18n.supported():
        for key, val in i18n.STRINGS[loc].items():
            assert val.strip(), f"{loc}.{key} boş"


def test_runtime_keys_exist_in_table():
    en = i18n.STRINGS["en"]
    for key in i18n.RUNTIME_KEYS:
        assert key in en, f"RUNTIME_KEYS'te olup tabloda olmayan anahtar: {key}"


def test_unknown_locale_falls_back_to_english_not_turkish():
    """En kritik davranış: Almanca kurs Türkçe DEĞİL İngilizce etiket görmeli."""
    assert i18n.t("de", "nav_next") == "Next"
    assert i18n.t("ja", "nav_next") == "Next"
    assert i18n.t(None, "nav_next") == "Next"
    assert i18n.t("tr", "nav_next") == "Sonraki"


def test_region_subtag_resolves_to_base_language():
    assert i18n.t("tr-TR", "nav_next") == "Sonraki"
    assert i18n.t("en-GB", "nav_next") == "Next"
    assert i18n.t("TR_tr", "nav_next") == "Sonraki"


def test_unknown_key_returns_key_not_empty():
    """Sessiz boş metin yerine görünür sinyal."""
    assert i18n.t("en", "yok_boyle_bir_anahtar") == "yok_boyle_bir_anahtar"


def test_fmt_fills_placeholders_and_tolerates_unknown():
    assert i18n.fmt("Marker {n}", n=3) == "Marker 3"
    assert i18n.fmt("{correct} / {answered}", correct=2, answered=5) == "2 / 5"
    assert i18n.fmt("Marker {n}") == "Marker {n}"     # eksik param → çökmez


# --------------------------------------------------------------------------- #
# Yazı yönü (I2)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lang,expected", [
    ("tr", "ltr"), ("en", "ltr"), ("de", "ltr"), ("", "ltr"), (None, "ltr"),
    ("ar", "rtl"), ("he", "rtl"), ("fa", "rtl"), ("ur", "rtl"),
    ("ar-EG", "rtl"), ("fa-IR", "rtl"),
])
def test_direction(lang, expected):
    assert i18n.direction(lang) == expected


def test_html_tag_carries_lang_and_dir():
    assert '<html lang="ar" dir="rtl">' in _html("ar")
    assert '<html lang="tr" dir="ltr">' in _html("tr")


def test_css_uses_logical_properties_for_flow():
    """Metin akışına bağlı yerleşim aynalanabilir olmalı."""
    css = _html("en")
    for prop in ("margin-inline-start", "inset-inline-start", "inset-inline-end",
                 "text-align:start", "border-inline-start"):
        assert prop in css, f"logical property eksik: {prop}"
    assert "--dir-x" in css and 'html[dir="rtl"]{--dir-x:-1}' in css


def test_numeric_pairs_stay_ltr_in_rtl():
    """RTL'de "1 / 2" ekranda "2 / 1" okunuyordu: nötr "/" ayracı yön alıyor.

    Sayaç ve süre ÖLÇÜdür, metin değil → kendi yön adacığında LTR kalmalı.
    """
    css = _html("ar")
    assert ".status-pill,.pl-time{direction:ltr;unicode-bidi:isolate}" in css


def test_directional_icons_mirrored_in_rtl():
    assert 'html[dir="rtl"] #btnPrev .ic' in _html("ar")


def test_spatial_coordinates_are_not_mirrored():
    """Pin koordinatları uzamsal veridir — logical property'ye çevrilmemeli."""
    from core.project import LabeledDiagramScreen
    s = LabeledDiagramScreen(
        id="ld", title="D", image_asset_id="img",
        labels=[{"id": "l1", "text": "A", "x": 300, "y": 400},
                {"id": "l2", "text": "B", "x": 700, "y": 200}],
    )
    html = _html("ar", [s])
    assert "style=\"left:30.00%;top:40.00%\"" in html


# --------------------------------------------------------------------------- #
# Render çıktısı gerçekten yerelleşiyor mu
# --------------------------------------------------------------------------- #
def test_shell_labels_localized():
    tr, en = _html("tr"), _html("en")
    assert 'aria-label="Sonraki"' in tr and 'aria-label="Önceki"' in tr
    assert 'aria-label="Next"' in en and 'aria-label="Previous"' in en
    assert "Sonraki" not in en and "Önceki" not in en


def test_screen_controls_localized():
    q = TrueFalseScreen(id="q", title="S", prompt_html="<p>?</p>", correct=True)
    tr, en = _html("tr", [q]), _html("en", [q])
    assert ">Doğru<" in tr and ">Kontrol Et<" in tr
    assert ">True<" in en and ">Check<" in en
    assert "Kontrol Et" not in en


def test_runtime_string_table_embedded_and_localized():
    """ENGINE_JS'in çalışma anında ürettiği metinler window.__I18N__'den gelir."""
    en = _html("en")
    assert "window.__I18N__ = " in en
    assert '"summary_passed": "You passed"' in en or '"summary_passed":"You passed"' in en
    tr = _html("tr")
    assert "Başarıyla tamamladınız" in tr


def test_runtime_table_is_subset_not_whole_table():
    """Sayfaya yalnız runtime'ın ihtiyaç duyduğu anahtarlar gömülür (gereksiz bayt yok)."""
    rt = i18n.runtime_table("en")
    assert set(rt) == set(i18n.RUNTIME_KEYS)
    assert "nav_next" not in rt        # kabuk anahtarı Python tarafında çözüldü


def test_feedback_defaults_localized_not_turkish():
    """Yazar feedback yazmadıysa metin kurs diline göre çözülür (eskiden sabit 'Doğru!' idi)."""
    q = MCQScreen(id="q", title="S", prompt_html="<p>?</p>",
                  options=[Choice(id="a", text_html="1", correct=True),
                           Choice(id="b", text_html="2")])
    assert q.feedback.correct_html is None      # şema varsayılanı artık dil-nötr
    assert "Correct!" in _html("en", [q])
    assert "Doğru!" in _html("tr", [q])
    assert "Doğru!" not in _html("en", [q])


def test_author_feedback_is_not_overridden():
    q = MCQScreen(id="q", title="S", prompt_html="<p>?</p>",
                  feedback={"correct_html": "Ja, genau!", "incorrect_html": "Leider nein."},
                  options=[Choice(id="a", text_html="1", correct=True),
                           Choice(id="b", text_html="2")])
    html = _html("de", [q])
    assert "Ja, genau!" in html and "Leider nein." in html
    assert "Correct!" not in html


def test_concurrent_renders_do_not_leak_language():
    """_LANG bir ContextVar; iç içe/ardışık render'lar birbirinin dilini ezmemeli."""
    a = _html("tr")
    b = _html("en")
    c = _html("tr")
    assert 'aria-label="Sonraki"' in a and 'aria-label="Sonraki"' in c
    assert 'aria-label="Next"' in b


# --------------------------------------------------------------------------- #
# Geriye dönüşü engelleyen bekçi
# --------------------------------------------------------------------------- #
def _string_literals(path: Path):
    """Dosyadaki string literal'ler (docstring'ler hariç)."""
    src = path.read_text(encoding="utf-8")
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.STRING:
            continue
        if tok.string.startswith(('"""', "'''", 'f"""', "f'''", 'r"""', "r'''")):
            continue          # docstring / çok satırlı sabit (BASE_CSS, ENGINE_JS ayrı kontrol)
        yield tok.start[0], tok.string


def test_no_hardcoded_turkish_ui_strings_in_renderer():
    """renderer.py'de Türkçe UI dizesi KALMAMALI — hepsi i18n tablosundan gelmeli.

    Bu test I1'in geri gelmesini engeller: yeni bir ekran tipi Türkçe etiketle eklenirse kırar.
    """
    offenders = [(ln, s) for ln, s in _string_literals(REPO / "components" / "renderer.py")
                 if re.search(f"[{TR_CHARS}]", s)]
    assert not offenders, (
        "renderer.py'de sabit Türkçe UI dizesi var — components/i18n.py'ye taşıyın:\n"
        + "\n".join(f"  satır {ln}: {s}" for ln, s in offenders)
    )


def test_no_hardcoded_turkish_ui_strings_in_engine_js():
    """ENGINE_JS'in ÜRETTİĞİ metinlerde Türkçe kalmamalı (JS // yorumları hariç)."""
    from components.templates import ENGINE_JS
    offenders = []
    for i, line in enumerate(ENGINE_JS.split("\n"), 1):
        if line.strip().startswith("//"):
            continue
        for m in re.finditer(r'"([^"]*[' + TR_CHARS + r'][^"]*)"'
                             r"|'([^']*[" + TR_CHARS + r"][^']*)'", line):
            offenders.append((i, m.group(1) or m.group(2)))
    assert not offenders, (
        "ENGINE_JS'te sabit Türkçe dizge var — T('anahtar') kullanın:\n"
        + "\n".join(f"  satır {ln}: {s!r}" for ln, s in offenders)
    )


def test_shell_has_no_hardcoded_turkish():
    from components.templates import SHELL
    offenders = [line for line in SHELL.split("\n") if re.search(f"[{TR_CHARS}]", line)]
    assert not offenders, "SHELL'de sabit Türkçe var:\n" + "\n".join(offenders)


def test_generated_page_for_english_course_has_no_turkish_ui():
    """Uçtan uca: İngilizce kursun ürettiği sayfada Türkçe UI metni olmamalı.

    JS/CSS yorumları hariç tutulur (kullanıcıya görünmez; ayrı bir konu — bkz. I3).
    """
    q = MCQScreen(id="q", title="Question", prompt_html="<p>?</p>",
                  options=[Choice(id="a", text_html="1", correct=True),
                           Choice(id="b", text_html="2")])
    html = _html("en", [q])
    body = "\n".join(
        line for line in html.split("\n")
        if not line.strip().startswith(("//", "/*", "*"))
    )
    # Kullanıcıya görünen metin taşıyıcıları
    visible = re.findall(r'aria-label="([^"]*)"|placeholder="([^"]*)"|>([^<>{}\n]{2,})<', body)
    flat = [x for group in visible for x in group if x and re.search(f"[{TR_CHARS}]", x)]
    assert not flat, f"İngilizce kursta Türkçe UI metni: {flat}"
