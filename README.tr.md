# edumints SCORM MCP

[![License: MIT](https://img.shields.io/github/license/kemalyy/edumints-scorm-mcp)](LICENSE)
[![Release](https://img.shields.io/github/v/release/kemalyy/edumints-scorm-mcp)](https://github.com/kemalyy/edumints-scorm-mcp/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-6E56CF)](https://modelcontextprotocol.io)

## Canlı demolar

Üç eksiksiz kurs — üç seviye, üç görsel kimlik — tamamen bu sunucuyla oluşturuldu ve canlı bir
deploy'dan sunuluyor. **Başlatmak için herhangi bir ekran görüntüsüne tıklayın.**

| [Be a Password Hero!](https://scorm.edumints.com/demo/password-hero) | [Spot the Phish](https://scorm.edumints.com/demo/spot-the-phish) | [The Ad Hominem Argument](https://scorm.edumints.com/demo/ad-hominem) |
|:---:|:---:|:---:|
| [![Password Hero demosu](docs/assets/demo-password-hero.png)](https://scorm.edumints.com/demo/password-hero) | [![Spot the Phish demosu](docs/assets/demo-spot-the-phish.png)](https://scorm.edumints.com/demo/spot-the-phish) | [![Ad Hominem demosu](docs/assets/demo-ad-hominem.png)](https://scorm.edumints.com/demo/ad-hominem) |
| 9–13 yaş · internet güvenliği · `style-playful` + özel marka | Kurumsal oryantasyon · e-posta güvenliği · `style-minimal` + kurumsal marka | Lisansüstü · argümantasyon teorisi · `style-premium` |

Her demo: anlatı ipliği, gerçekçi artifact-mockup SVG'leri, bayrak-bulma simülasyonları,
önce/sonra karşılaştırmaları, zaman çizelgeleri, bir vaka oyunu ve adaptif geri bildirim —
altyapıda soru düzeyinde SCORM raporlamasıyla birlikte.

> **Etkileşimli, SCORM-uyumlu e-öğrenme kursları üreten bir MCP sunucusu.**
> Sen (ya da Claude gibi bir yapay zekâ istemcisi) **yazarsın**; bu sunucu **derleyicidir**.
> Kursu yapılandırılmış bir spec olarak tarif edersin — sunucu doğrular, render eder ve
> **kendi kendine yeten bir SCORM zip** olarak paketler; her LMS'te çalışır (Moodle, SCORM Cloud, …).

**🌐 Diller:** [English](README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Azərbaycanca](README.az.md) · [Қазақша](README.kk.md) · [Кыргызча](README.ky.md)

Açık kaynak; **[edumints.com](https://edumints.com)** platformu tarafından geliştirildi. **Kendi
bilgisayarında veya kendi sunucunda host edilebilir** ve **geliştirmeye/katkıya açıktır**.

---

## Fikir (farklı bir yaklaşım)

E-öğrenme genelde ağır masaüstü araçlarıyla elle üretilir. Burada **bir yapay zekâ istemcisi kursu
tarif eder** (hedefler, ekranlar, quizler, dallanma, medya) — [Model Context Protocol](https://modelcontextprotocol.io)
üzerinden — ve zor kısmı sunucu yapar: doğrulama, premium tema, erişilebilir HTML render, SCORM
runtime köprüsü ve paketleme. Sonuç standartlara uygun bir SCORM paketi — sağlayıcı kilidi yok.

**Yazar = MCP istemcisi · Derleyici = bu sunucu.**

![Yerleşik slayt-sahne player'ında render edilen bir quiz ekranı](docs/assets/screenshot-player.png)

## Özellikler

- **28 ekran tipi** — başlık, içerik, çoktan seçmeli, doğru/yanlış, boşluk doldurma, sürükle-bırak,
  hotspot, dallanan senaryo, akordeon, sekme, bilgi kartı, eşleştirme, sıralama, zaman çizelgesi,
  lottie, **rehberli yazılım simülasyonu**, video, özet, **karar senaryosu**, **terim yarışı**,
  **kaçış odası**, **etiketli diyagram**, **veri grafiği**, **görsel karşılaştırma**,
  **sonuç dökümü**, **anket / yansıma**, **kompozisyonel oyun**, **adaptif pratik**.
- **Kompozisyonel oyun motoru** — **`game`** ekranı mekanik primitifleri (skor/can/süre/ipucu) +
  bildirimsel `when olay if koşul then aksiyon` kurallarını + dallanan düğümleri besteler;
  **`adaptive_practice`** ekranı yeterliliği (Elo veya Bayesian Knowledge Tracing) tahmin edip zorluğu
  öğrenciye kalibre eder. Opsiyonel **xAPI** telemetri (cmi5: kısmî — launch algılama), **anti-slop kalite kapısı** (`lint_course`)
  ve oyun erişilebilirliği (WCAG 2.2.1). Hepsi deterministik — sunucuda LLM yok.
- **Slayt-sahne oynatıcı** — her ekrana ölçeklenen sabit 16:9 sahne, player bar (oynat/seekbar/
  altyazı/menü/replay) ve seslendirmeyle senkron **zamanlanmış timeline akışı**. Bölümlere göre
  gruplu menü. Ayarlanabilir sahne ölçüsü; tam responsive/mobil; inline SVG ikonlar (emoji yok).
- **Mantık & oyunlaştırma** — değişkenler/durum, koşullu görünürlük, dallanma, puan & süre HUD'u.
- **Değerlendirme** — hizalı sorular, doğru/yanlış geri bildirimi, SCORM'a yazılan skor.
- **Medya** — çapraz-MCP içe aktarım (ses/görsel/video'yu kendi MCP'lerinden getir → `add_asset`),
  ffmpeg işleme, **programatik motion-graphic/veri-viz video** (HyperFrames) ve hızlı seslendirme
  için dahili **Türkçe TTS** (Piper, çevrimdışı).
- **Tema & erişilebilirlik** — açık/nötr/yüksek-kontrast preset'leri, marka token'ları, WCAG-bilinçli,
  `prefers-reduced-motion` desteği.
- **SCORM 1.2 & 2004**, deterministik paketleme, maliyet guardrail'leri, opt-in/lazy ağır özellikler
  (bir kurs kullanmıyorsa yüklenmez).

## Hızlı başlangıç (kendi host'unda)

### Docker (önerilen)
```bash
git clone https://github.com/kemalyy/edumints-scorm-mcp.git
cd edumints-scorm-mcp
docker build -t edumints-scorm-mcp .
docker run -p 8000:8000 -v "$PWD/data:/data" edumints-scorm-mcp
# MCP ucu: http://localhost:8000/mcp   ·   sağlık: http://localhost:8000/health
```
Image, opsiyonel özelliklerin hepsini içerir (ffmpeg, video için Node + HyperFrames, TTS için
Piper + Türkçe ses modeli).

> **Apple Silicon + Docker Desktop:** `docker build`/`run` `Illegal instruction` (SIGILL) ile
> çöküyorsa, bu `cryptography` paketinin Rust binding'lerindeki üst-akış native-ARM64 sorunu
> ([pyca/cryptography#14733](https://github.com/pyca/cryptography/issues/14733)) — bu repo'nun
> hatası değil. Çözüm: `docker build --platform linux/amd64 -t edumints-scorm-mcp .` (emülasyonla çalışır).

### Lokal (Python)
```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[tts]"          # ".[tts]" çevrimdışı Türkçe TTS'i (Piper) ekler; istemezsen çıkar
python server.py              # MCP'yi HTTP üzerinden sunar
```
Video üretimi için ayrıca Node 22+ ve HyperFrames (`npm i -g hyperframes`) + ffmpeg kur.

### Yapılandırma
`.env.example`'ı kopyalayıp uyarlayın (veri dizini, kotalar, base URL, TTL). Tüm seçenekler dosyada.
Lokal çalıştırmak için **hiçbir secret gerekmez**.

## Bir yapay zekâ istemcisi bağlama

Herhangi bir MCP istemcisini `http://<host>:8000/mcp` adresine yönlendir:
- **Claude** (masaüstü/web/Code) — connector / MCP sunucusu olarak ekle.
- **Antigravity** ve diğer MCP istemcileri — aynı uç (HTTP/Streamable).

Sonra iste: *"X konusunda 6 dakikalık, quizli ve özetli etkileşimli bir kurs oluştur."* İstemci
aşağıdaki araçları çağırır; indirilebilir bir SCORM zip alırsın.

> **Authoring skill** ile birlikte çalışır (bir yapay zekâ istemcisine bu sunucuyla kaliteli kurs
> üretmeyi öğreten Claude Agent Skill): https://github.com/kemalyy/edumints-scorm-skill

## Örnek

Bir kurs tek bir `build_from_spec` çağrısıyla üretilir (bu `examples/small.json`, kısaltılmış):

```json
{
  "title": "SCORM'a Giriş",
  "scorm_version": "1.2",
  "language": "tr",
  "tracking": { "completion_rule": "viewed_all_and_passed", "passing_score": 50 },
  "screens": [
    { "type": "title_slide", "id": "t1", "title": "SCORM'a Giriş", "subtitle": "5 dakikada temel kavramlar" },
    { "type": "content_slide", "id": "c1", "title": "SCORM Nedir?", "body_html": "<p><strong>SCORM</strong>, e-öğrenme içeriğinin LMS ile konuşmasını sağlar.</p>" },
    { "type": "mcq", "id": "q1", "title": "Mini Quiz", "prompt_html": "<p>SCORM ne işe yarar?</p>",
      "options": [
        { "id": "a", "text_html": "İçerik–LMS iletişimi", "correct": true },
        { "id": "b", "text_html": "Video düzenleme" }
      ], "points": 10 },
    { "type": "summary", "id": "s1", "title": "Tebrikler", "body_html": "<p>Temel kavramları öğrendiniz.</p>" }
  ]
}
```

```
build_from_spec(spec) → { project_id, screens: 4, warnings: [] }
build_package(project_id) → indirilebilir SCORM 1.2 zip
                              ├─ imsmanifest.xml
                              ├─ index.html          (kendi kendine yeten player + runtime)
                              └─ assets/
```

Zip, herhangi bir SCORM 1.2/2004 LMS'e (Moodle, SCORM Cloud, Rustici Engine, …) çalışma-zamanı
sunucu bağımlılığı olmadan içe aktarılabilir. Tam çalışan spec [`examples/small.json`](examples/small.json)
dosyasında; daha fazla gerçek-dünya spec (oyunlar, dallanma, temalı kurslar) [`examples/`](examples/)
altında.

## Başlıca araçlar (MCP)

| Araç | Amaç |
|---|---|
| `build_from_spec` | Tek JSON spec → doğrulanmış proje + paketlenmiş SCORM zip (ana yol) |
| `create_project` / `add_screen` / `update_screen` / … | Granüler, artımlı düzenleme |
| `set_theme` / `set_tracking` | Tema + tamamlanma/skor kuralları |
| `add_asset` | Ses/görsel/video içe aktarım (data-URI veya https, SSRF-korumalı) |
| `synthesize_speech` | Dahili Türkçe seslendirme (Piper, çevrimdışı) → ses asset |
| `make_video_from_image_audio` / `render_motion_video` / `render_screen_video` | Video (ffmpeg / HyperFrames) |
| `preview` / `validate_package` / `build_package` | Önizle, doğrula, SCORM zip indir |

## Mimari

```
MCP istemcisi (yazar)  ──►  scorm-mcp (derleyici)
                              ├─ core/        modeller (Pydantic), paketleme, depolama
                              ├─ components/  HTML renderer + runtime motoru + video derleyici
                              ├─ auth/        API-key + OAuth, SSRF korumaları
                              ├─ themes/      tasarım token'ları / preset'ler
                              ├─ runtime/     vendored SCORM runtime (scorm-again, MIT)
                              └─ server.py    FastMCP araçları (HTTP)
```
Çıktı: kendi kendine yeten `index.html` + `imsmanifest.xml` + asset'ler + SCORM runtime, zip'li.

## Katkı

Issue ve PR'lar memnuniyetle. Kod tabanı küçük/odaklı modüller, additive değişiklikler ve
geriye-uyumu tercih eder. [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

## Testler

Testler: `pytest`.

## Lisanslar

- Bu proje: **MIT** — [LICENSE](LICENSE).
- Gömülü 3. taraf bileşenler (scorm-again, lottie-web): [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**edumints.com** tarafından geliştirildi. SCORM, ADL'nin ticari markasıdır; anılan diğer ürün adları
ilgili sahiplerinin ticari markalarıdır (yalnız tanımlayıcı/nominative kullanım).


<!-- synced: d398775 -->
