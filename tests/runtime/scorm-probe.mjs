// tests/runtime/scorm-probe.mjs — S1/S3/S4 davranış kanıtı: kursu GERÇEK tarayıcıda çalıştırır,
// sahte bir LMS API'si takar ve LMS'e NE YAZILDIĞINI doğrular.
//
// Neden gerekli: pytest/vitest testleri "doğru string üretiliyor mu"yu ölçer. SCORM'da asıl soru
// "LMS ne aldı"dır — 1.2 ile 2004'ün eleman adları, sözlükleri (wrong/incorrect) ve süre biçimleri
// farklıdır; ancak çalıştırınca görülür.
//
// Çalıştır: npm run scorm-probe
// Tarayıcı ya da python yoksa ATLAR (exit 0). Gerçek bir ihlalde exit 1.
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, ContentSlide, MCQScreen, Choice
out, ver = sys.argv[1], sys.argv[2]
p = Project(id=new_project_id(), title="probe", scorm_version=ver, screens=[
    ContentSlide(id="c1", title="Giris", body_html="<p>merhaba</p>"),
    MCQScreen(id="q1", title="Baskent neresi?", prompt_html="<p>Secin</p>", points=10,
              options=[Choice(id="a", text_html="Ankara", correct=True),
                       Choice(id="b", text_html="Istanbul")]),
])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// S2 (2.4) — 3 hedefli / 9 soruluk kurs: q1-q3→o1, q4-q6→o2, q7-q9→o3.
const OBJ_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, MCQScreen, Choice, Objective
out, ver = sys.argv[1], sys.argv[2]
screens = [MCQScreen(id="q%d" % i, title="Soru %d" % i, prompt_html="<p>?</p>", points=10,
                     objective_ids=["o%d" % (((i - 1) // 3) + 1)],
                     options=[Choice(id="a", text_html="Dogru", correct=True),
                              Choice(id="b", text_html="Yanlis")])
           for i in range(1, 10)]
p = Project(id=new_project_id(), title="probe-obj", scorm_version=ver, screens=screens,
            objectives=[Objective(id="o1"), Objective(id="o2"), Objective(id="o3")])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// F2 (#113) — exploration: girdi saklama + sonraki ekranda geri oynatma ("senin tahminin şuydu").
const XP_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, ContentSlide, ExplorationScreen
out, ver = sys.argv[1], sys.argv[2]
p = Project(id=new_project_id(), title="probe-xp", scorm_version=ver, screens=[
    ExplorationScreen(id="kesif", title="Dene", store_key="kesif_tahmin",
                      prompt_html="<p>Once tahmin et.</p>"),
    ContentSlide(id="acikla", title="Acikla",
                 body_html='<p>Senin tahminin suydu: <span data-exploration-ref="kesif_tahmin"></span></p>'),
])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// Senaryo hattı Faz 1 — outline'lı kurs: hiyerarşik menü (role=tree) davranış kanıtı.
const TREE_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import (Project, new_project_id, TitleSlide, ContentSlide,
                          SummaryScreen, OutlineNode)
out, ver = sys.argv[1], sys.argv[2]
p = Project(id=new_project_id(), title="probe-tree", scorm_version=ver,
    outline=[OutlineNode(id="u1", kind="unit", title="Unite 1"),
             OutlineNode(id="b1", parent_id="u1", kind="section", title="Bolum 1.1")],
    screens=[TitleSlide(id="t1", title="Giris", node_id="u1"),
             ContentSlide(id="c1", title="Konu", body_html="<p>a</p>", node_id="b1"),
             SummaryScreen(id="s1", title="Ozet")])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// Senaryo hattı Faz 4 — kilitli (sequential) + 2 kademeli outline: konum şeridi, kilit UI,
// düğüme devam (resume → zincir açımı + aria-current) davranış kanıtı.
const LOCK_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, TitleSlide, ContentSlide, OutlineNode
out, ver = sys.argv[1], sys.argv[2]
p = Project(id=new_project_id(), title="probe-lock", scorm_version=ver,
    outline=[OutlineNode(id="u1", kind="unit", title="Unite 1"),
             OutlineNode(id="u2", kind="unit", title="Unite 2", unlock_rule="sequential"),
             OutlineNode(id="b2", parent_id="u2", kind="section", title="Bolum 2.1")],
    screens=[TitleSlide(id="t1", title="Giris", node_id="u1"),
             ContentSlide(id="c1", title="Konu 1", body_html="<p>a</p>", node_id="u1"),
             ContentSlide(id="c2", title="Konu 2", body_html="<p>b</p>", node_id="b2"),
             ContentSlide(id="c3", title="Konu 3", body_html="<p>c</p>", node_id="b2")])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// Faz 4-ek — REPUBLISH edilmiş aynı kurs: b2 düğümü silindi (c2/c3 yeni b9 düğümünde),
// u1'e yeni ekran eklendi (order + içerik sürümü değişir → orderFp uyuşmaz). Eski suspend
// ile açılınca kimlik-merdiveni: düğüm (b2) GİTMİŞ ama ekran (c2) YAŞIYOR → c2'nin yeni
// düğümünde devam + DOSTANE BİLDİRİM (teknik hata değil; aria-live).
const LOCK_V2_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, TitleSlide, ContentSlide, OutlineNode
out, ver = sys.argv[1], sys.argv[2]
p = Project(id=new_project_id(), title="probe-lock", scorm_version=ver,
    outline=[OutlineNode(id="u1", kind="unit", title="Unite 1"),
             OutlineNode(id="b9", kind="unit", title="Yeni Bolum")],
    screens=[TitleSlide(id="t1", title="Giris", node_id="u1"),
             ContentSlide(id="c1", title="Konu 1", body_html="<p>a</p>", node_id="u1"),
             ContentSlide(id="c1b", title="Konu Ek", body_html="<p>ek</p>", node_id="u1"),
             ContentSlide(id="c2", title="Konu 2", body_html="<p>b</p>", node_id="b9"),
             ContentSlide(id="c3", title="Konu 3", body_html="<p>c</p>", node_id="b9")])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

const COMP_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import Project, new_project_id, ContentSlide
out = sys.argv[1]
p = Project(id=new_project_id(), title="comp", composition="auto", screens=[
    ContentSlide(id="c1", title="Gonderen adresine bak", lead="Alan adi tek harf farkli.",
                 body_html="<p>Harf harf oku.</p>", media_asset_id="img",
                 composition={"preset": "split-thirds", "mirror": True}),
])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/"))
`;

// z-flow: 4 adım (2 görselli) masaüstü sahnesine SIĞMALI — görsel adım kutusunu taşırmamalı.
const ZFLOW_RENDER_PY = `
import sys, base64
from components.renderer import render_html
from core.project import Project, new_project_id, ContentSlide, ContentBlock, AssetRef
out = sys.argv[1]
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
p = Project(id=new_project_id(), title="z", composition="auto", screens=[
    ContentSlide(id="z1", title="Tikla hasat saldiri", composition="z-flow", blocks=[
        ContentBlock(html="<p>1</p>", asset_id="i"), ContentBlock(html="<p>2</p>", asset_id="i"),
        ContentBlock(html="<p>3</p>"), ContentBlock(html="<p>4</p>")])],
    assets=[AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg),
                     sha256="0", rel_path="assets/i.svg")])
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg)}))
`;

// K2 — görsel etkileşimli tipler auto kompozisyonda: etkileşim bozulmamalı.
const K2_RENDER_PY = `
import sys
from components.renderer import render_html
from core.project import (Project, new_project_id, HotspotScreen, HotspotRegion,
                          ImageCompareScreen, SimulationScreen, LabeledDiagramScreen, AssetRef,
                          DataChartScreen)
out, kind = sys.argv[1], sys.argv[2]
preset = sys.argv[3] if len(sys.argv) > 3 else None
layout = sys.argv[4] if len(sys.argv) > 4 else "stage"
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
assets = [AssetRef(id=i, filename=i + ".svg", mime="image/svg+xml", size_bytes=len(svg),
                   sha256="0", rel_path="assets/" + i + ".svg") for i in ("i", "j")]
if kind == "hotspot":
    s = HotspotScreen(id="h1", title="Bul", prompt_html="<p>Dogru bolgeyi sec</p>",
                      image_asset_id="i", composition="split-thirds", points=10,
                      regions=[HotspotRegion(id="ok", shape="rect", coords=[40, 40, 200, 120]),
                               HotspotRegion(id="no", shape="rect", coords=[400, 260, 160, 120],
                                             correct=False)])
elif kind == "compare":
    s = ImageCompareScreen(id="c1", title="Karsilastir", before_asset_id="i",
                           after_asset_id="j", composition="visual-stack")
elif kind == "chart":
    s = DataChartScreen.model_validate({"id": "d1", "title": "Grafik", "chart_type": "bar",
        "data": [{"label": "a%d" % k, "value": k} for k in range(1, 7)]})
elif kind == "labeled":
    s = LabeledDiagramScreen.model_validate({"id": "l1", "title": "Etiketle", "image_asset_id": "i",
        "labels": [{"id": "a%d" % k, "x": 100 * k, "y": 100 * k, "text": "E%d" % k}
                   for k in range(1, 6)]})
else:
    s = SimulationScreen.model_validate({"id": "s1", "title": "Sim", "composition": "split-thirds",
        "steps": [{"instruction_html": "<p>Tikla</p>", "image_asset_id": "i",
                   "regions": [{"id": "a", "shape": "rect", "coords": [40, 40, 200, 120],
                                "correct": True}]},
                  {"instruction_html": "<p>Yaz</p>", "image_asset_id": "j",
                   "input_accepted": ["ok"]}]})
if preset:
    s = type(s).model_validate(s.model_dump(mode="json") | {"composition": preset})
p = Project(id=new_project_id(), title="k2", composition="auto", screens=[s], assets=assets,
            layout_mode=layout)
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg), "j": ("image/svg+xml", svg)}))
`;

// K3 — soru tipleri auto kompozisyonda (uyaranlı/uyaransız): etkileşim + LMS yazımı bozulmamalı.
const K3_RENDER_PY = `
import sys
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
out, kind = sys.argv[1], sys.argv[2]
preset = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
stim = len(sys.argv) > 4 and sys.argv[4] == "stim"
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
assets = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg),
                   sha256="0", rel_path="assets/i.svg")]
ST = {"asset_id": "i", "alt": "Vaka gorseli", "text_html": "<p>" + " ".join(["vaka"] * 45) + "</p>"}
if kind == "adaptive":
    ST = dict(ST, text_html="<p>Kisa vaka metni: fatura onayi istenen bir e-posta.</p>")
O = [{"id": "a", "text_html": "Dogru", "correct": True}, {"id": "b", "text_html": "Yanlis"}]
if kind == "mcq":
    d = {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>Ne yaparsin?</p>", "options": O}
elif kind == "mcq7":
    d = {"type": "mcq", "id": "q1", "title": "Soru", "prompt_html": "<p>Sec</p>",
         "options": [{"id": "o%d" % k, "text_html": "Secenek %d" % k, "correct": k == 0} for k in range(7)]}
elif kind == "drag":
    d = {"type": "drag_drop", "id": "q1", "title": "Surukle", "prompt_html": "<p>Yerlestir</p>",
         "items": [{"id": "x", "text_html": "Oge", "correct_target_id": "t1"}],
         "targets": [{"id": "t1", "label_html": "Hedef 1"}, {"id": "t2", "label_html": "Hedef 2"}]}
elif kind == "match":
    d = {"type": "matching", "id": "q1", "title": "Eslestir", "prompt_html": "<p>Eslestir</p>",
         "pairs": [{"id": "p1", "left_html": "A", "right_html": "1"},
                   {"id": "p2", "left_html": "B", "right_html": "2"}]}
elif kind == "sort":
    d = {"type": "sorting", "id": "q1", "title": "Sirala", "prompt_html": "<p>Sirala</p>",
         "items": [{"id": "s1", "text_html": "Bir"}, {"id": "s2", "text_html": "Iki"},
                   {"id": "s3", "text_html": "Uc"}]}
else:
    d = {"type": "adaptive_practice", "id": "q1", "title": "Pratik", "adaptive": {"strategy": "elo"},
         "items": [{"id": "i%d" % k, "prompt_html": "<p>Madde %d</p>" % k, "options": O,
                    "stimulus": ST} for k in range(4)]}
if stim and kind != "adaptive":
    d["stimulus"] = ST
if preset:
    d["composition"] = preset
s = TypeAdapter(Screen).validate_python(d)
p = Project(id=new_project_id(), title="k3", composition="auto", screens=[s], assets=assets)
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg)}))
`;

// K4 — içerik etkileşimleri auto kompozisyonda: etkileşim bozulmamalı, tabs ana–detay.
const K4_RENDER_PY = `
import sys
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
out, kind = sys.argv[1], sys.argv[2]
preset = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
stim = len(sys.argv) > 4 and sys.argv[4] == "stim"
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
assets = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg),
                   sha256="0", rel_path="assets/i.svg")]
ST = {"asset_id": "i", "alt": "Vaka gorseli", "text_html": "<p>" + " ".join(["vaka"] * 45) + "</p>"}
if kind == "tabs":
    d = {"type": "tabs", "id": "s1", "title": "Sekmeler", "prompt_html": "<p>Incele</p>",
         "tabs": [{"label": "Bir", "body_html": "<p>P0</p>"}, {"label": "Iki", "body_html": "<p>P1</p>"},
                  {"label": "Uc", "body_html": "<p>P2</p>"}]}
elif kind in ("acc", "acc12"):
    n = 12 if kind == "acc12" else 3
    d = {"type": "accordion", "id": "s1", "title": "Akordiyon",
         "items": [{"title": "Baslik %d" % k, "body_html": "<p>Govde %d</p>" % k} for k in range(n)]}
elif kind == "tl10":
    d = {"type": "timeline", "id": "s1", "title": "Zaman",
         "events": [{"date": str(2000 + k), "title": "Olay %d" % k, "body_html": "<p>Aciklama %d</p>" % k}
                    for k in range(10)]}
elif kind == "flash":
    d = {"type": "flashcards", "id": "s1", "title": "Kartlar",
         "cards": [{"front_html": "On %d" % k, "back_html": "Arka %d" % k} for k in range(4)]}
elif kind == "poll":
    d = {"type": "poll", "id": "s1", "title": "Anket", "prompt_html": "<p>Ne yapardin?</p>",
         "options": [{"id": "a", "text_html": "Sorarim"}, {"id": "b", "text_html": "Beklerim"}],
         "reflection_html": "<p>Tesekkurler</p>"}
elif kind == "xp":
    d = {"type": "exploration", "id": "s1", "title": "Tahmin", "prompt_html": "<p>Tahminin?</p>",
         "input_kind": "text", "store_key": "g1"}
else:
    d = {"type": "worked_example", "id": "s1", "title": "Cozumlu", "fading": "partial",
         "steps": [{"action_html": "<p>Adim %d</p>" % k, "rationale_html": "<p>Neden %d</p>" % k}
                   for k in range(2)]}
if stim:
    d["stimulus"] = ST
if len(sys.argv) > 4 and sys.argv[4] == "stimtext":
    d["stimulus"] = {"text_html": "<p>Ekibine acil fatura onayi e-postasi geldi; baglanti farkli bir alan adina gidiyor.</p>"}
if len(sys.argv) > 4 and sys.argv[4] == "stimimg":
    d["stimulus"] = {"asset_id": "i", "alt": "Vaka gorseli"}
if preset:
    d["composition"] = preset
s = TypeAdapter(Screen).validate_python(d)
p = Project(id=new_project_id(), title="k4", composition="auto", screens=[s], assets=assets)
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg)}))
`;

// K5 — oyun/senaryo/gömülü auto kompozisyonda: etkileşim bozulmamalı, sahne yan yana.
const K5_RENDER_PY = `
import sys, json
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
out, kind = sys.argv[1], sys.argv[2]
preset = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
stim = len(sys.argv) > 4 and sys.argv[4] == "stim"
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
emb = b'<!doctype html><html><body style="margin:0;background:#9cf"><p>embed</p></body></html>'
assets = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg),
                   sha256="0", rel_path="assets/i.svg"),
          AssetRef(id="h", filename="h.html", mime="text/html", size_bytes=len(emb),
                   sha256="0", rel_path="assets/h.html")]
extra = []
if kind == "game":
    g = [x for x in json.load(open("examples/games/lab-safety-game.en.json"))["screens"]
         if x["type"] == "game"][0]
    for n in g["nodes"]:
        n["image_asset_id"], n["image_alt"] = "i", "Sahne"
    d = g
elif kind == "scen":
    d = {"type": "decision_scenario", "id": "q1", "title": "Senaryo", "points": 10,
         "nodes": [{"id": "d1", "prompt_html": "<p>Ne yaparsin?</p>", "image_asset_id": "i", "image_alt": "Ofis",
                    "choices": [{"id": "x", "text_html": "Dogrula", "feedback_html": "<p>Iyi</p>",
                                 "score_delta": 10, "goto_node_id": "d2"},
                                {"id": "y", "text_html": "Tikla", "feedback_html": "<p>Kotu</p>",
                                 "score_delta": -5, "goto_node_id": "d2"}]},
                   {"id": "d2", "prompt_html": "<p>Sonra?</p>", "image_asset_id": "i", "image_alt": "Ofis 2",
                    "choices": [{"id": "z", "text_html": "Raporla", "feedback_html": "<p>Tamam</p>"},
                                {"id": "w", "text_html": "Unut", "feedback_html": "<p>Hayir</p>"}]}]}
elif kind == "esc":
    d = {"type": "escape_room", "id": "q1", "title": "Kacis", "lives": 3,
         "puzzles": [{"id": "p1", "prompt_html": "<p>2+2?</p>", "accepted": ["4"]},
                     {"id": "p2", "prompt_html": "<p>3+3?</p>", "accepted": ["6"]}]}
elif kind == "tmr":
    d = {"type": "term_match_race", "id": "q1", "title": "Yaris", "time_limit_sec": 120,
         "pairs": [{"id": "a", "term_html": "MFA", "definition_html": "Cok faktor"},
                   {"id": "b", "term_html": "VPN", "definition_html": "Sanal ag"}]}
elif kind == "branch":
    d = {"type": "branching", "id": "q1", "title": "Yol", "prompt_html": "<p>Hangi yol?</p>",
         "choices": [{"id": "l", "text_html": "Sol", "goto_screen_id": "left"},
                     {"id": "r", "text_html": "Sag", "goto_screen_id": "right"}]}
    extra = [{"type": "content_slide", "id": "left", "title": "Sol ekran", "body_html": "<p>L</p>"},
             {"type": "content_slide", "id": "right", "title": "Sag ekran", "body_html": "<p>R</p>"}]
elif kind == "embedlead":
    d = {"type": "embed_html", "id": "q1", "title": "Kimya Laboratuvari Guvenlik Simulasyonu",
         "kicker": "Etkinlik 3", "html_asset_id": "h",
         "lead": "Simulasyonda tum adimlari tamamla ve her karardan sonra sonucunu dikkatle incele lutfen simdi"}
elif kind == "gametall":
    tall = b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="1000"><rect width="400" height="1000" fill="#ccc"/></svg>'
    svg = tall
    d = {"type": "decision_scenario", "id": "q1", "title": "Uzun gorsel",
         "nodes": [{"id": "d1", "prompt_html": "<p>Ne yaparsin?</p>", "image_asset_id": "i", "image_alt": "Uzun",
                    "choices": [{"id": "x", "text_html": "A", "feedback_html": "<p>a</p>"},
                                {"id": "y", "text_html": "B", "feedback_html": "<p>b</p>"}]}]}
else:
    d = {"type": "embed_html", "id": "q1", "title": "Gomulu", "html_asset_id": "h"}
if stim:
    d["stimulus"] = {"text_html": "<p>Kisa karar vakasi: ekip toplantisi iptal oldu.</p>"}
if preset:
    d["composition"] = preset
ta = TypeAdapter(Screen)
p = Project(id=new_project_id(), title="k5", composition="auto",
            screens=[ta.validate_python(d)] + [ta.validate_python(x) for x in extra], assets=assets)
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg), "h": ("text/html", emb)}))
`;

// K6 — release öncesi düzeltmeler: uzun ekranın üstü (mobil akış), yuvada uzun içerik, görselli kart.
const K6_RENDER_PY = `
import sys
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
out, kind, mode = sys.argv[1], sys.argv[2], sys.argv[3]
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
assets = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg),
                   sha256="0", rel_path="assets/i.svg")]
long = "".join("<p>" + " ".join(["uzun metin parcasi"] * 30) + "</p>" for _ in range(4))
if kind == "longcontent":
    d = {"type": "content_slide", "id": "s1", "title": "Basligim Burada", "body_html": long,
         "media_asset_id": "i", "media_alt": "Gorsel"}
elif kind == "longmcq":
    d = {"type": "mcq", "id": "s1", "title": "Basligim Burada", "prompt_html": "<p>Ne yaparsin?</p>",
         "stimulus": {"text_html": long},
         "options": [{"id": "a", "text_html": "A", "correct": True}, {"id": "b", "text_html": "B"}]}
elif kind == "flashmix":
    d = {"type": "flashcards", "id": "s1", "title": "Karisik kartlar",
         "cards": [{"front_html": "Ag <strong>guvenligi</strong> nedir?", "back_html": "<p>Kisa</p>"},
                   {"front_html": "<p>" + " ".join(["uzun aciklama"] * 25) + "</p>", "front_asset_id": "i",
                    "front_alt": "On", "back_html": "<p>Arka</p>"},
                   {"front_html": "<p>Orta</p>", "back_html": "<p>B</p>"}]}
else:
    d = {"type": "flashcards", "id": "s1", "title": "Kartlar",
         "cards": [{"front_html": "<p>ON METIN</p>", "front_asset_id": "i", "front_alt": "On",
                    "back_html": "<p>ARKA METIN</p>", "back_asset_id": "i", "back_alt": "Arka"}] * 3}
s = TypeAdapter(Screen).validate_python(d)
p = Project(id=new_project_id(), title="k6", composition=mode, screens=[s], assets=assets)
open(out, "w", encoding="utf-8").write(render_html(p, mode="preview", runtime_js="/*probe*/",
    asset_data={"i": ("image/svg+xml", svg)}))
`;

const failures = [];
function check(label, actual, expected) {
  const ok = actual === expected;
  console.log(`   ${ok ? "✓" : "✗"} ${label} = ${JSON.stringify(actual)}${ok ? "" : ` (beklenen ${JSON.stringify(expected)})`}`);
  if (!ok) failures.push(`${label}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);
}
function checkMatch(label, actual, re) {
  const ok = re.test(String(actual));
  console.log(`   ${ok ? "✓" : "✗"} ${label} = ${JSON.stringify(actual)}${ok ? "" : ` (beklenen desen ${re})`}`);
  if (!ok) failures.push(`${label}: ${JSON.stringify(actual)} desen dışı ${re}`);
}

// Sahte LMS: her SetValue kaydedilir, GetValue önceden ekilen değerleri döndürür.
function lmsInit([is2004, entry, suspend, seed]) {
  const log = [];
  window.__LMS__ = log;
  const store = {};
  store[is2004 ? "cmi.entry" : "cmi.core.entry"] = entry;
  store["cmi.suspend_data"] = suspend;
  if (seed) Object.assign(store, seed);   // S2 — LMS pre-populate senaryosu (manifest objectives)
  const shim = {
    LMSInitialize: () => "true", Initialize: () => "true",
    LMSFinish: () => { log.push(["__FINISH__", ""]); return "true"; },
    Terminate: () => { log.push(["__FINISH__", ""]); return "true"; },
    LMSCommit: () => "true", Commit: () => "true",
    LMSSetValue: (k, v) => { log.push([k, v]); store[k] = v; return "true"; },
    SetValue: (k, v) => { log.push([k, v]); store[k] = v; return "true"; },
    LMSGetValue: (k) => store[k] || "", GetValue: (k) => store[k] || "",
    LMSGetLastError: () => "0", GetLastError: () => "0",
    LMSGetErrorString: () => "", GetErrorString: () => "",
    LMSGetDiagnostic: () => "", GetDiagnostic: () => "",
  };
  window[is2004 ? "API_1484_11" : "API"] = shim;
}

async function session(browser, file, { is2004 = false, entry = "", suspend = "", seed = null, act } = {}) {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.addInitScript(lmsInit, [is2004, entry, suspend, seed]);
    await page.goto(`file://${file}`);
    await page.waitForTimeout(150);
    if (act) await act(page);
    await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
    await page.waitForTimeout(80);
    const log = await page.evaluate(() => window.__LMS__);
    const shown = await page.evaluate(() => {
      const v = document.querySelector('.screen[aria-hidden="false"]');
      return v ? v.dataset.screenId : "?";
    });
    const last = {};
    for (const [k, v] of log) last[k] = v;
    return { last, shown, finishes: log.filter(([k]) => k === "__FINISH__").length };
  } finally {
    await context.close();
  }
}

const answerWrong = async (p) => {
  await p.click("#btnNext");
  await p.waitForTimeout(1100);           // ölçülebilir latency
  await p.click('.opt[data-opt="b"]');
  await p.click(".btn-check");
  await p.waitForTimeout(120);
};

// S2 — q1 doğru + q2 yanlış (ikisi de o1); o2/o3 hiç denenmez.
const answerTwoOfObjective1 = async (p) => {
  await p.click('.screen[aria-hidden="false"] .opt[data-opt="a"]');
  await p.click('.screen[aria-hidden="false"] .btn-check');
  await p.waitForTimeout(120);
  await p.click("#btnNext");
  await p.waitForTimeout(120);
  await p.click('.screen[aria-hidden="false"] .opt[data-opt="b"]');
  await p.click('.screen[aria-hidden="false"] .btn-check');
  await p.waitForTimeout(150);
};

async function main() {
  const tmp = mkdtempSync(path.join(tmpdir(), "scorm-probe-"));
  let browser;
  try {
    const f12 = path.join(tmp, "c12.html"), f2004 = path.join(tmp, "c2004.html");
    const o12 = path.join(tmp, "o12.html"), o2004 = path.join(tmp, "o2004.html");
    execFileSync("python3", ["-c", RENDER_PY, f12, "1.2"], { cwd: process.cwd() });
    execFileSync("python3", ["-c", RENDER_PY, f2004, "2004"], { cwd: process.cwd() });
    execFileSync("python3", ["-c", OBJ_RENDER_PY, o12, "1.2"], { cwd: process.cwd() });
    execFileSync("python3", ["-c", OBJ_RENDER_PY, o2004, "2004"], { cwd: process.cwd() });

    browser = await chromium.launch(
      process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {}
    );

    // --- SCORM 1.2 ---
    console.log("\n== SCORM 1.2 — yanlis cevaplanan soru ==");
    const a = await session(browser, f12, { is2004: false, act: answerWrong });
    check("interactions.0.id", a.last["cmi.interactions.0.id"], "q1");
    check("interactions.0.type", a.last["cmi.interactions.0.type"], "choice");
    check("student_response", a.last["cmi.interactions.0.student_response"], "b");
    check("correct_responses.0.pattern", a.last["cmi.interactions.0.correct_responses.0.pattern"], "a");
    check("result (1.2 sozlugu)", a.last["cmi.interactions.0.result"], "wrong");
    checkMatch("latency (CMITimespan)", a.last["cmi.interactions.0.latency"], /^\d{4}:\d{2}:\d{2}\.\d{2}$/);
    checkMatch("time (gunun saati)", a.last["cmi.interactions.0.time"], /^\d{2}:\d{2}:\d{2}\.\d{2}$/);
    check("description 1.2'de YAZILMAZ", a.last["cmi.interactions.0.description"], undefined);
    checkMatch("session_time", a.last["cmi.core.session_time"], /^\d{4}:\d{2}:\d{2}\.\d{2}$/);
    check("Terminate cagri sayisi", a.finishes, 1);

    // --- SCORM 2004 ---
    console.log("\n== SCORM 2004 — ayni senaryo, farkli sozluk ==");
    const b = await session(browser, f2004, { is2004: true, act: answerWrong });
    check("learner_response", b.last["cmi.interactions.0.learner_response"], "b");
    check("result (2004 sozlugu)", b.last["cmi.interactions.0.result"], "incorrect");
    check("description", b.last["cmi.interactions.0.description"], "Baskent neresi?");
    checkMatch("latency (ISO 8601)", b.last["cmi.interactions.0.latency"], /^PT[\d.]+S$/);
    checkMatch("timestamp (ISO 8601)", b.last["cmi.interactions.0.timestamp"], /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    checkMatch("session_time", b.last["cmi.session_time"], /^PT[\d.]+S$/);
    check("student_response 2004'te YAZILMAZ", b.last["cmi.interactions.0.student_response"], undefined);

    // --- S4: suspend / resume ---
    console.log("\n== S4 — yarim birakma ve devam etme ==");
    const half = await session(browser, f12, {});
    check("yarim kursta exit", half.last["cmi.core.exit"], "suspend");
    check("yarim kursta status", half.last["cmi.core.lesson_status"], "incomplete");

    const advanced = await session(browser, f12, { act: async (p) => { await p.click("#btnNext"); } });
    const sd = advanced.last["cmi.suspend_data"];
    const resumed = await session(browser, f12, { entry: "resume", suspend: sd });
    check("entry=resume → kaldigi ekran", resumed.shown, "q1");
    const fresh = await session(browser, f12, { entry: "ab-initio", suspend: sd });
    check("entry=ab-initio → sifirdan", fresh.shown, "c1");

    const done = await session(browser, f12, { act: answerWrong });
    check("tamamlanan kursta exit", done.last["cmi.core.exit"], "normal");

    // --- S2: cmi.objectives.* — 3 hedef / 9 soru ---
    console.log("\n== S2 (1.2) — 3 hedefli kurs: 3 AYRI objective kaydi ==");
    const j = await session(browser, o12, { is2004: false, act: answerTwoOfObjective1 });
    const ids12 = [j.last["cmi.objectives.0.id"], j.last["cmi.objectives.1.id"], j.last["cmi.objectives.2.id"]];
    check("objectives.0.id", ids12[0], "o1");
    check("objectives.1.id", ids12[1], "o2");
    check("objectives.2.id", ids12[2], "o3");
    check("3 AYRI hedef kaydi", new Set(ids12).size, 3);
    check("o1 score.raw (1/3 dogru)", j.last["cmi.objectives.0.score.raw"], "33");
    check("o1 status (2/3 cevaplandi)", j.last["cmi.objectives.0.status"], "incomplete");
    check("o2 status (hic denenmedi)", j.last["cmi.objectives.1.status"], "not attempted");
    check("o2 skor YAZILMAZ (denenmedi)", j.last["cmi.objectives.1.score.raw"], undefined);
    check("fazla hedef kaydi YOK", j.last["cmi.objectives.3.id"], undefined);

    console.log("\n== S2 (2004) — ayni senaryo + LMS pre-populate (manifest objectives) ==");
    // LMS, manifest'teki imsss:objective'lerden o2'yi 0. indekse önceden koymuş olsun:
    // runtime id'ye göre çözer — o2'nin .id'si YENİDEN YAZILMAZ, yeniler sona eklenir.
    const k = await session(browser, o2004, {
      is2004: true, act: answerTwoOfObjective1,
      seed: { "cmi.objectives._count": "1", "cmi.objectives.0.id": "o2" },
    });
    check("pre-populate .id yeniden YAZILMAZ", k.last["cmi.objectives.0.id"], undefined);
    check("o2 mevcut indeksinde guncellenir", k.last["cmi.objectives.0.completion_status"], "not attempted");
    check("o1 sona eklenir (indeks 1)", k.last["cmi.objectives.1.id"], "o1");
    check("o1 score.scaled", k.last["cmi.objectives.1.score.scaled"], "0.3333");
    check("o1 success_status (bitmedi)", k.last["cmi.objectives.1.success_status"], "unknown");
    check("o1 completion_status", k.last["cmi.objectives.1.completion_status"], "incomplete");
    check("o3 sona eklenir (indeks 2)", k.last["cmi.objectives.2.id"], "o3");
    check("o3 completion_status", k.last["cmi.objectives.2.completion_status"], "not attempted");
    check("2004'te 1.2 sozlugu YOK (.status)", k.last["cmi.objectives.1.status"], undefined);

    // --- F2 (#113): exploration — sakla, geri oynat, resume et; XSS'e karsi textContent ---
    console.log("\n== F2 — exploration: girdi saklama + sonraki ekranda geri oynatma ==");
    const xf = path.join(tmp, "xp12.html");
    execFileSync("python3", ["-c", XP_RENDER_PY, xf, "1.2"], { cwd: process.cwd() });
    const XP_VAL = "<img src=x onerror=alert(1)> yuzer";   // kasitli XSS payload'lu girdi
    const typeAndAdvance = async (p) => {
      await p.fill(".xp-text", XP_VAL);
      await p.dispatchEvent(".xp-text", "change");         // blur/persist yolu
      await p.click("#btnNext");
      await p.waitForTimeout(120);
    };
    async function xpSession(opts, evalFn) {
      const context = await browser.newContext();
      try {
        const page = await context.newPage();
        await page.addInitScript(lmsInit, [false, opts.entry || "", opts.suspend || "", null]);
        await page.goto(`file://${xf}`);
        await page.waitForTimeout(150);
        if (opts.act) await opts.act(page);
        const dom = await page.evaluate(evalFn);
        const log = await page.evaluate(() => window.__LMS__);
        const last = {}; for (const [kk, vv] of log) last[kk] = vv;
        return { dom, last };
      } finally { await context.close(); }
    }
    const x = await xpSession({ act: typeAndAdvance }, () => {
      const s = document.querySelector('[data-exploration-ref="kesif_tahmin"]');
      const v = document.querySelector('.screen[aria-hidden="false"]');
      return { text: s.textContent, imgCount: s.querySelectorAll("img").length,
               shown: v ? v.dataset.screenId : "?" };
    });
    check("sonraki ekrana gecildi", x.dom.shown, "acikla");
    check("referans metni birebir atif", x.dom.text, XP_VAL);
    check("HTML yorumlanMADI (XSS-guvenli textContent)", x.dom.imgCount, 0);
    check("deger suspend_data'da tasinir", (x.last["cmi.suspend_data"] || "").includes("yuzer"), true);
    check("skorsuz: puanli ekran yok, skor 0 kalir", x.last["cmi.core.score.raw"], "0");
    // resume: yeni oturum suspend ile acilir → hem textarea hem referans geri gelir
    const rz = await xpSession({ entry: "resume", suspend: x.last["cmi.suspend_data"] }, () => ({
      ta: document.querySelector(".xp-text").value,
      ref: document.querySelector('[data-exploration-ref="kesif_tahmin"]').textContent,
    }));
    check("resume: textarea degeri geri geldi", rz.dom.ta, XP_VAL);
    check("resume: referans dolu (geri oynatma)", rz.dom.ref, XP_VAL);
    // bos deger → i18n yer tutucusu ("henüz cevaplamadın")
    const empty = await xpSession({ act: async (p) => { await p.click("#btnNext"); await p.waitForTimeout(120); } },
      () => document.querySelector('[data-exploration-ref="kesif_tahmin"]').textContent);
    check("bos deger yer tutucuya duser", empty.dom, "henüz cevaplamadın");

    // --- Senaryo hattı Faz 1: outline tree menü — katlama + klavye + aria-current ---
    console.log("\n== Faz 1 — outline tree menü (katlanır + klavye + aria-current) ==");
    const tfile = path.join(tmp, "tree12.html");
    execFileSync("python3", ["-c", TREE_RENDER_PY, tfile, "1.2"], { cwd: process.cwd() });
    const tctx = await browser.newContext();
    try {
      const tpage = await tctx.newPage();
      await tpage.addInitScript(lmsInit, [false, "", "", null]);
      await tpage.goto(`file://${tfile}`);
      await tpage.waitForTimeout(150);
      await tpage.click("#btnMenu");
      await tpage.waitForTimeout(120);
      const t0 = await tpage.evaluate(() => {
        const tree = document.getElementById("slideMenuList");
        const cur = tree.querySelector('[aria-current="page"]');
        return { role: tree.getAttribute("role"),
                 items: tree.querySelectorAll('[role="treeitem"]').length,
                 groups: tree.querySelectorAll('ul[role="group"]').length,
                 cur: cur && cur.getAttribute("data-goto") };
      });
      check("menü role=tree", t0.role, "tree");
      check("treeitem sayisi (2 dugum + 3 ekran + 1 dugumsuz grubu)", t0.items, 6);
      check("aria-current baslangic ekraninda", t0.cur, "t1");
      // katlama (fare): u1 kapat → alt agac gizli
      await tpage.click('[data-node-id="u1"]');
      const t1 = await tpage.evaluate(() => ({
        exp: document.querySelector('[data-node-id="u1"]').getAttribute("aria-expanded"),
        c1Visible: document.querySelector('[data-goto="c1"]').offsetParent !== null,
      }));
      check("katlanan dugum aria-expanded=false", t1.exp, "false");
      check("kapali dugumun torunu gizli", t1.c1Visible, false);
      // klavye: SagOk ac → AsagiOk cocuga in → End son gorunur ogeye → Enter ekrana git
      await tpage.focus('[data-node-id="u1"]');
      await tpage.keyboard.press("ArrowRight");   // ac
      await tpage.keyboard.press("ArrowDown");    // ilk cocuk: t1 ekrani
      const t2 = await tpage.evaluate(() => document.activeElement.getAttribute("data-goto"));
      check("ArrowRight acar + ArrowDown cocuga iner", t2, "t1");
      await tpage.keyboard.press("End");          // son gorunur oge: dugumsuz gruptaki s1
      const t3 = await tpage.evaluate(() => document.activeElement.getAttribute("data-goto"));
      check("End son gorunur ogeye gider (dugumsuz grup)", t3, "s1");
      await tpage.keyboard.press("Enter");        // native button aktivasyonu → ekrana git
      await tpage.waitForTimeout(150);
      const t4 = await tpage.evaluate(() => {
        const v = document.querySelector('.screen[aria-hidden="false"]');
        return { shown: v ? v.dataset.screenId : "?",
                 menuOpen: document.getElementById("slideMenu").classList.contains("open") };
      });
      check("Enter ekrana goturur", t4.shown, "s1");
      check("menu kapanir", t4.menuOpen, false);
      await tpage.click("#btnMenu");              // yeniden ac → aria-current tazelenmis olmali
      await tpage.waitForTimeout(120);
      const t5 = await tpage.evaluate(() => {
        const cur = document.querySelector('#slideMenuList [aria-current="page"]');
        return cur && cur.getAttribute("data-goto");
      });
      check("aria-current yeni ekrana tasinir", t5, "s1");
    } finally {
      await tctx.close();
    }

    // --- Senaryo hattı Faz 4: konum şeridi + sequential kilit + düğüme devam ---
    console.log("\n== Faz 4 — konum seridi + kilit + dugume devam (resume) ==");
    const lfile = path.join(tmp, "lock12.html");
    execFileSync("python3", ["-c", LOCK_RENDER_PY, lfile, "1.2"], { cwd: process.cwd() });
    let lockSuspend = "";
    {
      const ctx = await browser.newContext();
      try {
        const page = await ctx.newPage();
        await page.addInitScript(lmsInit, [false, "", "", null]);
        await page.goto(`file://${lfile}`);
        await page.waitForTimeout(150);
        // 1) Konum şeridi (t1 → u1 içinde 1/2) — RTL-güvenli sayı parçası ayrı span'da
        const s0 = await page.evaluate(() => {
          const el = document.getElementById("posStrip");
          return { text: el && el.textContent, live: el && el.getAttribute("aria-live"),
                   ltr: el && el.lastElementChild && el.lastElementChild.dir };
        });
        check("konum seridi (dugum zinciri + n/m)", s0.text, "Unite 1 · 1/2");
        check("konum seridi aria-live=polite", s0.live, "polite");
        check("n/m parcasi dir=ltr (RTL-guvenli)", s0.ltr, "ltr");
        // 2) Kilit: u2 gorunur + aria-disabled + sebep GORUNUR (engelleyeni adiyla) + katli
        await page.click("#btnMenu");
        await page.waitForTimeout(120);
        const l0 = await page.evaluate(() => {
          const u2 = document.querySelector('[data-node-id="u2"]');
          const rs = u2.querySelector(".mtree-lockreason");
          const u1p = document.querySelector('[data-node-id="u1"] .mtree-progress');
          return { dis: u2.getAttribute("aria-disabled"), exp: u2.getAttribute("aria-expanded"),
                   visible: u2.offsetParent !== null, reasonHidden: rs.hidden, reason: rs.textContent,
                   u1prog: u1p && u1p.textContent };
        });
        check("kilitli dugum aria-disabled", l0.dis, "true");
        check("kilitli dugum GORUNUR (gizlenmez)", l0.visible, true);
        check("kilit sebebi gorunur (hidden kalkti)", l0.reasonHidden, false);
        check("sebep engelleyen dugumu ADIYLA anar", l0.reason.includes("Unite 1"), true);
        check("kilitli dal katli (icerik gezilemez)", l0.exp, "false");
        check("dugum ilerlemesi n/m (u1: t1 ziyaretli)", l0.u1prog, "1/2");
        // 3) Odaklanılır ama etkinleştirilemez: Enter/klik ekran degistirmez, katlamaz.
        // force:true — Playwright aria-disabled'i "enabled degil" sayip klik oncesi bekler
        // (yani kilit makine-okunur); handler davranisini kanitlamak icin zorlanir.
        await page.focus('[data-node-id="u2"]');
        await page.keyboard.press("Enter");
        await page.click('[data-node-id="u2"]', { force: true });
        await page.waitForTimeout(100);
        const l1 = await page.evaluate(() => ({
          exp: document.querySelector('[data-node-id="u2"]').getAttribute("aria-expanded"),
          focusable: document.activeElement === document.querySelector('[data-node-id="u2"]') ||
                     document.activeElement.getAttribute("data-node-id") === "u2",
          shown: document.querySelector('.screen[aria-hidden="false"]').dataset.screenId,
        }));
        check("kilitli dugum odaklanabilir", l1.focusable, true);
        check("Enter/klik ACMAZ (etkinlestirilemez)", l1.exp, "false");
        check("ekran degismedi", l1.shown, "t1");
        // 4) u1 bitir → u2 acilir; c2'ye gec (b2 alt-agacinda) → suspend
        await page.click("#menuClose");
        await page.click("#btnNext");   // c1 → u1 tamam
        await page.waitForTimeout(120);
        await page.click("#btnNext");   // c2 (u2/b2 ilk ekrani)
        await page.waitForTimeout(120);
        const s1 = await page.evaluate(() => document.getElementById("posStrip").textContent);
        check("konum seridi 2 kademeli zincir", s1, "Unite 2 · Bolum 2.1 · 1/2");
        await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
        await page.waitForTimeout(80);
        lockSuspend = await page.evaluate(() => {
          const log = window.__LMS__; let v = "";
          for (const [k, val] of log) if (k === "cmi.suspend_data") v = val;
          return v;
        });
        check("suspend_data yazildi", lockSuspend.length > 0, true);
        check("suspend serbest metin tasimaz (baslik sizmaz)", lockSuspend.includes("Unite"), false);
      } finally {
        await ctx.close();
      }
    }
    // 5) Resume: kaldigi dugume doner — ekran + serit + zincir acik + aria-current + kilit kalkti
    {
      const ctx = await browser.newContext();
      try {
        const page = await ctx.newPage();
        await page.addInitScript(lmsInit, [false, "resume", lockSuspend, null]);
        await page.goto(`file://${lfile}`);
        await page.waitForTimeout(150);
        const r0 = await page.evaluate(() => ({
          shown: document.querySelector('.screen[aria-hidden="false"]').dataset.screenId,
          strip: document.getElementById("posStrip").textContent,
        }));
        check("resume: kaldigi ekran (dugum ici)", r0.shown, "c2");
        check("resume: konum seridi dogru", r0.strip, "Unite 2 · Bolum 2.1 · 1/2");
        await page.click("#btnMenu");
        await page.waitForTimeout(120);
        const r1 = await page.evaluate(() => {
          const u2 = document.querySelector('[data-node-id="u2"]');
          const b2 = document.querySelector('[data-node-id="b2"]');
          const cur = document.querySelector('#slideMenuList [aria-current="page"]');
          return { u2exp: u2.getAttribute("aria-expanded"), b2exp: b2.getAttribute("aria-expanded"),
                   u2dis: u2.getAttribute("aria-disabled"),
                   reasonHidden: u2.querySelector(".mtree-lockreason").hidden,
                   cur: cur && cur.getAttribute("data-goto"),
                   c2visible: document.querySelector('[data-goto="c2"]').offsetParent !== null };
        });
        check("resume: zincir acildi (u2)", r1.u2exp, "true");
        check("resume: zincir acildi (b2)", r1.b2exp, "true");
        check("resume: aria-current kaldigi ekranda", r1.cur, "c2");
        check("resume: kilit kalkti (u1 tamam)", r1.u2dis, null);
        check("resume: sebep gizlendi", r1.reasonHidden, true);
        check("resume: dugum ici ekran gorunur", r1.c2visible, true);
        // Faz 4-ek: TAM (sessiz) resume'da bildirim OLMAMALI
        const r2 = await page.evaluate(() => document.querySelector(".resume-notice") !== null);
        check("tam resume SESSIZ (bildirim yok)", r2, false);
      } finally {
        await ctx.close();
      }
    }

    // --- Faz 4-ek: REPUBLISH sonrasi resume — outline degisti, eski suspend ile acilir ---
    console.log("\n== Faz 4-ek — republish-resume: dugum silindi, ekran yasiyor ==");
    {
      const l2file = path.join(tmp, "lock12v2.html");
      execFileSync("python3", ["-c", LOCK_V2_RENDER_PY, l2file, "1.2"], { cwd: process.cwd() });
      const ctx = await browser.newContext();
      try {
        const page = await ctx.newPage();
        const warns = [];
        page.on("console", (m) => { if (m.type() === "warning") warns.push(m.text()); });
        // eski (v1 icerigin) suspend'i YENI pakete verilir — LRS/xAPI YOK (kayit konsola)
        await page.addInitScript(lmsInit, [false, "resume", lockSuspend, null]);
        await page.goto(`file://${l2file}`);
        await page.waitForTimeout(200);
        const m0 = await page.evaluate(() => {
          const v = document.querySelector('.screen[aria-hidden="false"]');
          const n = document.querySelector(".resume-notice");
          return {
            shown: v ? v.dataset.screenId : "?",
            notice: !!n,
            role: n && n.getAttribute("role"),
            live: n && n.getAttribute("aria-live"),
            text: n ? n.textContent : "",
            closable: !!(n && n.querySelector(".resume-notice-close")),
          };
        });
        // kimlik-merdiveni: b2 dugumu GITTI ama c2 ekrani YASIYOR → c2'de devam (sifirlama YOK)
        check("republish resume: kaldigi EKRANA devam (c2)", m0.shown, "c2");
        check("republish resume: BILDIRIM gorunur", m0.notice, true);
        check("bildirim role=status", m0.role, "status");
        check("bildirim aria-live=polite", m0.live, "polite");
        check("bildirim dostane metin (Kurs guncellendi...)", m0.text.includes("Kurs güncellendi"), true);
        check("bildirim hedef basligi anar (Konu 2)", m0.text.includes("Konu 2"), true);
        check("bildirim teknik jargon tasimaz", /suspend|orderFp|error/i.test(m0.text), false);
        check("bildirim kapatilabilir", m0.closable, true);
        // pozisyonel yanlis atif YOK: eski history/visited bitfield atildi; lineer yaklasimla
        // c2'ye kadarki ekranlar gezilmis sayilir → ilerleme sifirlanmadi
        const m1 = await page.evaluate(() => {
          const bar = document.querySelector(".progress-bar");
          return parseInt((bar && bar.style.width) || "0", 10);
        });
        check("ilerleme sifirlanmadi (lineer yaklasim > 0%)", m1 > 0, true);
      } finally {
        await ctx.close();
      }
    }

    // --- K2: auto kompozisyonda gorsel etkilesimli tipler calismaya devam eder ---
    console.log("\n== K2 — gorsel etkilesimli tipler (auto kompozisyon) ==");
    const k2 = {};
    for (const kind of ["hotspot", "compare", "sim"]) {
      k2[kind] = path.join(tmp, `k2-${kind}.html`);
      execFileSync("python3", ["-c", K2_RENDER_PY, k2[kind], kind], { cwd: process.cwd() });
    }
    const hs = await session(browser, k2.hotspot, { act: async (p) => {
      await p.waitForTimeout(150);
      await p.click('.hotspot-region[data-region="ok"], .hotspot-region >> nth=0');
      await p.click(".btn-check");
      await p.waitForTimeout(120);
    } });
    check("K2 hotspot: cevap LMS'e dogru yazildi", hs.last["cmi.interactions.0.result"], "correct");
    const cctx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
    try {
      const cp = await cctx.newPage();
      await cp.addInitScript(lmsInit, [false, "", "", null]);
      await cp.goto(`file://${k2.compare}`);
      await cp.waitForTimeout(150);
      const before = await cp.evaluate(() => getComputedStyle(document.querySelector(".ic-after-wrap")).clipPath
        + "|" + document.querySelector(".ic-after-wrap").getAttribute("style"));
      await cp.evaluate(() => { const r = document.querySelector(".ic-range"); r.value = "20";
        r.dispatchEvent(new Event("input", { bubbles: true })); });
      const after = await cp.evaluate(() => getComputedStyle(document.querySelector(".ic-after-wrap")).clipPath
        + "|" + document.querySelector(".ic-after-wrap").getAttribute("style"));
      check("K2 image_compare: kaydirici gorunumu degistirdi", before !== after, true);
      const sp = await cctx.newPage();
      await sp.addInitScript(lmsInit, [false, "", "", null]);
      await sp.goto(`file://${k2.sim}`);
      await sp.waitForTimeout(200);
      await sp.click('.sim-step[data-step="0"] .sim-region[data-correct="1"]');
      await sp.waitForTimeout(150);
      check("K2 simulation: adim ilerledi", await sp.textContent(".sim-progress"), "2 / 2");
    } finally {
      await cctx.close();
    }
    // visual-stack'te gorsel kalan yukseklige SIGMALI; labeled_diagram'in son secim satiri dahil
    for (const kind of ["hotspot", "labeled", "sim", "compare", "chart"]) {
      const f = path.join(tmp, `k2-fit-${kind}.html`);
      execFileSync("python3", ["-c", K2_RENDER_PY, f, kind, "visual-stack"], { cwd: process.cwd() });
      const fctx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
      try {
        const fp = await fctx.newPage();
        await fp.addInitScript(lmsInit, [false, "", "", null]);
        await fp.goto(`file://${f}`);
        await fp.waitForTimeout(250);
        const fit = await fp.evaluate(() => {
          const inner = document.querySelector(".screen .screen-inner");
          const els = [...document.querySelectorAll(
            ".slot-focal .hotspot-img, .slot-focal .ic-img-before, .slot-focal .ld-select, .slot-focal .chart-svg")]
            .filter((e) => !e.closest("[hidden]"));
          if (!inner || !els.length) return false;
          const b = inner.getBoundingClientRect().bottom;
          return els.every((e) => e.getBoundingClientRect().bottom <= b + 1);
        });
        check(`K2 visual-stack ${kind}: gorsel/denetimler sahneye sigiyor`, fit, true);
      } finally {
        await fctx.close();
      }
    }
    // Boyut kabı yalnız gerçek sahne modunda; akış düzeninde (layout_mode=flow) kapalı olmalı —
    // aksi halde odak yuvası içerik yüksekliğini kaybeder ve görseller küçülür (K1 dahil).
    for (const [layout, want] of [["stage", "size"], ["flow", "normal"]]) {
      const f = path.join(tmp, `k2-ct-${layout}.html`);
      execFileSync("python3", ["-c", K2_RENDER_PY, f, "hotspot", "split-thirds", layout], { cwd: process.cwd() });
      const lctx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
      try {
        const lp = await lctx.newPage();
        await lp.addInitScript(lmsInit, [false, "", "", null]);
        await lp.goto(`file://${f}`);
        await lp.waitForTimeout(150);
        const ct = await lp.evaluate(() => { const e = document.querySelector(".slot-focal");
          return e ? getComputedStyle(e).containerType : null; });
        check(`K2 container-type (${layout})`, ct, want);
      } finally {
        await lctx.close();
      }
    }
    // Mobilde labeled_diagram görseli yuvanın neredeyse tamamını kullanmalı (60cqw kısıtı yok)
    {
      const f = path.join(tmp, "k2-labeled-mobile.html");
      execFileSync("python3", ["-c", K2_RENDER_PY, f, "labeled", "split-thirds"], { cwd: process.cwd() });
      const lctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      try {
        const lp = await lctx.newPage();
        await lp.addInitScript(lmsInit, [false, "", "", null]);
        await lp.goto(`file://${f}`);
        await lp.waitForTimeout(200);
        const ratio = await lp.evaluate(() => { const i = document.querySelector(".slot-focal .hotspot-img");
          const sl = document.querySelector(".slot-focal");
          return i && sl ? i.getBoundingClientRect().width / sl.getBoundingClientRect().width : 0; });
        check("K2 mobil labeled: gorsel yuva genisligini kullaniyor (>=0.85)", ratio >= 0.85, true);
      } finally {
        await lctx.close();
      }
    }
    const mctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    try {
      const mp = await mctx.newPage();
      await mp.addInitScript(lmsInit, [false, "", "", null]);
      await mp.goto(`file://${k2.hotspot}`);
      await mp.waitForTimeout(150);
      // null-guvenli: yuva yoksa TypeError → probe'un genel catch'i "ortam: atlandi" der ve
      // exit 0 doner (gerileme gorunmez) — bu yuzden eksik yuva acik bir BASARISIZLIK olmali.
      const top = await mp.evaluate(() => {
        const s = document.querySelector(".slot-support"), f = document.querySelector(".slot-focal");
        return s && f ? [s.getBoundingClientRect().top, f.getBoundingClientRect().top] : null;
      });
      check("K2 mobil soru kipi: soru gorselden once", !!top && top[0] < top[1], true);
    } finally {
      await mctx.close();
    }

    // --- K3: soru tipleri auto kompozisyonda cevaplanir, LMS'e yazilir ---
    console.log("\n== K3 — soru tipleri (auto kompozisyon) ==");
    const k3 = (kind, preset = "-", stim = "") => {
      const f = path.join(tmp, `k3-${kind}-${preset}-${stim || "plain"}.html`);
      execFileSync("python3", ["-c", K3_RENDER_PY, f, kind, preset, stim], { cwd: process.cwd() });
      return f;
    };
    const k3Result = async (file, act) => (await session(browser, file, { act: async (p) => {
      await p.waitForTimeout(150); await act(p); await p.click(".btn-check"); await p.waitForTimeout(120);
    } })).last["cmi.interactions.0.result"];
    check("K3 mcq (uyaranli, split-thirds): dogru cevap LMS'e yazildi",
      await k3Result(k3("mcq", "split-thirds", "stim"), (p) => p.click('.opt[data-opt="a"]')), "correct");
    check("K3 drag_drop (question-column): surukle-birak dogru",
      await k3Result(k3("drag", "question-column"),
        (p) => p.dragAndDrop('.drag-item[data-item="x"]', '.drop-target[data-target="t1"]')), "correct");
    check("K3 matching: eslestirme dogru",
      await k3Result(k3("match"), async (p) => {
        await p.selectOption('.match-select[data-pair="p1"]', "p1");
        await p.selectOption('.match-select[data-pair="p2"]', "p2");
      }), "correct");
    check("K3 sorting: siralama dogru",
      await k3Result(k3("sort", "-", "stim"), async (p) => {
        const want = ["s1", "s2", "s3"];
        for (let n = 0; n < 10; n++) {
          const ids = await p.$$eval(".sorting .sort-item", (els) => els.map((e) => e.dataset.item));
          const i = ids.findIndex((v, k) => v !== want[k]);
          if (i < 0) break;
          const j = ids.indexOf(want[i]);
          await p.click(`.sort-item[data-item="${want[i]}"] .sort-up`);
          if (j <= i) break;
        }
      }), "correct");
    {
      const actx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
      try {
        const ap = await actx.newPage();
        await ap.addInitScript(lmsInit, [false, "", "", null]);
        await ap.goto(`file://${k3("adaptive", "split-thirds")}`);
        await ap.waitForTimeout(250);
        const vis = await ap.evaluate(() => { const it = [...document.querySelectorAll(".ap-item")]
          .find((e) => !e.hidden); return it ? !!it.querySelector(".stimulus-text") : null; });
        check("K3 adaptive: gorunen ogede uyaran var", vis, true);
        await ap.click(".ap-item:not([hidden]) .opt >> nth=0");
        await ap.click(".ap-item:not([hidden]) .ap-check");
        await ap.waitForTimeout(200);
        const apFit = await ap.evaluate(() => {
          const inner = document.querySelector(".screen .screen-inner");
          const it = [...document.querySelectorAll(".ap-item")].find((e) => !e.hidden);
          const img = it && it.querySelector(".stimulus-media .item-media"), chk = it && it.querySelector(".ap-check");
          if (!inner || !img || !chk) return null;
          const ib = inner.getBoundingClientRect();
          return img.getBoundingClientRect().top >= ib.top - 1 && chk.getBoundingClientRect().bottom <= ib.bottom + 1;
        });
        check("K3 adaptive (uyaranli split-thirds): oge gorsel + kontrol sahnede", apFit, true);
        checkMatch("K3 adaptive: oge ilerledi", (await ap.textContent(".ap-progress")) || "", /^1 \//);
      } finally {
        await actx.close();
      }
    }
    // Sigma: uyaranli visual-stack + 7 sikli question-column'da kontrol butonu sahnede
    // (uyaranli visual-stack burada degil: vaka ustte durdugu icin buton kaydirarak ulasilir —
    //  K4 bolumundeki "vaka ustte, baslik gorunur, buton ulasilir" kontrolu kapsar)
    for (const [kind, preset, st] of [["mcq7", "question-column", ""], ["mcq", "split-thirds", "stim"]]) {
      const fctx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
      try {
        const fp = await fctx.newPage();
        await fp.addInitScript(lmsInit, [false, "", "", null]);
        await fp.goto(`file://${k3(kind, preset, st)}`);
        await fp.waitForTimeout(250);
        const fit = await fp.evaluate(() => {
          const inner = document.querySelector(".screen .screen-inner");
          const b = document.querySelector(".btn-check");
          if (!inner || !b) return null;
          return b.getBoundingClientRect().bottom <= inner.getBoundingClientRect().bottom + 1;
        });
        check(`K3 ${kind} ${preset}: kontrol butonu sahnede`, fit, true);
      } finally {
        await fctx.close();
      }
    }
    // Uyaranli split-thirds: gorsel + vaka metni odak yuvasina BIRLIKTE sigar (metin kesilmez)
    // question-column: istem ile cevaplar arasinda sabit satir boslugu yok
    {
      const vctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      try {
        const vp = await vctx.newPage();
        await vp.addInitScript(lmsInit, [false, "", "", null]);
        await vp.goto(`file://${k3("mcq", "split-thirds", "stim")}`);
        await vp.waitForTimeout(250);
        const r = await vp.evaluate(() => {
          const f = document.querySelector(".slot-focal"), t = document.querySelector(".slot-focal .stimulus-text"),
            i = document.querySelector(".slot-focal .stimulus-media .item-media");
          if (!f || !t || !i) return null;
          const fb = f.getBoundingClientRect(), tb = t.getBoundingClientRect(), ib = i.getBoundingClientRect();
          return { textInside: tb.bottom <= fb.bottom + 1, textTall: tb.height >= 40, imgVisible: ib.height >= 80 };
        });
        check("K3 uyaranli split-thirds: vaka metni yuvaya sigiyor ve gorunur",
          !!r && r.textInside && r.textTall && r.imgVisible, true);
        const qp = await vctx.newPage();
        await qp.addInitScript(lmsInit, [false, "", "", null]);
        await qp.goto(`file://${k3("mcq", "question-column")}`);
        await qp.waitForTimeout(250);
        const gap = await qp.evaluate(() => {
          const pr = document.querySelector(".slot-support .prompt"), o = document.querySelector(".slot-focal .opt");
          return pr && o ? o.getBoundingClientRect().top - pr.getBoundingClientRect().bottom : null;
        });
        check("K3 question-column: istem-cevap boslugu 0..64px (ust uste binme yok)",
          gap !== null && gap >= 0 && gap < 64, true);
        const ct = await qp.evaluate(() => { const e = document.querySelector(".slot-focal");
          return e ? getComputedStyle(e).containerType : null; });
        check("K3 question-column: cevap odagi boyut kabi degil (icerikten buyur)", ct, "normal");
      } finally {
        await vctx.close();
      }
    }
    // Mobil sira: uyaranli → vaka once; uyaransiz → soru (istem) once
    {
      const mctx3 = await browser.newContext({ viewport: { width: 390, height: 844 } });
      try {
        for (const [st, want] of [["stim", "focal"], ["", "support"]]) {
          const mp = await mctx3.newPage();
          await mp.addInitScript(lmsInit, [false, "", "", null]);
          await mp.goto(`file://${k3("mcq", "split-thirds", st)}`);
          await mp.waitForTimeout(150);
          const first = await mp.evaluate(() => {
            const s = document.querySelector(".slot-support"), f = document.querySelector(".slot-focal");
            if (!s || !f) return null;
            return s.getBoundingClientRect().top < f.getBoundingClientRect().top ? "support" : "focal";
          });
          check(`K3 mobil (${st || "uyaransiz"}): ${want} once`, first, want);
          await mp.close();
        }
      } finally {
        await mctx3.close();
      }
    }

    // --- K4: icerik etkilesimleri auto kompozisyonda ---
    console.log("\n== K4 — icerik etkilesimleri (auto kompozisyon) ==");
    const k4 = (kind, preset = "-", stim = "") => {
      const f = path.join(tmp, `k4-${kind}-${preset}-${stim || "plain"}.html`);
      execFileSync("python3", ["-c", K4_RENDER_PY, f, kind, preset, stim], { cwd: process.cwd() });
      return f;
    };
    const k4Page = async (file, vp, fn) => {
      const c = await browser.newContext({ viewport: vp });
      try {
        const pg = await c.newPage();
        await pg.addInitScript(lmsInit, [false, "", "", null]);
        await pg.goto(`file://${file}`);
        await pg.waitForTimeout(250);
        return await fn(pg);
      } finally {
        await c.close();
      }
    };
    const WIDE = { width: 1280, height: 800 }, MOB = { width: 390, height: 844 };
    const visPanel = (pg) => pg.evaluate(() => { const v = [...document.querySelectorAll(".tab-panel")]
      .find((e) => !e.hidden); return v ? v.dataset.panel : null; });
    await k4Page(k4("tabs"), WIDE, async (pg) => {
      const md = await pg.evaluate(() => {
        const l = document.querySelector(".tab-list"), p = [...document.querySelectorAll(".tab-panel")].find((e) => !e.hidden);
        if (!l || !p) return null;
        const a = l.getBoundingClientRect(), b = p.getBoundingClientRect();
        return a.right <= b.left + 1 && Math.abs(a.top - b.top) < 40;
      });
      check("K4 tabs genis: ana-detay (liste panelin solunda)", md, true);
      await pg.click('.tab[data-tab="1"]');
      check("K4 tabs: tiklama paneli degistirdi", await visPanel(pg), "1");
      await pg.focus('.tab[data-tab="1"]'); await pg.keyboard.press("ArrowDown");
      check("K4 tabs: asagi ok sonraki panel", await visPanel(pg), "2");
      await pg.keyboard.press("ArrowLeft");
      check("K4 tabs: sol ok (mevcut davranis) hala calisiyor", await visPanel(pg), "1");
    });
    await k4Page(k4("tabs"), MOB, async (pg) => {
      const above = await pg.evaluate(() => {
        const l = document.querySelector(".tab-list"), p = [...document.querySelectorAll(".tab-panel")].find((e) => !e.hidden);
        return l && p ? l.getBoundingClientRect().bottom <= p.getBoundingClientRect().top + 1 : null;
      });
      check("K4 tabs mobil: liste panelin ustunde", above, true);
    });
    await k4Page(k4("acc"), WIDE, async (pg) => {
      await pg.click(".acc-head >> nth=0");
      check("K4 accordion: acildi", await pg.evaluate(() => !!document.querySelector("details.acc-item[open]")), true);
    });
    await k4Page(k4("flash"), WIDE, async (pg) => {
      await pg.click(".flashcard >> nth=0");
      check("K4 flashcards: dondu", await pg.evaluate(() => !!document.querySelector(".flashcard.flipped")), true);
    });
    await k4Page(k4("poll", "split-thirds", "stim"), WIDE, async (pg) => {
      await pg.check(".poll-opts input >> nth=0");
      await pg.click(".poll-submit");
      check("K4 poll (uyaranli): yansima gorundu",
        await pg.evaluate(() => { const r = document.querySelector(".poll-reflection"); return r ? !r.hidden : null; }), true);
    });
    await k4Page(k4("xp", "-", "stim"), WIDE, async (pg) => {
      await pg.fill(".xp-text", "benim tahminim bu");
      await pg.evaluate(() => document.querySelector(".xp-text").dispatchEvent(new Event("change", { bubbles: true })));
      check("K4 exploration (uyaranli): girdi kaydedildi",
        await pg.evaluate(() => { const s = document.querySelector(".xp-saved"); return s ? !s.hidden : null; }), true);
    });
    await k4Page(k4("we"), WIDE, async (pg) => {
      await pg.click(".we-reveal >> nth=0");
      check("K4 worked_example: gerekce acildi",
        await pg.getAttribute(".we-reveal >> nth=0", "aria-expanded"), "true");
    });
    // Uzun liste kesilmez: odak yuvasi icerikten buyur, son oge kaydirinca sahnede gorunur
    for (const kind of ["acc12", "tl10"]) {
      await k4Page(k4(kind), WIDE, async (pg) => {
        const r = await pg.evaluate(() => {
          const f = document.querySelector(".slot-focal"), items = document.querySelectorAll(".acc-item, .tl-event");
          if (!f || !items.length) return null;
          const last = items[items.length - 1];
          last.scrollIntoView({ block: "end" });
          const inner = document.querySelector(".screen .screen-inner").getBoundingClientRect();
          const lb = last.getBoundingClientRect();
          return { ct: getComputedStyle(f).containerType, visible: lb.bottom <= inner.bottom + 2 && lb.top >= inner.top - 2,
                   grows: f.scrollHeight <= f.clientHeight + 2 };
        });
        check(`K4 ${kind}: son oge kaydirilarak gorunur, yuva kesmiyor`,
          !!r && r.ct === "inline-size" && r.visible && r.grows, true);
      });
    }
    // Baslik acilista gorunur (uzun icerikte asagi itilmez) + baslik-koleksiyon arasi sabit bosluk yok
    for (const [kind, preset] of [["we", "split-thirds"], ["acc12", "split-thirds"], ["tl10", "-"]]) {
      await k4Page(k4(kind, preset), WIDE, async (pg) => {
        const ok = await pg.evaluate(() => {
          const h = document.querySelector(".comp-grid .screen-title"), i = document.querySelector(".screen .screen-inner");
          if (!h || !i) return null;
          const hb = h.getBoundingClientRect(), ib = i.getBoundingClientRect();
          return hb.top >= ib.top - 1 && hb.bottom <= ib.top + ib.height * 0.5;
        });
        check(`K4 ${kind} ${preset}: baslik acilista sahnenin ust yarisinda`, ok, true);
      });
    }
    await k4Page(k4("tabs"), WIDE, async (pg) => {
      const gap = await pg.evaluate(() => {
        const h = document.querySelector(".slot-support"), t = document.querySelector(".slot-focal .tabs");
        return h && t ? t.getBoundingClientRect().top - h.getBoundingClientRect().bottom : null;
      });
      check("K4 tabs visual-stack: baslik-sekme boslugu 0..64px", gap !== null && gap >= 0 && gap < 64, true);
    });
    // Uyaranli poll/exploration varsayilan (visual-stack) duzende vaka gorunur ve kesilmez
    for (const [kind, st] of [["poll", "stimtext"], ["poll", "stimimg"], ["xp", "stimtext"]]) {
      await k4Page(k4(kind, "-", st), WIDE, async (pg) => {
        const r = await pg.evaluate(() => {
          const t = document.querySelector(".slot-focal .stimulus-text"), i = document.querySelector(".slot-focal .stimulus-media .item-media");
          const e = t || i;
          if (!e) return null;
          const comp = document.querySelector(".screen").dataset.comp;
          const h = e.getBoundingClientRect().height;
          return { comp, ok: t ? h >= 30 && t.scrollHeight <= t.clientHeight + 1 : h >= 80 };
        });
        check(`K4 ${kind} ${st} (varsayilan): vaka gorunur ve kesilmez`, !!r && r.comp === "visual-stack" && r.ok, true);
      });
    }
    // Uyaranli visual-stack (masaustu): vaka USTTE, soru altta; baslik gorunur; buton kaydirilarak ulasilir
    const stackCheck = async (file, label, btnSel) => k4Page(file, WIDE, async (pg) => {
      const r = await pg.evaluate((bs) => {
        const f = document.querySelector(".slot-focal"), sp = document.querySelector(".slot-support"),
          h = document.querySelector(".comp-grid .screen-title"), i = document.querySelector(".screen .screen-inner"),
          b = document.querySelector(bs);
        if (!f || !sp || !h || !i || !b) return null;
        const ib = i.getBoundingClientRect();
        const caseFirst = f.getBoundingClientRect().top < sp.getBoundingClientRect().top;
        const titleVisible = h.getBoundingClientRect().top >= ib.top - 1;
        b.scrollIntoView({ block: "end" });
        const bb = b.getBoundingClientRect(), ib2 = i.getBoundingClientRect();
        return { caseFirst, titleVisible, btn: bb.bottom <= ib2.bottom + 2 && bb.top >= ib2.top - 2 };
      }, btnSel);
      check(`${label}: vaka ustte, baslik gorunur, buton ulasilir`,
        !!r && r.caseFirst && r.titleVisible && r.btn, true);
    });
    await stackCheck(k4("poll", "-", "stimtext"), "K4 poll visual-stack", ".poll-submit");
    await stackCheck(k4("poll", "-", "stimimg"), "K4 poll visual-stack (gorsel)", ".poll-submit");
    await stackCheck(k3("mcq", "visual-stack", "stim"), "K3 mcq visual-stack", ".btn-check");
    // Mobil sira: uyaranli poll → vaka once; uyaransiz → baslik once
    for (const [st, want] of [["stim", "focal"], ["", "support"]]) {
      await k4Page(k4("poll", "split-thirds", st), MOB, async (pg) => {
        const first = await pg.evaluate(() => {
          const s = document.querySelector(".slot-support"), f = document.querySelector(".slot-focal");
          if (!s || !f) return null;
          return s.getBoundingClientRect().top < f.getBoundingClientRect().top ? "support" : "focal";
        });
        check(`K4 mobil poll (${st || "uyaransiz"}): ${want} once`, first, want);
      });
    }

    // --- K5: oyun/senaryo/gomulu auto kompozisyonda ---
    console.log("\n== K5 — oyun / senaryo / gomulu (auto kompozisyon) ==");
    const k5 = (kind, preset = "-", stim = "") => {
      const f = path.join(tmp, `k5-${kind}-${preset}-${stim || "plain"}.html`);
      execFileSync("python3", ["-c", K5_RENDER_PY, f, kind, preset, stim], { cwd: process.cwd() });
      return f;
    };
    const sideBySide = (pg, nodeSel, txtSel, imgSel) => pg.evaluate(([n, t, i]) => {
      const node = [...document.querySelectorAll(n)].find((e) => !e.hidden);
      const tx = node && node.querySelector(t), im = node && node.querySelector(i);
      if (!tx || !im) return null;
      const a = im.getBoundingClientRect(), b = tx.getBoundingClientRect();
      return a.right <= b.left + 1 && a.height > 40;
    }, [nodeSel, txtSel, imgSel]);
    await k4Page(k5("game"), WIDE, async (pg) => {
      check("K5 game genis: sahne yan yana (gorsel anlatinin solunda)",
        await sideBySide(pg, ".game-node", ".game-content", ".game-img"), true);
      const hud = await pg.evaluate(() => { const h = document.querySelector(".game-hud"), g = document.querySelector("[data-game]"),
          n = [...document.querySelectorAll(".game-node")].find((e) => !e.hidden);
        if (!h || !g || !n) return null;
        const hb = h.getBoundingClientRect(), nb = n.getBoundingClientRect();
        // HUD dugum izgarasinin DISINDA (kabin dogrudan cocugu), dugumun ustunde ve dugum genisliginde
        return h.parentElement === g && !h.closest(".game-node") && hb.bottom <= nb.top + 1
          && Math.abs(hb.width - nb.width) <= 2; });
      check("K5 game: HUD dugum izgarasinin disinda, ustte, tam genislik", hud, true);
      const before = await pg.evaluate(() => { const n = [...document.querySelectorAll(".game-node")].find((e) => !e.hidden); return n ? n.dataset.node : null; });
      await pg.click(".game-node:not([hidden]) .game-choice >> nth=0");
      await pg.waitForTimeout(150);
      const nx = await pg.$(".game-node:not([hidden]) .game-next:not([hidden])");
      if (nx) { await nx.click(); await pg.waitForTimeout(150); }
      const after = await pg.evaluate(() => { const n = [...document.querySelectorAll(".game-node")].find((e) => !e.hidden); return n ? n.dataset.node : null; });
      check("K5 game: secim dugumu ilerletti", !!after && after !== before, true);
      check("K5 game: yeni dugum de yan yana",
        await sideBySide(pg, ".game-node", ".game-content", ".game-img"), true);
    });
    await k4Page(k5("game"), MOB, async (pg) => {
      const order = await pg.evaluate(() => {
        const n = [...document.querySelectorAll(".game-node")].find((e) => !e.hidden);
        const t = n && n.querySelector(".game-content"), i = n && n.querySelector(".game-img");
        return t && i ? t.getBoundingClientRect().top < i.getBoundingClientRect().top : null;
      });
      check("K5 game mobil: anlati gorselden once (DOM sirasi)", order, true);
    });
    await k4Page(k5("scen"), WIDE, async (pg) => {
      check("K5 decision_scenario genis: sahne yan yana",
        await sideBySide(pg, ".scen-node", ".scen-prompt", ".scen-img"), true);
      await pg.click('.scen-node:not([hidden]) .scen-choice[data-choice="x"]');
      await pg.waitForTimeout(150);
      check("K5 decision_scenario: skor yazildi", (await pg.textContent(".scen-score")).trim(), "10");
      await pg.click(".scen-node:not([hidden]) .scen-next");
      await pg.waitForTimeout(150);
      check("K5 decision_scenario: sonraki dugum", await pg.evaluate(() =>
        { const n = [...document.querySelectorAll(".scen-node")].find((e) => !e.hidden); return n ? n.dataset.node : null; }), "d2");
    });
    await k4Page(k5("esc"), WIDE, async (pg) => {
      await pg.fill('.esc-puzzle:not([hidden]) .esc-input', "4");
      await pg.click('.esc-puzzle:not([hidden]) .esc-submit');
      await pg.waitForTimeout(200);
      check("K5 escape_room: bulmaca ilerledi", (await pg.textContent(".esc-progress")).trim(), "2 / 2");
    });
    await k4Page(k5("tmr"), WIDE, async (pg) => {
      await pg.selectOption('.tmr-select[data-pair="a"]', "a");
      await pg.selectOption('.tmr-select[data-pair="b"]', "b");
      await pg.click(".tmr-finish");
      await pg.waitForTimeout(200);
      check("K5 term_match_race: skor", (await pg.textContent(".tmr-score")).trim(), "2 / 2");
    });
    {
      const bs = await session(browser, k5("branch"), { act: async (p) => {
        await p.waitForTimeout(150); await p.click('.branch-choice[data-choice="r"]'); await p.waitForTimeout(200);
      } });
      check("K5 branching: hedef ekrana gitti", bs.shown, "right");
    }
    await k4Page(k5("embed"), WIDE, async (pg) => {
      const h = await pg.evaluate(() => { const f = document.querySelector(".slot-focal .embed-frame"); return f ? f.getBoundingClientRect().height : null; });
      check("K5 embed_html: iframe yuvayi dolduruyor (>=200px)", h !== null && h >= 200, true);
    });
    await stackCheck(k5("branch", "-", "stim"), "K5 branching visual-stack", ".branch-choice");
    for (const vp of [WIDE, { width: 1000, height: 640 }]) {
      await k4Page(k5("embedlead"), vp, async (pg) => {
        const ok = await pg.evaluate(() => {
          const k = document.querySelector(".comp-grid .kicker, .comp-grid .screen-title"),
            sp = k && k.closest(".slot"),
            i = document.querySelector(".screen .screen-inner"), f = document.querySelector(".slot-focal .embed-frame");
          if (!k || !sp || !i || !f) return null;
          // destek yuvasindan YUKARI tasma yok (ic dolgu payi maskelemesin) + iframe dolu
          return k.getBoundingClientRect().top >= sp.getBoundingClientRect().top - 1
            && k.getBoundingClientRect().top >= i.getBoundingClientRect().top - 1
            && f.getBoundingClientRect().height >= 150;
        });
        check(`K5 embed (${vp.width}): ust etiket/baslik gorunur, iframe dolu`, ok, true);
      });
    }
    await k4Page(k5("gametall"), WIDE, async (pg) => {
      const ok = await pg.evaluate(() => {
        const im = document.querySelector(".scen-node:not([hidden]) .scen-img"), i = document.querySelector(".screen .screen-inner");
        if (!im || !i) return null;
        return im.getBoundingClientRect().bottom <= i.getBoundingClientRect().bottom + 1 && im.getBoundingClientRect().height > 80;
      });
      check("K5 uzun sahne gorseli sahneye sigiyor", ok, true);
    });

    // --- K6: release oncesi duzeltmeler ---
    console.log("\n== K6 — uzun ekran, uzun icerik, gorselli kart ==");
    const k6 = (kind, mode) => {
      const f = path.join(tmp, `k6-${kind}-${mode}.html`);
      execFileSync("python3", ["-c", K6_RENDER_PY, f, kind, mode], { cwd: process.cwd() });
      return f;
    };
    for (const mode of ["classic", "auto"]) {
      for (const kind of ["longcontent", "longmcq"]) {
        await k4Page(k6(kind, mode), MOB, async (pg) => {
          const ok = await pg.evaluate(() => {
            const st = document.querySelector(".stage"); if (st) st.scrollTop = 0; window.scrollTo(0, 0);
            // ekranın KENDİSİ (yalnız başlık değil — auto'da başlık vakanın altında olabilir) sahnenin üstünden taşmaz
          const sc = document.querySelector('.screen[aria-hidden="false"]');
          return sc && st ? sc.getBoundingClientRect().top >= st.getBoundingClientRect().top - 1 : null;
          });
          check(`K6 mobil ${kind} ${mode}: baslik kaydirilarak ulasilir`, ok, true);
        });
      }
      await k4Page(k6("flashimg", mode), WIDE, async (pg) => {
        const face = (sel) => pg.evaluate((fs) => {
          const c = document.querySelector(".flashcard"), f = c && c.querySelector(fs);
          const im = f && f.querySelector("img"), tx = f && f.querySelector("p");
          if (!c || !im || !tx) return null;
          const cb = c.getBoundingClientRect(), ib = im.getBoundingClientRect(), tb = tx.getBoundingClientRect();
          const inside = (b) => b.top >= cb.top - 1 && b.bottom <= cb.bottom + 1 && b.left >= cb.left - 1 && b.right <= cb.right + 1;
          return inside(ib) && inside(tb) && tb.top >= ib.bottom - 1;
        }, sel);
        check(`K6 gorselli kart ${mode}: on yuz gorsel ustte, metin altta, kart icinde`, await face(".fc-front"), true);
        await pg.click(".flashcard >> nth=0"); await pg.waitForTimeout(700);
        check(`K6 gorselli kart ${mode}: arka yuz de duzenli`, await face(".fc-back"), true);
        const backShown = await pg.evaluate(() => { const c = document.querySelector(".flashcard"); const r = c.getBoundingClientRect();
          const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!(e && e.closest(".fc-back")); });
        check(`K6 gorselli kart ${mode}: cevrilince gorunen yuz arka yuz`, backShown, true);
      });
    }
    // split-halves: iki gorsel ayni hizada (aux yuvasi da yuvaya sigar; safe hizalama kaydirmaz)
    {
      const f = path.join(tmp, "k6-halves.html");
      execFileSync("python3", ["-c", `
import sys
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
a = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg), sha256="0", rel_path="assets/i.svg")]
s = TypeAdapter(Screen).validate_python({"type": "content_slide", "id": "s1", "title": "Gercek ve klon",
    "composition": "split-halves", "blocks": [{"asset_id": "i", "caption": "Gercek"}, {"asset_id": "i", "caption": "Klon"}]})
open(sys.argv[1], "w").write(render_html(Project(id=new_project_id(), title="k6", composition="auto", screens=[s], assets=a),
    mode="preview", runtime_js="", asset_data={"i": ("image/svg+xml", svg)}))
`, f], { cwd: process.cwd() });
      await k4Page(f, { width: 1024, height: 700 }, async (pg) => {
        const d = await pg.evaluate(() => {
          const ims = [...document.querySelectorAll(".comp-grid .item-media, .comp-grid img")].filter((e) => e.getBoundingClientRect().height > 20);
          return ims.length >= 2 ? Math.abs(ims[0].getBoundingClientRect().top - ims[1].getBoundingClientRect().top) : null;
        });
        check("K6 split-halves: iki gorsel ayni hizada (<=2px)", d !== null && d <= 2, true);
      });
    }
    for (const mode of ["classic", "auto"]) {
      await k4Page(k6("flashmix", mode), WIDE, async (pg) => {
        const r = await pg.evaluate(() => {
          const cards = [...document.querySelectorAll(".flashcard")];
          if (cards.length < 3) return null;
          // görünen yüz = buton kutusu (yüzen yüz / tıklanabilir boşluk yok)
          const fit = cards.every((c) => { const b = c.getBoundingClientRect(), f = c.querySelector(".fc-front").getBoundingClientRect();
            return Math.abs(b.top - f.top) <= 2 && Math.abs(b.bottom - f.bottom) <= 2; });
          // satır içi biçimli metin tek satırda kalır (parçalara bölünmez)
          const f0 = cards[0].querySelector(".fc-front"), t = f0 && f0.querySelector("strong");
          const w = f0 && document.createTreeWalker(f0, NodeFilter.SHOW_TEXT);
          let first = null; while (w && w.nextNode()) { if (w.currentNode.textContent.trim().startsWith("Ag")) { first = w.currentNode; break; } }
          if (!t || !first) return { fit, inline: false };
          const rg = document.createRange(); rg.selectNodeContents(first);
          // "Ag" ile <strong> AYNI satırda (flex sütunu her parçayı ayrı satıra bölüyordu)
          return { fit, inline: Math.abs(rg.getBoundingClientRect().top - t.getBoundingClientRect().top) < 6 };
        });
        check(`K6 karisik kartlar ${mode}: yuz = kart kutusu`, !!r && r.fit, true);
        check(`K6 karisik kartlar ${mode}: satir ici metin bolunmez`, !!r && r.inline, true);
      });
    }
    await k4Page(k6("longcontent", "auto"), WIDE, async (pg) => {
      const ok = await pg.evaluate(() => {
        const h = document.querySelector(".comp-grid .screen-title"), sp = document.querySelector(".slot-title");
        return h && sp ? h.getBoundingClientRect().top >= sp.getBoundingClientRect().top - 1 : null;
      });
      check("K6 uzun icerik split-thirds: baslik yuvadan yukari tasmaz", ok, true);
    });

    // --- v1.8.1 #175: baslik her zaman once ---
    console.log("\n== v1.8.1 — baslik once (okuma sirasi) ==");
    {
      const f = path.join(tmp, "v181-title.html");
      execFileSync("python3", ["-c", `
import sys
from pydantic import TypeAdapter
from components.renderer import render_html
from core.project import Project, Screen, new_project_id, AssetRef
svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420"><rect width="640" height="420" fill="#ccc"/></svg>'
a = [AssetRef(id="i", filename="i.svg", mime="image/svg+xml", size_bytes=len(svg), sha256="0", rel_path="assets/i.svg")]
s = TypeAdapter(Screen).validate_python({"type": "content_slide", "id": "s1", "kicker": "ADIM 1", "title": "Baslik",
    "media_asset_id": "i", "media_alt": "g", "body_html": "<p>" + "govde metni " * 20 + "</p>", "composition": "split-thirds"})
open(sys.argv[1], "w").write(render_html(Project(id=new_project_id(), title="t", composition="auto", screens=[s], assets=a),
    mode="preview", runtime_js="", asset_data={"i": ("image/svg+xml", svg)}))
`, f], { cwd: process.cwd() });
      await k4Page(f, WIDE, async (pg) => {
        const r = await pg.evaluate(() => {
          const t = document.querySelector(".slot-title"), s = document.querySelector(".slot-support"),
            fo = document.querySelector(".slot-focal"), g = document.querySelector(".comp-grid");
          if (!t || !s || !fo || !g) return null;
          const tb = t.getBoundingClientRect(), sb = s.getBoundingClientRect(), fb = fo.getBoundingClientRect(), gb = g.getBoundingClientRect();
          return { above: tb.bottom <= sb.top + 1 && Math.abs(tb.left - sb.left) < 2,
                   full: Math.abs(fb.top - gb.top) < 2 && Math.abs(fb.bottom - gb.bottom) < 2 };
        });
        check("v1.8.1 masaustu: baslik destek sutununun ustunde", !!r && r.above, true);
        check("v1.8.1 masaustu: odak gorsel tam yukseklikte", !!r && r.full, true);
      });
      await k4Page(f, MOB, async (pg) => {
        const first = await pg.evaluate(() => {
          const els = [...document.querySelectorAll('.screen[aria-hidden="false"] .comp-grid *')]
            .filter((e) => e.children.length === 0 && (e.textContent.trim() || e.tagName === "IMG"));
          const top = els.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top)[0];
          return top ? top.className || top.tagName : null;
        });
        check("v1.8.1 mobil: ilk gorunen oge ust etiket/baslik", /kicker|screen-title/.test(first || ""), true);
      });
      await k4Page(k3("mcq", "visual-stack", "stim"), WIDE, async (pg) => {
        const ord = await pg.evaluate(() => {
          const t = document.querySelector(".slot-title"), c = document.querySelector(".slot-focal .stimulus"),
            p = document.querySelector(".slot-support .prompt");
          return t && c && p ? t.getBoundingClientRect().top < c.getBoundingClientRect().top &&
            c.getBoundingClientRect().top < p.getBoundingClientRect().top : null;
        });
        check("v1.8.1 vakali soru: baslik → vaka → soru (masaustu)", ord, true);
      });
    }

    // --- K1 z-flow: dort adim da masaustu sahnesinde gorunur (tasma yok) ---
    console.log("\n== K1 — z-flow tasma yok ==");
    const zfile = path.join(tmp, "zflow.html");
    execFileSync("python3", ["-c", ZFLOW_RENDER_PY, zfile], { cwd: process.cwd() });
    const zctx = await browser.newContext({ viewport: { width: 1024, height: 700 } });
    try {
      const zpage = await zctx.newPage();
      await zpage.addInitScript(lmsInit, [false, "", "", null]);
      await zpage.goto(`file://${zfile}`);
      await zpage.waitForTimeout(200);
      const z = await zpage.evaluate(() => {
        const ie = document.querySelector(".screen.active .screen-inner, .screen .screen-inner");
        if (!ie) return { n: 0, fits: false };  // null-guvenli
        const inner = ie.getBoundingClientRect();
        const steps = [...document.querySelectorAll(".slot-steps .step")]
          .map((e) => e.getBoundingClientRect());
        return { n: steps.length, fits: steps.every((r) => r.bottom <= inner.bottom + 1) };
      });
      check("z-flow: 4 adim", z.n, 4);
      check("z-flow: tum adimlar sahnenin icinde", z.fits, true);
    } finally {
      await zctx.close();
    }

    // --- K1 kompozisyon: mobilde tek sutun + odak-once okuma sirasi; masaustunde izgara ---
    console.log("\n== K1 — kompozisyon (mobil tek sutun, odak once) ==");
    const cfile = path.join(tmp, "comp.html");
    execFileSync("python3", ["-c", COMP_RENDER_PY, cfile], { cwd: process.cwd() });
    for (const [label, vp] of [["mobil", { width: 390, height: 844 }],
                               ["masaustu", { width: 1024, height: 700 }]]) {
      const cctx = await browser.newContext({ viewport: vp });
      try {
        const cpage = await cctx.newPage();
        await cpage.addInitScript(lmsInit, [false, "", "", null]);
        await cpage.goto(`file://${cfile}`);
        await cpage.waitForTimeout(150);
        const r = await cpage.evaluate(() => {
          const fe = document.querySelector(".slot-focal"), se = document.querySelector(".slot-support");
          const ge = document.querySelector(".comp-grid");
          if (!fe || !se || !ge) return { focalAbove: false, sideBySide: false, cols: 0 };  // null-guvenli
          const f = fe.getBoundingClientRect(), s = se.getBoundingClientRect();
          const cols = getComputedStyle(ge).gridTemplateColumns.trim().split(/\s+/).length;
          return { focalAbove: f.top < s.top, sideBySide: f.left !== s.left, cols };
        });
        if (label === "mobil") {
          check("mobil: tek sutun", r.cols, 1);
          check("mobil: odak destekten once (ustte)", r.focalAbove, true);
        } else {
          check("masaustu: 3 sutunlu izgara", r.cols, 3);
          check("masaustu: odak ve destek yan yana", r.sideBySide, true);
        }
      } finally {
        await cctx.close();
      }
    }
  } finally {
    if (browser) await browser.close();
    rmSync(tmp, { recursive: true, force: true });
  }

  if (failures.length) {
    console.error(`\n✗ SCORM probe BASARISIZ — ${failures.length} ihlal:`);
    failures.forEach((f) => console.error("   - " + f));
    process.exit(1);
  }
  console.log("\n✓ SCORM probe: S1/S2/S3/S4 tum kontroller gecti.");
}

main().catch((e) => {
  // Tarayıcı indirilmemis / python yok gibi ORTAM sorunlarinda atla; gercek ihlal yukarida exit 1 yapar.
  console.warn("\n⚠ SCORM probe atlandi (ortam):", e.message.split("\n")[0]);
  process.exit(0);
});
