# Telemetri (W5): xAPI/cmi5 — Motor Olaylarından İfadelere

`components/engine/xapi.js` (saf-mantık, DOM'suz, **AĞSIZ**, vitest, bundle-inline) — motor olaylarını
**xAPI (Experience API / Tin Can)** ifadelerine çevirir. ECD kanıt zincirinin telemetri ucu: her
**gözlemlenebilir** (choice/answer/hint/adaptive observe/finalize) bir statement olur → **stealth assessment**
(Shute) verisi. Bu modül YALNIZ ifade KURAR; iletim (LRS) W5b'de. Varsayılan **kapalı** (mahremiyet + zero-load).

## İfade modeli
xAPI ifadesi: `{ actor, verb, object, result?, context?, timestamp?, id? }`. **actor + timestamp DIŞARIDAN
enjekte** edilir (deterministik — vitest'te sabit; runtime'da launch'tan/now). Standart **ADL fiil IRI'leri**:

| olay | fiil | nesne | sonuç |
|---|---|---|---|
| `choice.taken` | answered | düğüm IRI | response = seçim |
| `answer` | answered | öğe IRI | success + difficulty uzantısı |
| `adaptive.observe` | answered | öğe IRI | success + **ability** ya da **mastery** uzantısı |
| `hint.revealed` | experienced | hint IRI | hint-cost / hint-index uzantısı |
| `lives.depleted` | failed | oyun IRI | completion |
| `finalize` | passed / failed | etkinlik IRI | success + score{raw,max} + completion |
| (bilinmeyen) | experienced | olay-adı IRI | — |

**Uzantı IRI'leri** (`XAPI_EXT`): difficulty / ability / mastery / hint-cost / hint-index — adaptif yeterlilik +
scaffolding sinyalleri. Bunlar W4 tahmincilerini (Elo ability, BKT mastery) telemetriye taşır → **ustalık eğrisi
LRS'te izlenebilir**.

## Yapı taşları (`xapi.js`)
`XAPI_VERBS` (anahtar→IRI) · `XAPI_EXT` (uzantı IRI'leri) · `verb(key)` · `activity(id, {name,type,...})` ·
`result({success,completion,scoreRaw/Min/Max/Scaled,response,durationMs,extensions})` (yalnız verilen alanlar;
ISO8601 duration) · `statement({actor,verb,object,result?,context?,timestamp?,id?})` (boş/undefined düşer) ·
`fromEngineEvent(event, payload, ctx)` (olay→ifade; ctx={actor, activityBase, timestamp?, context?}).

## Yapılandırma (`core/game_primitives.py` — `XapiConfig`)
`enabled` (vars. False) · `mode` (`cmi5` | `explicit`) · `endpoint` (explicit LRS) · `activity_base` (nesne IRI öneki).
- **cmi5:** LMS, AU'yu başlatma parametreleriyle (endpoint/auth/actor/registration) açar; runtime bunları okur — **öz-host LRS gerekmez**.
- **explicit:** endpoint spec'te (öz-host LRS); auth runtime/launch'tan.
- **LRS yoksa:** ifadeler güvenle yutulur (**graceful degrade**) — paket yine de geçerli SCORM; izleme SCORM API'siyle sürer.

## ECD'ye bağlanış
Yeterlilik modeli değişkeni (Elo/BKT) → `adaptive.observe` ifadesinin `ability`/`mastery` uzantısı. Kanıt kuralı
(rules/on_choose) → `answered` ifadesinin `success`. Görev modeli (node/item) → ifadenin `object` IRI'si.
Bkz. `docs/GAME-ECD.md`, `docs/GAME-ADAPTIVE.md`.

## Başlatma & iletim (W5b)
**Saf** (xapi.js, vitest): `parseLaunch(search)` — cmi5/xAPI başlatma sorgusundan endpoint/fetch/auth/
registration/activityId + normalize actor. `normalizeActor(raw)` — cmi5 JSON / isim → geçerli xAPI Agent.
**Runtime** (templates.py `XAPI` forwarder, defansif): config + `parseLaunch(location.search)`'ten LRS'i bulur;
`explicit` mod → spec endpoint, `cmi5` mod → launch endpoint; `fetch` varsa auth-token alır (`Basic`); ifadeleri
`<endpoint>/statements`'a **en-iyi-çaba** POST eder (`X-Experience-API-Version: 1.0.3`). **LRS yoksa hiç ifade
üretmez** (sessiz degrade); ağ hatası `try/catch` ile yutulur → **SCORM izleme ASLA bozulmaz**.
Yayılan olaylar: bindGame → `choice.taken`, `hint.revealed`, `finalize`; bindAdaptive → `adaptive.observe`
(ability/mastery), `finalize`.

## Durum & sıradaki
**W5a (done):** ifade modeli + builder + verb/uzantı sözlüğü + `XapiConfig` + vitest.
**W5b (done):** runtime'a bağlandı — `parseLaunch`/`normalizeActor` (saf, vitest) + kurs-düzeyi `Project.xapi`/
`CourseSpec.xapi` + course config serileştirme (yalnız açıkken) + `XAPI` forwarder (cmi5/explicit LRS, offline
tampon, en-iyi-çaba POST) + bindGame/bindAdaptive emit'leri. Bundle yalnız game/adaptive **veya açık xAPI** varsa
inline (`_uses_engine_bundle`). Örnek: `escape-cipher-game.tr.json` cmi5 açık. **159 Python + 99 vitest + ruff temiz.**
**Sıradaki W6:** oyun anti-slop kapısı (içsel-bütünleşme/mekanik-hedef izomorfizmi + a11y sözleşmesi denetimi).
