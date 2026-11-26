# Known Limitations — Bilinen Kısıtlar

> **İlke:** Bu doküman **kapatılmamış kısıtları** dürüstçe listeler. "Yapılıyor",
> "planlandı", "bilinçli erteleme" — her durum açıkça etiketlenir. Satın alma
> öncesi burayı okuyun.

**Son güncelleme:** 2026-10-13 (Moodle 5.x SCORM upload sınırı bugün keşfedildi, §11).

---

## 1. Erişilebilirlik (WCAG 2.2 AA) — Açık Kısıtlar

Detay: [docs/ACCESSIBILITY-CONFORMANCE.md §3](ACCESSIBILITY-CONFORMANCE.md#3-known-limitations).

| # | Kısıt | Durum | Issue | Plan |
|---|---|---|---|---|
| **MA-1** | WebVTT altyazı hattı | ✅ **Kapandı** (#145) | [kemalyy/edumints-scorm-mcp#145](https://github.com/kemalyy/edumints-scorm-mcp/issues/145) | Yayınlandı |
| **MA-2** | drag_drop klavye alternatifi | 🟡 Açık (QW) | [#146](https://github.com/kemalyy/edumints-scorm-mcp/issues/146) | K1-K6 sonrası, 2 gün |
| **MA-3** | Ayarlanabilir sayaçlar | 🟡 Açık | [#147](https://github.com/kemalyy/edumints-scorm-mcp/issues/147) | K1-K6 sonrası, 1-2 gün |
| **MA-4** | Lottie reduced-motion + duraklat | 🟡 Açık | [#148](https://github.com/kemalyy/edumints-scorm-mcp/issues/148) | K1-K6 sonrası, 1 gün |
| **MA-5** | data_chart programatik ad (strict) | 🟡 Açık | [#149](https://github.com/kemalyy/edumints-scorm-mcp/issues/149) | K1-K6 sonrası, 1 gün |
| **MA-6** | axe denetimi 31 ekran tipine yay | 🟡 Kapsam açık | — | FAZ 2 (JS test harness) ile birlikte |
| — | `aria-label` strict'e alınması (data_chart) | 🟡 Açık | — | MA-5 ile birlikte |

**Etki:** Kamu ihalesi "WCAG 2.2 AA zorunlu" şartı olan kurumlar için **MA-2/3/4/5 kapanana
kadar** resmi alım uygun değildir. Bunu planlama takvimine dahil edin.

---

## 2. Ölçme & Değerlendirme — Açık (Kurumsal İtiraz #1)

| # | Kısıt | Durum | Issue | Plan |
|---|---|---|---|---|
| **AS-1** | Soru havuzu + tohumlu rastgeleleştirme | 🟡 Açık | [#142](https://github.com/kemalyy/edumints-scorm-mcp/issues/142) | K3 merge sonrası pencere, 3-4 gün. Altyapı (`itembank.js`, `rng.js`) hazır. |
| **AS-2** | Deneme politikası (limit/retry/lock) | 🟡 Açık | [#143](https://github.com/kemalyy/edumints-scorm-mcp/issues/143) | AS-1 sonrası, 2-3 gün |
| **AS-3** | Gözden geçirme kipi (review) | 🟡 Açık | [#144](https://github.com/kemalyy/edumints-scorm-mcp/issues/144) | AS-1 ile birlikte, 2 gün |
| **AS-4** | Kısmî kredi | 🟡 Açık | — | AS-1 sonrası, 1-2 gün. `partial_credit: bool=False` default kapalı. |

**Etki:** "Her öğrenci aynı sınavı görüyor" — kurumsal alıcının fiilen ilk itirazı. AS-1
+ AS-2 olmadan **çok sayıda öğrenci olan** sınav senaryoları uygun değil. Pilot aşaması
veya küçük çaplı eğitimler için yeterli.

---

## 3. Etkileşim Derinliği — Açık

| # | Kısıt | Durum | Issue | Plan |
|---|---|---|---|---|
| **IX-1** | Exploration slider | ✅ **Kapandı** (#141) | [#141](https://github.com/kemalyy/edumints-scorm-mcp/issues/141) | Yayınlandı |
| **IX-2** | Etkileşimli video (zaman damgası + soru + dallanma) | 🟡 Açık | [#139](https://github.com/kemalyy/edumints-scorm-mcp/issues/139) | Pazar analizinin en yüksek değerli tek kapanmamış maddesi, 4-6 gün |
| **IX-3** | Metin-içi etkileşimler (mark/drag the words) | 🟡 Açık | — | 3-4 gün |
| **IX-4** | Görsel soru aileleri (MatchPair/SortItem image_asset_id) | 🟡 Açık | [#140](https://github.com/kemalyy/edumints-scorm-mcp/issues/140) | 1-2 gün |
| **IX-5** | Slider | ✅ **Kapandı** | — | Yayınlandı |

---

## 4. Paketleme / SCORM — Açık / Bilinçli Erteleme

| # | Kısıt | Durum | Not |
|---|---|---|---|
| **PK-1** | cmi5 / xAPI uçtan uca | 🟡 **Gating kararı açık** (SP-7) | A1 başlangıcı 3-5 gün; karar verilmedi. SCORM Cloud cmi5 kurs limiti / ADL CATAPULT / kendi LRS — hangisi? |
| **PK-3** | Çoklu-SCO + imsss sequencing | 🔵 **Bilinçli erteleme** (talebe bağlı) | Çoklu-SCO + `imsss` namespace. Kurumsal talep gelince açılır; mevcut tek-SCO çoğu kullanıcı için yeterli. |
| — | `suspend_data` heuristik şema | 🟡 Açık (FAZ 4) | 1.2: 4096-char, 2004: 64000-char. Gerçek şema + kompakt kodlama + sürüm-toleranslı geri okuma, 3-4 gün |

---

## 5. Tema / Kompozisyon

| # | Kısıt | Durum | Not |
|---|---|---|---|
| **K1** | Kompozisyon sistemi (odak, vurgu, desenler, 3 yeni palet, font gömülü) | ✅ **Kapandı** (#39) | master'da |
| **K2** | Görsel etkileşimli 7 tip için yuvalar + `visual-stack` deseni | ✅ **Kapandı** (#40) | master'da, 45→46 araç |
| **K3** | Soru ailesine kompozisyon yayılımı + `stimulus` + `question-column` | 🟡 **PR #41 (draft)**, 11 commit master önünde | `feat/composition-k3` dalında. Sırada: K4 → K5 → K6 → release (yol B: K3–K6 bitince tek seferde). |
| **K4-K6** | Yeni etkileşimler, görsel sistem, doküman + demo | 🔵 Planlandı | release bloğunda |

| # | Kısıt | Durum | Not |
|---|---|---|---|
| **Tema audience override** | Mekanizma hazır, içerik boş | 🟡 Açık | `themes/audience/_README.md` 6 paket sözleşmesi; K6 release'inde 2 pilot (K12 + kurumsal), gerisi talebe bağlı |
| **Tema CSS üretimi sırasında görsel baseline drift** | CI'da BLOKLAYICI (`ci.yml`) | ✅ | Yeni baseline'lar CI'dan alınır (lokal baseline üretimi ertelendi) |

---

## 6. LMS Entegrasyonu — Açık

| # | Kısıt | Durum | Issue / Plan |
|---|---|---|---|
| **Moodle 4.x** | ✅ **2/2 OK** (lokal + CI) | Otomatik gate | LMS smoke aracı (CI gate) |
| **Moodle 5.x SCORM upload** | 🟡 **Bilinçli skip** (2026-10-13 keşfi) | Detay: §11 | 5.x'te `core_course_add_module` kaldırıldı; `core_courseformat_new_module` "scorm does not support quick creation" hatası veriyor. **Moodle 4.x (moodlecloud.com vb.) veya direct DB insert** ile ekleme gerekir. |
| **TalentLMS** | 🟡 Açık | B2 (QW) | `.github/workflows/lms-conformance.yml`'e 2. job ekleniyor; 1-2 gün |
| **Canvas** | 🟡 Manuel checklist | — | Sandbox hesabı kurulumu + manuel doğrulama |
| **Blackboard** | 🟡 Manuel checklist | — | Aynı |
| **Docebo** | 🟡 Manuel checklist | — | Aynı |
| **5-LMS conformance gate** | 🟡 1/5 otomatik (Moodle) | — | Sırada: TalentLMS, sonra pilotlarla Canvas/Blackboard |

**Moodle 5.x SCORM upload sınırı detayı (§11):** Moodle 5.x'te web service API
`core_course_add_module` kaldırıldı; yeni `core_courseformat_new_module` API'si
sadece (courseid, modname, targetsectionid) alıyor, instance parametrelerini (özellikle
SCORM packagefile) kabul etmiyor. UI üzerinden ekleme hâlâ çalışır, ancak **web service
ile programatik SCORM ekleme artık mümkün değil**. Bu durum LMS smoke aracında
**dürüstçe skip + log** edilir. Çözüm yolları:
- (a) Moodle 4.x (moodlecloud.com) kullanmak — tam akış çalışır
- (b) `mod_scorm` için özel bir eklenti (kapsam dışı)
- (c) Direct DB insert ile scorm modülü oluşturmak (production'da önerilmez)

---

## 7. Dağıtım / Operasyon

| # | Kısıt | Durum | Not |
|---|---|---|---|
| **PyPI/npm reservation** | 🟡 Kullanıcı hesaplarında bekliyor | — | SP-9 (d). Kullanıcı tarafı 30 dk; alıcının "resmi paket" sorusuna cevap. |
| **Tek-node varsayımı (v1.9.1)** | 🟡 Bilinçli | — | Rate limit, kota rezervasyonu ve build kuyruğu süreç içinde tutulur: tek süreç/tek replica için doğrudur. Çoklu replica'ya geçişte (1) rate limit + kota rezervasyonu ortak depoya (Redis/DB transaction), (2) build kuyruğu dağıtık kuyruğa taşınmalı; açılıştaki yarım-iş kurtarması da replica'lar arası koordinasyon ister. |
| **MCP-2026-07-28 spec uyum migrasyonu** | 🟡 9 issue açık (#93-#101) | — | FastMCP 4, MCP Apps (ui://), CIMD, MRTR, tasks extension. **MCP Apps** kurumsal alıcının "Claude içi önizleme" beklentisini karşılar. |

---

## 8. Bilinçli Kapsam Dışı (Out of Scope)

| Kapsam | Karar | Neden |
|---|---|---|
| **LTI 1.3** | ❌ Bilinçli kapsam dışı | SCORM/Cmi5 ile örtüşüyor; kurumsal talep olursa ayrı bir "LTI adaptörü" olarak düşünülebilir. |
| **Çoklu-SCO + imsss sequencing** | ❌ Bilinçli erteleme (PK-3) | Çoğu kurumsal kullanım senaryosu tek-SCO ile çözülüyor; talep gelince açılır. |
| **Ders dışı formlar (harici anket)** | ❌ Bilinçli kapsam dışı | SCORM paketi içinde kalmalı; harici formlar ayrı bir araçla (Typeform, MS Forms). |
| **Video transkripsiyon / altyazı üretimi** | ❌ Kapsam dışı | Yazar tarafında (Whisper vb.) yapılır, scorm-mcp yalnız WebVTT dosyasını paketler. |
| **Çoklu dil içerik üretimi (AI çeviri)** | ❌ Kapsam dışı | Mevcut çeviri var; AI çeviri Claude tarafında. scorm-mcp i18n'i yönetir. |
| **Quiz soru bankası (öğrenci ilerlemesi)** | ❌ Kapsam dışı (AS-1 ile kısmen) | Soru havuzu (rastgele seçim) var; öğrenci-il bazlı ilerleme LRS tarafı (cmi5 sonrası). |
| **Ders yazarı çok-kullanıcılı (collaboration)** | ❌ Kapsam dışı | scorm-mcp "yazar" Claude'dur; collaboration Git tarafında. |
| **Eski SCORM 1.1 / 1.0 desteği** | ❌ Kapsam dışı | Çok eski, pazar talebi yok. SCORM 1.2 + 2004 4th Ed yeterli. |

---

## 9. Ölçülebilir "Bu Hazır" Listesi

Bir alıcının "scorm-mcp benim için hazır" diyebilmesi için minimum koşullar:

- [x] SCORM 1.2 + 2004 üretebiliyor
- [x] LMS'te import + launch + track doğrulanmış
- [x] 5+ farklı ekran tipi ile anlamlı kurs üretilebiliyor
- [x] Erişilebilirlik kısıtları **yazılı** (kapatılmadıysa yazıyor)
- [ ] **Soru havuzu + deneme** (AS-1 + AS-2) — kurumsal için zorunlu
- [ ] **MA-2 + MA-3 + MA-4 + MA-5** (klavye, sayaç, reduced-motion, data_chart ad)
- [ ] **Etkileşimli video** (IX-2) — yüksek değer
- [ ] **Fiyatlandırma kararı** (self-hosted / managed / hibrit)
- [ ] **5-LMS conformance otomasyonu** (en az 3/5: SCORM Cloud + Moodle + TalentLMS)
- [ ] **PyPI/npm reservation** (SP-9 (d))

Bu 10 maddeden 6'sı ✅, 4'ü 🔴. **Eğitim segmenti** (küçük ölçek, kısa kurslar) için
bugün hazır. **Kurumsal segment** (çok öğrenci, sınavlar, raporlama) için 4 madde daha
kapanmalı.

---

## 10. Bu dokümanı nasıl kullanmalı

- **Alıcı tarafı:** "Şu özellik açık" diye listeye bakın, gerçek teslimatta bunları talep edin.
- **Ekip tarafı:** Bir kısıt kapatıldığında burayı güncelleyin (PR checklist).
- **Issue tracker:** Her kısıt bir issue ile eşleşir; kapatılınca hem issue kapatılır hem burası güncellenir.

**PR checklist:** Her PR'da "bilinen bir kısıt kapatılıyorsa bu dokümana da yansıtılıyor mu?" kontrol edilir.
