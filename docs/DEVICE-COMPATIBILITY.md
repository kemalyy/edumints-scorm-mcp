# Cihaz Uyumluluğu (Device Compatibility)

`edumints-scorm-mcp` tarafından üretilen eğitim içerikleri, modern web standartlarına uygun olarak tasarlanmış olup geniş bir cihaz ve ekran yelpazesinde sorunsuz çalışacak şekilde optimize edilmiştir.

## 1. Desteklenen Görünüm Alanları (Viewports)

Sistem, iki temel görüntüleme modu arasında otomatik geçiş yapar:

### Masaüstü ve Tablet (Sahne Modu)
*   **Sabit 16:9 Tuval:** Varsayılan olarak 960×540 piksel boyutlarında sabit bir "sahne" (stage) kullanılır.
*   **Ölçekleme:** İçerik, kullanılabilir ekran alanına göre en-boy oranını koruyarak merkezde ölçeklenir.
*   **Ayarlanabilirlik:** Proje bazlı `stage_width` ve `stage_height` değerleri değiştirilebilir.

### Mobil ve Dar Ekranlar (Reflow Modu)
*   **Duyarlı Geçiş:** Ekran genişliği **640px veya daha az** olduğunda, sabit tuval ölçeklemesi devre dışı bırakılır.
*   **Doğal Akış (Reflow):** İçerik, mobil cihazın genişliğine tam oturacak şekilde doğal bir akışla yerleşir.
*   **Dikey Kaydırma:** Metin okunabilirliğini korumak için içerik dikey olarak kaydırılabilir hale gelir.

## 2. İçerik Taşması (Content Overflow)

Tasarım aşamasında belirlenen yükseklik sınırları (varsayılan 540px) aşıldığında içerik güvenliği korunur:
*   **Kırpma Yok:** İçerik hiçbir zaman dışarıda kalarak kaybolmaz.
*   **Dahili Kaydırma:** `.screen-inner` konteyneri `overflow-y: auto` özelliğine sahiptir. Bu sayede uzun metinler veya çok sayıda seçenek içeren sorular ekran içinde kaydırılarak tamamına erişilebilir.

## 3. Dokunmatik Desteği (Touch Support)

Tüm etkileşimli bileşenler dokunmatik ekranlarla uyumludur:

*   **Temel Etkileşimler:** Çoktan seçmeli (mcq), doğru-yanlış (true_false), eşleştirme (select-tabanlı), hotspot ve simülasyon (simulation) ekranları dokunmatik tıklamaları destekler.
*   **Sıralama (Sorting):** Öğeleri sürüklemek yerine mobil dostu yukarı-aşağı butonları ile de etkileşim kurulabilir.
*   **Sürükle ve Bırak (Drag & Drop):** Yerel dokunmatik sürükleme desteği (touchstart, touchmove, touchend) mevcuttur.
*   **Görsel Karşılaştırma (Image Compare):** Karşılaştırma sürgüsü standart bir `range input` olarak uygulanmıştır ve dokunmatik olarak kolayca kaydırılabilir.
*   **Performans:** Butonlarda `touch-action: manipulation` kullanılarak tarayıcıların varsayılan 300ms tıklama gecikmesi (tap delay) engellenmiştir.

## 4. LMS Entegrasyonu ve Iframe Davranışı

SCORM paketleri genellikle Öğrenme Yönetim Sistemleri (LMS) içerisinde bir `iframe` içinde çalıştırılır:
*   **Boyutlandırma:** Paketin boyutu, LMS tarafından sağlanan iframe genişliğine göre dinamik olarak ayarlanır.
*   **Responsive Uyumluluk:** Yukarıda belirtilen mobil geçiş davranışı (640px eşiği), iframe'in o anki genişliğine göre tetiklenir.

## 5. Erişilebilirlik ve Standartlar

*   **WCAG AA:** Varsayılan temalar, renk kontrastı ve metin boyutu açısından WCAG AA standartlarını hedefler.
*   **Klavye Erişilebilirliği:** Tüm butonlar, seçim alanları ve etkileşimli öğeler (örneğin etiketli diyagramlardaki select menüleri) klavye ile kontrol edilebilir.
*   **Hareket Azaltma:** Sistem, işletim sistemi düzeyindeki `prefers-reduced-motion` ayarlarına saygı duyar; animasyonlar bu ayara göre minimize edilir.
*   **Dokunma Hedefleri:** Dokunmatik butonlar ve etkileşim alanları, rahat kullanım için minimum 44x44px hedef boyutuna göre tasarlanmıştır.

Ekran tiplerinin teknik detayları ve veri modelleri için [docs/SCREEN_TYPES.md](SCREEN_TYPES.md) dosyasını inceleyebilirsiniz.

---
*docs-only*
