# LMS Entegrasyonu (LMS Integration)

`edumints-scorm-mcp` tarafından üretilen paketler, standartlara uygun (SCORM 1.2 veya SCORM 2004 4th Edition) ZIP dosyalarıdır ve çoğu modern Öğrenme Yönetim Sistemi (LMS) ile uyumludur.

## Desteklenen Standartlar

*   **SCORM 1.2:** En yaygın desteklenen versiyon. `suspend_data` sınırı 4096 karakterdir.
*   **SCORM 2004 (4th Edition):** Daha gelişmiş izleme ve daha geniş veri sınırları sunar.

## Popüler LMS Platformları

### 1. Moodle
Moodle, SCORM paketlerini yerel olarak destekler.

*   **Yükleme:** "Yeni bir etkinlik veya kaynak ekle" -> "SCORM paketi" seçeneğini kullanın. Üretilen ZIP dosyasını yükleyin.
*   **İzleme:** Moodle, öğrencinin ilerlemesini, puanını ve tamamlanma durumunu otomatik olarak yakalar.
*   **Ayarlar:** "Görünüm" ayarlarında "Yeni pencerede aç" seçeneği, bazı tarayıcı uyumluluk sorunlarını önlemek için önerilir.

#### Kabul senaryosu: devam etme ve puan raporu (SCORM 1.2)

Bu senaryo, kursu öğrencilere açmadan önce iki şeyi kendi Moodle kurulumunuzda
doğrulamanızı sağlar: (a) öğrenci kaldığı yerden devam edebiliyor, (b) puanı
öğretmenin göreceği raporlara doğru düşüyor. Yeni bir test altyapısı gerektirmez;
mevcut bir örnek paket ve Moodle'ın kendi arayüzü yeterlidir.

**A. Paketi üret**

Örnek spec: `examples/small.en.json` — dört ekran (başlık, içerik, 10 puanlık `mcq`,
özet), yani "en az iki ekran + bir puanlanan soru" koşulunu karşılar.

| spec alanı | senaryo değeri | etkisi |
|---|---|---|
| `scorm_version` | `"1.2"` | `imsmanifest.xml` → `schemaversion 1.2`, tek SCO (`adlcp:scormtype="sco"`, `href="index.html"`) |
| `tracking.completion_rule` | `"viewed_all_and_passed"` | tamamlanma = tüm ekranlar gezildi **ve** geçme notu alındı |
| `tracking.passing_score` | `50` | manifest'e `<adlcp:masteryscore>50</adlcp:masteryscore>` basılır |
| `tracking.score_scaling` | `true` (varsayılan) | puan 0–100'e ölçeklenir; `cmi.core.score.min=0`, `cmi.core.score.max=100` |

MCP çağrı sırası: `build_from_spec` (spec) → `build_package` (`project_id`) → ZIP.

Yükleme öncesi ZIP kontrolü: kökte `imsmanifest.xml` var, `masteryscore` beklenen
geçme notuna eşit, kaynak `index.html`'i işaret ediyor.

**B. Moodle etkinlik ayarları**

"Yeni bir etkinlik veya kaynak ekle" → "SCORM paketi" → ZIP'i yükleyin. Senaryonun
beklediği ayarlar:

| Moodle ayarı | senaryo değeri | neden |
|---|---|---|
| Deneme sayısı (*Number of attempts*) | 2 | "aynı denemeye dönüş" ile "yeni deneme" ayrımı raporda görünür olsun |
| Yeni deneme zorla (*Force new attempt*) | Hayır / *No* | tarayıcıyı kapatıp dönen öğrenci **aynı** denemeye girmeli (`cmi.core.entry=resume`) |
| Tamamlanmayı zorla (*Force completed*) | Hayır / *No* | tamamlanma kararını paketin kendi `completion_rule`'u vermeli |
| Not verme yöntemi (*Grading method*) | En yüksek not (*Highest grade*) | SCO puanı doğrudan not defterine düşsün |
| Denemelerin notu (*Attempts grading*) | En yüksek deneme (*Highest attempt*) | iki deneme açıldığında hangisinin sayıldığı belirli olsun |
| Görünüm → Yeni pencerede aç | Evet | iframe kaynaklı API bulma sorunlarını eler |

**C. Öğrenci adımları ve beklenen sonuç**

1. **Ara ekranda çık.** Kursu normal modda açın (`mod/scorm/player.php?...&mode=normal`),
   ikinci ekranda (içerik ekranı) bırakıp pencereyi kapatın.
   Beklenen: `cmi.core.lesson_status=incomplete`, `cmi.core.exit=suspend`,
   `cmi.suspend_data` dolu; Moodle raporunda **deneme 1 / tamamlanmadı**.
2. **Aynı denemeyi yeniden açın** — "yeni deneme başlat" seçeneğini işaretlemeyin.
   Beklenen: `cmi.core.entry=resume`; kurs **bırakılan ekranda** açılır; deneme sayısı
   **1'de kalır**; ekranda ayrıca bir "yeniden başlandı" bildirimi **görünmez**.
   Bildirimin görünme koşulu daha dardır: yalnız paket **yeniden yayımlandıktan** sonra,
   öğrencinin bulunduğu **içerik düğümü** artık pakette yoksa çıkar. Düğüm gittiği hâlde
   ekran yaşıyorsa kurs o ekranda devam eder **ve bildirim görünür**; ekran da gittiyse
   ilk ekrandan açılır ve bildirim görünür. Düğüm yaşadığı sürece devam **sessizdir**.
   (Kaynak: `components/engine/scorm.js` resume merdiveni — `mode=node` → bildirim yok,
   `mode=screen` / `mode=start` → bildirim var. Regresyon: `tests/runtime/scorm-probe.mjs`,
   "Faz 4-ek" blokları.)
   Not: "Yeni deneme zorla = Evet" ya da öğrencinin yeni deneme seçmesi `entry=ab-initio`
   üretir; bu durumda kurs **baştan** açılır ve eski `suspend_data` bilinçli olarak
   geri yüklenmez.
3. **Soruyu doğru yanıtlayıp özet ekranına gidin.**
   Beklenen: `cmi.core.score.raw=100` (`min=0`, `max=100`),
   `cmi.core.lesson_status=passed` (100 ≥ masteryscore 50), `cmi.core.exit=normal`,
   `cmi.core.session_time` yazılır, `cmi.interactions.0.id=q1` ve `result=correct`.
4. **Öğretmen görünümüyle eşleştirin** (Etkinlik → Raporlar → Temel rapor; ayrıca not defteri):

| öğretmenin bakacağı alan | beklenen değer | kaynak CMI alanı |
|---|---|---|
| Rapor → Durum | Geçti (*Passed*) | `cmi.core.lesson_status` |
| Rapor → Puan | 100 | `cmi.core.score.raw` |
| Rapor → Deneme | 1 | yeni deneme açılmadığı için artmaz |
| Rapor → Süre | sıfırdan büyük bir oturum süresi | `cmi.core.session_time` |
| Rapor → Etkileşimler | `q1` → correct | `cmi.interactions.0.*` |
| Not defteri sütunu | 100 | `score.raw` (grademethod = En yüksek not) |

**Yanlış yanıtta beklenen (1.2 sınırı — bilinçli kaydedilmiştir):** `score.raw=0`,
`cmi.interactions.0.result=wrong`, ancak `lesson_status` **`failed` değil `incomplete`**
kalır. `viewed_all_and_passed` ve `passed_quiz` kurallarında tamamlanma geçmeyi
içerdiğinden, **SCO düzeyindeki** tek durum kanalı olan `cmi.core.lesson_status`
"bitirdi ama kaldı" için ayrı bir değer üretmez. Öğretmen raporunda "kaldı" görmeyi
bekliyorsanız bu senaryoda doğru okuma **puan sütunu**dur; SCORM 2004 paketlerinde
`cmi.success_status` ayrı kanal olduğu için `failed` ayrıca yazılır.

> **Hedefli kurslarda istisna.** Kursta hedef (objective) tanımlıysa SCORM 1.2'de ikinci
> bir durum kanalı daha yazılır: hedefin bütün soruları yanıtlanmış ve puanı geçme
> oranının altındaysa `cmi.objectives.n.status` **`failed`** olur
> (`components/engine/scorm.js`, `objectiveElements`). Yukarıdaki örnek kursta hedef
> yoktur, bu yüzden senaryo etkilenmez; hedefli kurslarda ise öğretmen raporunun hedef
> sütunu "kaldı"yı gösterebilir ve yalnız puan sütununa bakmak eksik kalır.

**D. Test kaydı**

Her doğrulama turunu bu tabloya ekleyin; "gözlenen" boş kalan satır doğrulanmış sayılmaz.

| tarih | ortam | paket | adım | beklenen | gözlenen | sonuç |
|---|---|---|---|---|---|---|
| 2026-11-05 | simüle SCORM 1.2 API (Chromium, LMS yok) | `examples/small.en.json`, SCORM 1.2, masteryscore 50 | A — ZIP yapısı | kökte `imsmanifest.xml`, `masteryscore=50`, tek SCO | aynı | geçti |
| 2026-11-05 | simüle SCORM 1.2 API | aynı | C1 — ara ekranda çıkış | `incomplete` + `exit=suspend` + `suspend_data` dolu | aynı (pozisyon = içerik ekranı) | geçti |
| 2026-11-05 | simüle SCORM 1.2 API | aynı | C2 — `entry=resume` | bırakılan ekranda açılır, bildirim yok | aynı | geçti |
| 2026-11-05 | simüle SCORM 1.2 API | aynı | C2 — `entry=ab-initio` | baştan açılır, `suspend_data` geri yüklenmez | aynı | geçti |
| 2026-11-05 | simüle SCORM 1.2 API | aynı | C3 — doğru yanıtla bitirme | `score.raw=100`, `lesson_status=passed`, `exit=normal` | aynı | geçti |
| 2026-11-05 | simüle SCORM 1.2 API | aynı | C3 — yanlış yanıt | `score.raw=0`, `result=wrong`, durum `incomplete` | aynı | geçti |
| 2026-11-06 | simüle SCORM 1.2 API | aynı | C4 — Etkileşimler + Süre satırları | `interactions.0.id=q1`, `result=correct`, `session_time` yazılır | aynı (`0000:00:00.82`) | geçti |
| — | gerçek Moodle 4.x | — | B + C1–C4 | yukarıdaki tablo | **denenmedi** | — |
| — | gerçek Moodle 5.x | — | B + C1–C4 | yukarıdaki tablo | **denenmedi** | — |
| — | herhangi bir Moodle | SCORM 2004 | C3 + `success_status` | `failed` ayrıca yazılır | **denenmedi** | — |

**Henüz denenmeyen kombinasyonlar** (yukarıda açıkça işaretli): gerçek Moodle 4.x ve 5.x
kurulumlarında uçtan uca akış, SCORM 2004 paketiyle aynı senaryo, not defteri sütununun
gözlenmesi, iki öğrencinin aynı etkinliği eşzamanlı alması ve mobil tarayıcı turu.
Simüle API turu paketin LMS'e ne yazdığını doğrular; **Moodle'ın bunları raporunda nasıl
gösterdiğini doğrulamaz** — teslim öncesi kontrol listesi, kendi kurulumunuzda yukarıdaki
tabloyu doldurmakla tamamlanır.

### 2. SCORM Cloud
Paketlerinizi test etmek için endüstri standardı kabul edilen platformdur.

*   **Test:** Üretilen paketi SCORM Cloud'a yükleyerek "Debug Log" üzerinden sunucunun LMS ile nasıl haberleştiğini detaylı olarak görebilirsiniz.
*   **Uyumluluk:** Paketlerimiz SCORM Cloud testlerinden başarıyla geçecek şekilde tasarlanmıştır.

### 3. Genel LMS (Canvas, Blackboard, TalentLMS vb.)
Standart bir SCORM yükleme arayüzü olan her sistemde çalışacaktır.

## İzleme ve Veri (Tracking)

Sunucu tarafından üretilen `index.html`, çalışma zamanında LMS'in sağladığı API'yi arar:

1.  **LMS Bulunursa:** Gerçek zamanlı izleme yapılır. `cmi.core.lesson_status` (1.2) veya `cmi.completion_status` (2004) gibi standart alanlar güncellenir.
2.  **LMS Bulunmazsa:** Paket, dahili bir "fallback" (scorm-again) mekanizması kurar. Bu durumda izleme verileri tarayıcı oturumunda kalır ancak bir sunucuya kaydedilmez (Önizleme modu).

### Önemli Veri Alanları
*   **Score (Puan):** Quiz içeren ekranlardan gelen puanlar `cmi.core.score.raw` (1.2) alanına yazılır.
*   **Completion (Tamamlanma):** `completion_rule` ayarına göre (tüm sayfaları gezme veya quiz geçme) tamamlandı bilgisi gönderilir.
*   **Suspend Data:** Öğrencinin hangi sayfada kaldığı ve quiz cevapları bu alanda JSON olarak saklanır.

## Sorun Giderme (Troubleshooting)

*   **Paket Yüklenemiyor:** ZIP dosyasının bozulmadığından ve içerisinde `imsmanifest.xml` dosyasının kök dizinde olduğundan emin olun.
*   **Puan Kaydedilmiyor:** LMS'in SCORM versiyonu ile paketin versiyonunun (1.2 vs 2004) eşleştiğini kontrol edin.
*   **Cross-Domain Sorunları:** Eğer paket LMS'den farklı bir domain üzerinden sunuluyorsa (LTI vb.), tarayıcı güvenlik politikaları API erişimini engelleyebilir. Paketlerimizin LMS ile aynı domain/subdomain üzerinden servis edilmesi önerilir.
*   **Mobil Uyumluluk:** Paketlerimiz responsive (duyarlı) tasarıma sahiptir, ancak bazı eski LMS mobil uygulamaları iframe içerisinde kaydırma sorunları yaratabilir.

## Teknik Detay
Paket içerisinde yer alan `runtime/scorm-again.min.js` kütüphanesi, LMS ile haberleşmeyi sağlayan köprü görevini görür. Bu dosya üzerinde el ile değişiklik yapılmaması önerilir.
