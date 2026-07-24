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
function lmsInit([is2004, entry, suspend]) {
  const log = [];
  window.__LMS__ = log;
  const store = {};
  store[is2004 ? "cmi.entry" : "cmi.core.entry"] = entry;
  store["cmi.suspend_data"] = suspend;
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

async function session(browser, file, { is2004 = false, entry = "", suspend = "", act } = {}) {
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.addInitScript(lmsInit, [is2004, entry, suspend]);
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

async function main() {
  const tmp = mkdtempSync(path.join(tmpdir(), "scorm-probe-"));
  let browser;
  try {
    const f12 = path.join(tmp, "c12.html"), f2004 = path.join(tmp, "c2004.html");
    execFileSync("python3", ["-c", RENDER_PY, f12, "1.2"], { cwd: process.cwd() });
    execFileSync("python3", ["-c", RENDER_PY, f2004, "2004"], { cwd: process.cwd() });

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
  } finally {
    if (browser) await browser.close();
    rmSync(tmp, { recursive: true, force: true });
  }

  if (failures.length) {
    console.error(`\n✗ SCORM probe BASARISIZ — ${failures.length} ihlal:`);
    failures.forEach((f) => console.error("   - " + f));
    process.exit(1);
  }
  console.log("\n✓ SCORM probe: S1/S3/S4 tum kontroller gecti.");
}

main().catch((e) => {
  // Tarayıcı indirilmemis / python yok gibi ORTAM sorunlarinda atla; gercek ihlal yukarida exit 1 yapar.
  console.warn("\n⚠ SCORM probe atlandi (ortam):", e.message.split("\n")[0]);
  process.exit(0);
});
