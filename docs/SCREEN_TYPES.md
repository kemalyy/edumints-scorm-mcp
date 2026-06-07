# Ekran Tipleri (Screen Types)

`edumints-scorm-mcp` içerisinde tanımlı 18 ekran tipi bulunmaktadır. Her ekran tipi `core/project.py` içerisindeki modellerden türetilmiştir.

## Ortak Alanlar (Base Fields)

Tüm ekran tipleri aşağıdaki alanlara sahiptir:

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `id` | `str` | Hayır | Benzersiz ekran ID'si. Verilmezse sunucu üretir. |
| `title` | `str` | Evet | Ekran başlığı. |
| `notes` | `str` | Hayır | Yazar notları. |
| `duration_hint_sec` | `int` | Hayır | Tahmini süre (saniye). |
| `narration_asset_id` | `str` | Hayır | Seslendirme asset ID'si. |
| `visible_if` | `Condition` | Hayır | Koşullu görünürlük kuralı. |
| `on_enter` | `list[VarAction]` | Hayır | Girişte yapılacak değişken atamaları. |
| `timer_sec` | `int` | Hayır | Ekran süresi (saniye). |
| `section` | `str` | Hayır | Bölüm/Ünite adı. |

---

## 1. Giriş Slaytı (title_slide)

**Model:** `TitleSlide`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `subtitle` | `str` | Hayır | Alt başlık. |
| `background_asset_id` | `str` | Hayır | Arka plan görseli. |
| `body_html` | `str` | Hayır | Açıklama metni (HTML). |

**Örnek:**
```json
{
  "type": "title_slide",
  "title": "Giriş",
  "subtitle": "Hoş Geldiniz",
  "body_html": "<p>Bu kursa giriş yapıyorsunuz.</p>"
}
```

## 2. İçerik Slaytı (content_slide)

**Model:** `ContentSlide`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `body_html` | `str` | Evet | Ana içerik metni (HTML). |
| `media_asset_id` | `str` | Hayır | Görsel/Medya asset ID'si. |
| `layout` | `str` | Hayır | `text`, `text_media`, `media_text`, `full_media`. |

**Örnek:**
```json
{
  "type": "content_slide",
  "title": "Konu Anlatımı",
  "body_html": "<p>Konu detayları burada yer alır.</p>",
  "layout": "text_media",
  "media_asset_id": "asset_123"
}
```

## 3. Çoktan Seçmeli Soru (mcq)

**Model:** `MCQScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Soru metni. |
| `options` | `list[Choice]` | Evet | Seçenekler (min 2). |
| `multi_select` | `bool` | Hayır | Çoklu seçim aktif mi? (Varsayılan: false) |
| `feedback` | `Feedback` | Hayır | Doğru/Yanlış geri bildirimleri. |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 10). |

**Örnek:**
```json
{
  "type": "mcq",
  "title": "Soru 1",
  "prompt_html": "<p>Hangisi doğrudur?</p>",
  "options": [
    {"id": "a", "text_html": "Seçenek A", "correct": true},
    {"id": "b", "text_html": "Seçenek B", "correct": false}
  ]
}
```

## 4. Doğru/Yanlış (true_false)

**Model:** `TrueFalseScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Soru metni. |
| `correct` | `bool` | Evet | Doğru cevap. |
| `feedback` | `Feedback` | Hayır | Geri bildirimler. |

## 5. Boşluk Doldurma (fill_blank)

**Model:** `FillBlankScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Metin ve boşluk tanımı. |
| `blanks` | `list[Blank]` | Evet | Kabul edilen cevaplar listesi. |
| `case_sensitive`| `bool` | Hayır | Büyük/küçük harf duyarlılığı. |

## 6. Sürükle ve Bırak (drag_drop)

**Model:** `DragDropScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Talimat metni. |
| `items` | `list[DragItem]`| Evet | Sürüklenecek öğeler. |
| `targets` | `list[DropTarget]`| Evet | Hedef alanlar. |

## 7. Hotspot (hotspot)

**Model:** `HotspotScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Soru metni. |
| `image_asset_id` | `str` | Evet | Üzerinde seçim yapılacak görsel. |
| `regions` | `list[HotspotRegion]` | Evet | Tıklanabilir bölgeler. |

## 8. Senaryo / Dallanma (branching)

**Model:** `BranchingScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Senaryo metni. |
| `choices` | `list[BranchChoice]` | Evet | Seçenekler ve yönlendirilecek ekranlar. |
| `default_goto` | `str` | Hayır | Varsayılan hedef ekran ID'si. |

## 9. Video (video)

**Model:** `VideoScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `video_asset_id` | `str` | Hayır | Video asset ID'si. |
| `video_url` | `str` | Hayır | Harici video URL'si. |
| `caption` | `str` | Hayır | Video alt yazısı / açıklaması. |
| `poster_asset_id`| `str` | Hayır | Video kapak görseli. |
| `require_complete`| `bool` | Hayır | İzleme zorunluluğu (Varsayılan: false). |

## 10. Özet (summary)

**Model:** `SummaryScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `body_html` | `str` | Hayır | Özet metni. |
| `show_score` | `bool` | Hayır | Skoru göster (Varsayılan: true). |
| `show_completion`| `bool` | Hayır | Tamamlanma durumunu göster. |

## 11. Akordiyon (accordion)

**Model:** `AccordionScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `items` | `list[AccordionItem]` | Evet | Başlık ve içerikten oluşan öğeler. |

## 12. Sekmeler (tabs)

**Model:** `TabsScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `tabs` | `list[TabItem]` | Evet | Etiket ve içerikten oluşan sekmeler. |

## 13. Flashcards (flashcards)

**Model:** `FlashcardsScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `cards` | `list[Flashcard]` | Evet | Ön ve arka yüzden oluşan kartlar. |

## 14. Eşleştirme (matching)

**Model:** `MatchingScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `pairs` | `list[MatchPair]` | Evet | Sol ve sağ taraftan oluşan çiftler. |

## 15. Sıralama (sorting)

**Model:** `SortingScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `items` | `list[SortItem]` | Evet | Doğru sıradaki öğeler (Runtime'da karıştırılır). |

## 16. Zaman Tüneli (timeline)

**Model:** `TimelineScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `events` | `list[TimelineEvent]` | Evet | Tarih, başlık ve içerikten oluşan olaylar. |

## 17. Lottie Animasyonu (lottie)

**Model:** `LottieScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `lottie_asset_id` | `str` | Evet | Lottie JSON asset ID'si. |
| `loop` | `bool` | Hayır | Döngü (Varsayılan: true). |
| `autoplay` | `bool` | Hayır | Otomatik oynat (Varsayılan: true). |

## 18. Simülasyon (simulation)

**Model:** `SimulationScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Hayır | Giriş metni / Talimat. |
| `steps` | `list[SimStep]` | Evet | Çok adımlı etkileşim adımları. |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 10). |
| `feedback` | `Feedback` | Hayır | Doğru/Yanlış geri bildirimleri. |

---

<!-- synced: e0cb4fc2568bdf0234512d68d2327123afefc407 -->
