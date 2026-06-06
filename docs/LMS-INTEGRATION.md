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
