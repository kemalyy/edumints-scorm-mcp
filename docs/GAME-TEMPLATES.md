# Oyun & Adaptif Şablon Kataloğu (W7)

`examples/games/` altındaki kompozisyonel oyun (`game`) + adaptif pratik (`adaptive_practice`) örnekleri.
Hepsi **W6 anti-slop kapısından temiz geçer** (`lint_course` → 0 error, 0 warn) ve geçerli SCORM paketine
build olur. Yazarlar bunları **mekanik kompozisyon deseni** olarak kullanabilir — kopyalayıp konuyu değiştir.

## game (kompozisyonel oyun)
| dosya | şablon | mekanik kompozisyonu | dil | öne çıkan |
|---|---|---|---|---|
| `clinic-triage-game.tr.json` | case_sim | score + lives + hints | tr | dallanan klinik karar; gerekçeli sonuçlar |
| `escape-cipher-game.tr.json` | escape_room | score + lives + **timer(a11y)** + hints | tr | kilitli oda zinciri; **cmi5 telemetri açık** |
| `lab-safety-game.en.json` | case_sim | score + lives + hints | **en** | **i18n** (İngilizce); laboratuvar güvenliği |

Ortak desen: `nodes` (durum + `choices`), her seçim `on_choose` aksiyonları (`score.correct`/`lives.lose`),
olumsuz sonuçlu seçimlerde `feedback_html` gerekçesi (anti-slop), `rules` ile genel `when olay then aksiyon`.

## adaptive_practice (yeterlilik → ZPD zorluk)
| dosya | strateji | öne çıkan | dil |
|---|---|---|---|
| `adaptive-statistics.tr.json` | **elo** | akış/ZPD: hedef başarıya en yakın zorluk seçimi | tr |
| `adaptive-fractions-bkt.tr.json` | **bkt** | ustalık takibi + `mastery_stop` erken-bitir + kolaydan-zora | tr |

Ortak desen: `items` (MCQ + `difficulty` logit + `explain_html`), `adaptive.strategy` (elo|bkt),
`target_success` (elo akış hedefi) / `mastery_stop` (bkt ustalık eşiği).

## Strateji seçimi (elo vs bkt)
- **elo** — karışık konu, hızlı kalibrasyon, akış hedefi; durum = tek yetenek (bkz. `docs/GAME-ADAPTIVE.md`).
- **bkt** — tek beceride ustalık takibi + ustalık-tabanlı erken-çıkış; ECD yeterlilik modeline doğrudan eşlenir.

## Şablon eklerken (anti-slop checklist)
1. Her oyun düğümü start'tan ulaşılabilir; bir düğümdeki seçimler farklı sonuç versin (sahte seçim yok).
2. Skor/can değişimi gerçek karara bağlı (süs değil); olumsuz sonuçta gerekçe ver.
3. İpuçlarına maliyet ver (bedava ipucu öğrenmeyi baltalar).
4. Adaptif: ≥4 öğe, zorlukları yelpazeye yay (aralık ≥0.5), her öğeye `explain_html`.
5. Yayından önce `lint_course(project_id)` çalıştır → `clean: true` olmalı.

Diğer dok: `docs/GAME-ECD.md` (kanıt-merkezli tasarım), `docs/GAME-A11Y.md` (a11y sözleşmeleri),
`docs/GAME-XAPI.md` (telemetri), `docs/GAME-ANTISLOP.md` (kapı kuralları).
