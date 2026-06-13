# Oyun Anti-Slop Kalite Kapısı (W6)

`core/antislop.py` — kompozisyonel oyun (`game`) + adaptif pratik (`adaptive_practice`) spec'lerini
**araştırma-temelli, deterministik** kurallarla denetler. **SUNUCUDA LLM YOK** — heuristikler şeffaf,
test edilir, üretilebilir. Amaç: kalite kapısı W7 (şablon çoğaltma) öncesinde kurulur, çünkü kapı
olmadan şablon çoğaltmak **slop'u ölçeklendirir**.

## İki şiddet
- **ERROR** — yapısal bug. `validate_project`'e bağlanır → **build'i bloklar** (yalnız net bug'lar; mevcut geçerli kurslar bozulmaz).
- **WARN** — pedagojik koku. `lint_course` aracıyla **danışsal** (build'i bloklamaz). Yazar yayından önce temizler.

## Kurallar (her biri bir öğrenme ilkesine dayanır)

### game
| kod | şiddet | ilke | denetim |
|---|---|---|---|
| `unreachable_node` | ERROR | — (ölü içerik) | start'tan `choice.to` ile gezilemeyen düğüm |
| `fake_choice` | ERROR | öz-belirleme (anlamlı seçim) | bir düğümdeki ≥2 seçim **özdeş sonuç** (hedef+etki) → illüzyon |
| `decorative_score` | WARN | içsel-bütünleşme (Habgood) | skor mekaniği var ama hiçbir kural/seçim onu değiştirmiyor (süs) |
| `free_hints` | WARN | scaffolding (Shute) | ipucu+skor var ama **tüm** ipuçları maliyetsiz → bedava ipucu öğrenmeyi baltalar |
| `penalty_without_rationale` | WARN | yapıcı geri bildirim | can/skor kaybettiren seçimde `feedback_html` yok → "neden yanlış" öğretilmiyor |

### adaptive_practice
| kod | şiddet | ilke | denetim |
|---|---|---|---|
| `narrow_difficulty` | WARN | akış/ZPD | öğe zorluk aralığı < 0.5 → adaptiflik anlamsız (hep aynı öğe) |
| `few_items` | WARN | ölçüm güvenilirliği | < 4 öğe → tahminci kalibre olamadan biter |
| `item_without_explanation` | WARN | aktif geri bildirim | öğede `explain_html` yok → pasif doğru/yanlış |

> **İçsel-bütünleşme (anti-slop #1):** mekanik, öğrenme hedefinin izomorfu olmalı. `decorative_score`
> ve `fake_choice` "çikolata kaplı brokoli"yi (mekanik↔hedef ayrışması) deterministik proxy'lerle yakalar.
> Tam izomorfizm otomatik kanıtlanamaz; bu kurallar en yaygın slop kalıplarını eler.

## Kullanım
- **Araç:** `lint_course(project_id)` → `{error_count, warn_count, clean, issues:[{severity,code,message,path}]}`.
  Yazar/filo yayından ÖNCE çalıştırır. (22. MCP aracı.)
- **Build kapısı:** `validate_project` artık `lint_errors`'u (yalnız ERROR) içerir → yapısal bug build'i bloklar.
- **Filo review:** game/adaptive PR'larında `lint_course` çalıştırılıp WARN'lar review yorumuna eklenebilir.

## Durum & sıradaki
**W6 (done):** `core/antislop.py` (lint_course/lint_errors) + validate_project ERROR entegrasyonu +
`lint_course` MCP aracı + vitest yok (saf-Python) + Python testleri (yapısal ERROR + pedagojik WARN +
temiz-oyun) + dok. 3 mevcut örnek (clinic/escape/adaptive) **tertemiz** geçer. Additive.
**Sıradaki W7:** kalan şablonlar + i18n örnek (TAM FİLO paralel) — artık kalite kapısı kurulduğu için
şablon çoğaltma slop ölçeklendirmez. Sonra W8 endüstriyel kapanış (5-LMS matris CI + QTI + WCAG 2.2 oyun denetimi).
