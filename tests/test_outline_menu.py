"""tests/test_outline_menu.py — Senaryo hattı Faz 1: hiyerarşik player menüsü iskeleti.

İki garanti:
  1) GERİYE UYUM (pazarlık-dışı 3.3): outline BOŞKEN üretilen HTML, master'daki düz menü
     çıktısıyla BAYT-BAYT aynıdır. Fixture (tests/fixtures/flat_menu_small.preview.html)
     bu değişiklik setinden ÖNCE master renderer'dan üretildi; examples/small.json sabittir.
  2) Outline VARKEN menü role="tree" hiyerarşisi olarak SUNUCUDA render edilir:
     tree/treeitem/group rolleri, aria-expanded, aria-level (≤3), aria-current="page",
     düğümsüz ekranlar sondaki düz grupta, i18n başlık (tr/en).

Klavye/katlama JS'i DOM-ağırlıklıdır (OUTLINE_JS yalnız outline'lı kursa basılır);
davranış doğrulaması için bkz. docs/ACCESSIBILITY-CONFORMANCE.md player bölümü (manuel
doğrulama notu). Buradaki testler üretilen markup + enjeksiyon koşullarını sabitler.
"""

import json
import os
import re

from components.renderer import render_html
from core.project import (
    ContentSlide,
    CourseSpec,
    OutlineNode,
    Project,
    SummaryScreen,
    ThemeTokens,
    TitleSlide,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "flat_menu_small.preview.html")


def _small_project() -> Project:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "small.json")
    with open(path, encoding="utf-8") as f:
        spec = CourseSpec.model_validate(json.load(f))
    return Project(
        id="proj_FIXTURE0000000000000000000",
        title=spec.title,
        description=spec.description,
        scorm_version=spec.scorm_version,
        language=spec.language,
        theme=ThemeTokens(),
        tracking=spec.tracking,
        screens=list(spec.screens),
        objectives=list(spec.objectives),
    )


def _outline_project(lang: str = "tr") -> Project:
    """3 kademeli outline + düğümsüz bir ekran (sondaki düz grup)."""
    return Project(
        id="proj_T", title="Hiyerarşi", language=lang, theme=ThemeTokens(),
        outline=[
            OutlineNode(id="u1", kind="unit", title="Ünite 1"),
            OutlineNode(id="b1", parent_id="u1", kind="section", title="Bölüm 1.1"),
            OutlineNode(id="b1a", parent_id="b1", kind="section", title="Alt 1.1.1"),
            OutlineNode(id="u2", kind="unit", title="Ünite 2 (boş)"),
        ],
        screens=[
            TitleSlide(id="t1", title="Giriş", node_id="u1"),
            ContentSlide(id="c1", title="Konu A", body_html="<p>a</p>", node_id="b1"),
            ContentSlide(id="c2", title="Konu A detay", body_html="<p>d</p>", node_id="b1a"),
            SummaryScreen(id="s1", title="Kapanış"),  # node_id YOK → sondaki düz grup
        ],
    )


def _render(p: Project) -> str:
    return render_html(p, mode="preview", runtime_js="/*RUNTIME_STUB*/")


# --------------------------------------------------------------------------- #
# 1) Geriye uyum — outline boşken bayt-bayt aynı
# --------------------------------------------------------------------------- #
def test_flat_menu_byte_identical_to_master_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        expected = f.read()
    assert _render(_small_project()) == expected, (
        "Outline boşken üretilen HTML master fixture'ından saptı — geriye uyum kırıldı "
        "(pazarlık-dışı 3.3). Kasıtlı bir şablon değişikliği yaptıysan fixture'ı AYRI bir "
        "kararla yenile; outline işi bunu değiştiremez."
    )


def test_flat_render_has_no_tree_artifacts():
    html = _render(_small_project())
    assert 'role="tree"' not in html
    assert "mtree" not in html
    assert '<ul id="slideMenuList"></ul>' in html


# --------------------------------------------------------------------------- #
# 2) Tree markup — outline varken
# --------------------------------------------------------------------------- #
def test_tree_container_and_roles():
    html = _render(_outline_project())
    assert re.search(r'<ul id="slideMenuList" role="tree"[^>]*>', html)
    assert 'role="treeitem"' in html
    assert 'role="group"' in html
    assert 'role="none"' in html  # li sarmalayıcıları liste semantiğinden çıkar


def test_tree_nodes_collapsible_with_native_buttons():
    html = _render(_outline_project())
    # dallı düğümler: native button + aria-expanded (varsayılan açık)
    assert re.search(r'<button[^>]+data-node-id="u1"[^>]+aria-expanded="true"', html) or \
           re.search(r'<button[^>]+aria-expanded="true"[^>]+data-node-id="u1"', html)
    # yaprak düğüm (u2 — çocuğu/ekranı yok): aria-expanded OLMAMALI
    m = re.search(r'<button[^>]+data-node-id="u2"[^>]*>', html)
    assert m and "aria-expanded" not in m.group(0)


def test_tree_three_levels_and_screen_leaves():
    html = _render(_outline_project())
    for lvl in ("1", "2", "3"):
        assert f'aria-level="{lvl}"' in html
    # ekran yaprağı: data-goto + global numara + başlık
    m = re.search(r'<button[^>]+data-goto="c2"[^>]*>', html)
    assert m, "ekran yaprağı buton olarak render edilmeli"
    # b1a düğümü 3. kademe → ekranı 4. kademe yaprak
    assert 'aria-level="4"' in html


def test_tree_aria_current_on_start_screen():
    html = _render(_outline_project())
    m = re.search(r'<button[^>]+data-goto="t1"[^>]*>', html)
    assert m and 'aria-current="page"' in m.group(0)
    # yalnız TEK ekranda aria-current (CSS seçicisi değil, buton özniteliği sayılır)
    assert len(re.findall(r'<button[^>]+aria-current="page"', html)) == 1


def test_tree_ungrouped_screens_trail_in_flat_group():
    html = _render(_outline_project())
    # düğümsüz s1, i18n başlıklı sondaki grupta
    assert "Düğümsüz ekranlar" in html  # tr menu_ungrouped
    s1_pos = html.rindex('data-goto="s1"')
    c2_pos = html.rindex('data-goto="c2"')
    assert s1_pos > c2_pos, "düğümsüz ekranlar menünün SONUNDA gruplanmalı"
    en = _render(_outline_project(lang="en"))
    assert "Ungrouped screens" in en


def test_tree_roving_tabindex():
    html = _render(_outline_project())
    assert 'tabindex="0"' in html and 'tabindex="-1"' in html
    # tek giriş noktası: yalnız 1 treeitem tabindex=0
    btns = re.findall(r'<button[^>]+role="treeitem"[^>]*>', html)
    assert sum('tabindex="0"' in b for b in btns) == 1


def test_tree_css_and_js_only_with_outline():
    tree_html = _render(_outline_project())
    flat_html = _render(_small_project())
    assert ".mtree-btn" in tree_html and ".mtree-btn" not in flat_html
    assert "outline tree menü" in tree_html or "mtreeInit" in tree_html
    assert "mtreeInit" not in flat_html


def test_course_config_carries_outline_and_node_ids():
    tree_html = _render(_outline_project())
    m = re.search(r"window\.__COURSE__ = (\{.*?\});\n", tree_html, re.S)
    cfg = json.loads(m.group(1))
    assert [n["id"] for n in cfg["outline"]] == ["u1", "b1", "b1a", "u2"]
    assert cfg["outline"][1]["parent_id"] == "u1"
    by_id = {s["id"]: s for s in cfg["screens"]}
    assert by_id["c1"]["node_id"] == "b1"
    assert "node_id" not in by_id["s1"]
    # outline boşken course config'te outline anahtarı HİÇ yok
    m2 = re.search(r"window\.__COURSE__ = (\{.*?\});\n", _render(_small_project()), re.S)
    assert "outline" not in json.loads(m2.group(1))


def test_tree_titles_are_escaped():
    p = _outline_project()
    p.outline[0].title = 'Ünite <script>"1"</script>'
    html = _render(p)
    assert "<script>\"1\"</script>" not in html
    assert "&lt;script&gt;" in html
