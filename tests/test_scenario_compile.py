"""tests/test_scenario_compile.py — Faz 2: derleyici (senaryo → build_from_spec payload).

Kabul kalemleri:
  #1 — gerçekçi mini senaryo derlenir → lint_course 0 hata + evidence coverage 1.0
  #7 — derlenmiş spec'te faz adı GREP-0 (3.2 — Katman-1'e faz adı girmez)
  #8 — indeks bağımsızlığı: kanıt sayfası puanlı sayfadan SONRA da temiz derlenir+lint'lenir
  compile refusal — ⛔ blocker varken ScenarioCompileError (derleme reddedilir)
  md→html — deterministik çevirici + raw script/svg imkânsız (sanitize)
  screen_type derlemede zorunlu (gaps önerir; derleme ister)
"""

import json

import pytest

from core.project import Objective, OutlineNode, Project
from core.scenario import (
    Page,
    ScenarioCompileError,
    ScenarioDocument,
    compile_scenario,
    md_to_html,
)
from core.validator import validate_project


# --------------------------------------------------------------------------- #
# Gerçekçi mini senaryo fikstürü (kabul #1 / #7 / #8)
# --------------------------------------------------------------------------- #
def _mini_doc(evidence_order=0, scored_order=1) -> ScenarioDocument:
    return ScenarioDocument(
        id="scn_mini", title="Fotosentez", owner_key_id="k",
        duration_target_sec=300,
        outline=[
            OutlineNode(id="u1", kind="unit", title="Fotosentez",
                        objective=Objective(id="obj_ps", description="Süreci açıkla"),
                        pedagogy_pack="gagne-9"),
            OutlineNode(id="s1", parent_id="u1", kind="section", title="Işık evresi"),
        ],
        pages=[
            Page(id="ornek", node_id="s1", order=evidence_order, title="Hatalı örnek",
                 phase="dikkat_cek", screen_type="content_slide",
                 copy={"body_md": "## Yaygın hata\n\nÖğrenciler **karanlık** evreyi ışık sanır."},
                 evidence={"kind": "hatali_ornek",
                           "hata": "Karanlık evre ışık gerektirir sanılır",
                           "neden_yanlis": "Calvin döngüsü ışıktan bağımsızdır",
                           "dogru_karsilik": "Işık evresi ATP/NADPH üretir; Calvin bunları kullanır"}),
            Page(id="soru", node_id="s1", order=scored_order, title="Kontrol sorusu",
                 phase="performans", screen_type="mcq",
                 scoring={"scored": True, "points": 10}, evidence_from=["ornek"],
                 screen_payload={
                     "prompt_html": "Işık evresinin ürünü nedir?",
                     "options": [
                         {"id": "a", "text_html": "ATP ve NADPH", "correct": True},
                         {"id": "b", "text_html": "Glikoz", "correct": False}],
                 }),
        ],
    )


def _project_from_spec(spec: dict) -> Project:
    p = Project(
        id="proj_C", title=spec["title"],
        objectives=[Objective.model_validate(o) for o in spec.get("objectives", [])],
        outline=[OutlineNode.model_validate(n) for n in spec.get("outline", [])],
        screens=spec["screens"], owner_key_id="k",
    )
    return p


# --------------------------------------------------------------------------- #
# Kabul #1 — tur atma: 0 hata + coverage 1.0
# --------------------------------------------------------------------------- #
def test_compile_mini_passes_lint_zero_errors_and_full_coverage():
    from core.antislop import evidence_binding_coverage

    spec, warnings = compile_scenario(_mini_doc())
    p = _project_from_spec(spec)

    errs = validate_project(p)
    assert errs == [], [e.message for e in errs]
    assert evidence_binding_coverage(p) == 1.0


def test_compiled_objective_hoisted_to_course_with_method_pack():
    spec, _ = compile_scenario(_mini_doc())
    assert [o["id"] for o in spec["objectives"]] == ["obj_ps"]
    # node pedagogy_pack → Objective.method_pack (E2 bedava)
    assert spec["objectives"][0]["method_pack"] == "gagne-9"
    # outline hedefsiz taşınır (ad-alanı çakışması olmasın)
    assert all("objective" not in n for n in spec["outline"])
    # puanlı ekran hedefe bağlı; kanıt ekranı evidence_screen_ids'e girmez ama soru referanslar
    soru = next(s for s in spec["screens"] if s["id"] == "soru")
    assert soru["objective_ids"] == ["obj_ps"]
    assert soru["evidence_screen_ids"] == ["ornek"]


# --------------------------------------------------------------------------- #
# Kabul #7 — derlenmiş spec'te faz adı grep-0
# --------------------------------------------------------------------------- #
def test_compiled_spec_has_no_phase_leak():
    spec, _ = compile_scenario(_mini_doc())
    blob = json.dumps(spec, ensure_ascii=False)
    assert "phase" not in blob
    assert "dikkat_cek" not in blob
    assert "performans" not in blob
    for scr in spec["screens"]:
        assert "phase" not in scr


# --------------------------------------------------------------------------- #
# Kabul #8 — indeks bağımsızlığı: kanıt sayfası puanlı sayfadan SONRA
# --------------------------------------------------------------------------- #
def test_compile_index_independent_evidence_after_scored():
    spec, _ = compile_scenario(_mini_doc(evidence_order=9, scored_order=0))
    p = _project_from_spec(spec)
    assert validate_project(p) == []
    # kararlı sıralama: order alanına göre → soru (0) önce, örnek (9) sonra
    assert [s["id"] for s in spec["screens"]] == ["soru", "ornek"]


# --------------------------------------------------------------------------- #
# Derleme reddi — ⛔ blocker varken ScenarioCompileError
# --------------------------------------------------------------------------- #
def test_compile_refuses_when_blockers_present():
    doc = ScenarioDocument(
        id="scn_bad", title="Bozuk", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U")],  # hedefsiz
        pages=[Page(id="p1", node_id="u1", order=0, title="Orphan",
                    screen_type="content_slide")],
    )
    with pytest.raises(ScenarioCompileError) as ei:
        compile_scenario(doc)
    assert any(b["code"] == "ORPHAN_PAGE" for b in ei.value.blockers)


def test_compile_refuses_missing_screen_type():
    doc = ScenarioDocument(
        id="scn_ns", title="T", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U",
                             objective=Objective(id="o1"))],
        pages=[Page(id="p1", node_id="u1", order=0, title="P")],  # screen_type yok
    )
    with pytest.raises(ScenarioCompileError) as ei:
        compile_scenario(doc)
    assert any(b["code"] == "MISSING_SCREEN_TYPE" for b in ei.value.blockers)


def test_compile_refuses_unknown_screen_type():
    doc = ScenarioDocument(
        id="scn_u", title="T", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U",
                             objective=Objective(id="o1"))],
        pages=[Page(id="p1", node_id="u1", order=0, title="P", screen_type="uçan_halı")],
    )
    with pytest.raises(ScenarioCompileError) as ei:
        compile_scenario(doc)
    assert any(b["code"] == "UNKNOWN_SCREEN_TYPE" for b in ei.value.blockers)


# --------------------------------------------------------------------------- #
# md → html: deterministik + sanitizer (raw svg/canvas/script imkânsız)
# --------------------------------------------------------------------------- #
def test_md_to_html_basic_blocks():
    html = md_to_html("# Başlık\n\nParagraf **kalın** ve *italik*.\n\n- bir\n- iki")
    assert "<h1>Başlık</h1>" in html
    assert "<strong>kalın</strong>" in html
    assert "<em>italik</em>" in html
    assert "<ul><li>bir</li><li>iki</li></ul>" in html


def test_md_to_html_deterministic():
    src = "## Alt\n\n1. a\n2. b\n\nSon `kod` [bağ](https://x.test)."
    assert md_to_html(src) == md_to_html(src)
    assert '<a href="https://x.test"' in md_to_html(src)
    assert "<ol><li>a</li><li>b</li></ol>" in md_to_html(src)


def test_md_to_html_strips_raw_script_and_svg():
    html = md_to_html("Metin <script>alert(1)</script> ve <svg onload=x></svg> son")
    assert "<script" not in html
    assert "<svg" not in html
    assert "alert" in html  # kaçışlanmış literal olarak kalır, çalıştırılamaz


def test_compiled_body_is_sanitized_html():
    doc = _mini_doc()
    doc.pages[0].copy.body_md = "Metin <script>bad()</script>\n\n## Güvenli"
    spec, _ = compile_scenario(doc)
    blob = json.dumps(spec, ensure_ascii=False)
    assert "<script" not in blob
    assert "bad()" in blob  # literal metin korunur; etiket değil


# --------------------------------------------------------------------------- #
# Boş slot omit + model_3d uyarısı
# --------------------------------------------------------------------------- #
def test_empty_slot_omitted_and_model3d_warns():
    doc = ScenarioDocument(
        id="scn_slot", title="T", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U",
                             objective=Objective(id="o1"))],
        pages=[Page(id="p1", node_id="u1", order=0, title="P", screen_type="content_slide",
                    copy={"body_md": "gövde"},
                    media_slots=[
                        {"slot_id": "empty", "role": "aciklayici", "kind": "image",
                         "spec": "x"},  # boş → omit
                        {"slot_id": "m3d", "role": "aciklayici", "kind": "model_3d",
                         "spec": "y", "asset_id": "asset_z"},  # desteklenmez → warn
                    ])],
    )
    spec, warnings = compile_scenario(doc)
    scr = spec["screens"][0]
    assert "media_asset_id" not in scr  # boş slot basılmadı; ekran anlamlı kaldı
    assert any(w["code"] == "SLOT_KIND_UNSUPPORTED" for w in warnings)


def test_filled_image_slot_attached_with_alt():
    doc = ScenarioDocument(
        id="scn_img", title="T", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U",
                             objective=Objective(id="o1"))],
        pages=[Page(id="p1", node_id="u1", order=0, title="P", screen_type="content_slide",
                    copy={"body_md": "gövde"},
                    media_slots=[{"slot_id": "img", "role": "kanit", "kind": "image",
                                  "spec": "diyagram", "asset_id": "asset_d",
                                  "a11y": {"alt_text": "hücre diyagramı"}}],
                    evidence={"kind": "anotasyonlu_artefakt", "artefakt_ref": "img",
                              "anotasyonlar": ["çekirdek işaretli"]})],
    )
    spec, _ = compile_scenario(doc)
    scr = spec["screens"][0]
    assert scr["media_asset_id"] == "asset_d"
    assert scr["media_alt"] == "hücre diyagramı"


# --------------------------------------------------------------------------- #
# Kanıt beyanı → içerik türetme
# --------------------------------------------------------------------------- #
def test_worked_example_evidence_to_steps():
    doc = ScenarioDocument(
        id="scn_we", title="T", owner_key_id="k",
        outline=[OutlineNode(id="u1", kind="unit", title="U",
                             objective=Objective(id="o1"))],
        pages=[Page(id="we", node_id="u1", order=0, title="Çözümlü", screen_type="worked_example",
                    evidence={"kind": "islenmis_ornek", "steps": [
                        {"action": "Denklemi kur", "reasoning": "Değişkeni yalnız bırak"},
                        {"action": "Çöz", "reasoning": "İki tarafı böl"}]})],
    )
    spec, _ = compile_scenario(doc)
    p = _project_from_spec(spec)
    assert validate_project(p) == []
    scr = spec["screens"][0]
    assert len(scr["steps"]) == 2
    assert scr["steps"][0]["rationale_html"] == "Değişkeni yalnız bırak"
