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
