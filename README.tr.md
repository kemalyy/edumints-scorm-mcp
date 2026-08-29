# edumints SCORM MCP

[![License: MIT](https://img.shields.io/github/license/kemalyy/edumints-scorm-mcp)](LICENSE)
[![Release](https://img.shields.io/github/v/release/kemalyy/edumints-scorm-mcp)](https://github.com/kemalyy/edumints-scorm-mcp/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-6E56CF)](https://modelcontextprotocol.io)

> **Etkileşimli, standartlara uygun e-öğrenme kursları derleyen bir MCP sunucusu.**
> Sen (ya da Claude gibi bir yapay zekâ istemcisi) **yazarsın**; bu sunucu **derleyicidir**.
> Kursu yapılandırılmış bir spec olarak tarif edersin — sunucu doğrular, render eder ve
> **kendi kendine yeten bir SCORM zip** olarak paketler; her LMS'te çalışır (Moodle, SCORM Cloud,
> Rustici Engine, …).
> Deterministik — **sunucuda LLM çalışmaz**.

**🌐 Diller:** [English](README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Azərbaycanca](README.az.md) · [Қазақша](README.kk.md) · [Кыргызча](README.ky.md)

## Canlı demolar

Dört eksiksiz kurs — dört hedef kitle, dört görsel kimlik — tamamen bu sunucuyla oluşturuldu ve
canlı bir deploy'dan sunuluyor. **Başlatmak için herhangi bir ekran görüntüsüne tıklayın.**

| [Be a Password Hero!](https://scorm.edumints.com/demo/password-hero) | [Spot the Phish](https://scorm.edumints.com/demo/spot-the-phish) | [The Ad Hominem Argument](https://scorm.edumints.com/demo/ad-hominem) | [Grafik Dedektifi](https://scorm.edumints.com/demo/grafik-dedektifi) |
|:---:|:---:|:---:|:---:|
| [![Password Hero demosu](docs/assets/demo-password-hero.png)](https://scorm.edumints.com/demo/password-hero) | [![Spot the Phish demosu](docs/assets/demo-spot-the-phish.png)](https://scorm.edumints.com/demo/spot-the-phish) | [![Ad Hominem demosu](docs/assets/demo-ad-hominem.png)](https://scorm.edumints.com/demo/ad-hominem) | [![Grafik Dedektifi demosu](docs/assets/demo-grafik-dedektifi.png)](https://scorm.edumints.com/demo/grafik-dedektifi) |
| 9–13 yaş · internet güvenliği · `style-playful` + özel marka | Kurumsal oryantasyon · e-posta güvenliği · `style-minimal` + kurumsal marka | Lisansüstü · argümantasyon teorisi · `style-premium` | Türkçe · veri okuryazarlığı · keşif-temelli (5E) · kanıt-bağlı ölçme |

Her demo: anlatı ipliği, gerçekçi artifact-mockup SVG'leri, bayrak-bulma simülasyonları,
önce/sonra karşılaştırmaları, zaman çizelgeleri, bir vaka oyunu ve adaptif geri bildirim —
altyapıda soru düzeyinde SCORM raporlamasıyla birlikte.

## Bu proje neden var

E-öğrenme genelde ağır masaüstü yazarlık araçlarıyla elle üretilir. Bu proje kurs üretimini
bunun yerine **yapay zekâ ajanları için altyapı** olarak ele alır:

- **Kurulumsuz yazarlık.** Herhangi bir MCP istemcisini barındırılan uca bağla ve üretmeye başla —
  toolchain yok, yerel kurulum yok. İstemci kursu tarif eder (hedefler, ekranlar, quizler,
  dallanma, medya) — [Model Context Protocol](https://modelcontextprotocol.io) üzerinden — ve zor
  kısmı sunucu yapar: doğrulama, tema, erişilebilir HTML render, SCORM runtime köprüsü ve paketleme.
- **Hayır diyebilen bir kalite kapısı.** Yapay zekâ hızlıca çok sayıda vasat içerik üretebilir. Bu
  sunucu geri iter: her spec'te şema doğrulaması, hata katmanı **build'i bloklayan** bir
  **anti-slop lint** (`lint_course`) ve bir CI kanıt zinciri (XSD + gerçek SCORM Cloud içe
  aktarımları + davranışsal probe) — böylece yayınlanan şey LMS'te gerçekten çalışır; bkz.
  [Standartlar & kanıt](#standartlar--kanıt).
- **Sağlayıcı kilidi yok.** Çıktı, kendi kendine yeten bir player içeren düz bir SCORM 1.2/2004
  zip'idir. MIT lisanslı, kendi sunucunda barındırılabilir ve katkıya açık.

**Yazar = MCP istemcisi · Derleyici = bu sunucu.**

![Yerleşik slayt-sahne oynatıcısında render edilen bir quiz ekranı](docs/assets/screenshot-player.png)

## Hızlı başlangıç

### Seçenek 1 — Barındırılan MCP (kurulum yok)

Herhangi bir MCP istemcisini (Claude masaüstü/web/Code, Antigravity, …) şuraya yönlendir:

```
https://scorm.edumints.com/mcp
```

OAuth ile giriş yap ya da portaldan bir API anahtarı al: **https://mcp.edumints.com**.
Sonra iste: *"X konusunda 6 dakikalık, quizli ve özetli etkileşimli bir kurs oluştur."* — geriye
indirilebilir bir SCORM zip alırsın.

> **Authoring skill** ile birlikte en iyi sonucu verir (bir yapay zekâ istemcisine bu sunucuyla
> kaliteli kurs üretmeyi öğreten bir Claude Agent Skill):
> https://github.com/kemalyy/edumints-scorm-skill

### Seçenek 2 — Docker (kendi sunucunda)

```bash
docker run -p 8000:8000 -v "$PWD/data:/data" ghcr.io/kemalyy/edumints-scorm-mcp:latest
# MCP ucu: http://localhost:8000/mcp   ·   sağlık: http://localhost:8000/health
```

Image, opsiyonel özelliklerin hepsini içerir (ffmpeg, video için Node + HyperFrames, Piper TTS).

> **Apple Silicon + Docker Desktop:** container `Illegal instruction` (SIGILL) ile çöküyorsa, bu
> `cryptography` paketinin Rust binding'lerindeki üst-akış native-ARM64 sorunu
> ([pyca/cryptography#14733](https://github.com/pyca/cryptography/issues/14733)) — bu repo'nun
> hatası değil. Çözüm: `--platform linux/amd64` ile çalıştır (emülasyonlu).

### Seçenek 3 — Yerel (Python)

```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[tts]"          # ".[tts]" çevrimdışı Türkçe TTS'i (Piper) ekler; istemezsen çıkar
python server.py              # MCP'yi HTTP üzerinden sunar
```

Video üretimi için ayrıca Node 22+ ve HyperFrames (`npm i -g hyperframes`) + ffmpeg kur.
Yapılandırma: `.env.example`'ı kopyalayıp uyarla (veri dizini, kotalar, base URL, TTL'ler).
Yerel çalıştırmak için **hiçbir secret gerekmez**.

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
build_package(project_id) → indirilebilir SCORM zip
                              ├─ imsmanifest.xml
                              ├─ index.html          (kendi kendine yeten player + runtime)
                              └─ assets/
```

Tam çalışan spec'ler [`examples/`](examples/) altında (oyunlar, dallanma, temalı ve çok dilli kurslar).

## Özellikler

- **43 MCP aracı** — `build_from_spec` (tek çağrılık yol), granüler düzenleme
  (`create_project` / `add_screen` / `update_screen` / …), `set_theme` / `set_tracking`,
  `add_asset` (SSRF-korumalı içe aktarım), `synthesize_speech` (çevrimdışı Piper TTS), video
  araçları (ffmpeg / HyperFrames motion-graphics), `preview` / `validate_package` / `build_package`,
  `lint_course` (kalite kapısı), `export_qti` (QTI 2.1).
- **31 ekran tipi** — başlık, içerik, çoktan seçmeli, doğru/yanlış, boşluk doldurma, sürükle-bırak,
  hotspot, dallanan senaryo, video, akordeon, sekme, bilgi kartı, eşleştirme, sıralama, zaman
  çizelgesi, lottie, rehberli yazılım simülasyonu, karar senaryosu, terim yarışı, kaçış odası,
  etiketli diyagram, veri grafiği, görsel karşılaştırma, sonuç dökümü, anket/yansıma, özet,
  **kompozisyonel oyun**, **adaptif pratik**, çözümlü örnek, keşif, **gömülü HTML**
  (artifact→SCORM). Tam referans: [docs/SCREEN_TYPES.md](docs/SCREEN_TYPES.md).
- **Kompozisyonel oyun motoru** — `game` ekranı mekanik primitifleri (skor/can/süre/ipucu) +
  bildirimsel `when olay if koşul then aksiyon` kurallarını + dallanan düğümleri besteler;
  `adaptive_practice` yeterliliği (**Elo veya Bayesian Knowledge Tracing**) tahmin edip zorluğu
  öğrenciye kalibre eder. Bkz. [docs/GAME-PATTERNS.md](docs/GAME-PATTERNS.md).
- **Slayt-sahne oynatıcı** — her ekrana ölçeklenen sabit 16:9 sahne, player bar
  (oynat/seekbar/altyazı/menü/replay), seslendirmeyle senkron zamanlanmış timeline akışı,
  bölümlere göre gruplu menü, tam responsive, inline SVG ikonlar.
  **i18n kabuğu (tr/en) ve RTL desteği.**
- **Gerçek SCORM izleme** — `cmi.interactions` (soru düzeyinde raporlama), `cmi.objectives`,
  `adlcp:masteryscore` (1.2) / `completionThreshold` (2004), LOM metadata ve devam durumu için
  **kompakt suspend-data v2 kodlaması**.
- **Tema** — stil preset'leri (`style-minimal` / `style-playful` / `style-premium` ve dahası) marka
  token'larıyla katmanlanır: tek stil, çok marka. Açık/nötr/yüksek-kontrast preset'leri,
  WCAG-bilinçli, `prefers-reduced-motion` desteği.
- **Kalite kapıları** — bloklayan hata katmanı olan anti-slop lint ve oyun erişilebilirlik denetimleri.
- **Medya** — çapraz-MCP asset içe aktarımı (`add_asset`, data-URI veya https), ffmpeg işleme,
  programatik motion-graphic/veri-viz video (HyperFrames), dahili çevrimdışı Türkçe TTS (Piper).
- **Telemetri** — oynatıcıdan opsiyonel **xAPI** ifadeleri; **cmi5 kısmî** (yalnız launch algılama —
  henüz `cmi5.xml` paketlemesi yok). Bkz. [docs/GAME-XAPI.md](docs/GAME-XAPI.md).
- **QTI 2.1 dışa aktarımı** — quiz ekranları, ölçme platformlarıyla birlikte çalışabilirlik için QTI
  `assessmentItem` olarak dışa aktarılır. Bkz. [docs/QTI.md](docs/QTI.md).
- **SCORM 1.2 & 2004**, deterministik paketleme, maliyet guardrail'leri, opt-in/lazy ağır özellikler.

## Standartlar & kanıt

İddia ucuzdur; bu repo kanıt zincirini CI'da yayınlar:

1. **XSD uyumu** — üretilen `imsmanifest.xml` dosyaları hem SCORM 1.2 hem 2004 için **resmî ADL/IMS
   şemalarına** karşı doğrulanır (`tests/test_conformance.py` içinde otomatik).
2. **Gerçek SCORM Cloud gidiş-dönüşü** — CI, build edilen paketleri REST API üzerinden gerçek
   [SCORM Cloud](https://cloud.scorm.com)'a içe aktarır: **4/4 kombinasyon** (small/rich × 1.2/2004)
   **0 parser uyarısıyla** içe aktarılmalı ve başlatılabilir bir kayıt üretmelidir. Bu bir
   **bloklayan kapıdır**, tavsiye niteliğinde bir kontrol değil.
3. **Davranışsal probe** — `scorm-probe`, build edilen kursları **sahte bir LMS'e karşı gerçek
   Chromium'da** başlatır ve çalışma-zamanı davranışını doğrular (init, gezinme, skorlama,
   tamamlanma). CI'da o da bloklayıcıdır; sessiz atlama build'i düşürür.

Ayrıntılar, prosedürler ve dürüst sınırlar: **[docs/CONFORMANCE.md](docs/CONFORMANCE.md)**.
Erişilebilirlik: açıkça belgelenmiş kısıtlarıyla **WCAG 2.2 AA uygunluk beyanı** —
**[docs/ACCESSIBILITY-CONFORMANCE.md](docs/ACCESSIBILITY-CONFORMANCE.md)**.

## Resmî kaynaklar

Bu projenin **tek** resmî dağıtım kanalları şunlardır:

| Kanal | URL |
|---|---|
| Kaynak deposu | https://github.com/kemalyy/edumints-scorm-mcp |
| Authoring skill | https://github.com/kemalyy/edumints-scorm-skill |
| Container image | `ghcr.io/kemalyy/edumints-scorm-mcp` |
| Barındırılan MCP ucu | https://scorm.edumints.com/mcp |
| Hesap portalı | https://mcp.edumints.com |

Bunların dışındaki her şey — ayna repo'lar, yeniden yüklenmiş zip'ler, PyPI/npm paketleri, başka
kayıt defterleri veya alan adları — **resmî değildir ve doğrulanmamıştır**. Bugün itibarıyla **hiçbir**
PyPI veya npm paketi yayınlamıyoruz. Benzerini görürsen lütfen [SECURITY.md](SECURITY.md) üzerinden bildir.

## Dokümantasyon

| Doküman | İçerik |
|---|---|
| [docs/SCREEN_TYPES.md](docs/SCREEN_TYPES.md) | 31 ekran tipinin tamamı, alanları ve örnekleriyle |
| [docs/CONFORMANCE.md](docs/CONFORMANCE.md) | SCORM uyum kanıtları & prosedürleri |
| [docs/ACCESSIBILITY-CONFORMANCE.md](docs/ACCESSIBILITY-CONFORMANCE.md) | WCAG 2.2 AA beyanı |
| [docs/LMS-INTEGRATION.md](docs/LMS-INTEGRATION.md) | LMS'e özel entegrasyon notları |
| [docs/QTI.md](docs/QTI.md) | QTI 2.1 dışa aktarımı |
| [docs/GAME-PATTERNS.md](docs/GAME-PATTERNS.md) | Oyun motoru desenleri |
| [docs/GAME-ADAPTIVE.md](docs/GAME-ADAPTIVE.md) | Adaptif pratik (Elo/BKT) |
| [docs/GAME-ANTISLOP.md](docs/GAME-ANTISLOP.md) | Anti-slop kalite kapısı |
| [docs/GAME-XAPI.md](docs/GAME-XAPI.md) | xAPI/cmi5 telemetrisi |
| [docs/GAME-A11Y.md](docs/GAME-A11Y.md) | Oyun erişilebilirliği |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Sistem mimarisi |

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

Issue ve PR'lar memnuniyetle. Kod tabanı küçük/odaklı modülleri, additive değişiklikleri ve
geriye-uyumu tercih eder. [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın. Testler: `pytest`.

## Lisans

- Bu proje: **MIT** — [LICENSE](LICENSE).
- Gömülü 3. taraf bileşenler (scorm-again, lottie-web): [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**[edumints.com](https://edumints.com)** tarafından geliştirildi. SCORM, ADL'nin ticari markasıdır;
anılan diğer ürün adları ilgili sahiplerinin ticari markalarıdır (yalnız tanımlayıcı/nominative kullanım).

<!-- synced: 2a51e01 -->
