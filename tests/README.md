# Testler & Doğrulama

## Birim + golden testler

```bash
pip install -e ".[dev]"
pytest -q                      # tests/test_golden.py + tests/test_units.py
```

- `test_golden.py` — DoD (definition of done): `examples/small.json` → `build_from_spec` → zip aç →
  `imsmanifest.xml` geçerli + `index.html` + scorm-again gömülü + quiz skorlama hook'u. Ayrıca
  `rich.json` ile (fixture'ın kapsadığı ekran tipleri: 10/28) + asset paketleme; preview'in tek-dosya / harici bağımlısız olması.
- `test_units.py` — manifest well-formed (1.2/2004), SSRF blok listesi (private/CGNAT/ULA/metadata),
  https/userinfo reddi, data-URI çözme + boyut limiti, HTML sanitizasyon, fast-path + idempotency, kota.

Testler `SCORM_AUTH_ENABLED=0` ile in-memory FastMCP `Client` kullanır (ağ yok); `conftest.py`
geçici `DATA_DIR` kurar.

## Görsel regresyon (#150)

Ekran tiplerinin ve tema katmanlarının **görünen** çıktısını piksel karşılaştırmasıyla kilitler.
Bayt-parite fixture'ı yalnız HTML'i koruyor; bir CSS değişikliği düzeni bozduğunda "bayt farkı
var" diyor ama **neyin nasıl bozulduğunu göstermiyor**. Bu harness onu gösterir.

**BLOKLAYICI** (`a11y-audit`in aksine): kasıtsız bir görsel değişiklik CI'ı düşürür.

### Neden konteyner — bu adım atlanamaz

Kursların font yığını `'Outfit', system-ui, …` ile başlıyor ama **Outfit/Inter vendor'lanmamış**
ve CDN bilinçli olarak yasak. Yani render pratikte `system-ui`ye düşüyor: Windows'ta Segoe UI,
Linux'ta DejaVu, macOS'ta SF. Farklı glif → farklı metin genişliği → farklı satır kırılması →
farklı yerleşim. Snapshot doğrudan geliştirici makinesinde alınırsa CI'da **her metin taşıyan
ekran** kırılır. Bu yüzden hem CI hem yerel çalıştırma AYNI imajda olur:

```
mcr.microsoft.com/playwright:v<package.json'daki TAM playwright sürümü>-noble
```

`playwright` bu yüzden **tam sürüme sabit** (aralık değil) ve CI'daki imaj tag'i onunla eşleşmek
zorunda — `tests/test_visual_harness.py` ikisini test olarak kilitler.

### Çalıştırma

```bash
# 1) fixture'lar (examples/**'dan üretilir; depoya girmez, .gitignore'da)
python tests/visual/generate_fixtures.py

# 2) karşılaştır (Linux/macOS)
docker run --rm -v "$PWD":/work -w /work   mcr.microsoft.com/playwright:v1.61.1-noble node tests/visual/snapshot.mjs

# Windows / Git Bash — yol dönüşümünü kapat:
MSYS_NO_PATHCONV=1 docker run --rm -v "C:/…/scorm-mcp:/work" -w /work   mcr.microsoft.com/playwright:v1.61.1-noble node tests/visual/snapshot.mjs
```

Fark çıkarsa `tests/visual/diff/<ad>.diff.png` (kırmızı = değişen piksel) ve `.actual.png`
yazılır; CI bunları `visual-diff` artefaktı olarak yükler.

### Baseline yenileme — bayt-parite fixture'ıyla AYNI kural

Değişiklik **kasıtlıysa** aynı komutu `--update` ile koşun ve yenilenen PNG'leri **AYRI bir
`chore(test):` commit'inde** taşıyın. Özellik PR'ına karıştırılmaz — üçüncü seçenek yok.

```bash
docker run --rm -v "$PWD":/work -w /work   mcr.microsoft.com/playwright:v1.61.1-noble node tests/visual/snapshot.mjs --update
```

### Kapsam (bilinçli olarak dar)

31 tip × 18 tema × 2 kip = 1116 snapshot alınmadı. Bunun yerine iki katman:

- **A — ekran tipi kapsamı:** 31 tipin her biri bir kez, tek tema, açık kip (`screen-*.png`).
- **B — tema katmanlaması:** TEK sabit ekran (`mcq`) × {marka teması açık, marka teması koyu,
  ikinci stil preseti} (`theme-*.png`). Aynı ekranı üç tema altında karşılaştırmak tema
  regresyonunu ekran regresyonundan ayırır.

İçerik uydurulmuyor: `examples/**` 31 tipin 30'unu zaten kapsıyor; üreteç oradan ilgili ekranı
ve referans verdiği asset'leri çekip tek ekranlık bir projeye sarar. Yalnız `embed_html`
sentezlenir. Yeni bir tip eklenip örneği yazılmazsa hem üreteç hem `tests/test_visual_harness.py`
hata verir.

### Determinizmi sağlayan şeyler

| Kaynak | Çözüm |
|---|---|
| font/OS farkı | sabitlenmiş konteyner imajı |
| Chromium sürümü | `playwright` tam sürüme sabit + eşleşen imaj tag'i |
| animasyon/geçiş | `reducedMotion: reduce` + tüm animasyon/geçişi kapatan enjekte CSS |
| geri sayım / tarih | `page.clock.install()` ile sanal saat, sabit ana dondurulur |
| `Math.random()` karıştırması | harness'ta tohumlanmış `Math.random` (mulberry32) |
| `<video>` decode karesi | `screenshot({ mask: [video] })` — kutu korunur, kare içeriği hariç |
| retina ölçekleme | `deviceScaleFactor: 1` |
| alt-piksel anti-aliasing | `--disable-lcd-text`, `--font-render-hinting=none`, sRGB profili |

Kalan gürültü payı: toplam pikselin **%0.02**'si (1024×700'de 143 piksel). Tek harflik bir kayma
bunun çok üstünde fark üretir — üç ardışık koşuda 34/34 eşleşme ölçüldü.

**Bilinçli takas:** `<video>` maskesi kutunun İÇİNDEKİ görsel değişiklikleri (ör. video üstüne
bindirilen bir katman) görünmez kılar; konum/boyut regresyonu yine yakalanır.

**Yan bulgu:** `components/templates.py` iki yerde ham `Math.random()` kullanıyor (matching
`<select>` sıralaması, sorting başlangıç sırası) — oysa `components/engine/rng.js` "Math.random
YASAK" diyor. Öğrenen için doğru davranış; harness tarafında tohumlanarak çözüldü, ürün kodu
değiştirilmedi. Kuralın iki istisnası ayrıca değerlendirilmeli.

## MCP Inspector

Sunucuyu kaldır ve araçları görüntüle:

```bash
fastmcp run server.py --transport http --host 0.0.0.0 --port 8000
# başka terminalde:
npx @modelcontextprotocol/inspector
#   Transport: Streamable HTTP   URL: http://localhost:8000/mcp
#   (auth açıksa) Header: Authorization: Bearer <api_key>
```

43 tool görünmeli (tam liste: `server.py` içindeki `@mcp.tool` tanımları).

## Yük testi (build yolu)

```bash
# in-memory (çekirdek build kapasitesi, ağ yok)
python tests/load/load_build.py -c 16 -n 300

# uzak (gerçek HTTP sunucu)
MCP_URL=https://mcp.edumints.com/scorm/mcp API_KEY=<key> \
  python tests/load/load_build.py -c 16 -n 300
```

throughput + p50/p95/p99 raporlar. Not: `build_from_spec` her çağrıda yeni proje açar →
yük testinde `MAX_PROJECTS_PER_KEY` / `MAX_PROJECT_MB` env'lerini yükseltin yoksa kota guardrail'i devreye girer.

### İlk kapasite raporu (lokal dev baseline, in-memory)

| ölçüt | değer |
|---|---|
| ortam | yerel dev (in-memory, ağ yok), Python 3.11 |
| concurrency | 16 |
| istek | 300 build_from_spec (4 ekranlı kurs, 1 quiz) |
| hata | 0 |
| throughput | **~283 build/s** |
| p50 / p95 / p99 | **56 / 60 / 68 ms** |

> Hedef ARM kutusunda (Coolify, 9-core) `BUILD_WORKERS=8` ile yeniden ölçülmeli; bu sayı
> üst-sınır referansıdır (HTTP/proxy ek yükü hariç). Gerçek dağıtım sonrası bu tablo güncellenecek.

## Manuel doğrulama — SCORM Cloud (ücretsiz)

1. `build_from_spec` veya `build_package` ile zip üret, `download_url`'den indir.
2. https://cloud.scorm.com ücretsiz hesap → **Add Content → Import a SCORM package** → zip'i yükle.
3. Launch et: slaytlar geçişli görünmeli, quiz'i çöz, **skorun ve tamamlanma durumunun** SCORM Cloud
   raporunda (`cmi.core.score.raw` / `lesson_status`) göründüğünü doğrula.

## Coolify deploy notları

- Build pack: **Dockerfile**; exposed port **8000**; kalıcı volume → `DATA_DIR` (`/data`).
- Domain `mcp.edumints.com`, path `/scorm` (Traefik path routing + prefix strip), otomatik TLS.
- **Ters proxy buffering KAPALI** olmalı (Streamable HTTP streaming yapar; Traefik genelde sorunsuz).
- Env: bkz. `.env.example`. `PUBLIC_BASE_URL` tam dış URL'i (prefix dahil) içermeli.
- Claude'a bağlama: Custom Connector → `https://mcp.edumints.com/scorm/mcp`, header `Authorization: Bearer <api_key>`.
