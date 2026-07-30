"""tests/test_suspend_resilience.py — Faz 4-ek: suspend taşma merdiveni + republish-resume.

Python tarafı kapsam:
  1) content_version — deterministik içerik sürümü (id kümesi/sırası değişince değişir;
     başlık/metin değişince DEĞİŞMEZ) + COURSE konfigürasyonuna serileşme.
  2) i18n — republish bildirimi anahtarları (tr/en) runtime tablosunda.
  3) Kırpma merdiveni / bütçe sabitleri sunucu-runtime senkronu (3500 bayt).
  4) SUSPEND_OVERFLOW derleme-zamanı projeksiyonu (antislop) — ayrı commit'te genişler.
  5) ID kararlılığı — scenario_compile id'leri POZİSYONEL YENİDEN NUMARALANDIRMAZ
     (araya sayfa/düğüm eklemek mevcut id'leri değiştirmez) + silinen id yeniden
     kullanılamaz (retired_ids).

JS tarafı (merdiven/ladder/resume davranışı) vitest'te: tests/js/scorm.test.js.
Uçtan uca kanıt (gerçek tarayıcı + republish): tests/runtime/scorm-probe.mjs.
"""

import json
import re

import pytest

from components import i18n
from components.renderer import _content_version, render_html
from core.project import ContentSlide, OutlineNode, Project

# --------------------------------------------------------------------------- #
# yardımcılar
# --------------------------------------------------------------------------- #

def _project(screens=None, outline=None, **kw) -> Project:
    return Project(
        id="proj_T", title="Test",
        screens=screens if screens is not None else [
            ContentSlide(id="c1", title="Bir", body_html="<p>a</p>"),
            ContentSlide(id="c2", title="İki", body_html="<p>b</p>"),
        ],
        outline=outline or [],
        **kw,
    )


def _course_cfg(html: str) -> dict:
    m = re.search(r"window\.__COURSE__\s*=\s*(\{.*?\});?\s*\n", html)
    assert m, "__COURSE__ konfigürasyonu bulunamadı"
    return json.loads(m.group(1))


# --------------------------------------------------------------------------- #
# 1) content_version — deterministik, id-duyarlı, metin-duyarsız
# --------------------------------------------------------------------------- #

def test_content_version_deterministic_and_serialized():
    p = _project()
    v1 = _content_version(p)
    assert isinstance(v1, int) and 0 <= v1 < 2**20
    assert _content_version(_project()) == v1  # aynı içerik → aynı sürüm (deterministik)
    html = render_html(p, mode="preview", runtime_js="/*stub*/")
    assert _course_cfg(html)["content_version"] == v1


def test_content_version_changes_on_id_set_or_order_change():
    base = _content_version(_project())
    # ekran eklendi → değişir
    added = _project(screens=[
        ContentSlide(id="c1", title="Bir", body_html="<p>a</p>"),
        ContentSlide(id="cX", title="Ara", body_html="<p>x</p>"),
        ContentSlide(id="c2", title="İki", body_html="<p>b</p>"),
    ])
    assert _content_version(added) != base
    # sıra değişti → değişir (pozisyonel resume güvenliği)
    reordered = _project(screens=[
        ContentSlide(id="c2", title="İki", body_html="<p>b</p>"),
        ContentSlide(id="c1", title="Bir", body_html="<p>a</p>"),
    ])
    assert _content_version(reordered) != base
    # outline düğüm kümesi değişti → değişir (ekranlar aynı kalsa bile)
    with_node = _project(outline=[OutlineNode(id="u1", kind="unit", title="Ünite")])
    with_node.screens[0].node_id = None  # ekranlar düğümsüz kalabilir
    assert _content_version(with_node) != base


def test_content_version_ignores_text_only_edits():
    """Yalnız METİN değişen republish resume'u bozmamalı: id kümesi aynı → sürüm aynı
    (orderFp de aynı kalır → tam sessiz resume)."""
    a = _project()
    b = _project(screens=[
        ContentSlide(id="c1", title="Bir (düzeltildi)", body_html="<p>yeni metin</p>"),
        ContentSlide(id="c2", title="İki", body_html="<p>b</p>"),
    ])
    assert _content_version(a) == _content_version(b)


# --------------------------------------------------------------------------- #
# 2) i18n — bildirim anahtarları (dostane, teknik olmayan) tr/en + runtime tablosu
# --------------------------------------------------------------------------- #

def test_resume_notice_i18n_keys_in_both_languages_and_runtime_table():
    for lang in ("tr", "en"):
        table = i18n.runtime_table(lang)
        for key in ("resume_updated", "resume_restart", "notice_close"):
            assert key in table, f"{key} {lang} runtime tablosunda yok"
        assert "{name}" in table["resume_updated"]
    tr = i18n.table("tr")
    assert tr["resume_updated"].startswith("Kurs güncellendi")
    assert tr["resume_restart"] == "Kurs güncellendi. Baştan başlıyorsun."
    en = i18n.table("en")
    assert en["resume_updated"].startswith("The course has been updated")
    # teknik jargon yok (öğrenen-yüzü)
    for key in ("resume_updated", "resume_restart"):
        for bad in ("suspend", "orderFp", "SCORM", "error", "hata"):
            assert bad.lower() not in tr[key].lower()
            assert bad.lower() not in en[key].lower()


def test_notice_markup_is_runtime_only_but_css_and_engine_present():
    """Bildirim DOM'u yalnız fallback resume'da JS ile kurulur — statik HTML'de yoktur;
    CSS ve runtime kancaları her kursta hazırdır (düz kurs da republish edilebilir)."""
    html = render_html(_project(), mode="preview", runtime_js="/*stub*/")
    assert '<div class="resume-notice"' not in html          # statik markup yok
    assert ".resume-notice{" in html                          # stil hazır
    assert "resumeSuspend" in html                            # okuma merdiveni bağlı
    assert "resume_updated" in html                           # i18n runtime tablosunda


# --------------------------------------------------------------------------- #
# 3) bütçe sabitleri senkronu (sunucu ↔ runtime)
# --------------------------------------------------------------------------- #

def test_budget_constant_synced_with_engine_js():
    from core.antislop import _SUSPEND_BUDGET_12
    assert _SUSPEND_BUDGET_12 == 3500
    src = open("components/engine/scorm.js", encoding="utf-8").read()
    assert "SUSPEND_BUDGET_12 = 3500" in src


# --------------------------------------------------------------------------- #
# 4) derleme-zamanı kötü-durum projeksiyonu — yazar-görünür SUSPEND_OVERFLOW
# --------------------------------------------------------------------------- #

def test_scenario_compile_projection_warns_suspend_overflow():
    """Madde 1 yazar yarısı: scenario_compile'ın lint raporu (derlenen spec üzerinden) kötü
    durumu (tüm sayfalar cevaplı, keşifler tavanda) 3500 BAYT bütçesine karşı projekte eder;
    aşınca yazar SUSPEND_OVERFLOW uyarısını projeksiyon SAYISIYLA görür. Öğrenen tarafı
    (runtime kırpma merdiveni) son çaredir — yazar önlemi burada alır."""
    from core.antislop import estimate_suspend_size, lint_course
    from core.project import Objective
    from core.scenario import Page, ScenarioDocument, compile_scenario
    from server import _spec_to_project_for_lint

    doc = ScenarioDocument(
        id="scn_T", title="Keşif yoğun kurs",
        outline=[OutlineNode(id="u1", kind="unit", title="Ünite",
                             objective=Objective(id="o1"))])
    for i in range(8):                                     # 8 keşif × 500 bayt tavan > 3500
        doc.pages.append(Page(
            id=f"pg{i}", node_id="u1", order=i, title=f"Keşif {i}",
            screen_type="exploration",
            evidence={"kind": "ogrenci_kesfi", "kayit_yontemi": "serbest metin",
                      "commit_prompt": "Önce tahminini yaz"},
        ))
    spec, _warnings = compile_scenario(doc)
    proj = _spec_to_project_for_lint(spec, "owner_test")
    issues = {i.code: i for i in lint_course(proj)}
    assert "SUSPEND_OVERFLOW" in issues, "derleme projeksiyonu yazarı uyarmadı"
    msg = issues["SUSPEND_OVERFLOW"].message
    assert str(estimate_suspend_size(proj)) in msg         # projeksiyon sayısı mesajda
    assert "3500" in msg                                    # bütçe mesajda
    assert issues["SUSPEND_OVERFLOW"].severity == "warn"    # blocker DEĞİL (bilinçli)


def test_direct_spec_projection_same_path():
    """Doğrudan build_from_spec spec'leri de AYNI projeksiyondan geçer (estimate_suspend_size
    Project üstünde çalışır — kaynak-bağımsız)."""
    from core.antislop import lint_course
    from core.project import ExplorationScreen

    screens = [ExplorationScreen(id=f"x{i}", title=f"Keşif {i}", store_key=f"kesif_{i}",
                                 prompt_html="<p>?</p>") for i in range(8)]
    p = _project(screens=screens)
    assert p.scorm_version == "1.2"
    assert "SUSPEND_OVERFLOW" in {i.code for i in lint_course(p)}


# --------------------------------------------------------------------------- #
# 5) ID kararlılığı — madde-2 ön koşulu (Faz 2 derleyicisine dokunur)
# --------------------------------------------------------------------------- #

def _stability_doc():
    from core.project import Objective
    from core.scenario import Page, ScenarioDocument

    return ScenarioDocument(
        id="scn_S", title="Kararlılık",
        outline=[
            OutlineNode(id="u1", kind="unit", title="Ünite 1",
                        objective=Objective(id="o1")),
            OutlineNode(id="b1", parent_id="u1", kind="section", title="Bölüm 1.1"),
            OutlineNode(id="u2", kind="unit", title="Ünite 2",
                        objective=Objective(id="o2")),
        ],
        pages=[
            Page(id="pg_giris", node_id="u1", order=0, title="Giriş",
                 screen_type="content_slide", copy={"body_md": "Merhaba"}),
            Page(id="pg_konu", node_id="b1", order=1, title="Konu",
                 screen_type="content_slide", copy={"body_md": "İçerik"}),
            Page(id="pg_kapanis", node_id="u2", order=2, title="Kapanış",
                 screen_type="content_slide", copy={"body_md": "Bitti"}),
        ])


def test_compile_never_renumbers_ids_on_mid_outline_insert():
    """KABUL: derleyici id'leri OLDUĞU GİBİ geçirir — outline ortasına düğüm + sayfa eklemek
    önceden var olan HİÇBİR ekran/düğüm id'sini değiştirmez (pozisyonel numaralandırma YOK).
    Suspend pozisyon kaydı (z) ve kimlik-merdiveni bu değişmeze dayanır."""
    from core.scenario import Page, compile_scenario

    doc = _stability_doc()
    spec1, _ = compile_scenario(doc)
    ids1 = [s["id"] for s in spec1["screens"]]
    nodes1 = [n["id"] for n in spec1["outline"]]
    assert ids1 == ["pg_giris", "pg_konu", "pg_kapanis"]

    # outline ORTASINA yeni düğüm + araya yeni sayfa (order kaydırılır)
    doc.outline.insert(2, OutlineNode(id="b1b", parent_id="u1", kind="section",
                                      title="Bölüm 1.2 (yeni)"))
    for p in doc.pages:
        if p.order >= 1:
            p.order += 1
    doc.pages.append(Page(id="pg_yeni", node_id="b1b", order=1, title="Yeni",
                          screen_type="content_slide", copy={"body_md": "Ara"}))
    spec2, _ = compile_scenario(doc)
    ids2 = [s["id"] for s in spec2["screens"]]
    nodes2 = [n["id"] for n in spec2["outline"]]

    # önceden var olan TÜM id'ler değişmeden ve aynı GÖRELİ sırada durur
    assert [i for i in ids2 if i in ids1] == ids1
    assert [n for n in nodes2 if n in nodes1] == nodes1
    assert "pg_yeni" in ids2 and "b1b" in nodes2
    # sayfa→düğüm bağı da id ÜZERİNDEN korunur (pozisyon değil)
    by_id2 = {s["id"]: s for s in spec2["screens"]}
    assert by_id2["pg_konu"]["node_id"] == "b1"
    assert by_id2["pg_kapanis"]["node_id"] == "u2"


def test_compile_keeps_ids_on_reorder():
    """Sıra değişimi (order alanı) id'lere DOKUNMAZ — yalnız spec ekran sırası değişir."""
    from core.scenario import compile_scenario

    doc = _stability_doc()
    doc.pages[0].order, doc.pages[2].order = 2, 0
    spec, _ = compile_scenario(doc)
    assert [s["id"] for s in spec["screens"]] == ["pg_kapanis", "pg_konu", "pg_giris"]


@pytest.mark.asyncio
async def test_retired_ids_block_reuse_after_delete():
    """KABUL: silinen sayfa/düğüm id'si YENİDEN KULLANILAMAZ (retired_ids — upsert reddeder).
    Silinip başka içerikle dönen id, eski öğrencinin suspend pozisyonunu/skorunu yanlış
    içeriğe bağlardı."""
    import server
    from fastmcp import Client
    from fastmcp.exceptions import ToolError as MCPToolError

    await server.SVC.ensure()
    async with Client(server.mcp) as c:
        r = await c.call_tool("create_scenario", {
            "title": "T", "outline": [
                {"id": "u1", "kind": "unit", "title": "U", "objective": {"id": "o1"}},
                {"id": "b_sil", "parent_id": "u1", "kind": "section", "title": "Silinecek"}]})
        sid = r.data["scenario_id"]
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "pg_sil", "node_id": "u1", "title": "Silinecek sayfa"}})
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "pg_kal", "node_id": "u1", "title": "Kalan"}})

        # sil → emekli; aynı id ile YENİ sayfa reddedilir
        await c.call_tool("scenario_delete_page", {"scenario_id": sid, "page_id": "pg_sil"})
        with pytest.raises(MCPToolError, match="yeniden kullanılamaz"):
            await c.call_tool("scenario_upsert_page", {
                "scenario_id": sid,
                "page": {"id": "pg_sil", "node_id": "u1", "title": "Hortlak"}})

        # düğüm için aynı kural
        await c.call_tool("scenario_delete_node", {"scenario_id": sid, "node_id": "b_sil"})
        with pytest.raises(MCPToolError, match="yeniden kullanılamaz"):
            await c.call_tool("scenario_upsert_node", {
                "scenario_id": sid,
                "node": {"id": "b_sil", "parent_id": "u1", "kind": "section", "title": "Hortlak"}})

        # MEVCUT sayfayı güncellemek serbest kalır (emekli listesi yalnız YENİ id'yi keser)
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "pg_kal", "node_id": "u1", "title": "Kalan (güncel)"}})
        # yeni benzersiz id de serbest
        await c.call_tool("scenario_upsert_page", {
            "scenario_id": sid,
            "page": {"id": "pg_yeni", "node_id": "u1", "title": "Yeni"}})
