# Adaptif Katman (W4): Yeterlilik Tahmini + Akış/ZPD Zorluk Kalibrasyonu

`components/engine/adaptive.js` (saf-mantık, DOM'suz, vitest, bundle-inline) — öğrencinin gizli yeterliliğini
deterministik tahmin edip bir sonraki öğenin zorluğunu **arzu edilen zorluk** (Bjork) bandında tutar.
**Sunucuda LLM YOK** — zekâ spec'te + bu deterministik tahmincilerde. Durum **küçük** (SCORM 1.2 4096B bütçesi).

## İki tahminci — ortak arayüz arkasında (spec seçer)

Arayüz: `observe(...)` → durumu güncelle · `pCorrect(difficulty?)` → tahmini P(doğru) · `state()` → serileştirilebilir · `reset()`.

### Elo-lite (`createElo`, `strategy:"elo"`) — varsayılan
Rasch-benzeri 1-parametre lojistik. **Durum: tek float `ability`** (logit ölçeği).
`observe(difficulty, correct)` → `ability += k·(gerçek − beklenen)`. `pCorrect(d) = σ(ability − d)`.
- **Güçlü yön:** en küçük durum; zorluk eşleştirmeye doğal yatkın (akış); beceri-bağımsız öğeler için ideal.
- **Zayıf yön:** tek skaler yetenek — beceri-başına ustalık raporlamaz; slip/guess'i ayrı modellemez.
- **Ne zaman:** karışık-konu pratiği, hızlı kalibrasyon, raporlamadan çok akış hedefleniyorsa.

### BKT-lite (`createBkt`, `strategy:"bkt"`) — beceri-başına ustalık
Bayesian Knowledge Tracing. **Durum: tek float `mastery` = P(L)** + slip/guess/transit parametreleri.
`observe(correct)` → Bayes posterior P(L|gözlem) + öğrenme geçişi. `pCorrect = P(L)·(1−slip) + (1−P(L))·guess`.
- **Güçlü yön:** ECD **yeterlilik modeline doğrudan** eşlenir (P(ustalık) okunaklı, stealth assessment raporlanır);
  slip (bilip yanlış) / guess (bilmeden doğru) ayrımı.
- **Zayıf yön:** beceri-başına bir örnek (çok-becerili kurs → çok örnek → daha çok durum); parametre kalibrasyonu gerektirir.
- **Ne zaman:** belirli becerilerde ustalık takibi, ustalık-tabanlı ilerleme/kapı, ayrıntılı raporlama.

> **Seçim özeti:** akış + minimum durum → **Elo**; beceri-başına ustalık + raporlama → **BKT**. İkisi de
> deterministik ve 4096B-uyumlu; `createEstimator(spec)` `strategy` ile yönlendirir (bilinmeyen → Elo).

## Akış/ZPD seçici (`pickByTargetSuccess`)
`pickByTargetSuccess(predict, candidates, {target=0.7}, rng)` — `predict(aday)` tahmini P(doğru); hedef başarı
olasılığına **EN YAKIN** adayı seçer (ne çok kolay ne çok zor — Vygotsky ZPD / Bjork "desirable difficulty").
Eşitlikte **seed'li RNG** ile üretilebilir tie-break (aynı seed → aynı seçim; oynanış tekrarlanabilir).

## Şema (`core/game_primitives.py`)
`EloSpec{ability,k}` · `BktSpec{p_init,p_transit,p_slip,p_guess}` · `AdaptiveSpec = Union` (`strategy` ayrımlı) ·
`ADAPTIVE_STRATEGIES=("elo","bkt")`. Olasılık alanları [0,1], `k>0` validator'da zorlanır.

## ECD'ye bağlanış
Tahminci = **yeterlilik modeli değişkeni** (gizli ustalık). `observe` = **kanıt kuralı** (gözlem → yeterlilik
güncellemesi). Seçici = **görev modeli** seçimi (yeterliliğe uygun bir sonraki görev). Bkz. `docs/GAME-ECD.md`.

## Durum & sıradaki

**W4a (done):** tahminci çekirdeği + seçici + spec + vitest(14) + Python şema/bundle testi.
Bundle'a `adaptive.js` inline; `window.SCORMGame`'de `createElo`/`createBkt`/`createEstimator`/`pickByTargetSuccess`.

**W4b (done):** runtime'a bağlandı — **`adaptive_practice` ekran tipi** (`core/project.py`: AdaptivePracticeScreen +
AdaptiveItem; QUIZ_TYPES, skorlanır). `components/renderer.py` `_r_adaptive_practice` (öğeler statik HTML, gizli) +
`_adaptive_cfg` (tahminci spec + öğe-başına doğru cevap/zorluk/skill). `components/templates.py` **`bindAdaptive`**:
engine bundle'dan tahminciyi kurar; her cevap → `observe` → sıradaki öğe — **Elo: ZPD/akış** (`pickByTargetSuccess`,
hedef başarıya en yakın zorluk), **BKT: ustalık** (kolaydan-zora + `mastery_stop` erken-bitir). HUD: ilerleme +
canlı seviye/ustalık. `core/validator.py`: her öğe ≥1 doğru seçenek + `max_items` sınırı. Örnek:
`examples/games/adaptive-statistics.tr.json`. Bundle yalnız game/adaptive_practice ekranı varsa inline
(`_uses_engine_bundle`). **155 Python + 83 vitest + ruff temiz; Node'da adaptif döngü doğrulandı** (novice→kolay
öğe, doğru sonrası ability↑→sonraki zorlaşır).

**Sıradaki (W5):** xAPI/cmi5 — her `observe` bir statement'a çevrilir; adaptif kararlar + oyun olayları telemetriye
akar. Resume: tahminci durumu küçük (1 float) → suspend_data'ya eklenebilir (şu an ekran-içi tek oturum).
