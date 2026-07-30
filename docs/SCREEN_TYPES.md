# Ekran Tipleri (Screen Types)

`edumints-scorm-mcp` içerisinde tanımlı 30 ekran tipi bulunmaktadır. Her ekran tipi `core/project.py` içerisindeki modellerden türetilmiştir.

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
| `body_html` | `str` | Hayır* | Ana içerik metni (HTML). `blocks` verilirse zorunlu değil. |
| `media_asset_id` | `str` | Hayır | Görsel/Medya asset ID'si. |
| `layout` | `str` | Hayır | `text`, `text_media`, `media_text`, `full_media`. |
| `blocks` | `list[ContentBlock]` | Hayır | **Çoklu blok:** sırayla render edilir (paragraf→görsel→paragraf akışı). Verilirse `body_html`/`media_asset_id` yerine geçer. |

**`ContentBlock`:** `html` (metin bloğu) **veya** `asset_id` (+ ops. `caption`) — her blok biri.
*Inline görsel:* herhangi bir `*_html` alanına `{{asset:<id>}}` yazarak paketlenmiş bir asset'i metin akışına gömebilirsin; `data:` URI'li `<img>` de desteklenir.

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

**`AccordionItem`:** `title`, `body_html`, ops. `image_asset_id` (panel başına görsel).

## 12. Sekmeler (tabs)

**Model:** `TabsScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `tabs` | `list[TabItem]` | Evet | Etiket ve içerikten oluşan sekmeler. |

**`TabItem`:** `label`, `body_html`, ops. `image_asset_id` (sekme başına görsel).

## 13. Flashcards (flashcards)

**Model:** `FlashcardsScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `cards` | `list[Flashcard]` | Evet | Ön ve arka yüzden oluşan kartlar. |

**`Flashcard`:** `front_html`, `back_html`, ops. `front_asset_id` / `back_asset_id` (yüz başına görsel).

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

**`TimelineEvent`:** `date`, `title`, ops. `body_html`, ops. `image_asset_id` (olay başına görsel).

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

## 19. Karar Senaryosu (decision_scenario)

Tek ekranda çok-adımlı, durum (skor) taşıyan **dallanan karar senaryosu** — anlatı "try-mode".
Öğrenci kararlar verir; her kararın sonucu/gerekçesi ve puana etkisi gösterilir; senaryo bir uç
düğümde biter ve toplam skor `pass_score`'a göre geçer/kalır olarak skorlanır. `simulation`
(yazılım dene) ve `branching` (ekranlar-arası dallanma) ile tamamlayıcı.

**Model:** `DecisionScenarioScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `intro_html` | `str` | Hayır | Senaryo giriş metni. |
| `nodes` | `list[ScenarioNode]` | Evet | Karar düğümleri (≥1). |
| `start_node_id` | `str` | Hayır | Başlangıç düğümü (Varsayılan: ilk düğüm). |
| `pass_score` | `int` | Hayır | Geçme eşiği (yoksa skor > 0 geçer). |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 20). |
| `feedback` | `Feedback` | Hayır | Geçer/kalır kapanış geri bildirimi. |

**`ScenarioNode`:** `id`, `prompt_html`, ops. `image_asset_id`, `choices` (`list[ScenarioChoice]`, ≥2).
**`ScenarioChoice`:** `id`, `text_html`, `feedback_html` (seçimin sonucu/gerekçesi), `score_delta`
(int, negatif olabilir), ops. `goto_node_id` (None ise senaryoyu bitirir).

## 20. Terim Yarışı (term_match_race)

Süreli terim↔tanım eşleştirme **oyunu**. Öğrenci her terime doğru tanımı atar; geri sayım dolmadan
eşleştirir. Skor = doğru oranı × `points` (+ tümü doğruysa kalan süre bonusu). `matching`in
oyunlaştırılmış, süreli sürümü. **Skorlanır.**

**Model:** `TermMatchRaceScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Hayır | Talimat. |
| `pairs` | `list[TermPair]` | Evet | Terim/tanım çiftleri (≥2). |
| `time_limit_sec` | `int` | Hayır | Geri sayım (Varsayılan: 60). |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 15). |

**`TermPair`:** `id`, `term_html`, `definition_html`.

## 21. Kaçış Odası (escape_room)

Kilitli bulmaca zinciri **oyunu**. Her bulmacayı çöz → sonraki açılır; yanlış → can azalır + ipucu.
Tüm bulmacalar çözülürse geçer; can biterse kalır. **Skorlanır.**

**Model:** `EscapeRoomScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `intro_html` | `str` | Hayır | Giriş metni. |
| `puzzles` | `list[Puzzle]` | Evet | Bulmacalar (≥1, sıralı kilit). |
| `lives` | `int` | Hayır | Can sayısı (Varsayılan: 3). |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 20). |

**`Puzzle`:** `id`, `prompt_html`, `accepted` (`list[str]`), ops. `hint_html`, `case_sensitive`.

## 22. Etiketli Diyagram (labeled_diagram)

Görseldeki numaralı işaretçilere doğru etiketi atama (anatomi/şema/harita) — **görsel öğrenme**.
Her işaretçi için bir `<select>` (klavye-erişilebilir); seçim işaretçi id'siyle eşleşirse doğru. **Skorlanır.**

**Model:** `LabeledDiagramScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Hayır | Talimat. |
| `image_asset_id` | `str` | Evet | Diyagram görseli. |
| `labels` | `list[DiagramLabel]` | Evet | İşaretçiler (≥2). |
| `mode` | `"quiz"｜"display"` | Hayır | Davranış modu (Varsayılan: `quiz`). Bkz. aşağıda. |
| `points` | `int` | Hayır | Soru puanı (Varsayılan: 15; `display` modunda yok sayılır). |

**`DiagramLabel`:** `id`, `text`, `x`, `y` (0–1000 normalize konum).

### `mode` — quiz (varsayılan) vs display (salt-gösterim callout) — #126

- **`quiz`** (varsayılan): bugünkü davranış, **bayt-bayt** değişmez. Etkileşimli; her
  işaretçi için `<select>`, skorlanır.
- **`display`**: **salt-gösterim callout** modu — split-attention "exhibit" deseninin
  çözümü (ölçüm raporu §5.3). Her işaretçinin `text`'i görselin **ÜSTÜNDE** statik, daima
  görünür bir callout kutusu olarak (koordinatına bağlı num dot + leader line + metin
  kutusu) render edilir. Cevap seçtirme / select / skor / feedback **YOK**. Metin gerçek
  DOM metnidir (yalnız `title` tooltip **DEĞİL**) → klavye + dokunma + ekran-okuyucuda
  erişilebilir; renkler AA kontrast token'larından akar. Ekran **skorlanmaz** (`total_points`
  dışı) ama **kanıt-taşıyabilir** hedeftir — skorlu bir soru `evidence_screen_ids` ile bu
  exhibit'e yaslanabilir (K1, `references/core/evidence-binding.md`). ≤640px'te callout'lar
  görsel altında dikey listeye dönüşür (reflow).

  **Yazım örneği** (spot-the-phish/c_email okuma protokolünü görsel üstüne taşır):

  ```json
  {
    "type": "labeled_diagram", "id": "c_email", "title": "Bu e-postayı incele",
    "mode": "display", "image_asset_id": "email_mock",
    "image_alt": "şüpheli e-posta ekran görüntüsü",
    "labels": [
      {"id": "p0", "text": "Gönderen satırı sahte mi?", "x": 150, "y": 150},
      {"id": "p1", "text": "Ton aciliyet dayatıyor mu?", "x": 150, "y": 330},
      {"id": "p2", "text": "Butonun gerçek hedefi ne?", "x": 150, "y": 510},
      {"id": "p3", "text": "Ek güvenli mi?", "x": 150, "y": 690}
    ]
  }
  ```

## 23. Veri Grafiği (data_chart)

Veri-görseli (bar/line/pie). Sunucuda **deterministik inline-SVG** üretilir (dış lib/ağ YOK). İçerik
ekranı — pasif veri sunumu/karşılaştırma. **Skorlanmaz.**

**Model:** `DataChartScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Hayır | Açıklama. |
| `chart_type` | `"bar"｜"line"｜"pie"` | Hayır | Grafik tipi (Varsayılan: bar). |
| `data` | `list[ChartDatum]` | Evet | Veri noktaları (≥1). |
| `caption` | `str` | Hayır | Grafik altyazısı. |

**`ChartDatum`:** `label`, `value` (float).

## 24. Sonuç Dökümü (results_breakdown)

**Özelleştirilmiş sonuç:** hedef/bölüm bazlı skor dökümü. Her bölümün oranı, öğrencinin verdiği
cevaplardan **gösterim-zamanında** hesaplanır; eşik altındaki (zayıf) bölümler için adaptif öneri
gösterilir. `summary`'nin performansa-duyarlı, kişiselleştirilmiş versiyonu. **Skorlanmaz.**

**Model:** `ResultsBreakdownScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `body_html` | `str` | Hayır | Giriş metni. |
| `sections` | `list[ResultSection]` | Evet | Hedef/bölümler (≥1). |
| `weak_threshold` | `int` | Hayır | Zayıf eşik % (Varsayılan: 60). |
| `show_total` | `bool` | Hayır | Toplam oranı göster (Varsayılan: true). |

**`ResultSection`:** `title`, `screen_ids` (`list[str]` — bu hedefe ait skorlanan ekran id'leri),
ops. `advice_html` (bölüm zayıfsa gösterilir).

## 25. Anket / Yansıma (poll)

Puanlanmayan anket/yansıma. Öğrenci seçer (tek/çok) ya da açık metin yazar; gönderince yansıma
mesajı belirir. Katılım/öz-değerlendirme — **skorlanmaz**, İleri'yi engellemez.

**Model:** `PollScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Soru. |
| `options` | `list[PollOption]` | Hayır | Seçenekler (boş + `allow_text` → açık yansıma). |
| `multi` | `bool` | Hayır | Çoklu seçim (Varsayılan: false). |
| `allow_text` | `bool` | Hayır | Açık metin alanı (Varsayılan: false). |
| `reflection_html` | `str` | Hayır | Gönderimden sonra gösterilir. |

**`PollOption`:** `id`, `text_html`.

## 26. Görsel Karşılaştırma (image_compare)

Önce/sonra **sürüklenebilir** görsel karşılaştırma (slider). Değişim/fark gösterimi (tıp, tasarım,
önce-sonra). İçerik — **skorlanmaz.**

**Model:** `ImageCompareScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `before_asset_id` | `str` | Evet | "Önce" görseli. |
| `after_asset_id` | `str` | Evet | "Sonra" görseli. |
| `before_label` | `str` | Hayır | "Önce" etiketi. |
| `after_label` | `str` | Hayır | "Sonra" etiketi. |
| `prompt_html` / `caption` | `str` | Hayır | Talimat / altyazı. |

## 27. Kompozisyonel Oyun (game)

Sabit bir oyun TİPİ değil; mekanik primitiflerin (`score`/`lives`/`timer`/`hint`) + `when olay if
koşul then aksiyon` kurallarının + dallanan içerik düğümlerinin kompozisyonu. Mantık tek-kaynak
`components/engine/*.js` (vitest), pakette `core/engine_bundle.py` ile lazy inline edilir. İçsel
bütünleşme (Habgood): mekanik öğrenme hedefini taşır. **Skorlanır** (oyun bitince `score` primitifi
eşiğe göre geçer/kalır). Tasarım rehberi: `docs/GAME-ECD.md`, oyun erişilebilirliği: `docs/GAME-A11Y.md`.
**SUNUCUDA LLM YOK** — zekâ spec + deterministik runtime'da.

**Model:** `GameScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `nodes` | `list[GameNode]` | Evet | Dallanan içerik düğümleri (en az 1). |
| `template` | `"case_sim" \| "escape_room" \| "custom"` | Hayır | ECD/şablon referansı (Varsayılan: `custom`). |
| `mechanics` | `GameMechanics` | Hayır | `score`/`lives`/`timer`/`hint` primitif yapılandırması. |
| `rules` | `list[GameRule]` | Hayır | `when <olay> if <koşul> then <aksiyon>` kuralları. |
| `start_node_id` | `str` | Hayır | Başlangıç düğümü (boşsa ilk düğüm). |
| `pass_score` | `int` | Hayır | Geçme eşiği (boşsa skor > 0 geçer). |
| `points` | `int` | Hayır | Kursa katkı (Varsayılan: 25). |
| `seed` | `str` | Hayır | Üretilebilir oynanış için tohum (boşsa ekran id'sinden türetilir). |
| `intro_html` | `str` | Hayır | Giriş metni. |
| `feedback` | `Feedback` | Hayır | Doğru/yanlış geri bildirimi. |

## 28. Adaptif Pratik (adaptive_practice)

Öğe bankasından her cevaptan sonra yeterliliği güncelleyip (Elo veya BKT) bir sonraki öğeyi AKIŞ/ZPD
hedefine (`target_success`) en yakın zorlukta seçer — ne bunaltır ne sıkar. Mantık tek-kaynak
`components/engine/adaptive.js` (vitest). **Skorlanır** (doğru/cevaplanan oranı `pass_ratio`'ya göre).
Ayrıntı: `docs/GAME-ADAPTIVE.md`. **SUNUCUDA LLM YOK** — seçim deterministik, seed'li tie-break.

**Model:** `AdaptivePracticeScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `items` | `list[AdaptiveItem]` | Evet | Öğe bankası (en az 3; MCQ biçimi + `difficulty`). |
| `adaptive` | `AdaptiveSpec` | Evet | Tahminci yapılandırması (`strategy`: `elo` veya `bkt`). |
| `target_success` | `float` | Hayır | Akış hedefi / arzu edilen zorluk (Varsayılan: 0.7). |
| `max_items` | `int` | Hayır | En çok sunulacak öğe (0 → tümü birer kez). |
| `mastery_stop` | `float` | Hayır | BKT: ustalık ≥ bu olunca erken bitir. |
| `pass_ratio` | `float` | Hayır | Geçme oranı (Varsayılan: 0.6). |
| `points` | `int` | Hayır | Kursa katkı (Varsayılan: 20). |
| `seed` | `str` | Hayır | Tohum (boşsa ekran id'sinden türetilir). |
| `prompt_html` | `str` | Hayır | Yönerge. |
| `feedback` | `Feedback` | Hayır | Doğru/yanlış geri bildirimi. |

**`AdaptiveItem`:** `id`, `prompt_html`, `options` (`list[Choice]`, en az 2), `difficulty`
(logit ölçeği), ops. `skill` (BKT beceri), `explain_html`.

## 29. Çözümlü Örnek (worked_example)

Yazarlı-gösterim primitifi (F1 #112): uzman çözümü adım adım, her adım **eylem + gerekçe +
ops. artefakt** üçlüsüyle gösterilir. `fading` ile destek soluklaştırılır (4C/ID ve
Rosenshine-DI paketlerinin motoru — `rosenshine-di`/`4cid` skill paketleri bu tipe gereksinir):

- `full` — tam çözümlü: her şey açık (görev sınıfı 1 / tam destek).
- `partial` — tamamlama: eylemler açık, her adımın **gerekçesi** reveal butonu ardında
  (öğrenen önce kendi gerekçesini kurar, sonra karşılaştırır).
- `problem_only` — yalnız iskelet: problem (`intro_html`) açık, her adımın gövdesi tek tek açılır.

**Skorlanmaz** — `points` alanı YOK (destekli örneği puanlamak desteği ölçer, Z2/Z3); E1
kanıt-bağlama denetiminde **koşulsuz kanıt-taşıyabilir** ekrandır (K1 tür 1: skorlu sorular
`evidence_screen_ids` ile buna bağlanabilir). Öz-açıklama alanı SKORSUZ serbest metindir —
hiçbir LMS alanına yazılmaz. Artefaktlı adım görsel-bütçe sayımına girer; `artifact_caption`
hem `figcaption` hem alt-text kaynağıdır (boşsa `missing_alt_text` WARN). Boş `rationale_html`
`step_without_rationale` WARN üretir.

**Model:** `WorkedExampleScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `steps` | `list[WEStep]` | Evet | Çözüm adımları (en az 2). |
| `fading` | `str` | Hayır | `full` (vars.), `partial`, `problem_only`. |
| `intro_html` | `str` | Hayır | Problem/görev tanımı (her düzeyde açık kalır). |
| `self_explanation_prompt_html` | `str` | Hayır | SKORSUZ öz-açıklama istemi (+ serbest metin alanı). |

**`WEStep`:** `action_html` (NE yapıldı), `rationale_html` (NEDEN — zorunlu),
ops. `artifact_asset_id` + `artifact_caption` (ekran görüntüsü/kod çıktısı/diyagram).

**Örnek:** `examples/worked-example-4cid.tr.json` (3 fading düzeyi + kanıt bağı, lint-temiz).

```json
{
  "type": "worked_example",
  "title": "Çözümlü örnek: 'Mart'ta İzmir satışları?'",
  "fading": "partial",
  "intro_html": "<p>Görev: yönetici sorusunu SQL'e çevir.</p>",
  "steps": [
    { "action_html": "<p>Soruyu üç parçaya çevir (FROM/WHERE/SELECT).</p>",
      "rationale_html": "<p>Çeviri sözdiziminden önce gelir.</p>" },
    { "action_html": "<p><code>SELECT tarih, tutar FROM satislar WHERE ...;</code></p>",
      "rationale_html": "<p>İki koşul birden gerekli → AND.</p>",
      "artifact_asset_id": "cikti1", "artifact_caption": "Sorgu çıktısı" }
  ],
  "self_explanation_prompt_html": "<p>AND neden zorunlu? Kendi cümlelerinle açıkla.</p>"
}
```

## 30. Keşif (exploration)

Keşif/sorgulama primitifi (F2 #113): öğrenen girdisi (deneme, tahmin, sınıflama)
**SAKLANIR** ve sonraki ekranlar bu girdiyi **GERİ OYNATIR** — "senin tahminin şuydu"
atfı (`5e-inquiry` keşfet fazının kanıt kaynağı 1; `productive-failure` deneme kaydı).

- `input_kind: "text"` — serbest metin (gözlem/deneme notu; `placeholder`, ops. `min_length`).
- `input_kind: "choice"` — sınıflama/seçim (`choices`, ≥2).
- `input_kind: "prediction"` — tahmin taahhüdü (choice ile aynı yüzey; pedagojik olarak
  commit-then-see — deneme ÖNCESİ alınan tahmin).

**Geri oynatma:** herhangi bir ekranın zengin HTML'inde
`<span data-exploration-ref="store_key"></span>` — runtime saklanan değeri **textContent**
olarak enjekte eder (innerHTML asla — XSS-güvenli); boş değer i18n yer tutucusuna düşer
("henüz cevaplamadın"). `store_key` makine-dostudur (`[a-z0-9_-]+`, ≤64) ve kurs genelinde
**TEKİL** olmalıdır (`validate_project` çakışmayı SERT hatayla keser).

**Saklama:** suspend v2 zarf kuyruğundaki `xp` haritası (`components/engine/scorm.js`
`setExploration`/`getExploration`); değer **500 karakterde kırpılır** (SCORM 1.2 bütçesi).
1.2 hedefinde çok keşifli kurs `suspend_size_risk` WARN'ına düşer (`estimate_suspend_size`
keşif başına 500 + anahtar maliyeti sayar).

**Skorlanmaz** — `points` alanı YOK (A4 skorsuz-erken-deneme istisnasının teknik karşılığı;
denemeyi puanlamak keşfi tahmin-yarışına çevirir, Z3). E1 kanıt-bağlama denetiminde
**koşulsuz kanıt-taşıyabilir** ekrandır (K1 tür 2: öğrenenin KENDİ ürettiği artefakt —
skorlu sorular `evidence_screen_ids` ile buna bağlanabilir).

**Model:** `ExplorationScreen`

| Alan | Tip | Zorunlu mu? | Açıklama |
| :--- | :--- | :---: | :--- |
| `prompt_html` | `str` | Evet | Keşif yönergesi (choice/prediction'da radiogroup'u da etiketler). |
| `store_key` | `str` | Evet | Geri-oynatma adresi (`[a-z0-9_-]+`, ≤64, kurs genelinde tekil). |
| `input_kind` | `str` | Hayır | `text` (vars.), `choice`, `prediction`. |
| `choices` | `list[Choice]` | choice/prediction'da | Seçenekler (≥2; `correct` alanı YOK sayılır — skorsuz). |
| `placeholder` | `str` | Hayır | text: girdi yer tutucusu (boşsa i18n varsayılanı). |
| `min_length` | `int` | Hayır | text: asgari uzunluk ipucu (`minlength` + görünür ipucu). |

**Örnek:** `examples/exploration-5e.tr.json` (5e mini-döngü: prediction + choice + text,
geri oynatma + kanıt bağı, lint-temiz).

```json
{
  "type": "exploration",
  "id": "kesif_kutle",
  "title": "Tahmin et: kütle 2×, hacim sabit",
  "input_kind": "prediction",
  "store_key": "tahmin_kutle2x",
  "prompt_html": "<p>Küpün kütlesini iki katına çıkarıyoruz. Suya bırakınca ne olur?</p>",
  "choices": [
    { "id": "yuzer", "text_html": "Yüzer" },
    { "id": "batar", "text_html": "Batar" }
  ]
}
```

Sonraki ekranda geri oynatma:

```json
{
  "type": "content_slide",
  "title": "Açıkla",
  "body_html": "<p>Senin tahminin şuydu: <b><span data-exploration-ref=\"tahmin_kutle2x\"></span></b>.</p>"
}
```

---

<!-- synced: e0cb4fc2568bdf0234512d68d2327123afefc407 -->
