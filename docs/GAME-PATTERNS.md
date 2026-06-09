# Oyunlaştırma ve Karar Desenleri (Game Patterns)

`edumints-scorm-mcp`, doğrusal olmayan öğrenme deneyimleri ve ciddi oyun (serious games) kurguları için gelişmiş mekanikler sunar. Bu döküman, hangi mekaniğin ne zaman kullanılacağı ve etkili bir oyun tasarımı için gereken prensipleri kapsar.

## 1. Mekanik Seçimi: Hangi Tip Ne Zaman?

Öğrenme hedefine göre doğru etkileşim tipini seçmek, kullanıcı deneyimini doğrudan etkiler.

| Mekanik | Tür | En İyi Kullanım Alanı | Karakteristik |
| :--- | :--- | :--- | :--- |
| **Decision Scenario** | Anlatı (Narrative) | Davranışsal değişim, etik ikilemler, müşteri ilişkileri. | Tek ekranda çok adımlı, anlık geri bildirimli, puan etkili. |
| **Simulation** | Uygulama (Practical) | Yazılım kullanımı, teknik prosedürler, "nereye tıklanır?" eğitimi. | Ekran görüntüleri üzerinde rehberli adım takibi. |
| **Branching** | Yapısal (Structural) | "Kendi maceranı seç", seviye atlama, kişiselleştirilmiş öğrenme yolları. | Ekranlar arası geçiş, büyük ölçekli akış yönetimi. |
| **Quiz Tipleri** | Bilgi (Knowledge) | Kavram kontrolü, temel hatırlama (MCQ, Drag-Drop, Sorting vb.). | Tekil soru-cevap döngüsü. |

### Karşılaştırma Tablosu

| Özellik | Decision Scenario | Simulation | Branching | Quizzes |
| :--- | :--- | :--- | :--- | :--- |
| **Odak** | Karar & Sonuç | İşlem & Doğruluk | Akış & Yol | Bilgi Geri Çağırma |
| **Puanlama** | `score_delta` (Dinamik) | `points` (Statik) | Yok (Dolaylı) | `points` (Statik) |
| **Dallanma** | Düğüm bazlı (İçsel) | Doğrusal (Adım) | Ekran bazlı | Yok |
| **Geri Bildirim** | Gerekçe odaklı (Neden?) | İpucu odaklı (Nasıl?) | Bağlamsal | Doğru/Yanlış |

## 2. Skorlama Tasarımı

Sistem, hem basit quiz puanlamasını hem de karmaşık değişken tabanlı skorlamayı destekler.

-   **Points:** Ekranın veya senaryonun toplam başarı puanı (Varsayılan 10 veya 20).
-   **Pass Score:** `decision_scenario` içerisinde, senaryonun başarılı sayılması için gereken eşik değer.
-   **Score Delta:** Sadece `decision_scenario` içinde kullanılır; her seçimin toplam skora etkisi (+10, -5 vb.).
-   **Tracking (passing_score):** Kursun genel başarı eşiği (Varsayılan 80).
-   **Points HUD (`points_var`):** Proje ayarlarında bir değişken (örn. `puan`) atanırsa, ekranın üst kısmında canlı puan göstergesi belirir.

## 3. İçsel-Ustalaşma İlkesi (Intrinsic Mastery)

`edumints-scorm-mcp` felsefesi gereği, yüzeysel oyunlaştırma öğelerinden (rozetler, liderlik tabloları, "+10!" patlamaları) kaçınılır. Bunun yerine **Sonuç ve Gerekçe Odaklı** bir yaklaşım benimsenir:

1.  **Dışsal Ödül Yerine İçsel Mantık:** Kullanıcı doğru yaptığı için puan kazanmakla kalmamalı, yaptığı seçimin gerçek dünyadaki etkisini (`feedback_html`) görmelidir.
2.  **Hata Bir Öğrenme Fırsatıdır:** Negatif `score_delta` kullanımı, yanlış kararın maliyetini (zaman kaybı, müşteri memnuniyetsizliği vb.) simüle eder.
3.  **Anti-Slop:** Seçenek geri bildirimleri (`feedback_html`) asla boş bırakılmamalıdır. Kullanıcıya neden hatalı olduğu veya neden bu seçimin daha iyi olduğu pedagojik bir dille açıklanmalıdır.

## 4. Decision Scenario: ÖNCE / SONRA Örneği

Etkili bir senaryo tasarımı, kuru bir "doğru mu?" sorusundan "sonuç ne?" deneyimine dönüşmelidir.

### Zayıf Tasarım (Önce)
> **Soru:** Müşteri kızgınsa ne yaparsınız?
> - A) Özür dilerim. (Doğru)
> - B) Bağırırım. (Yanlış)
> *Geri bildirim: A seçeneği doğrudur.*

### Gerekçeli Senaryo (Sonra)
> **Senaryo Düğümü:** Müşteri siparişi geç kaldığı için sesini yükseltiyor.
>
> **Seçenek 1:** Sakin bir ses tonuyla dinleyip sorunu anladığınızı teyit etmek.
> - **Gerekçe (feedback_html):** Müşteri dinlenildiğini hissettiği için sakinleşti. Sorunu çözmek için size zaman kazandırdı.
> - **Puan Etkisi (score_delta):** +10
> - **Sonraki Adım:** Çözüm Aşaması
>
> **Seçenek 2:** Prosedürleri hatırlatarak gecikmenin sizin suçunuz olmadığını söylemek.
> - **Gerekçe (feedback_html):** Müşteri savunmacı tavrınız karşısında daha da sinirlendi ve yöneticinizi çağırmak istiyor.
> - **Puan Etkisi (score_delta):** -15
> - **Sonraki Adım:** Kriz Yönetimi

## 5. Uygulama Detayları

Senaryo ve etkileşim tiplerinin tam JSON şemaları ve zorunlu alanları için [Ekran Tipleri (SCREEN_TYPES.md) §19](./SCREEN_TYPES.md) bölümüne başvurun.
