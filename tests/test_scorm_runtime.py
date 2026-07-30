"""tests/test_scorm_runtime.py — S1/S3/S4: SCORM runtime veri sözleşmesi.

Kapatılan boşluklar:
  S1 — cmi.interactions.* (soru bazında raporlama / çeldirici analizi)
  S3 — cmi.core.session_time / cmi.session_time (seat time; CPD/MEB kredilendirme)
  S4 — cmi.core.exit / cmi.exit + entry (resume garantisi)

Saf-mantık katmanı components/engine/scorm.js'te vitest ile test edilir (tests/js/scorm.test.js);
buradaki testler KÖPRÜNÜN kurulduğunu doğrular: bundle inline mi, ENGINE_JS doğru elemanları
yazıyor mu, üretilen ZIP'te var mı.
"""

import asyncio
import io
import json
import os
import zipfile

import pytest
from fastmcp import Client

import server
from components.renderer import render_html
from core.engine_bundle import load_scorm_bundle
from core.project import (
    Choice,
    ContentSlide,
    MCQScreen,
    Objective,
    Project,
    TrueFalseScreen,
    new_project_id,
)


def _content_only() -> Project:
    """Puanlanan ekranı OLMAYAN kurs — SCORM RT yine de gerekir (seat time / exit her kursta)."""
    return Project(id=new_project_id(), title="Düz içerik",
                   screens=[ContentSlide(id="c1", title="Giriş", body_html="<p>merhaba</p>")])


def _quiz_project(ver: str = "1.2") -> Project:
    return Project(id=new_project_id(), title="Sınav", scorm_version=ver, screens=[
        ContentSlide(id="c1", title="Giriş", body_html="<p>merhaba</p>"),
        MCQScreen(id="q1", title="Başkent neresi?", prompt_html="<p>?</p>",
                  options=[Choice(id="a", text_html="Ankara", correct=True),
                           Choice(id="b", text_html="İstanbul")]),
        TrueFalseScreen(id="q2", title="Doğru mu?", prompt_html="<p>?</p>", correct=True),
    ])


# --------------------------------------------------------------------------- #
# Bundle köprüsü
# --------------------------------------------------------------------------- #
def test_scorm_bundle_inlines_cleanly():
    b = load_scorm_bundle()
    assert "export " not in b                       # ESM sızıntısı yok
    assert "\nimport " not in b and not b.startswith("import ")
    assert "window.SCORMRT = __E" in b
    for fn in ("interactionElements", "sessionTime", "exitValue", "shouldRestore",
               "duration12", "duration2004", "formatResponse", "resultValue"):
        assert fn in b, f"bundle eksik: {fn}"
    assert load_scorm_bundle() is b                  # lru_cache deterministik


def test_scorm_bundle_is_unconditional_unlike_game_bundle():
    """Oyun bundle'ı lazy, SCORM RT DEĞİL: en sade kursta bile bulunmalı."""
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert "window.SCORMRT = __E" in html
    assert "/* engine/scorm.js */" in html
    assert "/* engine/rng.js */" not in html         # oyun bundle'ı hâlâ lazy (zero-load korunuyor)


def test_scorm_bundle_precedes_engine_js():
    """window.SCORMRT, onu kullanan ENGINE_JS'ten ÖNCE tanımlanmalı."""
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert html.index("window.SCORMRT = __E") < html.index("var RT = window.SCORMRT")


# --------------------------------------------------------------------------- #
# S3 — seat time
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ver,element", [("1.2", "cmi.core.session_time"), ("2004", "cmi.session_time")])
def test_s3_session_time_written(ver, element):
    p = _quiz_project(ver)
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert element in html
    assert "RT.sessionTime(sessionMs(), S2004)" in html
    assert "function writeSessionTime" in html
    assert "writeSessionTime();" in html             # evaluate() içinde çağrılıyor


def test_s3_idle_time_is_excluded():
    """Sekme gizliyken geçen süre sayılmamalı (idle şişmesi koruması)."""
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert "visibilitychange" in html
    assert "document.hidden?_sesPause():_sesResume()" in html


# --------------------------------------------------------------------------- #
# S4 — exit / entry
# --------------------------------------------------------------------------- #
def test_s4_exit_written_for_both_versions():
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert 'S2004?"cmi.exit":"cmi.core.exit"' in html
    assert "RT.exitValue" in html


def test_s4_entry_gates_restore():
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert 'S2004?"cmi.entry":"cmi.core.entry"' in html
    assert "RT.shouldRestore" in html
    # eski ölü ternary (her iki dal da cmi.suspend_data) temizlendi
    assert 'sGet(S2004?"cmi.suspend_data":"cmi.suspend_data")' not in html


def test_s4_finish_is_idempotent_and_pagehide_covered():
    """beforeunload mobilde kaçırılabilir → pagehide de bağlı; çift Terminate engelli."""
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert 'window.addEventListener("beforeunload",finishNow)' in html
    assert 'window.addEventListener("pagehide",finishNow)' in html
    assert "if(_finished) return; _finished=true;" in html


# --------------------------------------------------------------------------- #
# S5 — suspend_data kompakt kodlama köprüsü
# --------------------------------------------------------------------------- #
def test_s5_suspend_codec_in_bundle():
    b = load_scorm_bundle()
    for fn in ("encodeSuspend", "decodeSuspend", "encodeSuspendFit", "suspendLimit"):
        assert fn in b, f"bundle eksik: {fn}"


def test_s5_persist_and_restore_use_rt_codec():
    """persist/restore mantığı templates.py'de KOPYALANMAZ — scorm.js codec'i çağrılır."""
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    # Faz 4-ek: fit çağrısı meta (pozisyon kaydı + hedef haritası) taşır; bütçe suspendBudget'tan
    assert "fit=RT.encodeSuspendFit(state,order,lim," in html
    assert "RT.suspendBudget" in html
    # restore artık republish okuma merdiveninden geçer (RT yoksa decodeSuspend'e düşer)
    assert "RT.resumeSuspend(raw,order," in html
    assert "RT.decodeSuspend(raw,order)" in html
    assert "RT.suspendLimit" in html


def test_s5_write_failure_visibility_wired():
    """2.2c — yazma hatası/kırpma sessiz kalmaz: kontrol edilen yazım + konsol + xAPI izi."""
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    assert 'sSetChecked("cmi.suspend_data",json)' in html
    assert "RT.suspendWriteIssues" in html
    assert "RT.setResultOk" in html
    assert 'console.warn("[scorm] suspend_data "' in html
    assert 'XAPI.emit("suspend.trouble"' in html
    # eski kontrolsüz yazım geri gelmesin
    assert 'sSet("cmi.suspend_data",json)' not in html


# --------------------------------------------------------------------------- #
# S1 — interactions
# --------------------------------------------------------------------------- #
def test_s1_record_interaction_wired():
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    assert "function recordInteraction" in html
    assert "RT.interactionElements(rec,_ixOf(iid),S2004)" in html
    # bindCheck zengin sonucu ({ok,response,correct}) çözüyor
    assert "recordInteraction(s,ok,rich?r.response:null,rich?r.correct:null)" in html


def test_s1_every_graded_screen_type_records_an_interaction():
    """core/project.py QUIZ_TYPES'taki her tip bir etkileşim üretmeli (video hariç — puansız)."""
    from core.project import QUIZ_TYPES
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    # bindCheck üzerinden gelenler tek noktadan; bileşik tipler kendi çağrılarını yapar
    composite = ("simulation", "decision_scenario", "term_match_race",
                 "escape_room", "game", "adaptive_practice")
    assert html.count("recordInteraction(") >= 1 + len(composite)
    assert len(QUIZ_TYPES) == 14  # tip eklenirse bu test eşlemeyi gözden geçirmeye zorlar


def test_s1_adaptive_practice_reports_per_item():
    """Adaptif havuz SORU BAZINDA raporlanmalı — S1'in asıl değeri burada."""
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    assert 'recordInteraction(s, ok, [sel.dataset.opt], correct, s.id+"."+p.id, "mcq")' in html


def test_s1_interaction_index_is_stable_across_reanswer():
    """Aynı soru tekrar cevaplanınca AYNI indekse yazılmalı (LMS'te kopya satır olmasın)."""
    html = render_html(_content_only(), mode="preview", runtime_js="/*rt*/")
    assert "function _ixOf(id){ var n=state.ix[id]; if(n==null){ n=state.inext++; state.ix[id]=n; }" in html


def test_s1_quiz_screen_title_exported_for_description():
    """cmi.interactions.n.description (2004) ekran başlığından beslenir."""
    p = _quiz_project()
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    cfg = json.loads(html.split("window.__COURSE__ = ", 1)[1].split(";\nwindow.__ASSETS__", 1)[0])
    by_id = {s["id"]: s for s in cfg["screens"]}
    assert by_id["q1"]["title"] == "Başkent neresi?"
    assert "title" not in by_id["c1"]                # puanlanmayan ekranda gereksiz bayt yok


# --------------------------------------------------------------------------- #
# S2 — cmi.objectives.* köprüsü
# --------------------------------------------------------------------------- #
def _objective_project(ver: str = "1.2") -> Project:
    p = _quiz_project(ver)
    p.objectives = [Objective(id="o1", description="Temel kavramlar"), Objective(id="o2")]
    p.screens[1].objective_ids = ["o1"]        # q1 → o1
    p.screens[2].objective_ids = ["o1", "o2"]  # q2 → o1 + o2
    return p


def test_s2_objective_helpers_in_bundle():
    b = load_scorm_bundle()
    for fn in ("aggregateObjectives", "objectiveIndices", "objectiveElements"):
        assert fn in b, f"bundle eksik: {fn}"


def test_s2_write_objectives_wired_at_score_commit_lifecycle():
    """writeObjectives evaluate() içinde, writeScore ile AYNI yaşam döngüsü noktasında."""
    html = render_html(_objective_project(), mode="preview", runtime_js="/*rt*/")
    assert "function writeObjectives" in html
    assert "RT.aggregateObjectives(OBJ_IDS,OBJ_MAP,state.results)" in html
    assert "RT.objectiveIndices(ex,ids)" in html
    assert "RT.objectiveElements(a," in html
    # evaluate: writeScore() hemen ardından writeObjectives()
    assert html.index("writeScore();") < html.index("writeObjectives();") < html.index("var complete=isComplete()")


def test_s2_config_serializes_objectives_and_bindings():
    html = render_html(_objective_project(), mode="preview", runtime_js="/*rt*/")
    cfg = json.loads(html.split("window.__COURSE__ = ", 1)[1].split(";\nwindow.__ASSETS__", 1)[0])
    assert cfg["objectives"] == ["o1", "o2"]   # kurs hedef sırası (determinizm kaynağı)
    by_id = {s["id"]: s for s in cfg["screens"]}
    assert by_id["q1"]["objective_ids"] == ["o1"]
    assert by_id["q2"]["objective_ids"] == ["o1", "o2"]
    assert "objective_ids" not in by_id["c1"]  # puansız ekran bağ taşımaz


def test_s2_no_objectives_no_config_key():
    """Hedefsiz kursta ne config anahtarı ne çalışan yazım — additive sıfır maliyet."""
    html = render_html(_quiz_project(), mode="preview", runtime_js="/*rt*/")
    cfg = json.loads(html.split("window.__COURSE__ = ", 1)[1].split(";\nwindow.__ASSETS__", 1)[0])
    assert "objectives" not in cfg
    assert all("objective_ids" not in s for s in cfg["screens"])
@pytest.mark.asyncio
@pytest.mark.parametrize("ver,session_el,exit_el", [
    ("1.2", "cmi.core.session_time", "cmi.core.exit"),
    ("2004", "cmi.session_time", "cmi.exit"),
])
async def test_built_package_contains_s1_s3_s4(ver, session_el, exit_el):
    spec = {
        "title": f"S-paket {ver}",
        "scorm_version": ver,
        "screens": [
            {"type": "content_slide", "id": "c1", "title": "Giriş", "body_html": "<p>merhaba</p>"},
            {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>?</p>",
             "options": [{"id": "a", "text_html": "1", "correct": True},
                         {"id": "b", "text_html": "2"}]},
        ],
    }
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": spec})
        assert res.data.status == "done", res.data
        token = res.data.download_url.rstrip("/").split("/")[-1]
    meta = await server.SVC.store.get_package_by_token(token)
    zpath = os.path.join(server.SETTINGS.data_dir, meta.rel_path)

    def _read() -> bytes:
        with open(zpath, "rb") as f:
            return f.read()

    raw = await asyncio.to_thread(_read)

    index = zipfile.ZipFile(io.BytesIO(raw)).read("index.html").decode("utf-8")
    assert "window.SCORMRT = __E" in index          # S1/S3/S4 yardımcıları pakette
    assert session_el in index                       # S3
    assert exit_el in index                          # S4
    assert "cmi.interactions." in index              # S1 (scorm.js içinden)
    assert "function recordInteraction" in index
