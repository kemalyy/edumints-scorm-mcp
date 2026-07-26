# scorm-mcp

## Live demos

| [Be a Password Hero!](https://scorm.edumints.com/demo/password-hero) | [Spot the Phish](https://scorm.edumints.com/demo/spot-the-phish) | [The Ad Hominem Argument](https://scorm.edumints.com/demo/ad-hominem) |
|:---:|:---:|:---:|
| [![Password Hero demo](docs/assets/demo-password-hero.png)](https://scorm.edumints.com/demo/password-hero) | [![Spot the Phish demo](docs/assets/demo-spot-the-phish.png)](https://scorm.edumints.com/demo/spot-the-phish) | [![Ad Hominem demo](docs/assets/demo-ad-hominem.png)](https://scorm.edumints.com/demo/ad-hominem) |
| Ages 9–13 · `style-playful` | Corporate · `style-minimal` | Graduate · `style-premium` |


> **Yazar Claude, montajcı sunucu.** Etkileşimli, SCORM uyumlu eğitim içeriği üreten bir **MCP sunucusu**.
> Claude (host tarafında) bu sunucunun araçlarını çağırarak temalı slaytlar, quizler,
> sürükle-bırak/hotspot etkileşimleri, dallanma senaryoları ve video içeren kurslar tasarlar;
> sunucu içeriği **paketler ve sunar**: HTML5 + `scorm-again` runtime + `imsmanifest.xml` → `.zip`.
> Çıktı herhangi bir LMS'e (Moodle, SCORM Cloud vb.) yüklenebilir.

Sunucu **LLM çağırmaz** — deterministik, ucuz, çok-kullanıcılı ücretsiz dağıtıma uygun.

## Durum

✅ **Faz 1 tamamlandı** — tüm modüller yazıldı ve test edildi. Sözleşme: [`CONTRACTS.md`](./CONTRACTS.md).

- 12 tool in-memory MCP client ile uçtan uca çalışıyor; **29/29 test geçiyor** (golden dahil).
- Örnek kurslar (`examples/small.json`, `examples/rich.json`) geçerli SCORM zip'lerine derleniyor.
- İlk kapasite (lokal dev baseline, in-memory): **~283 build/s, p95 60 ms** — bkz. [`tests/README.md`](./tests/README.md).

### API anahtarı yönetimi (auth varsayılan AÇIK)

```bash
DATA_DIR=/data python tools/manage_keys.py create --label "Okul X" --max-projects 100 --max-mb 500
DATA_DIR=/data python tools/manage_keys.py list
```
Ham anahtar yalnız oluşturmada bir kez gösterilir (DB'de sha256 hash saklanır).

## Mimari (özet)

| Katman | Konum | Sorumluluk |
|---|---|---|
| Sunucu/Transport/Auth | `server.py`, `auth/` | FastMCP, Streamable HTTP, çoklu API-key + kota, route'lar |
| Çekirdek & Paketleme | `core/` | veri modeli, store (SQLite WAL + fs), manifest, build-as-job, validator |
| Bileşen & Tema | `components/`, `themes/` | `spec → HTML` renderer, ekran tipleri, tema token'ları |
| Runtime | `runtime/` | vendored `scorm-again` (UMD/IIFE) |

## Tool'lar (v1)

`create_project`, `add_screen`, `update_screen`, `list_screens`, `remove_screen`, `set_theme`,
`set_tracking`, `add_asset`, `preview`, `build_package`, `validate_package`, `build_from_spec`.

Tam imzalar ve şemalar: [`CONTRACTS.md`](./CONTRACTS.md).

## Lokal geliştirme (Faz 1 sonrası)

```bash
pip install -e ".[dev]"
# Streamable HTTP
fastmcp run server.py --transport http --host 0.0.0.0 --port 8000
# veya lokal stdio testi
fastmcp run server.py --transport stdio
```

MCP Inspector ile araçları görüntüle: (Faz 1/D ajanı script ekleyecek).

## Deployment (Coolify)

- Build pack: **Dockerfile**, exposed port `8000`, kalıcı volume → `DATA_DIR`.
- Domain: `mcp.edumints.com`, path `/scorm` (Traefik path routing + prefix strip), otomatik TLS.
- **Ters proxy:** Streamable HTTP streaming yapar → **buffering kapalı** olmalı (Traefik genelde sorunsuz).
- Env: bkz. [`.env.example`](./.env.example) ve `CONTRACTS.md §8`.

### Claude'a bağlama

Custom Connector → URL `https://mcp.edumints.com/scorm/mcp`, header: `Authorization: Bearer <api_key>`.

## Manuel doğrulama (DoD)

1. `build_package` → inen `.zip`'i **SCORM Cloud ücretsiz hesabına** yükle, çalıştığını gör.
2. `preview` çıktısı tek dosya, harici bağımlılık yok — tarayıcıda aç.
3. `Dockerfile` build olur, konteyner `/health` 200 döner.
4. Yük testi (k6/locust) kapasite raporu: (Faz 1/D sonrası buraya).

## Kapsam dışı (v1)

xAPI/cmi5, SCORM 2004 sequencing tam implementasyonu, OAuth, çok-instance, admin paneli,
görsel/video üretimi (`add_asset` ile dış MCP çıktısı alınır).
