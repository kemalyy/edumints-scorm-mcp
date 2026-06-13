"""tests/test_units.py — birim testler (manifest, SSRF, sanitizasyon, fast-path, kota)."""

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
    # Faz 2: feedback annotation widget yalnız preview'da aktif (pakette gizli/çalışmaz)
    p = Project(id=new_project_id(), title="R")
    p.screens = [ContentSlide(id="c", title="C", body_html="<p>x</p>")]
    prev = render_html(p, mode="preview", runtime_js="/*rt*/")
    pkg = render_html(p, mode="package", runtime_js="/*rt*/")
    assert "window.__PREVIEW__ = true;" in prev
    assert "window.__PREVIEW__ = false;" in pkg
    assert 'id="reviewFab"' in prev and 'id="reviewFab"' in pkg  # markup her ikisinde, JS gate ediyor


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
    from core.project import GameScreen
    from core.antislop import lint_course
    # ulaşılabilir + gerçek (farklı) seçimler + skor aksiyonlu + ceza seçiminde gerekçe
    g = GameScreen(id="g", title="Temiz", mechanics={"score": {"id": "sc"}, "lives": {"id": "lv", "start": 3}},
        nodes=[
            {"id": "n1", "content_html": "<p>x</p>", "choices": [
                {"id": "a", "text_html": "Doğru", "to": "n2", "on_choose": [{"do": "score.correct", "points": 10}]},
                {"id": "b", "text_html": "Yanlış", "to": None, "feedback_html": "<p>Çünkü …</p>",
                 "on_choose": [{"do": "lives.lose", "n": 1}]}]},
            {"id": "n2", "content_html": "<p>y</p>", "choices": [{"id": "c", "text_html": "Bitir", "to": None}]},
        ])
    p = Project(id=new_project_id(), title="K", screens=[g])
    assert lint_course(p) == []
