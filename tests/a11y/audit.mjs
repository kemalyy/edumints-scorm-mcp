// tests/a11y/audit.mjs — Task 1'in ürettiği fixture HTML'lerini axe-core ile denetler (W9 P1 / W8c).
// NON-BLOCKING (kullanıcı kararı, 2026-07-22): ihlaller raporlanır, exit code her zaman 0.
// Sunucuda/istemcide LLM yok — axe-core tamamen deterministik statik/DOM kural motoru.
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES_DIR = path.join(__dirname, "fixtures");

async function auditOne(browser, fixturePath) {
  // NOT: browser.newPage() değil browser.newContext() + context.newPage() kullanılıyor —
  // @axe-core/playwright'in finishRun() adımı aynı context içinde ikinci bir sayfa açıyor
  // (axe.finishRun'ı izole çalıştırmak için); browser.newPage()'in oluşturduğu örtük context
  // bunu Playwright tarafında "Please use browser.newContext()" hatasıyla reddediyor.
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.goto(`file://${fixturePath}`);
    await page.waitForTimeout(500); // engine bundle + ilk render için kısa bekleme
    const results = await new AxeBuilder({ page }).analyze();
    return results;
  } finally {
    // mid-analyze() hatasında bile context'i sızdırma — dış handler zaten exit(0) yapacak
    await context.close();
  }
}

async function main() {
  // Tüm gövde try/catch içinde: readdirSync, browser launch/close, per-fixture audit
  // döngüsü dahil HER hata yakalanır — script HER KOŞULDA exit 0 ile döner
  // (non-blocking, kullanıcı kararı 2026-07-22).
  let browser;
  try {
    let files;
    try {
      files = readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".html"));
    } catch (err) {
      console.error(`Fixture dizini okunamadı: ${FIXTURES_DIR} — önce 'python tests/a11y/generate_fixtures.py' çalıştır.`);
      console.error(err.message);
      process.exit(0); // non-blocking: eksik/erişilemez fixture dizini bile CI'ı kırmasın
    }

    if (files.length === 0) {
      console.error(`Fixture bulunamadı: ${FIXTURES_DIR} — önce 'python tests/a11y/generate_fixtures.py' çalıştır.`);
      process.exit(0); // non-blocking: eksik fixture bile CI'ı kırmasın, sadece uyarsın
    }

    browser = await chromium.launch();
    let totalViolations = 0;
    const perFile = [];

    for (const file of files) {
      const fixturePath = path.join(FIXTURES_DIR, file);
      const results = await auditOne(browser, fixturePath);
      const count = results.violations.length;
      totalViolations += count;
      perFile.push({ file, count, violations: results.violations });

      console.log(`\n=== ${file} — ${count} ihlal ===`);
      for (const v of results.violations) {
        console.log(`  [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node) — ${v.helpUrl}`);
      }
    }

    await browser.close();
    browser = undefined;

    console.log(`\n${"=".repeat(60)}`);
    console.log(`TOPLAM: ${files.length} fixture, ${totalViolations} ihlal (non-blocking rapor)`);
    console.log(`${"=".repeat(60)}`);
    for (const { file, count } of perFile) {
      console.log(`  ${count.toString().padStart(3)}  ${file}`);
    }
  } catch (err) {
    console.error("a11y-audit içinde beklenmeyen hata (non-blocking, yine de exit 0):");
    console.error(err);
    if (browser) {
      try {
        await browser.close();
      } catch {
        // kapatma da başarısız olsa exit 0'ı engelleme
      }
    }
  } finally {
    process.exit(0); // her zaman 0 — non-blocking, kullanıcı kararı (2026-07-22)
  }
}

main().catch((err) => {
  // main() içindeki try/catch'i atlayan, senkron olarak fonksiyona girmeden
  // önce oluşan beklenmedik bir reddetme için son güvenlik ağı.
  console.error("a11y-audit main() dışında beklenmeyen hata (non-blocking, yine de exit 0):");
  console.error(err);
  process.exit(0);
});
