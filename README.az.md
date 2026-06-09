# edumints SCORM MCP

> **İnteraktiv, SCORM-uyğun e-təhsil kursları yığan bir MCP server.**
> Sən (və ya Claude kimi bir süni intellekt müştərisi) **müəllifsən**; bu server isə **yığıcıdır**.
> Kursu strukturlaşdırılmış spesifikasiya kimi təsvir et — server doğrulayır, render edir və istənilən
> LMS-də (Moodle, SCORM Cloud, …) işləyən **müstəqil SCORM zip** kimi paketləyir.

**🌐 Dillər:** [English](README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Azərbaycanca](README.az.md) · [Қазақша](README.kk.md) · [Кыргызча](README.ky.md)

Açıq mənbə, **[edumints.com](https://edumints.com)** platforması tərəfindən hazırlanıb. **Öz
kompüterində və ya öz serverində host etmək** üçün nəzərdə tutulub və **töhfəyə açıqdır**.

---

## İdeya (fərqli bir yanaşma)

E-təhsilin çoxu ağır masaüstü alətlərlə əllə qurulur. Burada **süni intellekt müştərisi kursu təsvir
edir** (məqsədlər, ekranlar, testlər, budaqlanma, media) — [Model Context Protocol](https://modelcontextprotocol.io)
vasitəsilə — server isə çətin hissəni görür: doğrulama, premium tema, əlçatan HTML render, SCORM
runtime körpüsü və paketləmə. Nəticə standartlara uyğun SCORM paketidir — provayder asılılığı yoxdur.

**Müəllif = MCP müştərisi · Yığıcı = bu server.**

## İmkanlar

- **18+ ekran növü** — başlıq, məzmun, çoxseçimli, doğru/yanlış, boşluq doldurma, sürüklə-burax,
  hotspot, budaqlanan ssenari, akkordeon, tablar, kartlar, uyğunlaşdırma, sıralama, zaman xətti,
  lottie, **bələdçili proqram simulyasiyası**, video, xülasə.
- **Slayd-səhnə pleyeri** — istənilən ekrana miqyaslanan sabit 16:9 səhnə, pleyer paneli
  (oynat/axtar/altyazı/menyu/təkrar) və səsləndirmə ilə sinxron **zaman xətti üzrə görünmə**.
  Bölmələrə görə qruplaşdırılmış menyu. Tənzimlənən səhnə ölçüsü; tam responsiv/mobil; daxili SVG
  ikonlar (emoji yoxdur).
- **Məntiq və oyunlaşdırma** — dəyişənlər/vəziyyət, şərti görünmə, budaqlanma, xal və taymer HUD-u.
- **Qiymətləndirmə** — məqsədə uyğun suallar, doğru/yanlış üçün geribildirim, SCORM-a yazılan bal.
- **Media** — MCP-lərarası daxiletmə (audio/şəkil/video öz MCP-lərindən gətir → `add_asset`), ffmpeg
  emalı, **proqramatik motion-graphic/data-vizualizasiya videosu** (HyperFrames) və sürətli
  səsləndirmə üçün daxili **Türk dili TTS** (Piper, oflayn).
- **Tema və əlçatanlıq** — açıq/neytral/yüksək kontrast presetlər, brend tokenləri, WCAG-yönümlü,
  `prefers-reduced-motion` dəstəyi.
- **SCORM 1.2 və 2004**, deterministik paketləmə, xərc məhdudiyyətləri, opt-in/tənbəl ağır funksiyalar
  (kurs istifadə etmirsə yüklənmir).

## Sürətli başlanğıc (öz host-unda)

### Docker (tövsiyə olunur)
```bash
git clone https://github.com/kemalyy/edumints-scorm-mcp.git
cd edumints-scorm-mcp
docker build -t edumints-scorm-mcp .
docker run -p 8000:8000 -v "$PWD/data:/data" edumints-scorm-mcp
# MCP ünvanı: http://localhost:8000/mcp   ·   sağlamlıq: http://localhost:8000/health
```
İmiclər bütün opsional funksiyalar üçün hər şeyi əhatə edir (ffmpeg, video üçün Node + HyperFrames,
TTS üçün Piper + Türk səsi).

### Lokal (Python)
```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[tts]"          # ".[tts]" oflayn Türk TTS-ni (Piper) əlavə edir; lazım deyilsə çıxar
python server.py              # MCP-ni HTTP üzərindən təqdim edir
```
Video yaratmaq üçün həmçinin Node 22+ və HyperFrames (`npm i -g hyperframes`) + ffmpeg quraşdır.

### Konfiqurasiya
`.env.example`-i kopyala və tənzimlə (data qovluğu, kvotalar, baza URL, TTL). Bütün seçimlər fayldadır.
Lokal işə salmaq üçün heç bir məxfi məlumat lazım deyil.

## Süni intellekt müştərisini qoşmaq

İstənilən MCP müştərisini `http://<host>:8000/mcp` ünvanına yönləndir:
- **Claude** (masaüstü/veb/Code) — konnektor / MCP server kimi əlavə et.
- **Antigravity** və digər MCP müştəriləri — eyni ünvan (HTTP/Streamable).

Sonra istə: *“X mövzusunda testli və xülasəli 6 dəqiqəlik interaktiv kurs yarat.”* Müştəri aşağıdakı
alətləri çağırır; sən yüklənə bilən SCORM zip alırsan.

> **Müəlliflik skill-i** ilə birlikdə işləyir (bu serverlə keyfiyyətli kurs yaratmağı süni intellekt
> müştərisinə öyrədən Claude Agent Skill): https://github.com/kemalyy/edumints-scorm-skill

## Əsas alətlər (MCP)

| Alət | Məqsəd |
|---|---|
| `build_from_spec` | Bir JSON spesifikasiya → doğrulanmış layihə + paketlənmiş SCORM zip (əsas yol) |
| `create_project` / `add_screen` / `update_screen` / … | Detallı, addım-addım redaktə |
| `set_theme` / `set_tracking` | Tema + tamamlama/qiymətləndirmə qaydaları |
| `add_asset` | Audio/şəkil/video daxiletmə (data-URI və ya https, SSRF-qorumalı) |
| `synthesize_speech` | Daxili Türk səsləndirməsi (Piper, oflayn) → audio resurs |
| `make_video_from_image_audio` / `render_motion_video` / `render_screen_video` | Video (ffmpeg / HyperFrames) |
| `preview` / `validate_package` / `build_package` | Önizləmə, doğrulama, SCORM zip yüklə |

## Arxitektura

```
MCP müştərisi (müəllif)  ──►  scorm-mcp (yığıcı)
                              ├─ core/        modellər (Pydantic), paketləmə, saxlama
                              ├─ components/  HTML render + runtime mühərriki + video kompilyatoru
                              ├─ auth/        API-açar + OAuth, SSRF qorumaları
                              ├─ themes/      dizayn tokenləri / presetlər
                              ├─ runtime/     daxili SCORM runtime (scorm-again, MIT)
                              └─ server.py    FastMCP alətləri (HTTP)
```
Nəticə: müstəqil `index.html` + `imsmanifest.xml` + resurslar + SCORM runtime, zip-lənmiş.

## Töhfə

Issue və PR-lar xoş qarşılanır. Kod kiçik, fokuslanmış modulları, additiv dəyişiklikləri və geriyə
uyğunluğu üstün tutur. [CONTRIBUTING.md](CONTRIBUTING.md) sənədinə baxın.

## Testlər

Testləri `pytest` ilə işə salın.

## Lisenziyalar

- Bu layihə: **MIT** — bax [LICENSE](LICENSE).
- Daxil edilmiş üçüncü tərəf komponentləri (scorm-again, lottie-web): bax [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**edumints.com** tərəfindən hazırlanıb. SCORM ADL-in ticarət nişanıdır; qeyd olunan digər məhsul adları
müvafiq sahiblərinin ticarət nişanlarıdır (yalnız nominativ istifadə).


<!-- synced: 448f0cb -->
