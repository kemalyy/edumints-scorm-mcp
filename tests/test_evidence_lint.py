"""tests/test_evidence_lint.py — E1 (#110): lint_course kanıt-bağlama denetimleri.

Skill kural kaynakları (lint semantiği bu kural metinleriyle birebir):
- K1–K3  skills/authoring-scorm-courses/references/core/evidence-binding.md
- H1–H3  .../core/alignment.md (H3: skorlanan > hedef + 1 → WARN)
- Z1–Z3  .../core/scoring-timing.md (Z1: skorlu = points>0 ya da puana yazan; Z3: points=0 deneme serbest)
- T1–T3  .../anti-slop.md "T. Tabanlar"

Tasarım kararı (revize c): kanıt bağı YALNIZ additive `evidence_screen_ids` alanıyla kurulur.
Heuristik (hedef-ortaklığı / aynı-section) HİÇBİR ZAMAN denetimi susturmaz — yalnız varsayılan
moddaki WARN mesajına aday önerisi ekler; strict modda sadece açık beyan geçer (aksi halde alan
hiç doldurulmaz, denetim "yakında artefaktımsı ekran var mı"ya sessizce geriler). Ek katman:
çözülen kanıt hedefi kanıt-TAŞIYABİLİR olmalı (`evidence_target_not_evidentiary`) — yoksa bağ
törenselleşir. SIRA/faz denetimi YOK — Katman-1 yöntem bağımsızlığı (dallanan/adaptif kursta
ekran indeksi ≠ sunum sırası).
"""

import pytest
from fastmcp import Client

import server
from core.antislop import (
    STRICT_PROMOTED_CODES,
    evidence_binding_coverage,
    lint_course,
    lint_errors,
)
from core.project import Project, new_project_id


def _cs(i, section=None, artifact=False):
    """Düz metin content_slide; artifact=True → blok görselli (kanıt-taşıyabilir artefakt)."""
    d = {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}",
         "body_html": f"<p>metin {i}</p>"}
    if artifact:
        d.pop("body_html")
        d["blocks"] = [{"asset_id": f"a{i}", "caption": f"Vaka artefaktı {i}"}]
    if section:
        d["section"] = section
    return d


def _mcq(qid="q1", **kw):
    d = {"type": "mcq", "id": qid, "title": "Soru", "prompt_html": "<p>?</p>",
         "options": [{"id": "a", "text_html": "A", "correct": True},
                     {"id": "b", "text_html": "B"}],
         "feedback": {"correct_html": "Doğru — kanıt ekranında gördüğün gibi.",
                      "incorrect_html": "Kanıt ekranına geri dön."}}
    d.update(kw)
    return d


def _proj(screens, **kw):
    return Project(id=new_project_id(), title="K", screens=screens, **kw)


# --------------------------------------------------------------------------- #
# unbound_scored_question (K1/K2/T1 — WARN, strict'te terfi)
# --------------------------------------------------------------------------- #
def test_e1_unbound_scored_question_warns():
    """#110 kabul: kanıtsız-skorlu-soru fikstürü FAIL (varsayılanda WARN, strict'te error)."""
    p = _proj([_cs(0), _mcq()])  # içerik var ama beyan edilmiş bağ yok
    issues = [i for i in lint_course(p) if i.code == "unbound_scored_question"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "K1" in issues[0].message  # kural künyesi mesajda
    assert issues[0].path == "screens[1]"


def test_e1_unbound_is_strict_promoted():
    """Geriye uyumluluk: varsayılan build BLOKLAMAZ; strict modda bloklamaya terfi eder."""
    assert "unbound_scored_question" in STRICT_PROMOTED_CODES
    p = _proj([_cs(0), _mcq()])
    assert "unbound_scored_question" not in {i.code for i in lint_errors(p)}
    assert "unbound_scored_question" in {i.code for i in lint_errors(p, strict=True)}


def test_e1_formative_question_not_flagged():
    """Z1/Z3 — points=0 (puana yazmayan) soru skorlu DEĞİL: kanıt şartı summatif ekranlara."""
    p = _proj([_cs(0), _mcq(points=0)])
    assert "unbound_scored_question" not in {i.code for i in lint_course(p)}


def test_e1_on_correct_points_var_writer_is_scored():
    """Z1 — points=0 ama on_correct ile puan değişkenine yazan ekran SKORLU sayılır (K1 kapsamı)."""
    p = _proj(
        [_cs(0), _mcq(points=0, on_correct=[{"var": "puan", "op": "add", "value": 10}])],
        points_var="puan",
        variables=[{"name": "puan", "type": "number", "default": 0}],
    )
    assert "unbound_scored_question" in {i.code for i in lint_course(p)}


# --------------------------------------------------------------------------- #
# evidence_screen_ids alanı — tek OTORİTER bağ + evidence_screen_missing (ERROR)
# --------------------------------------------------------------------------- #
def test_e1_evidence_field_binds():
    p = _proj([_cs(0, artifact=True), _mcq(evidence_screen_ids=["c0"])])
    codes = {i.code for i in lint_course(p)}
    assert "unbound_scored_question" not in codes
    assert "evidence_screen_missing" not in codes
    assert "evidence_target_not_evidentiary" not in codes


def test_e1_dangling_evidence_id_is_error():
    """K1 — sarkan kanıt referansı SERT hata (bilinmeyen objective_ids ile aynı sınıf): build'i bloklar."""
    from core.validator import validate_project
    p = _proj([_cs(0), _mcq(evidence_screen_ids=["yok_boyle_ekran"])])
    issues = [i for i in lint_course(p) if i.code == "evidence_screen_missing"]
    assert len(issues) == 1 and issues[0].severity == "error"
    assert "evidence_screen_missing" in {i.code for i in lint_errors(p)}  # varsayılanda da bloklar
    assert any("yok_boyle_ekran" in e.message for e in validate_project(p))


def test_e1_self_reference_evidence_is_error():
    """K2 — ekran kendi kendinin kanıtı olamaz (vacuous bağ): ERROR."""
    p = _proj([_cs(0), _mcq(evidence_screen_ids=["q1"])])
    issues = [i for i in lint_course(p) if i.code == "evidence_screen_missing"]
    assert len(issues) == 1 and issues[0].severity == "error"


# --------------------------------------------------------------------------- #
# evidence_target_not_evidentiary — çözülen hedef kanıt TAŞIYABİLMELİ (törensel bağ yasak)
# --------------------------------------------------------------------------- #
def test_e1_non_evidentiary_target_warns():
    """Düz iddia-metni content_slide (artefaktsız) kanıt hedefi olamaz — bağ törenselleşir."""
    p = _proj([_cs(0), _mcq(evidence_screen_ids=["c0"])])  # c0: yalnız body_html, artefakt yok
    issues = [i for i in lint_course(p) if i.code == "evidence_target_not_evidentiary"]
    assert len(issues) == 1 and issues[0].severity == "warn"
    assert "evidence_target_not_evidentiary" in STRICT_PROMOTED_CODES
    # alan dolu olduğundan unbound AYRICA verilmez (bulgu hedefin niteliğinde)
    assert "unbound_scored_question" not in {i.code for i in lint_course(p)}


def test_e1_scored_screen_is_not_evidentiary_target():
    """Skorlu bir soru başka skorlu sorunun kanıtı olamaz; formatif (points=0) deneme OLABİLİR
    (K1 tür 3/5, Z3 — deneme çıktısı/başarısız deneme kanıt kaynağına dönüşür)."""
    scored_target = _mcq("q_hedef")  # points vars. 10 → skorlu
    p = _proj([scored_target, _mcq("q1", evidence_screen_ids=["q_hedef"])])
    assert "evidence_target_not_evidentiary" in {i.code for i in lint_course(p)}
    formative = _mcq("try1", points=0)
    p2 = _proj([formative, _mcq("q1", evidence_screen_ids=["try1"])])
    assert "evidence_target_not_evidentiary" not in {i.code for i in lint_course(p2)}


def test_e1_video_target_requires_verifiable_content():
    """K1 — dış medya (video) kanıt sayılır YALNIZ içeriği spec'ten doğrulanabiliyorsa
    (caption/narration_text). Çıplak video = dış varlık kabı, kanıt değil."""
    bare = {"type": "video", "id": "v1", "title": "İzle", "video_url": "https://ornek.test/v.mp4"}
    p = _proj([bare, _mcq(evidence_screen_ids=["v1"])])
    assert "evidence_target_not_evidentiary" in {i.code for i in lint_course(p)}
    captioned = dict(bare, caption="Saldırgan 2 saat süre baskısı kuruyor — cevap burada.")
    p2 = _proj([captioned, _mcq(evidence_screen_ids=["v1"])])
    assert "evidence_target_not_evidentiary" not in {i.code for i in lint_course(p2)}


def test_e1_title_and_summary_are_not_evidentiary():
    title = {"type": "title_slide", "id": "t1", "title": "Kapak — neden buradasın?"}
    summary = {"type": "summary", "id": "sm", "title": "Ne öğrendin?"}
    p = _proj([title, summary, _mcq(evidence_screen_ids=["t1", "sm"])])
    issues = [i for i in lint_course(p) if i.code == "evidence_target_not_evidentiary"]
    assert len(issues) == 2


# --------------------------------------------------------------------------- #
# Heuristik fallback: ASLA susturmaz — yalnız varsayılan WARN mesajına aday önerir
# --------------------------------------------------------------------------- #
def test_e1_heuristic_suggests_candidates_but_still_warns():
    """Aynı hedefe bağlı formatif deneme (K1 tür 5) ADAY olarak önerilir; WARN yine verilir —
    çıkarım alanın yerine geçseydi alan hiç doldurulmazdı."""
    formative = _mcq("try1", points=0, objective_ids=["O1"])
    scored = _mcq("q1", objective_ids=["O1"])
    p = _proj([formative, scored],
              objectives=[{"id": "O1", "title": "Şüpheli e-postayı işaretlerinden tanır"}])
    issues = [i for i in lint_course(p) if i.code == "unbound_scored_question"]
    assert len(issues) == 1 and issues[0].severity == "warn"
    assert "try1" in issues[0].message  # aday önerisi mesajda


def test_e1_heuristic_never_satisfies_strict():
    """Strict modda YALNIZ açık `evidence_screen_ids` beyanı geçer; heuristik aday geçirmez."""
    formative = _mcq("try1", points=0, objective_ids=["O1"])
    scored = _mcq("q1", objective_ids=["O1"])
    p = _proj([formative, scored],
              objectives=[{"id": "O1", "title": "Tanır"}])
    assert "unbound_scored_question" in {i.code for i in lint_errors(p, strict=True)}
    # açık beyan → strict temiz
    scored2 = _mcq("q1", objective_ids=["O1"], evidence_screen_ids=["try1"])
    p2 = _proj([formative, scored2], objectives=[{"id": "O1", "title": "Tanır"}])
    assert "unbound_scored_question" not in {i.code for i in lint_errors(p2, strict=True)}


def test_e1_same_section_candidate_in_message():
    """Aynı `section`'daki kanıt-taşıyabilir ekran aday olarak önerilir (yine WARN)."""
    p = _proj([_cs(0, section="Vaka", artifact=True), _mcq(section="Vaka")])
    issues = [i for i in lint_course(p) if i.code == "unbound_scored_question"]
    assert len(issues) == 1 and "c0" in issues[0].message
    # farklı bölümde aday yok → mesajda öneri yok, K2/K3 prosedürü var
    p2 = _proj([_cs(0, section="Vaka", artifact=True), _mcq(section="Sınav")])
    issues2 = [i for i in lint_course(p2) if i.code == "unbound_scored_question"]
    assert len(issues2) == 1 and "c0" not in issues2[0].message and "K3" in issues2[0].message


def test_e1_candidate_discovery_is_order_independent():
    """Katman-1: adayın sorudan SONRA gelmesi öneriyi değiştirmez (ekran indeksi ≠ sunum sırası —
    dallanan/adaptif kursta kanıt ekranı koşullu/geç indeksli olabilir). Sıra denetimi YOKTUR."""
    p_before = _proj([_cs(0, section="Vaka", artifact=True), _mcq(section="Vaka")])
    p_after = _proj([_mcq(section="Vaka"), _cs(0, section="Vaka", artifact=True)])
    msg_b = [i.message for i in lint_course(p_before) if i.code == "unbound_scored_question"]
    msg_a = [i.message for i in lint_course(p_after) if i.code == "unbound_scored_question"]
    assert msg_b and msg_a
    assert ("c0" in msg_b[0]) and ("c0" in msg_a[0])


# --------------------------------------------------------------------------- #
# evidence_binding_coverage — açık-beyan kapsam metriği (sürüklenme görünür olsun)
# --------------------------------------------------------------------------- #
def test_e1_coverage_metric():
    art = _cs(0, artifact=True)
    bound = _mcq("q1", evidence_screen_ids=["c0"])
    unbound = _mcq("q2")
    assert evidence_binding_coverage(_proj([art, bound, unbound])) == 0.5
    assert evidence_binding_coverage(_proj([art, bound])) == 1.0
    assert evidence_binding_coverage(_proj([art, unbound])) == 0.0
    # skorlu soru yoksa vakum: 1.0
    assert evidence_binding_coverage(_proj([art])) == 1.0


def test_e1_coverage_ignores_ceremonial_bindings():
    """Törensel bağ (kanıt-taşıyamaz hedef / sarkan id) kapsamı ŞİŞİRMEZ."""
    plain = _cs(0)  # artefaktsız düz metin — kanıt-taşıyamaz
    ceremonial = _mcq("q1", evidence_screen_ids=["c0"])
    assert evidence_binding_coverage(_proj([plain, ceremonial])) == 0.0
    dangling = _mcq("q1", evidence_screen_ids=["yok"])
    assert evidence_binding_coverage(_proj([_cs(0), dangling])) == 0.0


# --------------------------------------------------------------------------- #
# scored_over_objectives (H3 — WARN, terfi YOK: sınav kursları meşru aşabilir)
# --------------------------------------------------------------------------- #
def test_e1_scored_over_objectives_warns():
    """#110 kabul: hedef+1 aşımı fikstürü WARN veriyor."""
    objs = [{"id": "O1", "title": "Tanır"}]
    screens = [_cs(0)] + [_mcq(f"q{i}", objective_ids=["O1"]) for i in range(3)]  # 3 > 1+1
    p = _proj(screens, objectives=objs)
    issues = [i for i in lint_course(p) if i.code == "scored_over_objectives"]
    assert len(issues) == 1 and issues[0].severity == "warn"
    assert "H3" in issues[0].message
    assert "scored_over_objectives" not in STRICT_PROMOTED_CODES  # H3 açıkça warn-düzeyi


def test_e1_scored_within_threshold_no_warn():
    objs = [{"id": "O1", "title": "Tanır"}]
    screens = [_cs(0)] + [_mcq(f"q{i}", objective_ids=["O1"]) for i in range(2)]  # 2 ≤ 1+1
    p = _proj(screens, objectives=objs)
    assert "scored_over_objectives" not in {i.code for i in lint_course(p)}
    # hedef beyan edilmemişse eşik uygulanamaz (H3 beyana bağlı) → WARN yok
    p2 = _proj([_mcq(f"q{i}") for i in range(5)])
    assert "scored_over_objectives" not in {i.code for i in lint_course(p2)}


# --------------------------------------------------------------------------- #
# source_item_parity (#110 — 1:1 kopya kokusu; beyan-temelli)
# --------------------------------------------------------------------------- #
def test_e1_source_item_parity_warns():
    """#110 kabul: kaynak-madde ≈ ekran-sayısı fikstürü WARN veriyor."""
    screens = [_cs(i) for i in range(10)]
    p = _proj(screens, source_item_count=10)
    issues = [i for i in lint_course(p) if i.code == "source_item_parity"]
    assert len(issues) == 1 and issues[0].severity == "warn"


def test_e1_source_item_parity_tolerance_and_optout():
    # belirgin fark → koku yok
    p = _proj([_cs(i) for i in range(10)], source_item_count=20)
    assert "source_item_parity" not in {i.code for i in lint_course(p)}
    # beyan yoksa denetim yok (geriye uyumlu)
    p2 = _proj([_cs(i) for i in range(10)])
    assert "source_item_parity" not in {i.code for i in lint_course(p2)}
    # çok küçük kaynak (<5 madde) gürültü — muaf
    p3 = _proj([_cs(i) for i in range(3)], source_item_count=3)
    assert "source_item_parity" not in {i.code for i in lint_course(p3)}


# --------------------------------------------------------------------------- #
# visual_poverty ÖĞRETEN artefakta bağlanır (#110 — süs görseli sayılmaz)
# --------------------------------------------------------------------------- #
def test_e1_visual_poverty_ignores_decorative_visuals():
    """Çıplak video (dış varlık kabı) ve prompt'suz lottie süs sayılır; caption'lı video ile
    prompt'lu lottie ÖĞRETEN artefakttır (spec'ten doğrulanabilir içerik taşır)."""
    def bare_video(vid):
        return {"type": "video", "id": vid, "title": "İzle", "video_url": "https://ornek.test/v.mp4"}

    # 8 ekran: 2 çıplak video + 6 metin → öğreten görsel 0 → WARN
    screens = [bare_video("v1"), bare_video("v2")] + [_cs(i) for i in range(6)]
    p = _proj(screens)
    assert "visual_poverty" in {i.code for i in lint_course(p)}

    # aynı kurs, videolara caption (spec'ten doğrulanabilir içerik) → 2/8 = %25 → WARN yok
    cap = [dict(bare_video(v), caption="Anlatım metni: cevap bu videoda gösteriliyor.")
           for v in ("v1", "v2")]
    p2 = _proj(cap + [_cs(i) for i in range(6)])
    assert "visual_poverty" not in {i.code for i in lint_course(p2)}


def test_e1_visual_poverty_lottie_needs_prompt():
    def lottie(lid, prompt=None):
        d = {"type": "lottie", "id": lid, "title": "Animasyon", "lottie_asset_id": "a1"}
        if prompt:
            d["prompt_html"] = prompt
        return d

    screens = [lottie("l1"), lottie("l2")] + [_cs(i) for i in range(6)]
    p = _proj(screens)
    assert "visual_poverty" in {i.code for i in lint_course(p)}

    screens2 = [lottie("l1", "<p>Adımları izle: neyin nereye aktığına bak.</p>"),
                lottie("l2", "<p>Döngünün kritik anını yakala.</p>")] + [_cs(i) for i in range(6)]
    p2 = _proj(screens2)
    assert "visual_poverty" not in {i.code for i in lint_course(p2)}


# --------------------------------------------------------------------------- #
# Tool yüzeyi — makine-okur JSON + fail/warn ayrımı + kapsam metriği (#110 kabul)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_e1_lint_course_tool_reports_machine_readable():
    spec = {"title": "E1 kanıt", "screens": [_cs(0), _mcq()]}
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        pid = res.data.project_id
        rep = (await c.call_tool("lint_course", {"project_id": pid})).data
        assert {"error_count", "warn_count", "clean", "issues",
                "evidence_binding_coverage"} <= set(rep)
        assert rep["evidence_binding_coverage"] == 0.0  # 1 skorlu soru, açık beyan yok
        hit = [i for i in rep["issues"] if i["code"] == "unbound_scored_question"]
        assert hit and hit[0]["severity"] == "warn"
        # strict: terfi → error sayısına düşer (fail/warn ayrımı makine-okur)
        srep = (await c.call_tool("lint_course", {"project_id": pid, "strict": True})).data
        assert any(i["code"] == "unbound_scored_question" and i["severity"] == "error"
                   for i in srep["issues"])
        assert srep["error_count"] >= 1


@pytest.mark.asyncio
async def test_e1_build_from_spec_carries_source_item_count():
    """CourseSpec.source_item_count → Project'e taşınır; lint parity kokusunu tool'dan raporlar."""
    spec = {"title": "E1 parity", "source_item_count": 10,
            "screens": [_cs(i) for i in range(10)]}
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        pid = res.data.project_id
        rep = (await c.call_tool("lint_course", {"project_id": pid})).data
        assert any(i["code"] == "source_item_parity" for i in rep["issues"])
