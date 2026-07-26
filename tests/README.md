# Testler & Doğrulama

## Birim + golden testler

```bash
pip install -e ".[dev]"
pytest -q                      # tests/test_golden.py + tests/test_units.py
```

- `test_golden.py` — DoD (CONTRACTS.md §11): `examples/small.json` → `build_from_spec` → zip aç →
  `imsmanifest.xml` geçerli + `index.html` + scorm-again gömülü + quiz skorlama hook'u. Ayrıca
  `rich.json` ile 10 ekran tipinin tamamı + asset paketleme; preview'in tek-dosya / harici bağımlısız olması.
- `test_units.py` — manifest well-formed (1.2/2004), SSRF blok listesi (private/CGNAT/ULA/metadata),
  https/userinfo reddi, data-URI çözme + boyut limiti, HTML sanitizasyon, fast-path + idempotency, kota.

Testler `SCORM_AUTH_ENABLED=0` ile in-memory FastMCP `Client` kullanır (ağ yok); `conftest.py`
geçici `DATA_DIR` kurar.

## MCP Inspector

Sunucuyu kaldır ve araçları görüntüle:

```bash
fastmcp run server.py --transport http --host 0.0.0.0 --port 8000
# başka terminalde:
npx @modelcontextprotocol/inspector
#   Transport: Streamable HTTP   URL: http://localhost:8000/mcp
#   (auth açıksa) Header: Authorization: Bearer <api_key>
```

12 tool görünmeli: create_project, add_screen, update_screen, list_screens, remove_screen,
set_theme, set_tracking, add_asset, preview, build_package, validate_package, build_from_spec.

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
