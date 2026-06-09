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
