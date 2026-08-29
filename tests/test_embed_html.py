"""tests/test_embed_html.py — embed_html ekran tipi + html_to_asset + wrap_artifact + köprü render."""

import pytest
from fastmcp import Client

import server
from core.project import Project, ScreenType, new_project_id


def test_embed_html_screen_validates_via_discriminator():
    p = Project(id=new_project_id(), title="E", owner_key_id="key_local", screens=[
        {"type": "embed_html", "id": "e1", "html_asset_id": "asset_x", "title": "App",
         "completion": "on_message", "min_seconds": 5, "aspect": "16:9"},
    ])
    s = p.screens[0]
    assert s.type == ScreenType.embed_html
    assert s.html_asset_id == "asset_x" and s.completion == "on_message" and s.min_seconds == 5


def test_embed_html_requires_html_asset_id():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Project(id=new_project_id(), title="E", owner_key_id="key_local",
                screens=[{"type": "embed_html", "id": "e1"}])  # html_asset_id yok


def test_embed_html_not_scored():
    from core.project import QUIZ_TYPES
    assert ScreenType.embed_html not in QUIZ_TYPES


async def test_list_screen_types_includes_embed_html():
    async with Client(server.mcp) as c:
        out = (await c.call_tool("list_screen_types", {})).data
        row = next(r for r in out["screen_types"] if r["type"] == "embed_html")
        assert row["scored"] is False and row["description"]


async def test_html_to_asset_stores_html():
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "H"})).data.project_id
        ref = (await c.call_tool("html_to_asset", {
            "project_id": pid,
            "html_content": "<!doctype html><html><body><h1>Merhaba</h1><script>1</script></body></html>",
            "filename": "app.html",
        })).data
        assert ref.mime == "text/html"
        assert ref.filename.endswith(".html")
        assert ref.size_bytes > 0


async def test_html_to_asset_rejects_empty():
    from fastmcp.exceptions import ToolError as MCPToolError
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "H2"})).data.project_id
        with pytest.raises(MCPToolError):
            await c.call_tool("html_to_asset", {"project_id": pid, "html_content": "   "})


def test_embed_html_renders_sandboxed_iframe():
    from components.renderer import render_html
    from components.renderer import load_runtime_js
    p = Project(id=new_project_id(), title="Emb", language="tr", owner_key_id="key_local",
                screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid1",
                          "title": "Uygulama", "completion": "time_threshold", "min_seconds": 8,
                          "aspect": "16:9"}])
    html = render_html(p, mode="package", runtime_js=load_runtime_js())
    assert '<iframe' in html and 'data-asset="aid1"' in html
    assert 'sandbox="allow-scripts allow-same-origin allow-forms allow-popups"' in html
    assert 'data-completion="time_threshold"' in html and 'data-min-seconds="8"' in html
    # artifact HTML launcher DOM'una GÖMÜLMEZ (yalnız iframe src referansı)
    assert 'data-embed-screen' in html


def test_bridge_inlined_only_for_embed_courses():
    """embed'li kursta köprü VAR; embed'siz kursta HİÇ YOK (koşullu bundle + sentinel)."""
    from components.renderer import render_html, load_runtime_js
    emb = Project(id=new_project_id(), title="B", language="tr", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid"}])
    html = render_html(emb, mode="package", runtime_js=load_runtime_js())
    # NOT (fix round 3 / FINDING F): işaret CANLI bir sembol (embedStateFromMsg — mesaj yolunda
    # gerçekten çağrılır). bridgeToScorm bundle'da KALIR ama runtime'da çağrılmaz (sözleşme
    # dokümanının referans imzası) — yalnız onu aramak, ölü kod silinince testi sessizce boşa
    # çıkarırdı.
    assert "embedStateFromMsg" in html and "iframe.embed-frame" in html
    assert "bridgeToScorm" in html

    plain = Project(id=new_project_id(), title="P", language="tr", owner_key_id="key_local",
                    screens=[{"type": "content_slide", "id": "c1", "title": "X",
                              "body_html": "<p>x</p>"}])
    plain_html = render_html(plain, mode="package", runtime_js=load_runtime_js())
    assert "bridgeToScorm" not in plain_html
    assert "SCORMEMBED" not in plain_html
    assert "iframe.embed-frame" not in plain_html


def test_embed_course_wraps_evaluate_and_showat_not_plain_course():
    """fix round 1 / CRITICAL — motorun evaluate()/showAt() bağlamaları YALNIZ embed'li kursta
    köprü sarmalayıcısıyla değiştirilir (ENGINE_JS gövdesi asla düzenlenmez — bayt-parite);
    embed'siz kursta bu kablolamadan hiçbir iz yoktur."""
    from components.renderer import render_html, load_runtime_js
    emb = Project(id=new_project_id(), title="B", language="tr", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid"}])
    html = render_html(emb, mode="package", runtime_js=load_runtime_js())
    assert "wrapEvaluate" in html
    assert "evaluate = EMB.wrapEvaluate(evaluate, sSet, lockedWrites, sCommit)" in html
    # fix round 3 / FINDING C — giriş kancası showAt DEĞİL updateChrome (prev()'in history hızlı
    # yolu showAt'i çağırmaz ve prev sarmalanamaz: btnPrev listener'ı referansı sentinel'den ÖNCE
    # bağlar). updateChrome HER gezinme yolunda adıyla çağrılır.
    assert "_origUpdateChrome" in html and "state.eb" in html
    assert "_origShowAt" not in html

    plain = Project(id=new_project_id(), title="P", language="tr", owner_key_id="key_local",
                    screens=[{"type": "content_slide", "id": "c1", "title": "X",
                              "body_html": "<p>x</p>"}])
    plain_html = render_html(plain, mode="package", runtime_js=load_runtime_js())
    assert "wrapEvaluate" not in plain_html
    assert "_origUpdateChrome" not in plain_html
    assert "embedWrites" not in plain_html


def test_launcher_auto_completion_writes_no_cmi_status():
    """fix round 2 / FINDING 1 + fix round 3 — launcher'ın KENDİ otomatik tamamlanması cmi'ye
    tamamlanma YAZMAZ: on_view motorun showAt→visited→evaluate akışına bırakılır; time_threshold
    ve on_message ise TAMAMLANMA KİLİDİ ile yalnız GERİ ÇEKİLİR (holdBackWrites — hiçbir girdi
    için "completed" üretemez). Round 2'nin motorun girdisini (state.visited) geri çeken
    `gateVisited` mekanizması KALDIRILDI.

    NOT (dürüstlük): bu DİZGE düzeyi bir kablolama testidir — asıl davranış kanıtı
    tests/js/embed.test.js'teki "EMBED_JS (real template text, mirrored engine)" bloğudur
    (gerçek EMBED_JS metnini yansılanmış bir motorla çalıştırır)."""
    from components.renderer import render_html, load_runtime_js
    emb = Project(id=new_project_id(), title="B", language="tr", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid",
                            "completion": "time_threshold", "min_seconds": 5},
                           {"type": "content_slide", "id": "c1", "title": "X",
                            "body_html": "<p>x</p>"}])
    html = render_html(emb, mode="package", runtime_js=load_runtime_js())
    assert "gatesPending" in html and "holdBackWrites" in html
    # fix round 4 / FIX 1 — sSet SARMALANIR ve sarmalama wrapEvaluate satırından ÖNCE gelir
    # (wrapEvaluate sSet'i DEĞER olarak saklar: sarmalanmışını almalı). Kapı beklerken motorun
    # kendi "completed"i cmi'ye HİÇ yazılmaz (round 3'te yazılıp commit edilip geri çekiliyordu).
    assert "sSet = EMB.wrapSet(sSet, pending, !!S2004)" in html
    assert html.index("EMB.wrapSet(") < html.index("EMB.wrapEvaluate(")
    # fix round 4 / FIX 2 — artifact pini bekleyen kapının ALTINDA. task-5 / FIX 3: bunu AYRI bir
    # katman (`suppressCompletionWrites`) yapıyordu; `wrapSet` onu tamamen kapsadığı için katman
    # SİLİNDİ. Guard TERSİNE çevrildi: bundle'da TANIM yok (aşağıda çağrı da yok — yorum
    # ayıklandıktan sonra `embed_code` üzerinde kontrol edilir).
    assert "function suppressCompletionWrites" not in html
    assert "isCompletionAssertion" in html and "isGatedCompletionWrite" in html
    # FINDING B — on_message ekran BAŞINA defter (eb.m); eb.c global olduğu için ekran atfı yapamaz
    assert "msgGate" in html and "eb.m = eb.m || {}" in html
    # round-2'nin motorun girdisini geri çeken kapısı TAMAMEN gitti (FINDING A/C/D'nin kaynağıydı)
    assert "gateVisited(" not in html          # (yalnız embed.js yorumunda ADI geçer, çağrı YOK)
    # motorun girdisine ARTIK dokunulmuyor: köprünün KODU state.visited'ı ne okur ne yazar
    # (yorum satırlarında geçmişe atıf olarak adı anılır → yorumlar ayıklanarak bakılır)
    embed_js = html.split("Artifact köprüsü (embed_html)")[1]
    embed_code = "\n".join(ln for ln in embed_js.splitlines() if not ln.strip().startswith("//"))
    assert "state.visited" not in embed_code
    # task-5 / FIX 3 — silinen katmanın ÇAĞRI yeri de gitti (adı yalnız gerekçe yorumunda geçer)
    assert "suppressCompletionWrites" not in embed_code
    # round-1 kalıntıları: markSeen köprüden "complete" üretip cmi'ye pinliyordu
    assert "markSeen" not in html
    assert 'bridgeToScorm({scorm:"complete"}' not in html
    # round-1'in cmi-anahtarlı birikim haritası artık YOK; yalnız eski blob'u temizleyen satır var
    assert "state.embedWrites[" not in html
    assert "delete state.embedWrites" in html


def test_embed_html_min_seconds_rejects_negative():
    """fix round 1 / MINOR 5 — negatif min_seconds setTimeout'u anında (gecikmesiz) tetiklerdi."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Project(id=new_project_id(), title="E", owner_key_id="key_local", screens=[
            {"type": "embed_html", "id": "e1", "html_asset_id": "aid",
             "completion": "time_threshold", "min_seconds": -1},
        ])


def test_lms_adapter_shim_only_for_gated_embed_courses():
    """fix round 6 — LMS-adaptör vekili (EMBED_SHIM_JS) YALNIZ KAPILI (on_message/time_threshold)
    embed_html ekranı olan pakete, embed bundle'ından SONRA ve engine_js'ten ÖNCE basılır.

    ÜÇ DURUM ölçülür (round 5'te yalnız 1. ve 3. vardı — test kendi ADINI test etmiyordu):
      1. kapılı embed kursu  → vekil VAR
      2. yalnız on_view embed kursu → vekil YOK (şablon içinde zaten no-op'tu: ~2.5KB ölü script;
         artık Python'da kapıda kesiliyor). embed BUNDLE'ı ise burada da VAR — kesilen yalnız vekil.
      3. embed'siz kurs → vekil YOK ve bundle da YOK (bayt-parite).

    NEDEN engine_js'ten ÖNCE: ENGINE_JS'in bootstrap `showAt(startIdx,false)`'u sentinel'den
    (EMBED_JS) önce koşar ve kapılı kursta LMS'e tam olarak bir `completed`+`Commit` sızdırır;
    vekil motorun ALTINA (SCORM API katmanına) kurulduğu için o pencereyi kapatabilir.
    NEDEN bundle'dan SONRA: bastırma yüklemini `window.SCORMEMBED.isGatedCompletionWrite`
    üzerinden okur (kural tek yerde: components/engine/embed.js).

    NOT (dürüstlük): bu DİZGE düzeyi bir kablolama/sıralama testidir; davranış kanıtı
    tests/js/embed.test.js'teki "EMBED_SHIM_JS (LMS adapter proxy, real template text)"
    bloğudur (gerçek şablon metnini gerçek bir adaptör nesnesiyle çalıştırır)."""
    from components.renderer import render_html, load_runtime_js
    emb = Project(id=new_project_id(), title="B", language="tr", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid",
                            "completion": "time_threshold", "min_seconds": 5}])
    html = render_html(emb, mode="package", runtime_js=load_runtime_js())
    assert "__SCORM_EMBED_SHIM__" in html
    assert "__scormEmbedShim" in html
    assert "isGatedCompletionWrite" in html
    # SIRA: bundle → vekil → motor. (window.SCORMEMBED ataması bundle'ın son satırıdır.)
    assert html.index("window.SCORMEMBED") < html.index("__scormEmbedShim")
    assert html.index("__scormEmbedShim") < html.index("var SCORM_NAME = S2004")
    # DEVİR: EMBED_JS gerçek kilidi (wrapSet) kurar kurmaz vekili bırakır → çift bastırma yok
    assert "window.__SCORM_EMBED_SHIM__.release()" in html
    assert html.index("EMB.wrapSet(") < html.index("window.__SCORM_EMBED_SHIM__.release()")
    # FAILSAFE (fix round 6): bırakma tetiği DOMContentLoaded — TÜM senkron script'lerden (yani
    # ENGINE_JS'ten) SONRA ateşlenmesi GARANTİ. setTimeout(0) değildi: vekil ile {engine_js}
    # arasındaki ~4.5KB + kurs JSON'una bir parser/chunk sınırı düşerse zamanlayıcı motorun
    # bootstrap'inden ÖNCE koşabilir → bastırma erken emekli olur.
    assert 'D.addEventListener("DOMContentLoaded", release)' in html
    assert "setTimeout(release, 0)" in html          # yalnız readyState!=="loading" dalında
    assert html.index('D.readyState !== "loading"') < html.index("setTimeout(release, 0)")
    # ÜST AKIŞTA API YOKSA kurulmaz (ENGINE_JS'in yerel Scorm12API fallback'i bozulmasın)
    assert "if(!real || real.__scormEmbedShim) return;" in html
    # fix round 6 / FIX 2 — metot varlığı ÇAĞRI anında sınanır (kurulumda DEĞİL): geç kurulan
    # adaptörlerde (applet/eklenti) sıfır-metotlu vekil TÜM raporlamayı sessizce yok ederdi.
    assert 'typeof f !== "function"' in html
    assert "for(var j=0;j<ms.length;j++)" in html and 'typeof real[ms[j]]' not in html

    # 2. YALNIZ on_view: vekil basılmaz (şablonda no-op'tu), köprü bundle'ı basılır
    on_view = Project(id=new_project_id(), title="V", language="tr", owner_key_id="key_local",
                      screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid",
                                "completion": "on_view"}])
    on_view_html = render_html(on_view, mode="package", runtime_js=load_runtime_js())
    assert "window.SCORMEMBED" in on_view_html          # bundle YERİNDE (kesilen yalnız vekil)
    assert "isGatedCompletionWrite" in on_view_html     # ...yüklem de bundle'ın içinde
    assert "__SCORM_EMBED_SHIM__ = {" not in on_view_html
    assert "__scormEmbedShim" not in on_view_html
    # ...ve EMBED_JS'in devir satırı korumalı olduğu için vekilsiz kursta patlamaz
    assert "if(window.__SCORM_EMBED_SHIM__) window.__SCORM_EMBED_SHIM__.release();" in on_view_html

    # KARIŞIK kurs (bir on_view + bir time_threshold) → vekil YİNE basılır
    mixed = Project(id=new_project_id(), title="M", language="tr", owner_key_id="key_local",
                    screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid",
                              "completion": "on_view"},
                             {"type": "embed_html", "id": "e2", "html_asset_id": "aid",
                              "completion": "time_threshold", "min_seconds": 5}])
    mixed_html = render_html(mixed, mode="package", runtime_js=load_runtime_js())
    assert "__scormEmbedShim" in mixed_html
    # on_message tek başına da kapıdır
    msg = Project(id=new_project_id(), title="Msg", language="tr", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1", "html_asset_id": "aid",
                            "completion": "on_message"}])
    assert "__scormEmbedShim" in render_html(msg, mode="package", runtime_js=load_runtime_js())

    # 3. embed'siz kurs → ne vekil ne bundle (bayt-parite)
    plain = Project(id=new_project_id(), title="P", language="tr", owner_key_id="key_local",
                    screens=[{"type": "content_slide", "id": "c1", "title": "X",
                              "body_html": "<p>x</p>"}])
    plain_html = render_html(plain, mode="package", runtime_js=load_runtime_js())
    assert "__SCORM_EMBED_SHIM__" not in plain_html
    assert "__scormEmbedShim" not in plain_html
    assert "isGatedCompletionWrite" not in plain_html


def test_lms_adapter_shim_proxies_the_full_scorm_surface():
    """fix round 5 — vekil TAM 8-metotlu SCORM yüzeyini kapsar (her iki sürüm için). Eksik bir
    `LMSGetValue`/`GetLastError`/`GetDiagnostic` motorun tamamını bozardı."""
    from components.templates import EMBED_SHIM_JS
    for m in ("LMSInitialize", "LMSFinish", "LMSGetValue", "LMSSetValue", "LMSCommit",
              "LMSGetLastError", "LMSGetErrorString", "LMSGetDiagnostic"):
        assert f'"{m}"' in EMBED_SHIM_JS
    for m in ("Initialize", "Terminate", "GetValue", "SetValue", "Commit",
              "GetLastError", "GetErrorString", "GetDiagnostic"):
        assert f'"{m}"' in EMBED_SHIM_JS
    # LMS'in KENDİ adaptörü yamalanmaz: yalnız kendi window'umuza vekil konur, çağrılar
    # `this` gerçek adaptöre bağlı olarak yukarı devredilir.
    # (fix round 6: `real[m]` çağrı anında `f`'e alınır — bkz. geç kurulan adaptör)
    assert "var f = real[m];" in EMBED_SHIM_JS
    assert "return f.apply(real, arguments);" in EMBED_SHIM_JS
    # API adı sniff edilir (window.__SCORM_2004__ bu script'ten SONRA atanır)
    assert '"__SCORM_2004__"' not in EMBED_SHIM_JS
    assert 'install("API_1484_11", true)' in EMBED_SHIM_JS and 'install("API", false)' in EMBED_SHIM_JS


async def test_wrap_artifact_html_content_path():
    async with Client(server.mcp) as c:
        out = (await c.call_tool("wrap_artifact", {
            "html_content": "<!doctype html><html><body><h1>Wrap</h1></body></html>",
            "title": "Sar", "scorm_version": "1.2",
        })).data
        assert out["project_id"] and out["screen_id"] and out["asset_id"]
        screens = (await c.call_tool("list_screens", {"project_id": out["project_id"]})).data
        assert any(s.type == "embed_html" for s in screens.screens)


async def test_wrap_artifact_xor_violation():
    from fastmcp.exceptions import ToolError as MCPToolError
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError):
            await c.call_tool("wrap_artifact", {"title": "X"})  # ne html_content ne source_url
        with pytest.raises(MCPToolError):
            await c.call_tool("wrap_artifact", {"html_content": "<p>a</p>", "source_url": "https://x/y.html"})


# --------------------------------------------------------------------------- #
# fix dalgası — wrap_artifact kusurları (her test ilgili düzeltme YOKKEN kırmızı)
# --------------------------------------------------------------------------- #

_ARTIFACT_HTML = b"<!doctype html><html><body><h1>Uzak</h1></body></html>"


def _fake_fetch(content_type: str, body: bytes = _ARTIFACT_HTML):
    """`safe_fetch_asset` yerine geçen sahte — ağ yok, ama GERÇEK mime kapısını çağrı-yerinin
    verdiği `allowed_mimes` ile uygular. (Kapıyı taklit etmezsek test, FIX 1 olmadan da geçer
    ve kritik kusuru yakalamaz.)"""
    from auth import ToolError as AuthToolError
    from auth.ssrf import DEFAULT_ALLOWED_MIMES, _mime_allowed

    async def fake(url, *, max_bytes, allowed_mimes=DEFAULT_ALLOWED_MIMES, **kw):
        assert url.startswith("https://")
        assert max_bytes > 0
        if not _mime_allowed(content_type, allowed_mimes):
            raise AuthToolError("asset_error", f"İzin verilmeyen mime: {content_type}")
        return body, content_type.split(";")[0].strip()

    return fake


async def _count_projects() -> int:
    await server.SVC.ensure()
    return await server.SVC.store.count_projects("key_local")


@pytest.mark.parametrize("content_type", ["text/html", "text/html; charset=utf-8"])
async def test_wrap_artifact_source_url_path(monkeypatch, content_type):
    """FIX 1: source_url yolu gerçekten HTML çekebilmeli (DEFAULT_ALLOWED_MIMES text/html içermez)."""
    monkeypatch.setattr(server, "safe_fetch_asset", _fake_fetch(content_type))
    async with Client(server.mcp) as c:
        out = (await c.call_tool("wrap_artifact", {
            "source_url": "https://artifact.test/app.html", "title": "Uzak",
        })).data
    p = await server.SVC.store.get_project(out["project_id"], "key_local")
    ref = p.asset_by_id(out["asset_id"])
    assert ref.mime == "text/html"
    assert await server.SVC.store.get_asset_bytes(p.id, ref.id) == _ARTIFACT_HTML
    s = next(s for s in p.screens if s.id == out["screen_id"])
    assert s.type == ScreenType.embed_html and s.html_asset_id == ref.id


async def test_wrap_artifact_theme_matches_create_project():
    """FIX 2: tema, create_project ile aynı olmalı (çıplak ThemeTokens() değil)."""
    async with Client(server.mcp) as c:
        pid = (await c.call_tool("create_project", {"title": "Tema"})).data.project_id
        out = (await c.call_tool("wrap_artifact", {
            "html_content": "<!doctype html><p>x</p>", "title": "Tema",
        })).data
    ref_p = await server.SVC.store.get_project(pid, "key_local")
    wrapped = await server.SVC.store.get_project(out["project_id"], "key_local")
    assert wrapped.theme == ref_p.theme
    assert wrapped.theme == server._load_theme("default")


async def test_wrap_artifact_min_seconds_reaches_screen():
    """FIX 3: min_seconds parametresi ekrana ulaşmalı."""
    async with Client(server.mcp) as c:
        out = (await c.call_tool("wrap_artifact", {
            "html_content": "<!doctype html><p>x</p>", "title": "Süre",
            "completion": "time_threshold", "min_seconds": 45,
        })).data
    p = await server.SVC.store.get_project(out["project_id"], "key_local")
    s = next(s for s in p.screens if s.id == out["screen_id"])
    assert s.completion == "time_threshold" and s.min_seconds == 45


async def test_wrap_artifact_rejects_negative_min_seconds():
    """FIX 3: negatif min_seconds → ToolError (ValidationError sızıntısı DEĞİL) ve yetim proje yok."""
    from fastmcp.exceptions import ToolError as MCPToolError
    before = await _count_projects()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as ei:
            await c.call_tool("wrap_artifact", {
                "html_content": "<!doctype html><p>x</p>", "min_seconds": -5,
            })
    assert "invalid_input" in str(ei.value) and "min_seconds" in str(ei.value)
    assert await _count_projects() == before


async def test_wrap_artifact_rejects_time_threshold_with_zero_min_seconds():
    """FIX 3: time_threshold + min_seconds=0 tutarsız kombinasyon → açıkça reddedilir."""
    from fastmcp.exceptions import ToolError as MCPToolError
    before = await _count_projects()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as ei:
            await c.call_tool("wrap_artifact", {
                "html_content": "<!doctype html><p>x</p>", "completion": "time_threshold",
            })
    assert "invalid_input" in str(ei.value)
    assert await _count_projects() == before


async def test_wrap_artifact_fetch_failure_leaves_no_project(monkeypatch):
    """FIX 4: çekim hatasında yaratılmış proje geri alınmalı (kotayı yemesin)."""
    from auth import ToolError as AuthToolError
    from fastmcp.exceptions import ToolError as MCPToolError

    async def boom(url, **kw):
        raise AuthToolError("asset_error", "HTTP 502")

    monkeypatch.setattr(server, "safe_fetch_asset", boom)
    before = await _count_projects()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as ei:
            await c.call_tool("wrap_artifact", {"source_url": "https://artifact.test/x.html"})
    assert "asset_error" in str(ei.value)  # rollback orijinal hatayı maskelemez
    assert await _count_projects() == before


async def test_wrap_artifact_empty_html_content_with_source_url_is_input_error(monkeypatch):
    """FIX 5: XOR artık None'a göre — html_content="" MEVCUT sayılır, source_url ile birlikte
    sessizce yok sayılmak yerine yüksek sesle invalid_input verir."""
    from fastmcp.exceptions import ToolError as MCPToolError
    monkeypatch.setattr(server, "safe_fetch_asset", _fake_fetch("text/html"))
    before = await _count_projects()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as ei:
            await c.call_tool("wrap_artifact", {
                "html_content": "", "source_url": "https://artifact.test/app.html",
            })
    assert "invalid_input" in str(ei.value)  # invalid_html DEĞİL: source_url yok sayılmıyor
    assert await _count_projects() == before


async def test_wrap_artifact_empty_html_content_alone_is_invalid_html():
    """FIX 5: html_content="" tek başına → invalid_html (mevcut ama boş) + yetim proje yok."""
    from fastmcp.exceptions import ToolError as MCPToolError
    before = await _count_projects()
    async with Client(server.mcp) as c:
        with pytest.raises(MCPToolError) as ei:
            await c.call_tool("wrap_artifact", {"html_content": "   "})
    assert "invalid_html" in str(ei.value)
    assert await _count_projects() == before


# --------------------------------------------------------------------------- #
# task-5 fix dalgası — her test ilgili düzeltme YOKKEN kırmızı
# --------------------------------------------------------------------------- #
def _embed_project(**screen):
    from core.project import AssetRef
    base = {"type": "embed_html", "id": "e1", "html_asset_id": "aid"}
    base.update(screen)
    return Project(
        id=new_project_id(), title="Emb", language=screen.pop("language", "tr"),
        owner_key_id="key_local",
        assets=[AssetRef(id="aid", filename="app.html", mime="text/html", size_bytes=4,
                         sha256="0" * 64, rel_path="assets/app.html")],
        screens=[base])


def test_embed_layout_css_present_only_for_embed_courses():
    """task-5 / FIX 1 — `.embed-wrap`/`.embed-frame`/`[data-aspect]` seçicilerini TANIMLAYAN
    hiçbir kural yoktu: iframe UA varsayılanı 300x150'ye, kendi kenarlığı ve kaydırma çubuklarıyla
    düşüyordu. Kurallar OUTLINE_CSS presedanıyla KOŞULLU enjekte edilir → embed'siz kursta hiç yok
    (bayt-parite: tests/test_golden.py + tests/test_outline_menu.py)."""
    from components.renderer import render_html, load_runtime_js
    html = render_html(_embed_project(), mode="package", runtime_js=load_runtime_js())
    assert ".embed-wrap{" in html                      # sarmalayıcı tanımlı
    assert ".embed-frame{border:0" in html             # UA kenarlığı kaldırılır
    assert '.screen[data-type="embed_html"] .screen-inner{' in html
    # `fill` sarmalayicisi SERBEST YUKSEKLIKLI her yerleşimde taban yükseklik almalı, yoksa 0px'e
    # çöker: layout_mode="flow" (sabit tuval yok), stage'in data-fit="flow" geri düşüşü ve <=640px.
    for sel in ('body[data-layout="flow"] .embed-wrap[data-aspect="fill"]{min-height:60vh}',
                'body[data-layout="stage"][data-fit="flow"] .embed-wrap[data-aspect="fill"]'
                '{min-height:60vh}'):
        assert sel in html

    plain = Project(id=new_project_id(), title="P", language="tr", owner_key_id="key_local",
                    screens=[{"type": "content_slide", "id": "c1", "title": "X",
                              "body_html": "<p>x</p>"}])
    plain_html = render_html(plain, mode="package", runtime_js=load_runtime_js())
    assert ".embed-wrap" not in plain_html
    assert ".embed-frame" not in plain_html


@pytest.mark.parametrize("aspect,rule", [
    # her `aspect` değeri KENDİ kuralını üretir — `aspect` alanı pydantic'te doğrulanıyor ve
    # add_screen kabul ediyordu ama hiçbir şey TÜKETMİYORDU (FIX 1'in ikinci yarısı).
    ("fill", '.embed-wrap[data-aspect="fill"]{flex:1 1 auto}'),
    ("16:9", '.embed-wrap[data-aspect="16:9"] .embed-frame{aspect-ratio:16/9}'),
    ("4:3", '.embed-wrap[data-aspect="4:3"] .embed-frame{aspect-ratio:4/3}'),
])
def test_each_aspect_value_has_a_matching_rule(aspect, rule):
    from components.renderer import render_html, load_runtime_js
    html = render_html(_embed_project(aspect=aspect), mode="package",
                       runtime_js=load_runtime_js())
    assert f'data-aspect="{aspect}"' in html      # markup özniteliği
    assert rule in html                            # ve onu TÜKETEN kural


def test_embed_iframe_title_falls_back_to_course_language():
    """task-5 / FIX 8 — başlıksız embed ekranının iframe `title`'ı İngilizce SABİT KODLUYDU."""
    from components.renderer import render_html, load_runtime_js
    tr = render_html(_embed_project(), mode="package", runtime_js=load_runtime_js())
    assert 'title="Gömülü içerik"' in tr
    en_p = _embed_project()
    en_p.language = "en"
    en = render_html(en_p, mode="package", runtime_js=load_runtime_js())
    assert 'title="Embedded content"' in en
    # ekranın kendi başlığı varsa o kazanır (davranış değişmedi)
    named = render_html(_embed_project(title="Uygulama"), mode="package",
                        runtime_js=load_runtime_js())
    assert 'title="Uygulama"' in named


def test_validator_catches_unknown_html_asset_id():
    """task-5 / FIX 2 — `html_asset_id` doğrulayıcının asset alan listesinde YOKTU: hatalı id
    sıfır hata üretiyor, build_package başarılı oluyor, manifest geçerli kalıyor ama assetSrc()
    "" dönüp iframe'e src HİÇ verilmiyordu — üstelik varsayılan on_view ile kurs LMS'e yine
    `completed` raporluyordu (doğrulamayı geçen BOŞ kurs)."""
    from core.validator import validate_project
    bad = Project(id=new_project_id(), title="E", owner_key_id="key_local",
                  screens=[{"type": "embed_html", "id": "e1",
                            "html_asset_id": "asset_DOES_NOT_EXIST"}])
    errs = [e for e in validate_project(bad) if e.path == "screens[0].html_asset_id"]
    assert errs and errs[0].code == "validation_error"
    # tanımlı asset → hata yok (yanlış pozitif yok)
    assert not [e for e in validate_project(_embed_project()) if "html_asset_id" in (e.path or "")]


async def test_wrap_artifact_language_reaches_project_and_output():
    """task-5 / FIX 4 — `wrap_artifact` `language` geçmiyordu → Project.language "tr"ye düşüyor ve
    hiçbir tool onu SONRADAN değiştiremediği için kalıcı oluyordu (İngilizce kullanıcı için
    Türkçe kabuk + Türkçe runtime i18n + Türkçe LOM general/language)."""
    from components.renderer import render_html, load_runtime_js
    async with Client(server.mcp) as c:
        out = (await c.call_tool("wrap_artifact", {
            "html_content": "<h1>Hi</h1>", "title": "App", "language": "en"})).data
        p = await server.SVC.store.get_project(out["project_id"], "key_local")
    assert p.language == "en"
    html = render_html(p, mode="package", runtime_js=load_runtime_js())
    assert '<html lang="en"' in html
    # varsayılan create_project ile AYNI: "tr"
    async with Client(server.mcp) as c:
        out2 = (await c.call_tool("wrap_artifact", {
            "html_content": "<h1>Merhaba</h1>", "title": "App"})).data
        p2 = await server.SVC.store.get_project(out2["project_id"], "key_local")
    assert p2.language == "tr"


def test_embed_html_rejects_empty_asset_id():
    # Nihai review / NEW-2: boş html_asset_id, validator'ın `if ref and ...` kolundan sıyrılıp
    # doğrulamayı geçen BOŞ kurs üretiyordu (iframe src'siz, ama on_view ile yine `completed`).
    # Model seviyesinde reddedilir → add_screen çağrısı ValidationError verir, kurs hiç kurulmaz.
    import pytest as _pytest
    from pydantic import ValidationError as _PydValidationError

    from core.project import EmbedHtmlScreen

    with _pytest.raises(_PydValidationError):
        EmbedHtmlScreen(id="e1", html_asset_id="")
    # dolu id sorunsuz
    assert EmbedHtmlScreen(id="e1", html_asset_id="asset_x").html_asset_id == "asset_x"
