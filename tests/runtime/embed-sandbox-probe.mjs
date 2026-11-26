// embed_html iframe izolasyonu GERÇEK tarayıcıda, paket modunda, HTTP üzerinden (LMS'teki gibi aynı
// köken: iframe src göreli `assets/…`). file:// kullanılmaz — Chromium file:// kökenini zaten opak sayar ve
// kaçışı gizler. Kötü niyetli artifact: üst DOM, window.parent.API (SCORM), üst pencere gezinmesi, form
// gönderimi; köprü (postMessage → cmi) çalışmaya devam etmeli.
// Kullanım: PYTHONPATH=. node tests/runtime/embed-sandbox-probe.mjs   (çıkış kodu 0 = geçti)
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";

const EVIL = `<!doctype html><html><body><script>
const r = {};
try { r.parentDom = !!window.parent.document.title || true; } catch (e) { r.parentDom = false; }
try { r.parentApi = !!(window.parent.API || window.parent.API_1484_11); } catch (e) { r.parentApi = false; }
try { r.storage = (localStorage.setItem("x","1"), true); } catch (e) { r.storage = false; }
try { window.top.location.href = "about:blank#escaped"; r.topNav = true; } catch (e) { r.topNav = false; }
window.parent.postMessage({ probe: r }, "*");
window.parent.postMessage({ scorm: "setScore", value: 77 }, "*");
</script></body></html>`;

const PY = `
import sys
from pydantic import TypeAdapter
import os
from components.renderer import render_html, load_runtime_js
from core.packager import RUNTIME_REL
from core.project import Project, Screen, new_project_id, AssetRef
out = sys.argv[1]
emb = open(sys.argv[2], "rb").read()
a = [AssetRef(id="h", filename="evil.html", mime="text/html", size_bytes=len(emb), sha256="0",
              rel_path="assets/evil.html")]
s = TypeAdapter(Screen).validate_python({"type": "embed_html", "id": "e1", "title": "Gomulu", "html_asset_id": "h"})
p = Project(id=new_project_id(), title="t", screens=[s], assets=a)
rt = load_runtime_js()
open(out, "w").write(render_html(p, mode="package", runtime_js=rt))
rp = os.path.join(os.path.dirname(out), RUNTIME_REL)
os.makedirs(os.path.dirname(rp), exist_ok=True)
open(rp, "w").write(rt)
`;

const dir = mkdtempSync(path.join(tmpdir(), "embed-sbx-"));
let failures = 0;
const check = (name, got, want) => {
  const ok = got === want;
  if (!ok) failures++;
  console.log(`  ${ok ? "✓" : "✗"} ${name} = ${got} (beklenen ${want})`);
};

try {
  mkdirSync(path.join(dir, "assets"));
  writeFileSync(path.join(dir, "assets", "evil.html"), EVIL);
  execFileSync("python3", ["-c", PY, path.join(dir, "index.html"), path.join(dir, "assets", "evil.html")],
               { cwd: process.cwd(), stdio: ["ignore", "inherit", "inherit"] });
  const server = http.createServer((req, res) => {
    const p = path.join(dir, decodeURIComponent(new URL(req.url, "http://x").pathname));
    try {
      const body = readFileSync(p.endsWith("/") ? path.join(p, "index.html") : p);
      const ct = p.endsWith(".html") || p.endsWith("/") ? "text/html" : p.endsWith(".js") ? "text/javascript" : "application/octet-stream";
      res.writeHead(200, { "content-type": ct });
      res.end(body);
    } catch { res.writeHead(404); res.end(); }
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${server.address().port}/index.html`;

  const browser = await chromium.launch();
  const page = await browser.newPage();
  // LMS adaptörü: parent'ta sahte SCORM 1.2 API; köprünün yazdığı skor burada görünür
  await page.addInitScript(() => {
    window.__probe = null;
    window.__cmi = {};
    window.API = { LMSInitialize: () => "true", LMSFinish: () => "true", LMSGetValue: (k) => window.__cmi[k] || "",
      LMSSetValue: (k, v) => { window.__cmi[k] = v; return "true"; }, LMSCommit: () => "true",
      LMSGetLastError: () => "0", LMSGetErrorString: () => "", LMSGetDiagnostic: () => "" };
    window.addEventListener("message", (ev) => { if (ev.data && ev.data.probe) window.__probe = ev.data.probe; });
  });
  await page.goto(url);
  await page.waitForFunction(() => window.__probe !== null, null, { timeout: 10000 });
  await page.waitForTimeout(500);
  const r = await page.evaluate(() => ({ probe: window.__probe, href: location.href, cmi: window.__cmi }));
  console.log("== embed_html sandbox (paket modu, HTTP aynı köken)");
  check("üst DOM erişimi engelli", r.probe.parentDom, false);
  check("window.parent.API (SCORM) erişimi engelli", r.probe.parentApi, false);
  check("üst pencere gezinmesi engelli", r.probe.topNav === false && !r.href.includes("escaped"), true);
  check("köprü çalışıyor (skor cmi'ye yazıldı)", Object.values(r.cmi).some((v) => String(v) === "77"), true);
  await browser.close();
  server.close();
} finally {
  rmSync(dir, { recursive: true, force: true });
}
if (failures) {
  console.log(`✗ embed sandbox probe BAŞARISIZ — ${failures} ihlal`);
  process.exit(1);
}
console.log("✓ embed sandbox probe: tüm kontroller geçti");
