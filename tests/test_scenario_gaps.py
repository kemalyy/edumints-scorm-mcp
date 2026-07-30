"""tests/test_scenario_gaps.py — Faz 2: boşluk raporu (derleme KAPISI) doğruluğu.

Kabul #2: kasten bozuk senaryo → TAM beklenen ⛔ kümesi, fazlası değil (kod-hassas).
Denetimler SIRA-BAĞIMSIZ (3.9). Ekran-tipi önerisi YALNIZ öneridir (asla otomatik seçim).
"""

from core.project import Objective, OutlineNode
from core.scenario import Page, ScenarioDocument, gaps_report


def _outline():
    return [
        OutlineNode(id="u1", kind="unit", title="Ünite",
                    objective=Objective(id="obj1"), pedagogy_pack="gagne-9"),
        OutlineNode(id="u2", kind="unit", title="Hedefsiz Ünite"),
    ]


def _doc(pages, **kw) -> ScenarioDocument:
    base = dict(id="scn_G", title="G", outline=_outline(), pages=pages, owner_key_id="k")
    base.update(kw)
    return ScenarioDocument(**base)


def _ev_page(pid="ev1", node="u1", **kw):
    base = dict(id=pid, node_id=node, order=0, title="Kanıt",
                evidence={"kind": "hatali_ornek", "hata": "h", "neden_yanlis": "n",
                          "dogru_karsilik": "d"})
    base.update(kw)
    return Page(**base)


def _q_page(pid="q1", node="u1", ev=("ev1",), **kw):
    base = dict(id=pid, node_id=node, order=1, title="Soru", screen_type="mcq",
                scoring={"scored": True, "points": 10}, evidence_from=list(ev))
    base.update(kw)
    return Page(**base)


# --------------------------------------------------------------------------- #
# Temiz senaryo → SIFIR blocker
# --------------------------------------------------------------------------- #
def test_clean_scenario_zero_blockers():
    r = gaps_report(_doc([_ev_page(), _q_page()]))
    assert r["blockers"] == []
    assert r["evidence_binding_coverage_estimate"] == 1.0


def test_report_shape():
    r = gaps_report(_doc([]))
    assert set(r) == {"blockers", "warnings", "suggestions",
                      "evidence_binding_coverage_estimate"}


# --------------------------------------------------------------------------- #
# Kabul #2 — kasten bozuk senaryo: TAM beklenen ⛔ kümesi, fazlası değil
# --------------------------------------------------------------------------- #
def test_broken_scenario_exact_blocker_set():
    doc = _doc([
        # 1) sarkan düğüm referansı
        Page(id="pA", node_id="yok", order=0, title="A", screen_type="content_slide"),
        # 2) hedefsiz zincir (orphan)
        Page(id="pB", node_id="u2", order=1, title="B", screen_type="content_slide"),
        # 3) puanlı + evidence_from boş + sarkan extra hedef
        Page(id="pC", node_id="u1", order=2, title="C", screen_type="mcq",
             scoring={"scored": True}, extra_objective_refs=["obj_yok"]),
        # 4) sarkan evidence_from + öz-referans
        Page(id="pD", node_id="u1", order=3, title="D", screen_type="mcq",
             scoring={"scored": True}, evidence_from=["hayalet", "pD"]),
        # 5) kanıt-rolü slot ama EvidenceDecl yok
        Page(id="pE", node_id="u1", order=4, title="E", screen_type="content_slide",
             media_slots=[{"slot_id": "m1", "role": "kanit", "kind": "image", "spec": "x"}]),
        # 6) öğrenci keşfi PUANLI (tahmin-yarışı yasağı)
        Page(id="pF", node_id="u1", order=5, title="F", screen_type="mcq",
             scoring={"scored": True}, evidence_from=["pE"],
             evidence={"kind": "ogrenci_kesfi", "kayit_yontemi": "k", "commit_prompt": "c"}),
        # 7) puanlı + açık-metin/içerik tipi (otomatik puanlanamaz)
        Page(id="pG", node_id="u1", order=6, title="G", screen_type="content_slide",
             scoring={"scored": True}, evidence_from=["pE"]),
    ])
    r = gaps_report(doc)
    got = sorted((b["code"], b["path"]) for b in r["blockers"])
    expected = sorted([
        ("DANGLING_NODE_REF", "pages[pA].node_id"),
        ("ORPHAN_PAGE", "pages[pB]"),
        ("SCORED_NO_EVIDENCE_FROM", "pages[pC].evidence_from"),
        ("DANGLING_OBJECTIVE_REF", "pages[pC].extra_objective_refs"),
        ("DANGLING_EVIDENCE_FROM", "pages[pD].evidence_from"),   # hayalet
        ("DANGLING_EVIDENCE_FROM", "pages[pD].evidence_from"),   # öz-referans
        ("EVIDENCE_KIND_MISSING", "pages[pE].evidence"),
        ("PREDICTION_SCORED", "pages[pF].scoring"),
        ("AUTO_GRADE_OPEN_TEXT", "pages[pG].screen_type"),
        # obj1: puanlı sayfalar var; kanıt-taşıyan sayfası pF (evidence'lı) OLDUĞU için
        # OBJECTIVE_NO_EVIDENCE BEKLENMEZ — tam-küme testi bunu da doğrular.
    ])
    assert got == expected


def test_objective_no_evidence_blocker():
    """Hedefte ≥1 puanlı sayfa ama SIFIR kanıt-beyanlı sayfa → OBJECTIVE_NO_EVIDENCE."""
    doc = _doc([
        Page(id="c1", node_id="u1", order=0, title="İçerik", screen_type="content_slide"),
        _q_page(pid="q1", ev=("c1",)),
    ])
    r = gaps_report(doc)
    codes = [b["code"] for b in r["blockers"]]
    assert codes == ["OBJECTIVE_NO_EVIDENCE"]


def test_order_independence_evidence_after_scored():
    """Kabul #8 (gaps yarısı): kanıt sayfası puanlı sayfadan SONRA → yine sıfır blocker."""
    r = gaps_report(_doc([_q_page(order=0), _ev_page(order=5)]))
    assert r["blockers"] == []


# --------------------------------------------------------------------------- #
# Uyarılar (⚠ — danışsal, bloklamaz)
# --------------------------------------------------------------------------- #
def test_warn_empty_media_slots_counted():
    doc = _doc([_ev_page(media_slots=[
        {"slot_id": "m1", "role": "aciklayici", "kind": "image", "spec": "x"},
        {"slot_id": "m2", "role": "aciklayici", "kind": "audio", "spec": "y",
         "asset_id": "asset_1"},
    ])])
    w = [x for x in gaps_report(doc)["warnings"] if x["code"] == "EMPTY_MEDIA_SLOTS"]
    assert len(w) == 1
    assert "1 boş" in w[0]["message"]
    assert "ev1/m1" in w[0]["message"]


def test_warn_phase_not_in_pack():
    """u1 gagne-9 beyan ediyor → paket fazında olmayan faz adı WARN üretir; paketteki
    gerçek faz adı üretmez (runtime/pedagogy-packs.json'a karşı — E2 _load_packs)."""
    from core.antislop import _load_packs

    packs = _load_packs()
    assert "gagne-9" in packs, "vendored manifest testin ön koşulu"
    real_phase = (packs["gagne-9"]["phases"] or [{}])[0].get("id")

    doc = _doc([_ev_page(phase="uydurma_faz"), _ev_page(pid="ev2", phase=real_phase)])
    w = [x for x in gaps_report(doc)["warnings"] if x["code"] == "PHASE_NOT_IN_PACK"]
    assert [x["path"] for x in w] == ["pages[ev1].phase"]


def test_warn_phase_silent_without_pack_declaration():
    doc = _doc([_ev_page(node="u2", phase="her_ne_ise")])  # u2 zincirinde paket beyanı yok
    assert [x for x in gaps_report(doc)["warnings"]
            if x["code"] == "PHASE_NOT_IN_PACK"] == []


def test_warn_duration_drift():
    pages = [_ev_page(duration_hint_sec=100), _q_page(duration_hint_sec=100)]
    r = gaps_report(_doc(pages, duration_target_sec=600))  # 200 vs 600 → sapma > %20
    assert any(x["code"] == "DURATION_DRIFT" for x in r["warnings"])
    r2 = gaps_report(_doc(pages, duration_target_sec=220))  # 200 vs 220 → tolerans içi
    assert not any(x["code"] == "DURATION_DRIFT" for x in r2["warnings"])


def test_warn_narration_echo_and_algorithm():
    body = "Mitokondri hücrenin enerji santralidir ve ATP üretiminden sorumludur burada"
    echo = _ev_page(copy={"body_md": body, "narration": body})  # birebir yankı → 1.0
    fresh = _ev_page(pid="ev2", copy={
        "body_md": body,
        "narration": "Şimdi diyagramda gördüğün krista kıvrımlarının yüzeyi neden artırdığını düşün"})
    r = gaps_report(_doc([echo, fresh]))
    w = [x for x in r["warnings"] if x["code"] == "NARRATION_ECHO"]
    assert [x["path"] for x in w] == ["pages[ev1].copy"]


def test_narration_echo_short_texts_ignored():
    p = _ev_page(copy={"body_md": "Kısa metin", "narration": "Kısa metin"})  # < 5 token
    assert not any(x["code"] == "NARRATION_ECHO"
                   for x in gaps_report(_doc([p]))["warnings"])


# --------------------------------------------------------------------------- #
# Öneriler — screen_type ÖNERİLİR, asla otomatik seçilmez
# --------------------------------------------------------------------------- #
def test_screen_type_suggestions_only():
    doc = _doc([
        Page(id="we", node_id="u1", order=0, title="Çözümlü",
             evidence={"kind": "islenmis_ornek", "steps": [
                 {"action": "a", "reasoning": "r"}, {"action": "b", "reasoning": "s"}]}),
        Page(id="kesif", node_id="u1", order=1, title="Keşif",
             evidence={"kind": "ogrenci_kesfi", "kayit_yontemi": "k", "commit_prompt": "c"}),
        Page(id="soru", node_id="u1", order=2, title="Soru",
             scoring={"scored": True}, evidence_from=["we"]),
        Page(id="film", node_id="u1", order=3, title="Video", media_slots=[
            {"slot_id": "v1", "role": "aciklayici", "kind": "video", "spec": "x"}]),
        Page(id="duz", node_id="u1", order=4, title="Düz"),
    ])
    r = gaps_report(doc)
    sug = {s["path"]: s["suggested_screen_type"] for s in r["suggestions"]
           if s["code"] == "SCREEN_TYPE_SUGGESTION"}
    assert sug == {
        "pages[we].screen_type": "worked_example",
        "pages[kesif].screen_type": "exploration",
        "pages[soru].screen_type": "mcq",
        "pages[film].screen_type": "video",
        "pages[duz].screen_type": "content_slide",
    }
    # ÖNERİ otomatik seçime dönüşmez: doküman sayfalarında screen_type hâlâ None
    assert all(p.screen_type is None for p in doc.pages)


def test_explicit_screen_type_no_suggestion():
    doc = _doc([_ev_page(screen_type="content_slide"), _q_page()])
    assert [s for s in gaps_report(doc)["suggestions"]
            if s["code"] == "SCREEN_TYPE_SUGGESTION"] == []


# --------------------------------------------------------------------------- #
# Kanıt-bağ kapsam tahmini
# --------------------------------------------------------------------------- #
def test_coverage_estimate_partial():
    doc = _doc([
        _ev_page(),
        _q_page(pid="q1", ev=("ev1",)),                      # kanıt-beyanlı sayfaya bağlı ✓
        _q_page(pid="q2", ev=("q1",), order=2),              # kanıta DEĞİL soruya bağlı ✗
    ])
    assert gaps_report(doc)["evidence_binding_coverage_estimate"] == 0.5


def test_coverage_vacuum_no_scored_pages():
    assert gaps_report(_doc([_ev_page()]))["evidence_binding_coverage_estimate"] == 1.0
