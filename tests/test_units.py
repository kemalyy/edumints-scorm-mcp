"""tests/test_units.py — birim testler (manifest, SSRF, sanitizasyon, fast-path, kota)."""

import json
import pytest
from fastmcp import Client

import server
from auth.errors import ToolError
from auth.ssrf import _is_blocked_ip, assert_safe_url, decode_data_uri
from components.renderer import render_html, sanitize
from core.manifest import build_manifest
from core.project import Project, new_project_id, ContentSlide, MCQScreen, Choice


# ---- manifest ----
@pytest.mark.parametrize("ver", ["1.2", "2004"])
def test_manifest_wellformed(ver):
    from lxml import etree

    p = Project(id=new_project_id(), title="T", scorm_version=ver)
    xml = build_manifest(p, file_list=["index.html", "runtime/scorm-again.min.js"])
    root = etree.fromstring(xml.encode())
    assert etree.QName(root).localname == "manifest"
    assert "schemaversion" in xml


# ---- SSRF blocklist ----
@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.1", "172.16.5.5", "192.168.1.1", "169.254.169.254",
    "100.64.0.1", "::1", "fe80::1", "fd00:ec2::254", "fc00::1", "::ffff:10.0.0.1",
])
def test_ssrf_blocks_internal(ip):
    assert _is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "93.184.216.34"])
def test_ssrf_allows_public(ip):
    assert _is_blocked_ip(ip) is False


@pytest.mark.parametrize("url", [
    "http://example.com/a.png",          # https değil
    "https://user:pw@example.com/a.png",  # userinfo
    "ftp://example.com/a.png",
])
def test_ssrf_rejects_bad_urls(url):
    with pytest.raises(ToolError):
        assert_safe_url(url)


def test_ssrf_metadata_host_blocked():
    with pytest.raises(ToolError):
        assert_safe_url("https://169.254.169.254/latest/meta-data/")


def test_data_uri_decode():
    data, mime = decode_data_uri("data:image/png;base64,aGVsbG8=", max_bytes=100)
    assert data == b"hello" and mime == "image/png"


def test_data_uri_size_limit():
    with pytest.raises(ToolError):
        decode_data_uri("data:image/png;base64,aGVsbG8=", max_bytes=2)


# ---- HTML sanitizasyon ----
def test_sanitize_strips_script_and_handlers():
    out = sanitize('<p onclick="x()">hi</p><script>alert(1)</script>'
                   '<a href="javascript:evil()">l</a>')
    assert "<script" not in out and "onclick" not in out and "javascript:" not in out
    assert "hi" in out


def test_render_no_placeholder_leak():
    # SHELL str.format placeholder'larından hiçbiri çıktıda kalmamalı (runtime JS'in meşru
    # {n} gibi ifadelerini yanlış pozitif saymamak için spesifik isimler kontrol edilir).
    p = Project(id=new_project_id(), title="T")
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    for ph in ("{title}", "{screens}", "{css_vars}", "{engine_js}", "{course_json}",
               "{asset_json}", "{base_css}", "{runtime_block}", "{header_title}",
               "{lang}", "{scorm_2004}", "{bg_pattern}", "{custom_css}"):
        assert ph not in html, f"placeholder sızıntısı: {ph}"


def test_render_content_interaction_types():
    # Faz 1b: accordion/tabs/flashcards render + erişilebilir işaretleyiciler
    from core.project import (AccordionScreen, AccordionItem, TabsScreen, TabItem,
                              FlashcardsScreen, Flashcard)
    p = Project(id=new_project_id(), title="1b")
    p.screens = [
        AccordionScreen(id="a", title="SSS", items=[AccordionItem(title="S1", body_html="<p>C1</p>")]),
        TabsScreen(id="t", title="Tabs", tabs=[TabItem(label="L1", body_html="<p>P1</p>"),
                                               TabItem(label="L2", body_html="<p>P2</p>")]),
        FlashcardsScreen(id="f", title="Kart", cards=[Flashcard(front_html="<b>Ön</b>", back_html="<b>Arka</b>")]),
    ]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "<details class=\"acc-item" in html          # native accordion
    assert 'role="tablist"' in html and 'role="tab"' in html  # tabs ARIA
    assert 'role="tabpanel"' in html
    assert 'class="flashcard"' in html and "fc-front" in html and "fc-back" in html


def test_render_scored_interaction_types():
    # Faz 1b dalga 2: matching/sorting (skorlanır) + timeline (içerik)
    from core.project import (MatchingScreen, MatchPair, SortingScreen, SortItem,
                              TimelineScreen, TimelineEvent, QUIZ_TYPES, ScreenType)
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="w2")
    p.screens = [
        MatchingScreen(id="m", title="M", prompt_html="<p>e</p>", points=20,
                       pairs=[MatchPair(id="a", left_html="L1", right_html="R1"),
                              MatchPair(id="b", left_html="L2", right_html="R2")]),
        SortingScreen(id="s", title="S", prompt_html="<p>s</p>", points=15,
                      items=[SortItem(id="x", text_html="1"), SortItem(id="y", text_html="2")]),
        TimelineScreen(id="t", title="T", events=[TimelineEvent(date="2020", title="E1")]),
    ]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'class="match-select"' in html and 'data-pair="a"' in html  # matching select
    assert 'class="sorting ui-stack"' in html and "sort-up" in html    # sorting kontrolleri
    assert 'class="timeline"' in html and "tl-marker" in html          # timeline
    # skor + correct_order config'e düşüyor mu
    assert ScreenType.matching in QUIZ_TYPES and ScreenType.sorting in QUIZ_TYPES
    cfg = _course_config(p)
    smap = {s["id"]: s for s in cfg["screens"]}
    assert smap["s"]["correct_order"] == ["x", "y"]
    assert cfg["total_points"] == 35  # 20 + 15


def test_render_decision_scenario():
    # Faz 12 (G2): dallanan karar senaryosu — skorlanır, durum (skor) taşır, uç düğümde biter
    from core.project import (DecisionScenarioScreen, ScenarioNode, ScenarioChoice,
                              QUIZ_TYPES, ScreenType)
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="g2")
    p.screens = [
        DecisionScenarioScreen(
            id="sc", title="Senaryo", intro_html="<p>Giriş</p>", points=20, pass_score=10,
            nodes=[
                ScenarioNode(id="n1", prompt_html="<p>İlk karar?</p>", choices=[
                    ScenarioChoice(id="a", text_html="İyi", feedback_html="<p>Doğru çünkü…</p>",
                                   score_delta=15, goto_node_id="n2"),
                    ScenarioChoice(id="b", text_html="Kötü", feedback_html="<p>Yanlış çünkü…</p>",
                                   score_delta=-15, goto_node_id="n2"),
                ]),
                ScenarioNode(id="n2", prompt_html="<p>Son karar?</p>", choices=[
                    ScenarioChoice(id="c", text_html="Bildir", feedback_html="<p>İyi.</p>",
                                   score_delta=5, goto_node_id=None),
                    ScenarioChoice(id="d", text_html="Yok say", feedback_html="<p>Kötü.</p>",
                                   score_delta=-5, goto_node_id=None),
                ]),
            ],
        ),
    ]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "data-scenario" in html and 'data-points="20"' in html and 'data-pass="10"' in html
    assert 'data-node="n1"' in html and 'data-goto="n2"' in html  # düğüm + navigasyon
    assert 'data-delta="15"' in html and 'data-delta="-15"' in html  # skor etkisi
    assert "scen-choice" in html and "scen-conseq" in html and "scen-next" in html
    assert "bindScenario" in html  # engine wiring (SHELL/ENGINE_JS gömülü)
    # skorlanır tip + config
    assert ScreenType.decision_scenario in QUIZ_TYPES
    cfg = _course_config(p)
    item = {s["id"]: s for s in cfg["screens"]}["sc"]
    assert item["is_quiz"] and item["points"] == 20 and item["pass_score"] == 10
    assert "feedback" in item and cfg["total_points"] == 20


def test_render_g3_game_and_visual_types():
    # Faz 13 (G3): term_match_race, escape_room, labeled_diagram (skorlu) + data_chart (içerik)
    from core.project import (TermMatchRaceScreen, EscapeRoomScreen, LabeledDiagramScreen,
                              DataChartScreen, QUIZ_TYPES, ScreenType)
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="g3")
    p.screens = [
        TermMatchRaceScreen(id="tmr", title="T", time_limit_sec=30, points=15, pairs=[
            {"id": "a", "term_html": "Phishing", "definition_html": "Kimlik avı"},
            {"id": "b", "term_html": "Ransomware", "definition_html": "Fidye"}]),
        EscapeRoomScreen(id="esc", title="E", lives=2, points=20, puzzles=[
            {"id": "p1", "prompt_html": "<p>?</p>", "accepted": ["2fa"], "hint_html": "<p>h</p>"},
            {"id": "p2", "prompt_html": "<p>?</p>", "accepted": ["443"]}]),
        LabeledDiagramScreen(id="ld", title="L", image_asset_id="img", points=15, labels=[
            {"id": "l1", "text": "Kalp", "x": 300, "y": 400},
            {"id": "l2", "text": "Akciğer", "x": 600, "y": 350}]),
        DataChartScreen(id="dc", title="D", chart_type="bar", data=[
            {"label": "2023", "value": 10}, {"label": "2024", "value": 25}]),
    ]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # term_match_race: süreli eşleştirme
    assert "data-tmr" in html and 'data-time="30"' in html and "bindTermRace" in html
    # escape_room: bulmaca + can
    assert "data-escape" in html and 'data-lives="2"' in html and "esc-life" in html and "bindEscape" in html
    # labeled_diagram: pin + select
    assert "ld-pin" in html and "ld-select" in html and "bindLabeledDiagram" in html
    # data_chart: server-side SVG (skorlanmaz, içerik)
    assert "<svg" in html and "chart-svg" in html
    # skorlu tipler QUIZ_TYPES'da; data_chart DEĞİL
    for t in (ScreenType.term_match_race, ScreenType.escape_room, ScreenType.labeled_diagram):
        assert t in QUIZ_TYPES
    assert ScreenType.data_chart not in QUIZ_TYPES
    cfg = _course_config(p)
    smap = {s["id"]: s for s in cfg["screens"]}
    assert smap["tmr"]["time_limit_sec"] == 30 and smap["esc"]["lives"] == 2
    assert cfg["total_points"] == 50  # 15+20+15, data_chart skorlanmaz
    assert smap["dc"]["is_quiz"] is False


def test_render_faz14_results_poll_compare():
    # Faz 14: results_breakdown (özelleştirilmiş sonuç) + poll + image_compare — hepsi içerik
    from core.project import (ResultsBreakdownScreen, PollScreen, ImageCompareScreen,
                              QUIZ_TYPES, ScreenType)
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="f14")
    p.screens = [
        ResultsBreakdownScreen(id="rb", title="Sonuç", weak_threshold=60, sections=[
            {"title": "Bölüm A", "screen_ids": ["q1", "q2"], "advice_html": "<p>Tekrar et.</p>"},
            {"title": "Bölüm B", "screen_ids": ["q3"]}]),
        PollScreen(id="pl", title="Anket", prompt_html="<p>Görüş?</p>",
                   options=[{"id": "a", "text_html": "X"}, {"id": "b", "text_html": "Y"}],
                   reflection_html="<p>Teşekkürler.</p>"),
        ImageCompareScreen(id="ic", title="Karşılaştır", before_asset_id="b", after_asset_id="a",
                           before_label="Önce", after_label="Sonra"),
    ]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # results_breakdown: bölümler + compute-on-show
    assert "data-results" in html and 'data-screens="q1,q2"' in html and "rb-fill" in html
    assert "renderResultsIfNeeded" in html and "rb-advice" in html
    # poll: seçenek + gönder + yansıma
    assert "data-poll" in html and "poll-submit" in html and "bindPoll" in html
    # image_compare: slider
    assert "data-compare" in html and "ic-range" in html and "bindImageCompare" in html
    # üçü de içerik (skorlanmaz)
    for t in (ScreenType.results_breakdown, ScreenType.poll, ScreenType.image_compare):
        assert t not in QUIZ_TYPES
    cfg = _course_config(p)
    assert all(s["is_quiz"] is False for s in cfg["screens"])
    assert cfg["total_points"] == 0  # hiçbiri skorlanmaz


def test_g1_gamification_hud():
    # Faz 15 (G1): birleşik HUD — seviye (puan→rozet) + can (kalpler), points_var üzerine
    from core.project import GameLevel
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="oyun", scorm_version="2004", points_var="puan",
                lives_var="can", max_lives=3,
                levels=[GameLevel(name="Çırak", min_points=0), GameLevel(name="Usta", min_points=100)],
                screens=[MCQScreen(id="q", title="Q", prompt_html="<p>?</p>",
                                   options=[Choice(id="a", text_html="1", correct=True),
                                            Choice(id="b", text_html="2")])])
    cfg = _course_config(p)
    assert cfg["points_var"] == "puan" and cfg["lives_var"] == "can" and cfg["max_lives"] == 3
    assert cfg["levels"] == [{"name": "Çırak", "min_points": 0}, {"name": "Usta", "min_points": 100}]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'id="levelHud"' in html and 'id="livesHud"' in html
    assert "currentLevel" in html and "updateLevel" in html and "updateLives" in html and "updateHud" in html


def test_faz16_responsive_and_touch():
    # Faz 16: cihaz uyumluluğu — içerik taşma kaydırması + mobil reflow + dokunma sürükleme
    from core.project import ContentSlide, DragDropScreen, DragItem, DropTarget
    p = Project(id=new_project_id(), title="resp", scorm_version="2004", screens=[
        ContentSlide(id="c", title="A", body_html="<p>x</p>"),
        DragDropScreen(id="d", title="D", prompt_html="<p>?</p>",
                       items=[DragItem(id="i1", text_html="X", correct_target_id="t1")],
                       targets=[DropTarget(id="t1", label_html="T")]),
    ])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # içerik taşması kırpılmaz, kaydırılır
    assert "overflow-y:auto;overflow-x:hidden;display:flex" in html
    # mobilde sabit-tuval ölçeklemesi bırakılır → doğal akış reflow
    assert "transform:none!important" in html and 'matchMedia("(max-width:640px)")' in html
    # viewport meta
    assert 'name="viewport"' in html and "width=device-width" in html
    # dokunma sürükle-bırak (HTML5 drag dokunmada çalışmaz)
    assert "touchmove" in html and "elementFromPoint" in html and "touch-action:none" in html
    # tap gecikmesini önle
    assert "touch-action:manipulation" in html


@pytest.mark.asyncio
async def test_discovery_tools_list_screen_types_and_themes():
    # Keşif tool'ları: list_screen_types (26) + list_themes — proje/auth gerektirmez
    from core.project import ScreenType, QUIZ_TYPES
    async with Client(server.mcp) as c:
        names = sorted(t.name for t in await c.list_tools())
        assert "list_screen_types" in names and "list_themes" in names
        st = (await c.call_tool("list_screen_types", {})).data
        assert st["count"] == len(list(ScreenType))
        by = {x["type"]: x for x in st["screen_types"]}
        assert by["decision_scenario"]["scored"] is True and by["content_slide"]["scored"] is False
        assert by["decision_scenario"]["scored"] == (ScreenType.decision_scenario in QUIZ_TYPES)
        th = (await c.call_tool("list_themes", {})).data
        tnames = [t["name"] for t in th["themes"]]
        assert th["count"] >= 12
        for expected in ("editorial", "playground", "boardroom-clinic", "default"):
            assert expected in tnames


def test_w2_game_primitive_specs():
    # W2: 6 mekanik primitif yapılandırma şeması (additive; mevcut 26 tipi etkilemez)
    from core.game_primitives import (
        TimerSpec, ScoreSpec, LivesSpec, HintLadderSpec, ItemBankSpec, BranchGraphSpec,
        PRIMITIVE_KINDS,
    )
    assert set(PRIMITIVE_KINDS) == {
        "timer", "score", "lives", "hint_ladder", "item_bank", "branch_graph"
    }
    t = TimerSpec(id="t", duration_sec=60)
    assert t.kind == "timer" and t.allow_extend is True and t.allow_disable is True  # a11y 2.2.1
    assert ScoreSpec(id="s", streak_step=3, max_multiplier=3).kind == "score"
    assert LivesSpec(id="l", start=3).max is None
    hl = HintLadderSpec(id="h", hints=[{"text": "Alan adına bak", "cost": 5}])
    assert hl.hints[0].text and hl.hints[0].cost == 5
    # parametrik + statik madde aynı bankada
    ib = ItemBankSpec(id="b", items=[
        {"id": "p", "template": "{{a}}+{{b}}", "vars": {"a": {"min": 2, "max": 9}, "b": {"min": 2, "max": 9}},
         "answer": {"op": "add", "operands": ["a", "b"]}},
        {"id": "st", "prompt": "Başkent?", "answer": "Ankara", "distractors": ["İzmir"]},
    ])
    assert ib.items[0].template and ib.items[1].answer == "Ankara"
    bg = BranchGraphSpec(id="g", start="n1", nodes=[
        {"id": "n1", "choices": [{"id": "c", "to": "n2", "condition": {"var": "lvl", "cmp": ">=", "value": 2}}]},
        {"id": "n2", "choices": []},
    ])
    assert bg.nodes[0].choices[0].condition.cmp == ">="


def test_w3_engine_bundle_inlines_cleanly():
    # W3 köprü: components/engine/ → tek JS bundle (ESM-strip, per-modül IIFE, çakışmasız)
    from core.engine_bundle import load_engine_bundle
    b = load_engine_bundle()
    assert "export " not in b  # ESM export sızıntısı yok
    assert "\nimport " not in b and not b.startswith("import ")  # import sızıntısı yok
    assert "window.SCORMGame" in b and "var __E" in b
    # tüm primitif/çekirdek fonksiyonları + kural motoru açık
    for fn in ("createRng", "createEventBus", "createBranchGraph", "createItemBank",
               "createTimer", "createScore", "createLives", "createHintLadder", "attachRules"):
        assert fn in b, f"bundle eksik: {fn}"
    # iki modülde de `const CMP` var → per-modül IIFE ile çakışmamalı (sayım ≥ 2)
    assert b.count("const CMP") >= 2 and b.count("(function(){") >= 10  # her modül + dış sarmal
    assert load_engine_bundle() is b  # lru_cache deterministik


def test_w3_game_rule_schema():
    # W3 kural dili (when/if/then) + oyun tanımı şeması
    from core.game_primitives import GameRule, GameAction, GameDefinition, GameMechanics, ACTION_DOS
    r = GameRule(when="answer.correct", then=[{"do": "score.correct", "points": 10}])
    assert r.when == "answer.correct" and r.then[0].do == "score.correct" and r.then[0].points == 10
    # 'if' alias çalışır
    r2 = GameRule(when="x", **{"if": {"var": "lvl", "cmp": ">=", "value": 2}}, then=[{"do": "lives.lose", "n": 1}])
    assert r2.if_.cmp == ">=" and r2.then[0].do == "lives.lose"
    # her aksiyon do'su şemada
    for do in ACTION_DOS:
        GameAction(do=do)
    # oyun tanımı: mekanik + kural kompozisyonu
    g = GameDefinition(
        mechanics=GameMechanics(score={"id": "s"}, lives={"id": "l", "start": 3}),
        rules=[{"when": "choice.taken", "then": [{"do": "score.add", "value": 5}]}],
        seed="case-2026",
    )
    assert g.mechanics.score.id == "s" and g.rules[0].then[0].value == 5 and g.seed == "case-2026"


def test_review_widget_only_in_preview():
    # 1.1: feedback annotation widget artık mode'dan BAĞIMSIZ `review` bayrağına bağlı —
    # review=False iken markup HTML'de hiç yok (gizli değil); review=True iken var.
    p = Project(id=new_project_id(), title="R")
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    prev = render_html(p, mode="preview", runtime_js="/*rt*/", review=True)
    pkg = render_html(p, mode="package", runtime_js="/*rt*/")
    assert "window.__PREVIEW__ = true;" in prev
    assert "window.__PREVIEW__ = false;" in pkg
    assert 'id="reviewFab"' in prev
    assert 'id="reviewFab"' not in pkg  # paket her zaman review=False (varsayılan)


def test_media_mimes_and_narration():
    # Faz 3: çapraz-MCP medya — genişletilmiş audio/video allowlist + ekran narration
    from auth.ssrf import _mime_allowed
    from core.project import AssetRef
    for ok in ("audio/wav", "audio/ogg", "audio/mp4", "video/webm", "video/mp4", "image/png"):
        assert _mime_allowed(ok), ok
    for bad in ("text/html", "application/x-msdownload", "application/zip"):
        assert not _mime_allowed(bad), bad
    p = Project(id=new_project_id(), title="N")
    p.assets = [AssetRef(id="a1", filename="n.mp3", mime="audio/mpeg", size_bytes=10,
                         sha256="x" * 64, rel_path="assets/n.mp3")]
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>", narration_asset_id="a1")]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert '<audio class="narration"' in html and 'data-asset="a1"' in html


def test_media_module_is_lazy():
    # Faz 4: media modülü import edilmek için ffmpeg gerektirmez (zero-load/opt-in)
    from core import media
    assert hasattr(media, "image_audio_to_video") and hasattr(media, "normalize_audio")
    assert isinstance(media.ffmpeg_available(), bool)
    assert media._ext("a.MP3", "x") == "mp3" and media._ext("noext", "png") == "png"


@pytest.mark.asyncio
async def test_ffmpeg_image_audio_to_video():
    # Faz 4: ffmpeg varsa görsel+ses → geçerli mp4 (yoksa atla)
    import subprocess
    from core import media
    if not media.ffmpeg_available():
        pytest.skip("ffmpeg yok")
    img = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                          "color=c=blue:s=160x120", "-frames:v", "1", "-f", "image2pipe",
                          "-vcodec", "png", "-"], capture_output=True).stdout
    aud = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                          "anullsrc=r=44100:cl=mono", "-t", "1", "-f", "mp3", "-"],
                         capture_output=True).stdout
    out = await media.image_audio_to_video(img, aud, img_ext="png", aud_ext="mp3")
    assert len(out) > 500 and out[4:8] == b"ftyp"  # geçerli mp4


@pytest.mark.asyncio
async def test_feedback_store_flow(tmp_path):
    # Faz 2: store add/list/resolve/count
    from core.store import create_store, Feedback
    from core.project import new_feedback_id
    st = create_store(str(tmp_path / "f.db"), str(tmp_path / "data"))
    await st.init()
    fb = Feedback(id=new_feedback_id(), project_id="p1", screen_id="s1", comment="kısalt")
    await st.add_feedback(fb)
    assert await st.count_open_feedback("p1") == 1
    items = await st.list_feedback("p1")
    assert len(items) == 1 and items[0].comment == "kısalt"
    assert await st.resolve_feedback(fb.id, "p1") is True
    assert await st.count_open_feedback("p1") == 0
    assert await st.resolve_feedback("yok", "p1") is False
    await st.close()


def test_variables_and_conditional_config():
    # Faz 5: değişken/durum + koşullu → course_config + {{var}} interpolasyon işaretleyici
    from core.project import Variable, VarAction, Condition
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="V",
                variables=[Variable(name="score", type="number", default=0)])
    p.screens = [ContentSlide(id="a", title="A", body_html="<p>Skor {{score}}</p>",
                              on_enter=[VarAction(var="score", op="add", value=5)],
                              visible_if=Condition(var="score", cmp=">=", value=10))]
    cfg = _course_config(p)
    assert cfg["variables"] == [{"name": "score", "type": "number", "default": 0}]
    s = cfg["screens"][0]
    assert s["on_enter"] == [{"var": "score", "op": "add", "value": 5}]
    assert s["visible_if"] == {"var": "score", "cmp": ">=", "value": 10}
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "{{score}}" in html  # literal kalır; runtime interpolate eder


def test_gamification_config():
    # Faz 6: timer + on_correct + points HUD config'e düşüyor
    from core.project import Variable, VarAction, ContentSlide as CS
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="G",
                variables=[Variable(name="score", default=0)], points_var="score")
    p.screens = [
        MCQScreen(id="q", title="Q", prompt_html="<p>?</p>", points=10,
                  options=[Choice(id="a", text_html="A", correct=True), Choice(id="b", text_html="B")],
                  on_correct=[VarAction(var="score", op="add", value=10)]),
        CS(id="t", title="T", body_html="<p>x</p>", timer_sec=30, timeout_goto="q"),
    ]
    cfg = _course_config(p)
    assert cfg["points_var"] == "score"
    sm = {s["id"]: s for s in cfg["screens"]}
    assert sm["q"]["on_correct"] == [{"var": "score", "op": "add", "value": 10}]
    assert sm["t"]["timer_sec"] == 30 and sm["t"]["timeout_goto"] == "q"
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'id="timerHud"' in html and 'id="pointsHud"' in html


def test_lottie_lazy_zero_load():
    # Faz 7: lottie lib YALNIZ animasyon kullanılırsa (opt-in/zero-load)
    from core.project import LottieScreen, AssetRef
    from components.renderer import extra_runtime_files
    # animasyonsuz kurs → lottie YOK
    p0 = Project(id=new_project_id(), title="z")
    p0.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    h0 = render_html(p0, mode="package", runtime_js="/*rt*/")
    # zero-load = heavy LIB (164KB JS) yok; küçük .lottie CSS class'ı paylaşımlı bundle'da olabilir
    assert "data-lottie-asset" not in h0
    assert "runtime/lottie_light.min.js" not in h0
    assert extra_runtime_files(p0) == []
    # lottie kursu → lib referansı + extra file
    p1 = Project(id=new_project_id(), title="l")
    p1.assets = [AssetRef(id="a", filename="a.json", mime="application/json", size_bytes=2,
                          sha256="x" * 64, rel_path="assets/a.json")]
    p1.screens = [LottieScreen(id="ls", title="A", lottie_asset_id="a")]
    h1 = render_html(p1, mode="package", runtime_js="/*rt*/")
    assert "data-lottie-asset" in h1 and "runtime/lottie_light.min.js" in h1
    ex = extra_runtime_files(p1)
    assert len(ex) == 1 and ex[0][0] == "runtime/lottie_light.min.js"


def test_simulation_screen():
    # Faz 8: çok-adımlı simülasyon (Uygula) — render + skor config + QUIZ_TYPES
    from core.project import (SimulationScreen, SimStep, HotspotRegion, AssetRef,
                              QUIZ_TYPES, ScreenType)
    from components.renderer import _course_config
    assert ScreenType.simulation in QUIZ_TYPES
    p = Project(id=new_project_id(), title="S")
    p.assets = [AssetRef(id="i", filename="i.png", mime="image/png", size_bytes=2,
                         sha256="x" * 64, rel_path="assets/i.png")]
    p.screens = [SimulationScreen(id="sm", title="Sim", prompt_html="<p>…</p>", points=20,
        steps=[SimStep(image_asset_id="i", instruction_html="<p>Adım 1</p>", hint_html="<p>ipucu</p>",
                       regions=[HotspotRegion(id="r", shape="rect", coords=[10, 10, 50, 50], correct=True)]),
               SimStep(image_asset_id="i", instruction_html="<p>Adım 2</p>",
                       regions=[HotspotRegion(id="r2", shape="rect", coords=[5, 5, 40, 40], correct=True)])])]
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'data-steps="2"' in html and "sim-region" in html and 'data-correct="1"' in html
    assert _course_config(p)["screens"][0]["points"] == 20
    # input adımı (Wooclap deseni — yazma)
    p2 = Project(id=new_project_id(), title="S2")
    p2.assets = [AssetRef(id="i", filename="i.png", mime="image/png", size_bytes=2, sha256="x" * 64, rel_path="assets/i.png")]
    p2.screens = [SimulationScreen(id="s2", title="Sim", points=10,
        steps=[SimStep(image_asset_id="i", instruction_html="<p>Yaz</p>",
                       input_accepted=["merhaba", "selam"], input_label="Cevap")])]
    h2 = render_html(p2, mode="preview", runtime_js="/*rt*/")
    assert 'class="sim-input"' in h2 and "data-accepted" in h2 and "merhaba" in h2


@pytest.mark.asyncio
async def test_expired_preview_cleanup(tmp_path):
    # O2 (Antigravity review): süresi geçmiş preview DB satırı temizlenebilir
    from core.store import create_store
    from core.project import utcnow
    st = create_store(str(tmp_path / "p.db"), str(tmp_path / "data"))
    await st.init()
    await st.put_preview("old", "p1", -10)   # süresi geçmiş
    await st.put_preview("fresh", "p1", 3600)  # geçerli
    exp = await st.expired_previews(utcnow())
    assert [p.token for p in exp] == ["old"]
    await st.delete_preview("old")
    assert await st.get_preview("old") is None
    assert await st.get_preview("fresh") is not None
    await st.close()


# ---- fast-path / idempotency ----
@pytest.mark.asyncio
async def test_build_fast_path_returns_done_sync():
    async with Client(server.mcp) as c:
        proj = await c.call_tool("create_project", {"title": "FP"})
        pid = proj.data.project_id
        await c.call_tool("add_screen", {"project_id": pid,
                                         "screen": {"type": "title_slide", "title": "T"}})
        b1 = await c.call_tool("build_package", {"project_id": pid})
        assert b1.data.status == "done"  # küçük kurs senkron
        # idempotent: değişmediyse aynı job
        b2 = await c.call_tool("build_package", {"project_id": pid})
        assert b2.data.job_id == b1.data.job_id


# ---- kota ----
@pytest.mark.asyncio
async def test_validation_error_on_empty_project():
    async with Client(server.mcp) as c:
        proj = await c.call_tool("create_project", {"title": "Boş"})
        pid = proj.data.project_id
        with pytest.raises(Exception) as ei:
            await c.call_tool("build_package", {"project_id": pid})
        assert "validation_error" in str(ei.value)


# ---- Faz 9: sabit-sahne/timeline modelleri ----
def test_faz9_models_defaults_and_overrides():
    from core.project import CourseSpec
    spec = CourseSpec.model_validate({
        "title": "T", "scorm_version": "2004",
        "screens": [
            {"type": "content_slide", "title": "A", "body_html": "<p>x</p>",
             "narration_text": "Merhaba", "reveal": "click", "animation": "zoom",
             "block_sec": 1.5, "lock_until_complete": True},
            {"type": "mcq", "title": "Q", "prompt_html": "<p>?</p>",
             "options": [{"id": "a", "text_html": "1", "correct": True},
                         {"id": "b", "text_html": "2"}]},
        ],
    })
    assert spec.layout_mode == "stage"            # yeni varsayılan
    s0 = spec.screens[0]
    assert s0.narration_text == "Merhaba"
    assert s0.reveal == "click" and s0.animation == "zoom"
    assert s0.block_sec == 1.5 and s0.lock_until_complete is True
    # varsayılanlar (override yok)
    assert spec.screens[1].reveal is None and spec.screens[1].lock_until_complete is False
    # Project de layout_mode taşır
    p = Project(id=new_project_id(), title="T", layout_mode="flow")
    assert p.layout_mode == "flow"


def test_faz9_renderer_wraps_blocks_and_config():
    from core.project import Project, new_project_id, ContentSlide
    p = Project(
        id=new_project_id(), title="T", scorm_version="2004", layout_mode="stage",
        screens=[
            ContentSlide(id="c1", title="Başlık", body_html="<p>bir</p><p>iki</p>",
                         narration_text="Anlatım metni", animation="fade"),
            MCQScreen(id="q1", title="Q", prompt_html="<p>?</p>",
                      options=[Choice(id="a", text_html="1", correct=True),
                               Choice(id="b", text_html="2")]),
        ],
    )
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # blok sarma: başlık(0) + 2 paragraf(1,2)
    assert 'class="tl-block"' in html
    assert 'data-block="0"' in html and 'data-block="2"' in html
    # reveal türetimi
    assert 'data-reveal="auto"' in html   # content_slide
    assert 'data-reveal="none"' in html   # mcq
    assert 'data-anim="fade"' in html
    # altyazı
    assert 'class="cc-text"' in html and "Anlatım metni" in html
    # course_json'da layout_mode
    assert '"layout_mode": "stage"' in html


def test_faz9_shell_has_player_and_stage():
    from core.project import Project, new_project_id, ContentSlide
    p = Project(id=new_project_id(), title="T", scorm_version="2004",
                screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'data-layout="stage"' in html            # body layout attr
    assert 'class="stage-frame"' in html            # sabit 16:9 çerçeve
    assert 'id="seekbar"' in html                   # player seekbar
    assert 'id="btnPlay"' in html                   # oynat/duraklat
    assert 'id="btnCc"' in html                     # altyazı toggle
    assert 'id="btnMenu"' in html                   # slayt menüsü
    assert 'id="btnReplay"' in html                 # replay
    assert "distributeCues" in html                 # timeline engine gömülü
    assert "fitStage" in html                       # stage scaler gömülü


def test_faz9_flow_mode_opts_out():
    from core.project import Project, new_project_id, ContentSlide
    p = Project(id=new_project_id(), title="T", scorm_version="2004", layout_mode="flow",
                screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'data-layout="flow"' in html


def test_faz91_section_and_stage_size():
    from core.project import Project, new_project_id, ContentSlide
    from components.renderer import render_html, _course_config
    p = Project(id=new_project_id(), title="T", scorm_version="2004",
                stage_width=1280, stage_height=720,
                screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>", section="Bölüm 1")])
    cfg = _course_config(p)
    assert cfg["stage_width"] == 1280 and cfg["stage_height"] == 720
    assert cfg["screens"][0]["section"] == "Bölüm 1"
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "--stage-w:1280px" in html and "--stage-h:720px" in html
    assert '"stage_width": 1280' in html


def test_faz91_icons_no_emoji_and_sections():
    import re
    from core.project import Project, new_project_id, ContentSlide
    from components.renderer import render_html
    p = Project(id=new_project_id(), title="T", scorm_version="2004", points_var="p",
                screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>", section="Giriş"),
                         MCQScreen(id="q", title="Q", prompt_html="<p>?</p>",
                                   options=[Choice(id="a", text_html="1", correct=True),
                                            Choice(id="b", text_html="2")])])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # hiç emoji yok
    emo = re.findall(r'[\U0001F300-\U0001FAFF☀-➿★✓▶⏸☰↻🔊🔇💬]', html)
    assert not emo, f"emoji sızıntısı: {set(emo)}"
    # inline SVG ikonlar var (player + toggle)
    assert '<svg class="ic"' in html
    assert 'id="btnPlay"' in html and 'class="ic-a"' in html and 'class="ic-b"' in html
    # mobil media query + menu-section CSS
    assert "@media(max-width:640px)" in html and ".menu-section" in html


# ---- W3b: kompozisyonel oyun (game) ekranı ----
def _game_screen(**over):
    from core.project import GameScreen
    base = dict(
        id="g1", title="Oyun",
        nodes=[
            {"id": "n1", "content_html": "<p>Başla</p>", "choices": [
                {"id": "a", "text_html": "Doğru", "to": "n2",
                 "on_choose": [{"do": "score.correct", "points": 10}]},
                {"id": "b", "text_html": "Yanlış", "to": None,
                 "on_choose": [{"do": "lives.lose", "n": 1}]},
            ]},
            {"id": "n2", "content_html": "<p>İkinci</p>", "choices": [
                {"id": "c", "text_html": "Bitir", "to": None}]},
        ],
        mechanics={"score": {"id": "sc"}, "lives": {"id": "lv", "start": 3}},
        rules=[{"when": "choice.taken", "then": [{"do": "var.add", "var": "k", "value": 1}]}],
        points=30, pass_score=20,
    )
    base.update(over)
    return GameScreen(**base)


def test_w3b_game_renders_and_inlines_engine_bundle_only_when_present():
    from core.project import ScreenType, QUIZ_TYPES
    assert ScreenType.game in QUIZ_TYPES  # skorlanır
    g = _game_screen()
    p = Project(id=new_project_id(), title="K", screens=[g])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'data-type="game"' in html
    # bindGame kaynağı 'window.SCORMGame'i string olarak içerir (her zaman) → bundle'a-ÖZGÜ token kullan
    assert "/* engine/rng.js */" in html
    assert "window.SCORMGame = __E" in html       # bundle gerçekten inline (lazy)
    assert "function bindGame" in html
    assert 'data-node="n1"' in html and 'data-choice="a"' in html
    # game ekranı OLMAYAN kursta bundle inline EDİLMEZ (zero-load)
    p2 = Project(id=new_project_id(), title="K2",
                 screens=[ContentSlide(id="c", title="x", body_html="<p>y</p>")])
    html2 = render_html(p2, mode="preview", runtime_js="/*rt*/")
    assert "/* engine/rng.js */" not in html2


def test_w3b_game_config_serializes_logic_and_mechanics():
    from components.renderer import _course_config
    p = Project(id=new_project_id(), title="K", screens=[_game_screen()])
    cfg = _course_config(p)
    item = [s for s in cfg["screens"] if s["type"] == "game"][0]
    gc = item["game"]
    assert set(gc["logic"].keys()) == {"n1/a", "n1/b", "n2/c"}
    assert gc["logic"]["n1/a"]["to"] == "n2"
    assert gc["mechanics"]["score"] and gc["mechanics"]["timer"] is None
    assert gc["rules"][0]["when"] == "choice.taken"
    assert item["points"] == 30 and cfg["total_points"] == 30


def test_w3b_game_validator_rejects_bad_target_and_a11y_timer_gate():
    from core.validator import validate_project
    # geçersiz `to` hedefi → hata
    bad = _game_screen(nodes=[
        {"id": "n1", "content_html": "<p>x</p>", "choices": [
            {"id": "a", "text_html": "git", "to": "YOK"}]}])
    p = Project(id=new_project_id(), title="K", screens=[bad])
    errs = validate_project(p)
    assert any("seçim hedefi" in e.message for e in errs)
    # a11y süre kapısı: timer hem extend hem disable kapalıysa → hata (WCAG 2.2.1)
    g2 = _game_screen(mechanics={
        "score": {"id": "sc"},
        "timer": {"id": "t", "duration_sec": 60, "allow_extend": False, "allow_disable": False}})
    p2 = Project(id=new_project_id(), title="K2", screens=[g2])
    assert any("2.2.1" in e.message for e in validate_project(p2))
    # geçerli oyun → temiz
    p3 = Project(id=new_project_id(), title="K3", screens=[_game_screen()])
    assert validate_project(p3) == []


def test_w3b_game_hud_hidden_chip_actually_hidden_by_css():
    """Bug: .game-hud çipleri (score/lives/timer) HER ZAMAN 'hidden' özniteliğiyle statik
    render edilir (bindGame mevcut mekaniğe göre açar — progresif geliştirme, bkz. _r_game).
    Ama .ui-chip{display:inline-flex} yazar stil sayfasında olduğundan, özgüllükten BAĞIMSIZ
    UA'nın öntanımlı [hidden]{display:none} kuralını ezer (cascade: author > user-agent) —
    açık bir .ui-chip[hidden]{display:none} karşı-kuralı olmadıkça 'gizli' render edilen çip
    tarayıcıda GÖRÜNÜR kalır. Süresiz oyunda (mechanics.timer=None) bu yüzden boş '⏱ 0' çipi
    hiç kapanmadan görünüyordu (Playwright reprosu ile doğrulandı)."""
    import re

    p = Project(id=new_project_id(), title="K", screens=[_game_screen()])  # timer:None (varsayılan)
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    # statik markup: çip yine 'hidden' ile render edilir (progresif geliştirme sözleşmesi bozulmaz)
    assert '<span class="game-hud-timer ui-chip" hidden>' in html
    assert '<span class="game-hud-score ui-chip" hidden>' in html
    assert '<span class="game-hud-lives ui-chip" hidden>' in html
    # KÖK NEDEN düzeltmesi: .ui-chip[hidden] için display:none karşı-kuralı CSS'te olmalı,
    # yoksa yukarıdaki 'hidden' özniteliği tarayıcıda etkisiz kalır (author CSS UA'yı ezer)
    assert re.search(r"\.ui-chip\[hidden\]\s*\{[^}]*display\s*:\s*none", html)


# ---- W4a: adaptif katman (Elo-vs-BKT tahminci + akış/ZPD seçici) ----
def test_w4a_adaptive_specs_discriminate_by_strategy():
    from core.game_primitives import EloSpec, BktSpec, AdaptiveSpec, ADAPTIVE_STRATEGIES
    from pydantic import TypeAdapter
    assert ADAPTIVE_STRATEGIES == ("elo", "bkt")
    ad = TypeAdapter(AdaptiveSpec)
    e = ad.validate_python({"strategy": "elo", "ability": 1.0, "k": 0.3})
    assert isinstance(e, EloSpec) and e.ability == 1.0
    b = ad.validate_python({"strategy": "bkt", "p_init": 0.3})
    assert isinstance(b, BktSpec) and b.p_init == 0.3
    # parametre sınırları (olasılıklar [0,1], k>0)
    import pytest as _pt
    from pydantic import ValidationError
    with _pt.raises(ValidationError):
        BktSpec(p_slip=1.5)
    with _pt.raises(ValidationError):
        EloSpec(k=0)


def test_w4a_engine_bundle_inlines_adaptive_module():
    from core.engine_bundle import load_engine_bundle
    b = load_engine_bundle()
    # adaptif modül bundle'a dahil + export'lar window.SCORMGame'e açık
    assert "/* engine/adaptive.js */" in b
    for fn in ("createElo", "createBkt", "createEstimator", "pickByTargetSuccess"):
        assert f"__E.{fn} = {fn}" in b


# ---- W4b: adaptif pratik ekranı ----
def _adaptive_screen(**over):
    from core.project import AdaptivePracticeScreen
    base = dict(
        id="ap1", title="Pratik",
        items=[
            {"id": "i1", "prompt_html": "<p>kolay</p>", "difficulty": -2.0,
             "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]},
            {"id": "i2", "prompt_html": "<p>orta</p>", "difficulty": 0.0,
             "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]},
            {"id": "i3", "prompt_html": "<p>zor</p>", "difficulty": 2.0,
             "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]},
        ],
        adaptive={"strategy": "elo", "ability": 0.0},
        target_success=0.7, points=20,
    )
    base.update(over)
    return AdaptivePracticeScreen(**base)


def test_w4b_adaptive_renders_and_serializes_difficulties():
    from core.project import ScreenType, QUIZ_TYPES
    from components.renderer import _course_config
    assert ScreenType.adaptive_practice in QUIZ_TYPES
    p = Project(id=new_project_id(), title="K", screens=[_adaptive_screen()])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'data-type="adaptive_practice"' in html
    assert "/* engine/rng.js */" in html and "function bindAdaptive" in html
    assert 'data-difficulty="-2.0"' in html and 'data-item="i1"' in html
    cfg = _course_config(p)
    item = [s for s in cfg["screens"] if s["type"] == "adaptive_practice"][0]
    ad = item["adaptive"]
    assert ad["adaptive"]["strategy"] == "elo"
    assert ad["items"]["i3"]["difficulty"] == 2.0 and ad["items"]["i1"]["correct"] == ["a"]
    assert item["points"] == 20 and cfg["total_points"] == 20


def test_w4b_adaptive_validator_requires_correct_option_and_bounds():
    from core.validator import validate_project
    # doğru seçeneği olmayan öğe → hata
    bad = _adaptive_screen(items=[
        {"id": "i1", "prompt_html": "<p>x</p>", "difficulty": 0.0,
         "options": [{"id": "a", "text_html": "x"}, {"id": "b", "text_html": "y"}]},
        {"id": "i2", "prompt_html": "<p>y</p>", "difficulty": 1.0,
         "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]},
        {"id": "i3", "prompt_html": "<p>z</p>", "difficulty": 2.0,
         "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]},
    ])
    p = Project(id=new_project_id(), title="K", screens=[bad])
    assert any("doğru seçenek" in e.message for e in validate_project(p))
    # max_items > öğe sayısı → hata
    p2 = Project(id=new_project_id(), title="K2", screens=[_adaptive_screen(max_items=99)])
    assert any("max_items" in e.message for e in validate_project(p2))
    # geçerli → temiz
    p3 = Project(id=new_project_id(), title="K3", screens=[_adaptive_screen()])
    assert validate_project(p3) == []


# ---- W5a: xAPI/cmi5 telemetri (ifade modeli + builder) ----
def test_w5a_xapi_config_defaults_and_modes():
    from core.game_primitives import XapiConfig, XAPI_VERB_KEYS
    c = XapiConfig()
    assert c.enabled is False and c.mode == "cmi5"  # varsayılan kapalı + cmi5
    assert c.activity_base.startswith("https://")
    ex = XapiConfig(enabled=True, mode="explicit", endpoint="https://lrs.example/xapi")
    assert ex.mode == "explicit" and ex.endpoint.endswith("/xapi")
    import pytest as _pt
    from pydantic import ValidationError
    with _pt.raises(ValidationError):
        XapiConfig(mode="invalid")
    assert "answered" in XAPI_VERB_KEYS and "passed" in XAPI_VERB_KEYS


def test_w5a_engine_bundle_inlines_xapi_module():
    from core.engine_bundle import load_engine_bundle
    b = load_engine_bundle()
    assert "/* engine/xapi.js */" in b
    for fn in ("verb", "activity", "result", "statement", "fromEngineEvent"):
        assert f"__E.{fn} = {fn}" in b
    assert "__E.XAPI_VERBS = XAPI_VERBS" in b


# ---- W5b: xAPI telemetri runtime bağlama (kurs düzeyi config + forwarder) ----
def test_w5b_xapi_config_serializes_and_inlines_only_when_enabled():
    from core.game_primitives import XapiConfig
    from components.renderer import _course_config
    scr = [ContentSlide(id="c", title="A", body_html="<p>x</p>")]
    # AÇIK → config'e düşer + bundle inline + forwarder
    on = Project(id=new_project_id(), title="K", screens=scr, xapi=XapiConfig(enabled=True, mode="cmi5"))
    cfg = _course_config(on)
    assert cfg["xapi"]["enabled"] is True and cfg["xapi"]["mode"] == "cmi5"
    html = render_html(on, mode="preview", runtime_js="/*rt*/")
    assert "/* engine/xapi.js */" in html and "var XAPI=(function" in html
    assert "SCORMGame.parseLaunch" in html
    # KAPALI (varsayılan) → config'te xapi YOK + bundle inline EDİLMEZ (zero-load); forwarder yine var ama no-op
    off = Project(id=new_project_id(), title="K2", screens=scr)
    cfg2 = _course_config(off)
    assert "xapi" not in cfg2
    html2 = render_html(off, mode="preview", runtime_js="/*rt*/")
    assert "/* engine/xapi.js */" not in html2 and "var XAPI=(function" in html2


def test_w5b_build_from_spec_carries_xapi(tmp_path):
    # CourseSpec.xapi → Project.xapi aktarımı (build_from_spec)
    from core.project import CourseSpec, Project
    spec = CourseSpec(title="K", screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>")],
                      xapi={"enabled": True, "mode": "explicit", "endpoint": "https://lrs.example/xapi"})
    assert spec.xapi.enabled and spec.xapi.endpoint.endswith("/xapi")
    # Project'e taşındığında da geçerli
    p = Project(id=new_project_id(), title="K", screens=list(spec.screens), xapi=spec.xapi)
    assert p.xapi.mode == "explicit"


# ---- S7 (2.3): CourseMetadata (LOM) modeli ----
def test_s7_course_metadata_defaults_and_full():
    from core.project import CourseMetadata
    m = CourseMetadata()
    assert m.description is None and m.keywords == [] and m.intended_audience is None
    assert m.typical_learning_time is None
    full = CourseMetadata(description="Açıklama", keywords=["a", "b"],
                          intended_audience="Yeni başlayanlar", typical_learning_time="PT1H30M")
    assert full.keywords == ["a", "b"] and full.typical_learning_time == "PT1H30M"


@pytest.mark.parametrize("good", ["PT1H30M", "P1D", "PT45M", "P1Y2M3DT4H5M6S", "PT0.5S"])
def test_s7_typical_learning_time_accepts_iso8601(good):
    from core.project import CourseMetadata
    assert CourseMetadata(typical_learning_time=good).typical_learning_time == good


@pytest.mark.parametrize("bad", ["1h30m", "P", "PT", "90 minutes", "1:30", ""])
def test_s7_typical_learning_time_rejects_non_iso8601(bad):
    from core.project import CourseMetadata
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CourseMetadata(typical_learning_time=bad)


def test_s7_build_from_spec_carries_metadata():
    # CourseSpec.metadata → Project.metadata aktarımı (build_from_spec, additive/opsiyonel)
    from core.project import CourseSpec, CourseMetadata, Project
    spec = CourseSpec(title="K", screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>")],
                      metadata={"description": "D", "keywords": ["k1"],
                                "typical_learning_time": "PT20M"})
    assert isinstance(spec.metadata, CourseMetadata) and spec.metadata.description == "D"
    p = Project(id=new_project_id(), title="K", screens=list(spec.screens), metadata=spec.metadata)
    assert p.metadata.keywords == ["k1"] and p.metadata.typical_learning_time == "PT20M"
    # metadata verilmezse None (additive, geriye dönük uyumlu)
    spec2 = CourseSpec(title="K2", screens=[ContentSlide(id="c", title="A", body_html="<p>x</p>")])
    assert spec2.metadata is None
    p2 = Project(id=new_project_id(), title="K2", screens=list(spec2.screens))
    assert p2.metadata is None


# ---- W6: oyun anti-slop kalite kapısı ----
def test_w6_antislop_catches_structural_errors_and_pedagogical_warns():
    from core.project import GameScreen, AdaptivePracticeScreen
    from core.antislop import lint_course, lint_errors
    bad = GameScreen(
        id="g", title="Kötü",
        mechanics={"score": {"id": "sc"}, "hints": {"id": "h", "hints": [{"text": "ip", "cost": 0}]}},
        nodes=[
            {"id": "n1", "content_html": "<p>x</p>", "choices": [
                {"id": "a", "text_html": "A", "to": "n2"},
                {"id": "b", "text_html": "B", "to": "n2"}]},  # sahte seçim (özdeş sonuç)
            {"id": "n2", "content_html": "<p>y</p>", "choices": [{"id": "c", "text_html": "son", "to": None}]},
            {"id": "orphan", "content_html": "<p>ölü</p>", "choices": [{"id": "d", "text_html": "x", "to": None}]},
        ], rules=[])  # skor var ama hiç değişmiyor → süs
    p = Project(id=new_project_id(), title="K", screens=[bad])
    codes = {i.code for i in lint_course(p)}
    assert {"unreachable_node", "fake_choice", "decorative_score", "free_hints"} <= codes
    # ERROR alt-kümesi yalnız yapısal bug'lar
    ecodes = {i.code for i in lint_errors(p)}
    assert ecodes == {"unreachable_node", "fake_choice"}
    # adaptif kokular
    ad = AdaptivePracticeScreen(id="ap", title="K", adaptive={"strategy": "elo"},
        items=[{"id": f"i{k}", "prompt_html": "<p>q</p>", "difficulty": 0.1,
                "options": [{"id": "a", "text_html": "x", "correct": True}, {"id": "b", "text_html": "y"}]}
               for k in range(3)])
    p2 = Project(id=new_project_id(), title="K2", screens=[ad])
    acodes = {i.code for i in lint_course(p2)}
    assert {"narrow_difficulty", "few_items", "item_without_explanation"} <= acodes


def test_w6_antislop_errors_block_validate_project():
    from core.project import GameScreen
    from core.validator import validate_project
    bad = GameScreen(id="g", title="K", mechanics={},
        nodes=[
            {"id": "n1", "content_html": "<p>x</p>", "choices": [{"id": "a", "text_html": "A", "to": None}]},
            {"id": "dead", "content_html": "<p>ölü</p>", "choices": [{"id": "b", "text_html": "B", "to": None}]},
        ])
    p = Project(id=new_project_id(), title="K", screens=[bad])
    msgs = " ".join(e.message for e in validate_project(p))
    assert "Ulaşılamaz" in msgs  # anti-slop ERROR validate'i bloklar


def test_w6_clean_game_passes_lint():
    from core.project import GameScreen, ContentSlide, ContentBlock
    from core.antislop import lint_course
    # ulaşılabilir + gerçek (farklı) seçimler + skor aksiyonlu + ceza seçiminde gerekçe + gerçek feedback
    # (feedback şema varsayılanında bırakılırsa W9 P1 B3 kuralı ("default_feedback") tetiklenir —
    # burada gerçekçi bir feedback veriyoruz çünkü bu test "temiz" bir kursu temsil etmeli).
    # E1 (#110): skorlu oyun artık açık kanıt beyanı ister (K1/T1) → artefaktlı kanıt ekranı +
    # evidence_screen_ids beyanı olmadan "temiz kurs" sayılmaz.
    ev = ContentSlide(id="vaka", title="Vaka artefaktı: kararların dayandığı kanıt",
                      blocks=[ContentBlock(asset_id="a1", caption="İncelenen vaka ekran görüntüsü")])
    g = GameScreen(id="g", title="Temiz", mechanics={"score": {"id": "sc"}, "lives": {"id": "lv", "start": 3}},
        evidence_screen_ids=["vaka"],
        feedback={"correct_html": "Kazandın — kararların skor mekaniğine gerçekten bağlıydı.",
                  "incorrect_html": "Canların bitti — hangi seçimlerin can kaybettirdiğini tekrar incele."},
        nodes=[
            {"id": "n1", "content_html": "<p>x</p>", "choices": [
                {"id": "a", "text_html": "Doğru", "to": "n2", "on_choose": [{"do": "score.correct", "points": 10}]},
                {"id": "b", "text_html": "Yanlış", "to": None, "feedback_html": "<p>Çünkü …</p>",
                 "on_choose": [{"do": "lives.lose", "n": 1}]}]},
            {"id": "n2", "content_html": "<p>y</p>", "choices": [{"id": "c", "text_html": "Bitir", "to": None}]},
        ])
    p = Project(id=new_project_id(), title="K", screens=[ev, g])
    assert lint_course(p) == []


# ---- W8: QTI 2.1 dışa aktarım ----
def test_w8_qti_export_mcq_tf_fill():
    from core.project import (MCQScreen, Choice, TrueFalseScreen, FillBlankScreen, Blank,
                              ContentSlide)
    from core.qti import export_qti_items, QTI_NS
    from lxml import etree
    p = Project(id=new_project_id(), title="K", screens=[
        ContentSlide(id="c", title="x", body_html="<p>y</p>"),  # QTI'a girmez (atlanmalı)
        MCQScreen(id="q1", title="Q", prompt_html="<p>2+2?</p>",
                  options=[Choice(id="a", text_html="4", correct=True), Choice(id="b", text_html="5")]),
        TrueFalseScreen(id="q2", title="TF", prompt_html="<p>?</p>", correct=False),
        FillBlankScreen(id="q3", title="FB", prompt_html="<p>__?</p>",
                        blanks=[Blank(id="b1", accepted=["Ankara", "ankara"])]),
    ])
    items = dict(export_qti_items(p))
    # content_slide atlandı; 3 quiz dışa aktarıldı
    assert set(items.keys()) == {"qti/q1.xml", "qti/q2.xml", "qti/q3.xml"}
    ns = {"q": QTI_NS}
    mcq = etree.fromstring(items["qti/q1.xml"].encode())
    assert mcq.get("identifier") == "item-q1"
    assert [v.text for v in mcq.findall(".//q:correctResponse/q:value", ns)] == ["a"]
    assert mcq.find(".//q:choiceInteraction", ns) is not None
    tf = etree.fromstring(items["qti/q2.xml"].encode())
    assert [v.text for v in tf.findall(".//q:correctResponse/q:value", ns)] == ["false"]
    fb = etree.fromstring(items["qti/q3.xml"].encode())
    assert fb.find(".//q:textEntryInteraction", ns) is not None
    assert [v.text for v in fb.findall(".//q:correctResponse/q:value", ns)] == ["Ankara"]


@pytest.mark.asyncio
async def test_w8_export_qti_tool():
    async with Client(server.mcp) as c:
        # önce projeyi spec ile kur
        spec = {"title": "QTI", "screens": [
            {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>?</p>",
             "options": [{"id": "a", "text_html": "1", "correct": True}, {"id": "b", "text_html": "2"}]},
            {"type": "title_slide", "id": "t", "title": "T"},
        ]}
        res = await c.call_tool("build_from_spec", {"spec": spec})
        pid = res.data.project_id
        out = await c.call_tool("export_qti", {"project_id": pid})
    assert out.data["count"] == 1  # yalnız mcq
    assert out.data["items"][0]["filename"] == "qti/q1.xml"
    assert "imsqti_v2p1" in out.data["items"][0]["xml"]


def test_w9_alt_text_fields_optional_and_backward_compatible():
    """Yeni alt-text alanları opsiyonel — eski (alt'sız) spec'ler değişmeden validate olmalı."""
    from core.project import HotspotScreen, LabeledDiagramScreen, TimelineEvent, AccordionItem

    # Eski stil (alt YOK) — kırılmamalı
    h = HotspotScreen(id="h", title="T", prompt_html="<p>x</p>", image_asset_id="a1",
                       regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    assert h.image_alt is None

    # Yeni stil (alt VAR) — kabul edilmeli
    h2 = HotspotScreen(id="h2", title="T", prompt_html="<p>x</p>", image_asset_id="a1", image_alt="Kontrol paneli ekran görüntüsü",
                        regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    assert h2.image_alt == "Kontrol paneli ekran görüntüsü"

    ld = LabeledDiagramScreen(id="ld", title="T", image_asset_id="a1", image_alt="Kalp anatomisi diyagramı",
                               labels=[{"id": "l1", "x": 10, "y": 10, "text": "Sol karıncık"},
                                       {"id": "l2", "x": 20, "y": 20, "text": "Sağ karıncık"}])
    assert ld.image_alt == "Kalp anatomisi diyagramı"

    ev = TimelineEvent(date="2020", title="Olay", image_asset_id="a1", image_alt="Fotoğraf")
    assert ev.image_alt == "Fotoğraf"

    it = AccordionItem(title="Panel", body_html="<p>x</p>", image_asset_id="a1", image_alt="Şema")
    assert it.image_alt == "Şema"


def test_w9_renderer_emits_real_alt_text():
    """Alt-text alanı doluysa <img alt="..."> gerçek metni taşımalı, alt="" değil."""
    from components.renderer import render_html
    from core.project import Project, HotspotScreen, LabeledDiagramScreen

    h = HotspotScreen(id="h", title="T", prompt_html="<p>x</p>", image_asset_id="a1",
                       image_alt="Kontrol paneli ekran görüntüsü",
                       regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    p = Project(id=new_project_id(), title="K", screens=[h])
    html = render_html(p, mode="package", runtime_js="")
    assert 'alt="Kontrol paneli ekran görüntüsü"' in html

    ld = LabeledDiagramScreen(id="ld", title="T", image_asset_id="a1", image_alt="Kalp anatomisi",
                               labels=[{"id": "l1", "x": 10, "y": 10, "text": "Sol"},
                                       {"id": "l2", "x": 20, "y": 20, "text": "Sağ"}])
    p2 = Project(id=new_project_id(), title="K2", screens=[ld])
    html2 = render_html(p2, mode="package", runtime_js="")
    assert 'alt="Kalp anatomisi"' in html2

    # alt verilmezse boş string'e düşer (kırılmaz), ama hardcoded değil — alan tabanlı
    h3 = HotspotScreen(id="h3", title="T", prompt_html="<p>x</p>", image_asset_id="a1",
                        regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    p3 = Project(id=new_project_id(), title="K3", screens=[h3])
    html3 = render_html(p3, mode="package", runtime_js="")
    assert 'alt=""' in html3


def test_w9_antislop_warns_on_missing_alt_text():
    from core.project import HotspotScreen, LabeledDiagramScreen
    from core.antislop import lint_course

    # alt YOK → WARN beklenir
    h = HotspotScreen(id="h", title="T", prompt_html="<p>x</p>", image_asset_id="a1",
                       regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    p = Project(id=new_project_id(), title="K", screens=[h])
    codes = {i.code for i in lint_course(p)}
    assert "missing_alt_text" in codes

    # alt VAR → WARN yok
    h2 = HotspotScreen(id="h2", title="T", prompt_html="<p>x</p>", image_asset_id="a1",
                        image_alt="Kontrol paneli", regions=[{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}])
    p2 = Project(id=new_project_id(), title="K2", screens=[h2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "missing_alt_text" not in codes2

    # görsel yok → hiç kural tetiklenmez (LabeledDiagram image_asset_id ZORUNLU, o yüzden hotspot ile sınırlı kalır)
    ld = LabeledDiagramScreen(id="ld", title="T", image_asset_id="a1",
                               labels=[{"id": "l1", "x": 10, "y": 10, "text": "Sol"},
                                       {"id": "l2", "x": 20, "y": 20, "text": "Sağ"}])
    p3 = Project(id=new_project_id(), title="K3", screens=[ld])
    codes3 = {i.code for i in lint_course(p3)}
    assert "missing_alt_text" in codes3  # image_asset_id zorunlu ama image_alt opsiyonel — alt eksikse yine WARN


def test_w9_antislop_warns_on_missing_alt_text_flashcards():
    from core.project import Flashcard, FlashcardsScreen
    from core.antislop import lint_course

    # front_asset_id VAR ama front_alt YOK → WARN beklenir
    card = Flashcard(front_html="<p>ön</p>", back_html="<p>arka</p>", front_asset_id="a1")
    fc = FlashcardsScreen(id="fc", title="T", cards=[card])
    p = Project(id=new_project_id(), title="K", screens=[fc])
    codes = {i.code for i in lint_course(p)}
    assert "missing_alt_text" in codes

    # front_asset_id VE front_alt İKİSİ DE VAR → o alan için WARN yok
    card2 = Flashcard(front_html="<p>ön</p>", back_html="<p>arka</p>",
                       front_asset_id="a1", front_alt="Ön yüz görseli")
    fc2 = FlashcardsScreen(id="fc2", title="T", cards=[card2])
    p2 = Project(id=new_project_id(), title="K2", screens=[fc2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "missing_alt_text" not in codes2

    # back_asset_id VAR ama back_alt YOK → arka yüz için de WARN beklenir
    card3 = Flashcard(front_html="<p>ön</p>", back_html="<p>arka</p>", back_asset_id="a1")
    fc3 = FlashcardsScreen(id="fc3", title="T", cards=[card3])
    p3 = Project(id=new_project_id(), title="K3", screens=[fc3])
    issues3 = lint_course(p3)
    assert any(i.code == "missing_alt_text" and "back_asset_id" in i.path for i in issues3)

    # back_asset_id VE back_alt İKİSİ DE VAR → arka yüz için WARN yok
    card4 = Flashcard(front_html="<p>ön</p>", back_html="<p>arka</p>",
                       back_asset_id="a1", back_alt="Arka yüz görseli")
    fc4 = FlashcardsScreen(id="fc4", title="T", cards=[card4])
    p4 = Project(id=new_project_id(), title="K4", screens=[fc4])
    issues4 = lint_course(p4)
    assert not any(i.code == "missing_alt_text" and "back_asset_id" in i.path for i in issues4)


def test_w9_antislop_warns_on_missing_alt_text_content_blocks():
    """Final-review fix — ContentSlide.blocks görselleri de lint kapsamına girmeli
    (renderer b.caption'ı alt-text olarak kullanıyor; blocks önceden gözden kaçıyordu)."""
    from core.project import ContentSlide
    from core.antislop import lint_course

    # blocks içinde asset_id VAR ama caption YOK → WARN beklenir, path blocks[0] içermeli
    cs = ContentSlide(id="cs", title="T", blocks=[{"asset_id": "a1"}])
    p = Project(id=new_project_id(), title="K", screens=[cs])
    issues = lint_course(p)
    matches = [i for i in issues if i.code == "missing_alt_text" and "blocks[0]" in i.path]
    assert len(matches) == 1

    # blocks içinde asset_id VE caption İKİSİ DE VAR → WARN yok
    cs2 = ContentSlide(id="cs2", title="T", blocks=[{"asset_id": "a1", "caption": "Bir görsel"}])
    p2 = Project(id=new_project_id(), title="K2", screens=[cs2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "missing_alt_text" not in codes2


# ---- W9 P0: rate limiting (token bucket) ----
def test_w9_rate_limiter_token_bucket():
    from auth.ratelimit import RateLimiter

    rl = RateLimiter(capacity=3, refill_per_sec=0.0)  # refill=0 → tükendiğinde geri gelmez (test kolaylığı)
    assert rl.allow("user-a") is True
    assert rl.allow("user-a") is True
    assert rl.allow("user-a") is True
    assert rl.allow("user-a") is False  # 4. istek: kapasite doldu
    # farklı principal ayrı bucket kullanır
    assert rl.allow("user-b") is True


def test_w9_rate_limiter_refills_over_time():
    from auth.ratelimit import RateLimiter
    import time as _time

    rl = RateLimiter(capacity=1, refill_per_sec=1000.0)  # çok hızlı refill
    assert rl.allow("user-c") is True
    assert rl.allow("user-c") is False
    _time.sleep(0.01)  # 1000/sn refill ile 10ms'de ~10 token dolar
    assert rl.allow("user-c") is True


@pytest.mark.asyncio
async def test_w9_rate_limit_blocks_excessive_tool_calls(monkeypatch):
    import server as _server

    monkeypatch.setattr(_server, "_RATE_LIMITER", _server.RateLimiter(capacity=2, refill_per_sec=0.0))
    async with Client(_server.mcp) as c:
        r1 = await c.call_tool("create_project", {"title": "A"})
        r2 = await c.call_tool("create_project", {"title": "B"})
        assert r1 and r2
        with pytest.raises(Exception, match="rate_limited"):
            await c.call_tool("create_project", {"title": "C"})


# ---- W9 P0: audit logging ----
def test_w9_audit_log_emits_on_project_create(caplog):
    import logging
    import server
    from fastmcp import Client
    import asyncio

    async def _run():
        async with Client(server.mcp) as c:
            await c.call_tool("create_project", {"title": "Audit Test"})

    with caplog.at_level(logging.INFO, logger="scorm_mcp.audit"):
        asyncio.run(_run())
    assert any("event=project_create" in r.message for r in caplog.records)


# ---- W9 P1: içerik yapısı mekanik kurallar (A1/A2/A3/B3) ----
def test_w9_antislop_a1_consecutive_content_slides():
    from core.antislop import lint_course
    # 3 ardışık content_slide (araya etkileşim girmeden) → WARN
    screens = [
        {"type": "content_slide", "id": "c1", "title": "Birinci fikir", "body_html": "<p>x</p>"},
        {"type": "content_slide", "id": "c2", "title": "İkinci fikir", "body_html": "<p>y</p>"},
        {"type": "content_slide", "id": "c3", "title": "Üçüncü fikir", "body_html": "<p>z</p>"},
    ]
    p = Project(id=new_project_id(), title="K", screens=screens)
    codes = {i.code for i in lint_course(p)}
    assert "consecutive_content_slides" in codes

    # 2 ardışık (izinli) → WARN yok
    p2 = Project(id=new_project_id(), title="K2", screens=screens[:2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "consecutive_content_slides" not in codes2


def test_w9_antislop_a2_too_many_list_items():
    from core.antislop import lint_course
    # 5 <li> → WARN (eşik: >4)
    s = {"type": "content_slide", "id": "c1", "title": "Liste",
         "body_html": "<ul>" + "<li>x</li>" * 5 + "</ul>"}
    p = Project(id=new_project_id(), title="K", screens=[s])
    codes = {i.code for i in lint_course(p)}
    assert "too_many_list_items" in codes

    # 4 <li> → WARN yok
    s2 = {"type": "content_slide", "id": "c2", "title": "Liste",
          "body_html": "<ul>" + "<li>x</li>" * 4 + "</ul>"}
    p2 = Project(id=new_project_id(), title="K2", screens=[s2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "too_many_list_items" not in codes2


def test_w9_antislop_a3_generic_title():
    from core.antislop import lint_course
    for bad_title in ["Modül 1: Giriş", "Bölüm 2: Genel Bakış", "Konu 3", "Ünite: Temeller"]:
        s = {"type": "content_slide", "id": "c1", "title": bad_title, "body_html": "<p>x</p>"}
        p = Project(id=new_project_id(), title="K", screens=[s])
        codes = {i.code for i in lint_course(p)}
        assert "generic_title" in codes, f"beklenen WARN yok: {bad_title!r}"

    # Somut başlık → WARN yok
    s2 = {"type": "content_slide", "id": "c2", "title": "Neden 8 saniyede karar veriyoruz?",
          "body_html": "<p>x</p>"}
    p2 = Project(id=new_project_id(), title="K2", screens=[s2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "generic_title" not in codes2

    # Yanlış-pozitif kontrolü: prefix kelimeyle başlıyor ama anlamlı ek içerik taşıyor → WARN yok
    s3 = {"type": "content_slide", "id": "c3", "title": "Bölüm bazlı erişim kontrolü nasıl çalışır?",
          "body_html": "<p>x</p>"}
    p3 = Project(id=new_project_id(), title="K3", screens=[s3])
    codes3 = {i.code for i in lint_course(p3)}
    assert "generic_title" not in codes3
    assert "generic_title" not in codes2


def test_w9_antislop_b3_default_feedback():
    from core.antislop import lint_course
    # feedback hiç verilmemiş → şema varsayılanı ("Doğru!"/"Tekrar deneyin.") → WARN
    s = {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>?</p>",
         "options": [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]}
    p = Project(id=new_project_id(), title="K", screens=[s])
    codes = {i.code for i in lint_course(p)}
    assert "default_feedback" in codes

    # Gerçek feedback verilmiş → WARN yok
    s2 = {"type": "mcq", "id": "q2", "title": "Soru", "prompt_html": "<p>?</p>",
          "options": [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}],
          "feedback": {"correct_html": "Doğru — çünkü alan adı asıl kanıttır.",
                       "incorrect_html": "Tıklamadan önce alan adını kontrol et."}}
    p2 = Project(id=new_project_id(), title="K2", screens=[s2])
    codes2 = {i.code for i in lint_course(p2)}
    assert "default_feedback" not in codes2


def test_w10_theme_logo_alt_and_custom_fonts_fields():
    from core.project import ThemeTokens, CustomFont

    t = ThemeTokens()
    assert t.logo_alt is None
    assert t.custom_fonts == []

    t2 = ThemeTokens(
        logo_asset_id="logo1", logo_alt="Acme Corp logo",
        custom_fonts=[CustomFont(family="Acme Sans", asset_id="font1", weight=700)],
    )
    assert t2.logo_alt == "Acme Corp logo"
    assert t2.custom_fonts[0].family == "Acme Sans"
    assert t2.custom_fonts[0].asset_id == "font1"
    assert t2.custom_fonts[0].weight == 700
    assert t2.custom_fonts[0].style == "normal"


def test_w10_chrome_logo_absent_keeps_brand_dot():

    p = Project(id=new_project_id(), title="K",
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert '<span class="brand-dot"></span>' in html
    # NOT: BASE_CSS her zaman ".chrome-logo{...}" kuralını içerir (statik CSS, davranış
    # değişikliği yok) — burada asıl markup'ta <img class="chrome-logo"> ELEMANI olmadığını
    # doğruluyoruz, ham "chrome-logo" alt-dizesini değil.
    assert 'class="chrome-logo"' not in html


def test_w10_chrome_logo_present_renders_img():
    from core.project import ThemeTokens

    theme = ThemeTokens(logo_asset_id="corp_logo", logo_alt="Acme Corp logo")
    p = Project(id=new_project_id(), title="K", theme=theme,
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert '<span class="brand-dot"></span>' not in html
    assert 'class="chrome-logo"' in html
    assert 'data-asset="corp_logo"' in html
    assert 'alt="Acme Corp logo"' in html


def test_w10_chrome_logo_alt_falls_back_to_theme_name():
    from core.project import ThemeTokens

    theme = ThemeTokens(name="acme", logo_asset_id="corp_logo")  # logo_alt verilmedi
    p = Project(id=new_project_id(), title="K", theme=theme,
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert 'alt="acme"' in html


def test_w10_font_faces_empty_when_no_custom_fonts():
    p = Project(id=new_project_id(), title="K",
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "@font-face" not in html


def test_w10_font_faces_rendered_for_custom_fonts():
    from core.project import ThemeTokens, CustomFont, AssetRef

    theme = ThemeTokens(custom_fonts=[CustomFont(family="Acme Sans", asset_id="font1", weight=700,
                                                   style="italic")])
    p = Project(id=new_project_id(), title="K", theme=theme,
                assets=[AssetRef(id="font1", filename="acme.woff2", mime="font/woff2",
                                  size_bytes=20, sha256="0" * 64, rel_path="assets/acme.woff2")],
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/",
                        asset_data={"font1": ("font/woff2", b"\x00\x01fake-woff2-bytes")})
    assert "@font-face" in html
    assert 'font-family:"Acme Sans"' in html
    assert "font-weight:700" in html
    assert "font-style:italic" in html
    assert "data:font/woff2;base64," in html  # asset_map preview'da data-URI'ye çözülmüş olmalı


def test_w10_font_faces_skips_unresolved_asset():
    """asset_map'te bulunmayan bir asset_id sessizce atlanır (paket bozulmaz)."""
    from core.project import ThemeTokens, CustomFont

    theme = ThemeTokens(custom_fonts=[CustomFont(family="Ghost", asset_id="missing_asset")])
    p = Project(id=new_project_id(), title="K", theme=theme,
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    html = render_html(p, mode="preview", runtime_js="/*rt*/")
    assert "@font-face" not in html


def test_w10_lint_warns_on_theme_logo_missing_alt():
    from core.antislop import lint_course
    from core.project import ThemeTokens

    theme = ThemeTokens(logo_asset_id="corp_logo")  # logo_alt YOK
    p = Project(id=new_project_id(), title="K", theme=theme,
                screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    issues = lint_course(p)
    matches = [i for i in issues if i.code == "missing_alt_text" and i.path == "theme.logo_asset_id"]
    assert len(matches) == 1

    theme2 = ThemeTokens(logo_asset_id="corp_logo", logo_alt="Acme Corp logo")
    p2 = Project(id=new_project_id(), title="K2", theme=theme2,
                 screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    issues2 = lint_course(p2)
    assert not any(i.path == "theme.logo_asset_id" for i in issues2)

    # logo_asset_id yoksa hiç tetiklenmez
    p3 = Project(id=new_project_id(), title="K3",
                 screens=[ContentSlide(id="c1", title="T", body_html="<p>x</p>")])
    issues3 = lint_course(p3)
    assert not any(i.path == "theme.logo_asset_id" for i in issues3)


def test_w10_load_theme_extends_merges_parent(tmp_path, monkeypatch):
    import server as srv

    (tmp_path / "base.json").write_text(json.dumps({
        "name": "base",
        "typography": {"font_heading": "Arial", "font_body": "Arial", "font_mono": "monospace",
                        "base_size_px": 16, "scale_ratio": 1.25, "weight_heading": 700,
                        "weight_body": 400, "weight_strong": 600, "line_height_tight": 1.15,
                        "line_height_normal": 1.6, "letter_spacing_heading": "0"},
        "color": {"primary": "#111111", "primary_hover": "#000000", "primary_contrast": "#ffffff",
                   "secondary": "#222222", "accent": "#333333", "bg": "#ffffff", "surface": "#ffffff",
                   "surface_alt": "#eeeeee", "border": "#dddddd", "text": "#000000",
                   "text_muted": "#666666", "text_on_dark": "#ffffff", "success": "#00ff00",
                   "success_bg": "#eaffea", "error": "#ff0000", "error_bg": "#ffeaea",
                   "warning": "#ffaa00", "info": "#0000ff", "focus_ring": "#111111"},
        "background_pattern": "dots",
        "custom_css": ".btn{color:var(--c-primary)}",
    }), encoding="utf-8")
    (tmp_path / "child.json").write_text(json.dumps({
        "extends": "base", "name": "child",
        "color": {"primary": "#004dcf"},
    }), encoding="utf-8")

    monkeypatch.setattr(srv, "THEMES_DIR", tmp_path)
    resolved = srv._load_theme("child")

    assert resolved.name == "child"                       # child'ın kendi alanı kazanır
    assert resolved.color.primary == "#004dcf"             # child override'ı uygulanmış
    assert resolved.color.secondary == "#222222"           # base'ten miras (child override etmedi)
    assert resolved.background_pattern == "dots"           # base'ten miras
    assert resolved.custom_css == ".btn{color:var(--c-primary)}"  # base'ten miras, KOPYALANMADI


def test_w10_load_theme_extends_detects_cycle(tmp_path, monkeypatch):
    import server as srv

    (tmp_path / "a.json").write_text(json.dumps({"extends": "b", "name": "a"}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"extends": "a", "name": "b"}), encoding="utf-8")

    monkeypatch.setattr(srv, "THEMES_DIR", tmp_path)
    with pytest.raises(ToolError):
        srv._load_theme("a")


def test_w10_load_theme_without_extends_unaffected(tmp_path, monkeypatch):
    """extends anahtarı YOKSA davranış eskisiyle birebir aynı — mevcut 12 tema bundan etkilenmez."""
    import server as srv

    (tmp_path / "plain.json").write_text(json.dumps({
        "name": "plain",
        "typography": {"font_heading": "Arial", "font_body": "Arial", "font_mono": "monospace",
                        "base_size_px": 16, "scale_ratio": 1.25, "weight_heading": 700,
                        "weight_body": 400, "weight_strong": 600, "line_height_tight": 1.15,
                        "line_height_normal": 1.6, "letter_spacing_heading": "0"},
        "color": {"primary": "#111111", "primary_hover": "#000000", "primary_contrast": "#ffffff",
                   "secondary": "#222222", "accent": "#333333", "bg": "#ffffff", "surface": "#ffffff",
                   "surface_alt": "#eeeeee", "border": "#dddddd", "text": "#000000",
                   "text_muted": "#666666", "text_on_dark": "#ffffff", "success": "#00ff00",
                   "success_bg": "#eaffea", "error": "#ff0000", "error_bg": "#ffeaea",
                   "warning": "#ffaa00", "info": "#0000ff", "focus_ring": "#111111"},
        "background_pattern": "none",
    }), encoding="utf-8")

    monkeypatch.setattr(srv, "THEMES_DIR", tmp_path)
    resolved = srv._load_theme("plain")
    assert resolved.name == "plain"
    assert resolved.color.primary == "#111111"


@pytest.mark.asyncio
async def test_w10_style_brand_composition_end_to_end():
    """style-playful (extends: playground) + marka rengi/logo/font set_theme ile deep-merge edilince,
    playful'ın MİRAS ALINMIŞ yapısal custom_css'i (3D buton efekti) KORUNUR, marka rengi/logo/font
    ÜZERİNE yazılır."""
    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "Marka Testi", "scorm_version": "1.2", "theme": "style-playful",
            "assets": [
                {"id": "corp_logo", "filename": "logo.svg",
                 "source": "data:image/svg+xml;base64,"
                           "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCI+PC9zdmc+"},
                {"id": "corp_font", "filename": "font.woff2",
                 "source": "data:font/woff2;base64,AAECAw=="},
            ],
            "screens": [{"type": "content_slide", "id": "c1", "title": "T", "body_html": "<p>x</p>"}],
        }})
        pid = res.data.project_id if hasattr(res.data, "project_id") else res.data["project_id"]

        await c.call_tool("set_theme", {"project_id": pid, "theme_tokens": {
            "color": {"primary": "#004dcf"},
            "logo_asset_id": "corp_logo", "logo_alt": "Acme Corp logo",
            "custom_fonts": [{"family": "Acme Sans", "asset_id": "corp_font", "weight": 700}],
        }})

        prev = await c.call_tool("preview", {"project_id": pid})
        html = prev.data.inline_html if hasattr(prev.data, "inline_html") else prev.data["inline_html"]

        # playful'ın MİRAS ALINMIŞ yapısal kişiliği korunmuş (3D buton efekti, playground'dan extends)
        assert "box-shadow:0 4px 0 -1px color-mix(in srgb,var(--c-primary) 60%,#000)" in html
        # marka rengi override edilmiş
        assert "--c-primary:#004dcf" in html
        # logo render edilmiş (dot YOK)
        assert 'class="chrome-logo"' in html
        assert '<span class="brand-dot"></span>' not in html
        assert 'alt="Acme Corp logo"' in html
        # custom font @font-face üretilmiş
        assert "@font-face" in html
        assert 'font-family:"Acme Sans"' in html


# ---- W11 Kural 1: text_only_run (≥4 ardışık görselsiz ekran) ----
def test_w11_antislop_text_only_run_threshold():
    """W11 Kural 1 — 4 ardışık görselsiz ekran text_only_run WARN tetikler; 3 tanesi tetiklemez
    (2-3 metin-ağırlıklı ekran meşru, 4+ 'metin duvarı' desenidir)."""
    from core.antislop import lint_course

    def cs(i):
        return {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}", "body_html": "<p>x</p>"}

    screens4 = [cs(i) for i in range(4)]
    p = Project(id=new_project_id(), title="K", screens=screens4)
    codes = {i.code for i in lint_course(p)}
    assert "text_only_run" in codes

    screens3 = [cs(i) for i in range(3)]
    p2 = Project(id=new_project_id(), title="K2", screens=screens3)
    codes2 = {i.code for i in lint_course(p2)}
    assert "text_only_run" not in codes2


def test_w11_antislop_text_only_run_broken_by_visual_field():
    """W11 Kural 1 — blocks[].asset_id ya da flashcard front_asset_id dolu bir ekran görselsiz
    koşuyu KIRAR: koşu 4'e ulaşmadan bölünür, text_only_run tetiklenmez."""
    from core.antislop import lint_course

    def cs(i):
        return {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}", "body_html": "<p>x</p>"}

    # blocks[].asset_id ile kırılan koşu: 2 metin + 1 görselli blok + 2 metin (en uzun koşu 2)
    visual_block = {"type": "content_slide", "id": "vb", "title": "Görsel",
                     "blocks": [{"asset_id": "a1", "caption": "Bir görsel"}]}
    screens = [cs(0), cs(1), visual_block, cs(2), cs(3)]
    p = Project(id=new_project_id(), title="K", screens=screens)
    codes = {i.code for i in lint_course(p)}
    assert "text_only_run" not in codes

    # flashcard front_asset_id ile kırılan koşu
    flash = {"type": "flashcards", "id": "fc", "title": "Kartlar",
             "cards": [{"front_html": "<p>ön</p>", "back_html": "<p>arka</p>", "front_asset_id": "a1"}]}
    screens2 = [cs(0), cs(1), flash, cs(2), cs(3)]
    p2 = Project(id=new_project_id(), title="K2", screens=screens2)
    codes2 = {i.code for i in lint_course(p2)}
    assert "text_only_run" not in codes2


# ---- W11 Kural 2: visual_poverty (≥8 ekran VE görsel oran <%25) ----
def test_w11_antislop_visual_poverty():
    """W11 Kural 2 — ekran sayısı ≥8 VE görsel ekran oranı <%25 → visual_poverty WARN. <8 ekranlı
    kurslar muaf; oran tam %25 (eşik dahil değil, katı '<') iken de WARN yok."""
    from core.antislop import lint_course

    def cs(i):
        return {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}", "body_html": "<p>x</p>"}

    def hotspot(hid):
        return {"type": "hotspot", "id": hid, "title": "Bul", "prompt_html": "<p>x</p>",
                "image_asset_id": "a1", "image_alt": "Görsel",
                "regions": [{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}]}

    # 10 ekran, yalnızca 1 görsel (%10 < %25) → WARN
    screens10 = [hotspot("h1")] + [cs(i) for i in range(9)]
    p = Project(id=new_project_id(), title="K", screens=screens10)
    codes = {i.code for i in lint_course(p)}
    assert "visual_poverty" in codes

    # 7 ekran, yalnızca 1 görsel (<8 muaf) → WARN yok
    screens7 = [hotspot("h1")] + [cs(i) for i in range(6)]
    p2 = Project(id=new_project_id(), title="K2", screens=screens7)
    codes2 = {i.code for i in lint_course(p2)}
    assert "visual_poverty" not in codes2

    # 8 ekran, 2 görsel (%25 tam eşik, "<" katı) → WARN yok
    screens8 = [hotspot("h1"), hotspot("h2")] + [cs(i) for i in range(6)]
    p3 = Project(id=new_project_id(), title="K3", screens=screens8)
    codes3 = {i.code for i in lint_course(p3)}
    assert "visual_poverty" not in codes3


def test_w11_antislop_visually_rich_course_triggers_neither_rule():
    """W11 — görsel-zengin bir kurs (v2 'Spot the Phish' vitrin deseni: hotspot/image_compare/
    flashcards karışımı, hiçbir görselsiz koşu 4'e ulaşmıyor, görsel oran ≥%25) NE text_only_run
    NE DE visual_poverty üretir."""
    from core.antislop import lint_course

    def cs(i):
        return {"type": "content_slide", "id": f"c{i}", "title": f"Fikir {i}", "body_html": "<p>x</p>"}

    hotspot = {"type": "hotspot", "id": "h1", "title": "Bul", "prompt_html": "<p>x</p>",
               "image_asset_id": "a1", "image_alt": "Gelen kutusu ekran görüntüsü",
               "regions": [{"id": "r1", "shape": "rect", "coords": [0, 0, 10, 10], "correct": True}]}
    content_with_block = {"type": "content_slide", "id": "cb", "title": "Domain kontrolü",
                           "blocks": [{"asset_id": "a2", "caption": "Sahte domain örneği"}]}
    mcq = {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>?</p>",
           "options": [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}],
           "feedback": {"correct_html": "Doğru.", "incorrect_html": "Tekrar dene."}}
    image_compare = {"type": "image_compare", "id": "ic", "title": "Önce/Sonra",
                      "before_asset_id": "a3", "after_asset_id": "a4"}
    flashcards = {"type": "flashcards", "id": "fc", "title": "Kartlar",
                  "cards": [{"front_html": "<p>ön</p>", "back_html": "<p>arka</p>", "front_asset_id": "a5"}]}
    summary = {"type": "summary", "id": "sm", "title": "Özet"}

    screens = [cs(0), hotspot, cs(1), content_with_block, mcq, image_compare, cs(2), flashcards, cs(3), summary]
    p = Project(id=new_project_id(), title="K", screens=screens)
    codes = {i.code for i in lint_course(p)}
    assert "text_only_run" not in codes
    assert "visual_poverty" not in codes


# ---- W11 Bölüm 2: search_images (Openverse/Wikimedia adaptör + MCP tool) ----
@pytest.mark.asyncio
async def test_w11_openverse_adapter_search_maps_results():
    """OpenverseAdapter.search — API JSON'unu dokümante edilen aday şekline eşler; indirme yapmaz
    (safe_fetch_asset hiç çağrılmamalı)."""
    from unittest.mock import MagicMock, patch
    from core.integrations.openverse import OpenverseAdapter

    mock_api_resp = {
        "results": [{
            "title": "Kedi fotoğrafı",
            "url": "https://safe.example.com/cat.jpg",
            "thumbnail": "https://safe.example.com/cat_thumb.jpg",
            "width": 800, "height": 600,
            "license": "cc0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "Artist Name",
            "foreign_landing_url": "https://openverse.org/image/abc",
        }]
    }

    with patch("core.integrations.openverse.assert_safe_url") as mock_assert, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.openverse.safe_fetch_asset") as mock_fetch:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)

        adapter = OpenverseAdapter()
        images = await adapter.search("cats", limit=3)

        assert mock_assert.called
        assert not mock_fetch.called  # search yalnız aday listeler, İNDİRME YAPMAZ
        assert images == [{
            "title": "Kedi fotoğrafı",
            "url": "https://safe.example.com/cat.jpg",
            "thumb_url": "https://safe.example.com/cat_thumb.jpg",
            "width": 800, "height": 600,
            "license": "CC0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "Artist Name",
            "source_page": "https://openverse.org/image/abc",
        }]


@pytest.mark.asyncio
async def test_w11_openverse_adapter_search_graceful_on_error():
    """OpenverseAdapter.search — HTTP hatasında/boş sonuçta [] döner (istisna fırlatmaz)."""
    from unittest.mock import MagicMock, patch
    from core.integrations.openverse import OpenverseAdapter

    with patch("core.integrations.openverse.assert_safe_url"), \
         patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500)
        adapter = OpenverseAdapter()
        assert await adapter.search("error") == []


@pytest.mark.asyncio
async def test_w11_openverse_adapter_search_encodes_query():
    """OpenverseAdapter.search — sorgu URL-encode edilir; '#' gibi karakterler license filtresini
    URL fragment'ına çevirip CC0/PD filtresini atlatamaz (query smuggling koruması)."""
    from unittest.mock import MagicMock, patch
    from core.integrations.openverse import OpenverseAdapter

    with patch("core.integrations.openverse.assert_safe_url"), \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.openverse.safe_fetch_asset"):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"results": []})

        adapter = OpenverseAdapter()
        await adapter.search("cats#evil", limit=3)

        assert mock_get.called
        called_url = mock_get.call_args.args[0]
        assert "cats%23evil" in called_url
        assert "license=cc0,pdm" in called_url


@pytest.mark.asyncio
async def test_w11_wikimedia_adapter_search_filters_by_license():
    """WikimediaAdapter.search — yalnız PD/CC0 ailesinden lisanslı sonuçlar dahil edilir; diğerleri
    atlanır (indirme yapmadan)."""
    from unittest.mock import MagicMock, patch
    from core.integrations.wikimedia import WikimediaAdapter

    mock_api_resp = {
        "query": {
            "pages": {
                "1": {
                    "title": "File:test.jpg",
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:test.jpg",
                        "width": 640, "height": 480,
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC0"},
                            "Artist": {"value": "Wikimedia Artist"},
                        },
                    }],
                },
                "2": {
                    "title": "File:copyrighted.jpg",
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/wikipedia/commons/copyrighted.jpg",
                        "extmetadata": {"LicenseShortName": {"value": "CC-BY-SA-4.0"}},
                    }],
                },
            }
        }
    }

    with patch("core.integrations.wikimedia.assert_safe_url") as mock_assert, \
         patch("httpx.AsyncClient.get") as mock_get, \
         patch("core.integrations.wikimedia.safe_fetch_asset") as mock_fetch:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_api_resp)

        adapter = WikimediaAdapter()
        images = await adapter.search("test", limit=5)

        assert mock_assert.called
        assert not mock_fetch.called
        assert len(images) == 1
        assert images[0]["url"] == "https://upload.wikimedia.org/wikipedia/commons/test.jpg"
        assert images[0]["license"] == "CC0"
        assert images[0]["creator"] == "Wikimedia Artist"


@pytest.mark.asyncio
async def test_w11_search_images_tool_returns_count_and_images(monkeypatch):
    """search_images tool'u — adaptörün search() sonucunu {count, source, images} şekline sarar."""
    from core.integrations.openverse import OpenverseAdapter

    async def fake_search(self, query, limit=5):
        return [{
            "title": "Örnek", "url": "https://safe.example.com/x.jpg", "thumb_url": None,
            "width": None, "height": None, "license": "CC0", "license_url": None,
            "creator": "Biri", "source_page": None,
        }]

    monkeypatch.setattr(OpenverseAdapter, "search", fake_search)

    async with Client(server.mcp) as c:
        res = await c.call_tool("search_images", {"query": "cats", "source": "openverse", "limit": 3})
        assert res.data["count"] == 1
        assert res.data["source"] == "openverse"
        assert res.data["images"][0]["url"] == "https://safe.example.com/x.jpg"
        assert res.data["images"][0]["creator"] == "Biri"


@pytest.mark.asyncio
async def test_w11_search_images_unknown_source_raises():
    """search_images — bilinmeyen `source` değeri ToolError('invalid_source', ...) fırlatır."""
    async with Client(server.mcp) as c:
        with pytest.raises(Exception, match="invalid_source"):
            await c.call_tool("search_images", {"query": "cats", "source": "bogus"})


@pytest.mark.asyncio
async def test_w11_search_images_clamps_limit(monkeypatch):
    """search_images — `limit` her zaman 1..10 aralığına kelepçelenir (99 verilse bile adaptöre 10
    gider)."""
    from core.integrations.openverse import OpenverseAdapter

    captured = {}

    async def fake_search(self, query, limit=5):
        captured["limit"] = limit
        return []

    monkeypatch.setattr(OpenverseAdapter, "search", fake_search)

    async with Client(server.mcp) as c:
        await c.call_tool("search_images", {"query": "cats", "source": "openverse", "limit": 99})

    assert captured["limit"] == 10


# ---- W12: kalıcı demo yayını (publish_demo + /demo/{slug}) ----
async def test_w12_publish_demo_and_route():
    """publish_demo kalıcı URL döner; /demo/{slug} rotası TTL'siz servis eder; upsert çalışır."""
    from starlette.requests import Request as StarReq  # noqa: F401

    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "Demo K", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
        }})
        pid = res.data.project_id
        out = await c.call_tool("publish_demo", {"project_id": pid, "slug": "test-demo"})
        d = out.data if isinstance(out.data, dict) else out.data.__dict__
        assert d["url"].endswith("/demo/test-demo")

        # dosya diske yazıldı ve rota içeriği döner
        import pathlib
        f = pathlib.Path(server.SETTINGS.data_dir) / "demos" / "test-demo.html"
        assert f.exists() and "<!DOCTYPE html>" in f.read_text(encoding="utf-8")

        # upsert: tekrar yayınlamak hata vermez
        await c.call_tool("publish_demo", {"project_id": pid, "slug": "test-demo"})


async def test_w12_publish_demo_invalid_slug_and_foreign_owner():
    from fastmcp.exceptions import ToolError as MCPToolError

    async with Client(server.mcp) as c:
        res = await c.call_tool("build_from_spec", {"spec": {
            "title": "Demo K2", "scorm_version": "1.2",
            "screens": [{"type": "title_slide", "id": "t1", "title": "T"}],
        }})
        pid = res.data.project_id
        with pytest.raises(MCPToolError, match="invalid_slug"):
            await c.call_tool("publish_demo", {"project_id": pid, "slug": "Bad Slug!"})

        # başka sahibe ait slug → forbidden (owner dosyasını elle farklı yaz)
        import pathlib
        demos = pathlib.Path(server.SETTINGS.data_dir) / "demos"
        demos.mkdir(parents=True, exist_ok=True)
        (demos / "taken-slug.owner").write_text("someone-else", encoding="utf-8")
        with pytest.raises(MCPToolError, match="forbidden"):
            await c.call_tool("publish_demo", {"project_id": pid, "slug": "taken-slug"})


# ---- S5 (2.2b): suspend_data boyut tahmini WARN ----
def test_s5_lint_warns_on_suspend_size_risk_for_scorm12():
    from core.antislop import estimate_suspend_size, lint_course

    def big(n_screens: int, ver: str = "1.2") -> Project:
        screens = []
        for i in range(n_screens):
            if i % 2:
                screens.append(MCQScreen(id=f"q{i}", title=f"Soru {i}?", prompt_html="<p>?</p>",
                                         options=[Choice(id="a", text_html="A", correct=True),
                                                  Choice(id="b", text_html="B")]))
            else:
                screens.append(ContentSlide(id=f"c{i}", title=f"Neden {i} önemli?", body_html="<p>x</p>"))
        return Project(id=new_project_id(), title="Büyük", scorm_version=ver, screens=screens)

    # kabul senaryosu: 60 ekran / 30 puanlı — v2 kodlayıcı rahat sığdırır → WARN YOK
    ok = big(60)
    assert estimate_suspend_size(ok) < int(4096 * 0.9)
    assert "suspend_size_risk" not in {i.code for i in lint_course(ok)}

    # 500 ekran / 250 puanlı — tahmin sınıra dayanır → WARN (FAIL değil; runtime yine sığdırmaya çalışır)
    risky = big(500)
    issues = [i for i in lint_course(risky) if i.code == "suspend_size_risk"]
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "4096" in issues[0].message

    # aynı kurs 2004 hedefinde: sınır 64k → kural sessiz (yalnız 1.2 hedefi denetlenir)
    assert "suspend_size_risk" not in {i.code for i in lint_course(big(500, ver="2004"))}


# ---- S2 (2.4): kurs hedefleri — model + doğrulama + lint ----
def _obj_screens():
    return [
        ContentSlide(id="c1", title="Neden hedefler?", body_html="<p>x</p>"),
        MCQScreen(id="q1", title="Soru?", prompt_html="<p>?</p>", objective_ids=["o1"],
                  options=[Choice(id="a", text_html="A", correct=True),
                           Choice(id="b", text_html="B")]),
    ]


def test_s2_objective_id_must_be_machine_friendly():
    from core.project import Objective
    import pydantic

    assert Objective(id="obj-1.a_B").id == "obj-1.a_B"
    for bad in ("", "hedef bir", "türkçe-İd", "a" * 256):
        with pytest.raises(pydantic.ValidationError):
            Objective(id=bad)


def test_s2_validator_rejects_unknown_objective_ref_and_duplicate_ids():
    from core.project import Objective
    from core.validator import validate_project

    ok = Project(id=new_project_id(), title="T", objectives=[Objective(id="o1")],
                 screens=_obj_screens())
    assert validate_project(ok) == []

    # bilinmeyen hedef referansı → sert hata (build bloklanır)
    p = Project(id=new_project_id(), title="T", objectives=[Objective(id="baska")],
                screens=_obj_screens())
    errs = validate_project(p)
    assert any("Bilinmeyen hedef" in e.message and "o1" in e.message for e in errs)

    # hedefler hiç tanımlanmamışken referans da hata
    p2 = Project(id=new_project_id(), title="T", screens=_obj_screens())
    assert any("Bilinmeyen hedef" in e.message for e in validate_project(p2))

    # yinelenen kurs hedef id'si → sert hata
    p3 = Project(id=new_project_id(), title="T",
                 objectives=[Objective(id="o1"), Objective(id="o1")], screens=_obj_screens())
    assert any("Yinelenen hedef" in e.message for e in validate_project(p3))


def test_s2_lint_warns_on_unbound_objective():
    from core.antislop import lint_course
    from core.project import Objective

    # o1 bağlı, o2 bağsız → yalnız o2 için WARN
    p = Project(id=new_project_id(), title="T",
                objectives=[Objective(id="o1"), Objective(id="o2")], screens=_obj_screens())
    issues = [i for i in lint_course(p) if i.code == "unbound_objective"]
    assert len(issues) == 1
    assert issues[0].severity == "warn" and "o2" in issues[0].message

    # hepsi bağlıysa sessiz; hedef yoksa sessiz
    p.screens[1].objective_ids = ["o1", "o2"]
    assert "unbound_objective" not in {i.code for i in lint_course(p)}
    p2 = Project(id=new_project_id(), title="T", screens=_obj_screens()[:1])
    assert "unbound_objective" not in {i.code for i in lint_course(p2)}


def test_item_media_centered_in_wide_columns_by_css():
    """Bug (2026-07-29): .item-media display:block + margin:'var(--space-3) 0' — görsel geniş
    ekranda kolonundan darsa (block + width:auto) SOLA yapışır (canlı ölçüm: sol 341px /
    sağ 659px). Yatay margin 'auto' olmadan blok görselin ortalanması mümkün değil; dar
    ekranda genişlik dolu olduğundan auto etkisizdir (mobil davranış değişmez)."""
    from components.templates import BASE_CSS
    import re

    m = re.search(r"\.item-media\{[^}]*\}", BASE_CSS)
    assert m, ".item-media kuralı BASE_CSS'te bulunamadı"
    rule = m.group(0)
    assert re.search(r"margin:[^;}]*auto", rule), (
        ".item-media yatay margin'i auto olmalı (geniş ekranda ortalama): " + rule
    )
