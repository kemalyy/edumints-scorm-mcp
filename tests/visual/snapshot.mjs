// tests/visual/snapshot.mjs — #150 gorsel regresyon kapisi.
//
// tests/visual/fixtures/*.html dosyalarini SABITLENMIS bir Playwright konteynerinde acar,
// PNG'ye ceker ve tests/visual/baseline/ altindaki referansla piksel karsilastirir.
//
// ORTAM SABITLIGI ZORUNLU — bu betik dogrudan gelistirici makinesinde kosturulmak ICIN DEGILDIR.
// Kurslarin font yigini 'Outfit'/'Inter' ile basliyor ama bu fontlar vendor'lanmamis ve CDN
// yasak; render pratikte system-ui'ye dusuyor: Windows'ta Segoe UI, Linux'ta DejaVu, macOS'ta
// SF. Farkli glif -> farkli metin genisligi -> farkli satir kirilmasi -> farkli yerlesim.
// Bu yuzden hem CI hem yerel calistirma AYNI imajda olur:
//     mcr.microsoft.com/playwright:v<package.json'daki TAM surum>-noble
// `npm run visual` / `npm run visual:update` bunu sizin icin yapar (bkz. tests/README.md).
//
// BLOKLAYICI (a11y-audit'in AKSINE): kasitsiz bir gorsel degisiklik CI'i dusurmeli — kabul
// kriteri bu. Kasitli degisiklikte baseline yenileme, bayt-parite fixture'iyla AYNI kurala
// tabidir: ayri bir `chore(test):` commit'i, ozellik PR'ina karistirilmaz.
import { chromium } from "playwright";
import { PNG } from "pngjs";
import pixelmatch from "pixelmatch";
import { readdirSync, mkdirSync, existsSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.join(__dirname, "fixtures");
const BASELINE = path.join(__dirname, "baseline");
const DIFF = path.join(__dirname, "diff");

const UPDATE = process.argv.includes("--update");

// Sabit goruntu alani — snapshot boyutu deterministik olsun. deviceScaleFactor 1: retina
// olcekleme rasterizasyonu degistirir.
const VIEWPORT = { width: 1024, height: 700 };
// Sanal saatin sabitlendigi an: geri sayim basan ekranlar (term_match_race, game, timer_sec
// HUD) gercek zamana bagli kalirsa iki kosu asla eslesmez.
const FROZEN_TIME = new Date("2026-01-01T09:00:00Z");
// Anti-aliasing gurultusu payi. 0 degil (alt-piksel yuvarlamalari ayni imajda bile kenar
// piksellerinde oynayabiliyor), ama gercek bir yerlesim kaymasini yakalayacak kadar dar:
// 1024x700 = 716.800 piksel -> %0.02 = 143 piksel. Tek harflik bir kayma bunun cok ustunde
// fark uretir.
const PIXEL_THRESHOLD = 0.1;      // pixelmatch renk toleransi (0-1)
const MAX_DIFF_RATIO = 0.0002;    // toplam pikselin %0.02'si

// Animasyon/gecis/caret oldurucu — emulateMedia(reducedMotion) ustune ikinci kemer.
// Oynaticinin giris animasyonlari (data-anim) ve ui-chip gecisleri kareyi kaydirabiliyor.
const FREEZE_CSS = `*,*::before,*::after{
  animation:none!important;transition:none!important;
  animation-duration:0s!important;transition-duration:0s!important;
  caret-color:transparent!important;scroll-behavior:auto!important}`;

async function shoot(browser, file) {
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 1,
    reducedMotion: "reduce",
    // Tema kipi fixture'da ACIKCA veriliyor; prefers-color-scheme'i sabitlemek "auto"
    // temalarin kosuya gore degismesini engeller.
    colorScheme: "light",
    locale: "tr-TR",
    timezoneId: "UTC",
  });
  try {
    const page = await context.newPage();
    // Tohumlanmis Math.random. GEREKCE: components/templates.py iki yerde HAM Math.random()
    // kullaniyor (satir ~1661 matching <select> siralamasi, ~2049 sorting baslangic sirasi) —
    // ogrenen icin dogru davranis, ama snapshot icin her yuklemede baska bir kare demek.
    // Urun kodu DEGISTIRILMEZ; rastgelelik yalniz harness tarafinda sabitlenir.
    // (Not: components/engine/rng.js "Math.random YASAK" diyor; bu iki cagri o kurala uymuyor
    //  — ayri bir bulgu, bu issue'nun kapsaminda degil.)
    await page.addInitScript(() => {
      let seed = 0x2f6e2b1;                       // mulberry32, sabit tohum
      Math.random = () => {
        seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    });
    await page.clock.install({ time: FROZEN_TIME });
    await page.goto(`file://${path.join(FIXTURES, file)}`);
    await page.addStyleTag({ content: FREEZE_CSS });
    // Sanal saati ileri sar: init timer'lari deterministik olarak tamamlansin, sonra dondur.
    // Gercek waitForTimeout yerine sanal zaman -> kosudan kosuya ayni.
    // clock.install() zamani MANUEL kontrole alir — kendi kendine ilerlemez, dolayisiyla
    // runFor'dan sonra saat zaten donmus durumdadir; ayrica pauseAt cagirmak gerekmez
    // (ve "cannot fast-forward to the past" hatasi verir).
    await page.clock.runFor(1500);
    // Medya konumunu sifirla. GEREKCE (CI'da olculdu): page.clock SANAL zamani yonetir ama
    // medya oynatmasini YONETMEZ — <video>.currentTime gercek decode hiziyla ilerliyor.
    // Video kutusu maskeli olsa bile oynaticinin KENDI alt barindaki scrubber konumu ve
    // "0:0x / 0:05" suresi makineden makineye kayiyordu (149 piksel; esigin 6 piksel ustu).
    // Cozum esigi gevsetmek DEGIL, konumu sabitlemek: duraklat + basa sar.
    await page.evaluate(() => {
      document.querySelectorAll("video,audio").forEach((m) => {
        try { m.pause(); m.autoplay = false; m.loop = false; m.currentTime = 0; } catch (e) { /**/ }
      });
    });
    await page.clock.runFor(200);   // scrubber/sure gostergesi 0 konumunda yeniden boyansin
    await page.waitForFunction(() => document.fonts && document.fonts.status === "loaded");
    // <video> maskelenir. GEREKCE: cozulmus video karesi kosudan kosuya degisiyor (decode
    // zamanlamasi) — olculdu: screen-video'da ~4000 piksel oynuyor. Bu bizim kodumuz degil,
    // tarayicinin decode'u. Maske elementin KUTUSUNU duz renkle boyar: konum/boyut/object-fit
    // kaynakli bir yerlesim regresyonu HALA yakalanir, yalnizca kare icerigi disarida kalir.
    // Kutunun ICINDEKI gorsel degisiklikler (or. video ustune bindirilen bir katman) bu
    // maskeyle GORUNMEZ olur — bilincli takas, tests/README.md'de yazili.
    return await page.screenshot({
      fullPage: false,
      mask: [page.locator("video")],
      maskColor: "#ff00ff",
    });
  } finally {
    await context.close();
  }
}

function compare(name, actualBuf) {
  const basePath = path.join(BASELINE, `${name}.png`);
  if (!existsSync(basePath)) {
    return {
      ok: false,
      reason: `baseline yok: ${path.relative(process.cwd(), basePath)} — kasitli yeni ` +
        "fixture ise `npm run visual:update` ile uret (AYRI chore(test): commit'i)",
    };
  }
  const expected = PNG.sync.read(readFileSync(basePath));
  const actual = PNG.sync.read(actualBuf);
  if (expected.width !== actual.width || expected.height !== actual.height) {
    return {
      ok: false,
      reason: `boyut farki: baseline ${expected.width}x${expected.height}, ` +
        `simdi ${actual.width}x${actual.height}`,
    };
  }
  const diff = new PNG({ width: expected.width, height: expected.height });
  const changed = pixelmatch(expected.data, actual.data, diff.data,
    expected.width, expected.height, { threshold: PIXEL_THRESHOLD });
  const ratio = changed / (expected.width * expected.height);
  if (ratio > MAX_DIFF_RATIO) {
    mkdirSync(DIFF, { recursive: true });
    writeFileSync(path.join(DIFF, `${name}.diff.png`), PNG.sync.write(diff));
    writeFileSync(path.join(DIFF, `${name}.actual.png`), actualBuf);
    return {
      ok: false,
      reason: `${changed} piksel farkli (%${(ratio * 100).toFixed(4)} > ` +
        `%${(MAX_DIFF_RATIO * 100).toFixed(4)}) — tests/visual/diff/${name}.diff.png`,
    };
  }
  return { ok: true, changed };
}

async function main() {
  let files;
  try {
    files = readdirSync(FIXTURES).filter((f) => f.endsWith(".html")).sort();
  } catch {
    console.error(`Fixture dizini yok: ${FIXTURES}`);
    console.error("Once: python tests/visual/generate_fixtures.py");
    process.exit(1);
  }
  if (files.length === 0) {
    console.error("Fixture bulunamadi — once: python tests/visual/generate_fixtures.py");
    process.exit(1);
  }
  if (UPDATE) {
    mkdirSync(BASELINE, { recursive: true });
    rmSync(DIFF, { recursive: true, force: true });
  }

  const browser = await chromium.launch({
    args: [
      "--force-color-profile=srgb",   // renk yonetimi makineden makineye degismesin
      "--font-render-hinting=none",   // hinting farki = alt-piksel kaymasi
      "--disable-lcd-text",           // alt-piksel anti-aliasing kapali: gri tonlamali, kararli
      "--hide-scrollbars",
    ],
  });
  const failures = [];
  let updated = 0;
  try {
    for (const file of files) {
      const name = file.replace(/\.html$/, "");
      const buf = await shoot(browser, file);
      if (UPDATE) {
        writeFileSync(path.join(BASELINE, `${name}.png`), buf);
        updated++;
        console.log(`baseline yazildi: ${name}.png (${buf.length} bayt)`);
        continue;
      }
      const r = compare(name, buf);
      if (r.ok) console.log(`ok    ${name}${r.changed ? `  (${r.changed} px gurultu)` : ""}`);
      else { console.error(`FARK  ${name}: ${r.reason}`); failures.push(name); }
    }
    // Sahipsiz baseline: fixture silinmis ama PNG kalmis -> sessiz olu dosya birikmesin.
    if (!UPDATE && existsSync(BASELINE)) {
      const names = new Set(files.map((f) => f.replace(/\.html$/, "")));
      for (const png of readdirSync(BASELINE).filter((f) => f.endsWith(".png"))) {
        const n = png.replace(/\.png$/, "");
        if (!names.has(n)) {
          console.error(`FAZLA baseline: ${png} — karsiligi olan fixture yok`);
          failures.push(n);
        }
      }
    }
  } finally {
    await browser.close();
  }

  if (UPDATE) {
    console.log(`\n${updated} baseline yenilendi. AYRI bir chore(test): commit'inde tasiyin.`);
    return;
  }
  if (failures.length) {
    console.error(`\n${failures.length} gorsel regresyon: ${failures.join(", ")}`);
    console.error("Kasitliysa: npm run visual:update (ayri chore(test): commit'i) — tests/README.md");
    process.exit(1);
  }
  console.log(`\n${files.length} snapshot eslesti.`);
}

main().catch((err) => { console.error(err); process.exit(1); });
