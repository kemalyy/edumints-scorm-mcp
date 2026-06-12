# Oyun Tasarımı: Kanıt-Merkezli Tasarım (ECD) Üç Modeli

W3b `game` ekran tipi, **Kanıt-Merkezli Tasarım** (Evidence-Centered Design — Mislevy, Steinberg & Almond) çerçevesine
göre belgelenir. ECD, bir değerlendirmeyi üç birbirine bağlı modele ayırır. `game` ekranı bunların üçünü de
**deklaratif spec'te** taşır — sunucuda LLM yok; zekâ spec + deterministik runtime'da (`components/engine/*.js`).

Bu doküman aynı zamanda **stealth assessment** (Shute) ilkesini taşır: öğrenci "sınav" değil, oyun oynar; kanıt
oynanışın içinden, mekaniklerin durumundan (skor/can/ipucu/seçim izi) sürekli toplanır.

---

## 1. Yeterlilik Modeli (Competency / Student Model) — "Neyi ölçüyoruz?"

Öğrencinin hakkında çıkarım yaptığımız **gizli değişkenler** (bilgi/beceri/yatkınlık).

`game` spec'inde nasıl temsil edilir:
- **`mechanics.score`** — birikimli ustalık sinyali. `streak`/`multiplier` ardışık doğru kararları (tutarlı
  yeterlilik) seyrek isabetten ayırır → tek bir şanslı tıklama yüksek skor vermez.
- **`mechanics.lives`** — hata toleransı altındaki karar kalitesi; can = kalibre edilmiş zorluk.
- **`rules` + `vars`** — ara yeterlilik göstergeleri (örn. `vars.adim`, `vars.deneme`) ECD'nin "competency
  model variables"ına karşılık gelir; kilitli seçimler (`choice.condition`) bir yeterliliği gerektiren görevleri açar.

Geçer/kalır kararı: `pass_score` (verilirse skor ≥ eşik), yoksa skor > 0; **can biterse her durumda kalır**
(yeterlilik kanıtlanamadı).

## 2. Kanıt Modeli (Evidence Model) — "Gözlemden çıkarıma nasıl geçeriz?"

İki parça: **gözlemlenebilir değişkenler** (öğrencinin yaptığı) + **kanıt kuralları** (gözlemi yeterlilik
güncellemesine çeviren mantık).

`game` spec'inde:
- **Gözlemlenebilirler:** `choice.taken` olayı (hangi düğümde hangi seçim), ipucu kullanımı (`hint.revealed`,
  maliyetli → yardımsız ustalığı ayırır), süre davranışı (`timer.tick`/`expired`).
- **Kanıt kuralları = `rules` + `choice.on_choose`:** `when <olay> if <koşul> then <aksiyon>`. Her seçim
  yeterliliği **deterministik** olarak günceller (`score.correct` doğru akıl yürütmeyi ödüllendirir;
  `lives.lose` zayıf kanıtı cezalandırır). Eşleşme `components/engine/rules.js`'te (vitest), eval YOK.
- **Puanlama kuralı (scoring):** runtime skor primitifini `pass_score`'a göre değerlendirip SCORM `recordResult`
  ile LMS'e yazar — gözlemden nota giden zincir tamamen izlenebilir.

**Anti-slop / içsel-bütünleşme (Habgood):** kanıt-üreten mekanik, ölçülen hedefin **izomorfu** olmalı.
"EKG iste → skor" yalnızca doğru klinik karar bir mekanik avantaja dönüştüğü için geçerli kanıttır
(skor süs değil). Mekanik ile hedef ayrışırsa ("çikolata kaplı brokoli") kanıt geçersizdir — W6 oyun anti-slop
kapısı bunu denetleyecek.

## 3. Görev Modeli (Task Model) — "Hangi durumlar kanıt üretir?"

Öğrencinin yeterliliği gösterebileceği **görev/durum biçimleri**.

`game` spec'inde:
- **`nodes`** — her düğüm bir görev durumu (vaka anı / kilitli oda). `content_html` durumu kurar, `choices`
  eylem alanını tanımlar.
- **`nodes[].choices[].to`** — dallanan görev akışı: kararlar sonraki durumu belirler (doğrusal değil), böylece
  farklı yeterlilik profilleri farklı kanıt yolları üretir.
- **`template`** — görev ailesi etiketi: `case_sim` (dallanan vaka simülasyonu — tanısal/etik akıl yürütme),
  `escape_room` (kilitli görev zinciri — süre baskısı altında uygulama).
- **Erişilebilirlik bir görev kısıtıdır, kanıtı çarpıtmamalı:** süreli görevlerde `timer.allow_extend` /
  `allow_disable` zorunlu (WCAG 2.2.1) — süre bir öğrenciyi yeterliliğinden bağımsız eleyemez. Validator bunu
  zorlar (`core/validator.py`).

---

## Uçtan uca izlenebilirlik

```
Görev (node) → Gözlemlenebilir (choice.taken/hint/timer) → Kanıt kuralı (rules/on_choose)
   → Yeterlilik güncellemesi (score/lives/vars) → Puanlama (pass_score) → LMS (recordResult → cmi.score)
```

Her ok **deterministik ve spec'te açık** — denetlenebilir, üretilebilir (seed'li RNG), test edilir
(vitest mantık + Python golden). Bu, W5'te xAPI/cmi5 ifadelerinin (her gözlemlenebilir bir statement)
ve W4 adaptif katmanın (yeterlilik tahmini → zorluk kalibrasyonu) üzerine kurulacağı temeldir.

İlgili: `core/game_primitives.py` (spec), `components/engine/` (mantık), `docs/GAME-A11Y.md` (primitif a11y
sözleşmeleri), `examples/games/clinic-triage-game.tr.json` & `escape-cipher-game.tr.json` (şablonlar).
