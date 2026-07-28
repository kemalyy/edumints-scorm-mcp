# QTI 2.1 Dışa Aktarım (W8)

`core/qti.py` + **`export_qti` aracı** — quiz ekranlarını **IMS QTI 2.1** `assessmentItem` XML'lerine çevirir.
Endüstriyel interop: scorm-mcp içeriği QTI-uyumlu LMS / madde bankası / değerlendirme platformlarına taşınabilir.
Deterministik XML üretimi (lxml — `imsmanifest` ile aynı yaklaşım). **SUNUCUDA LLM YOK.** Additive.

## Desteklenen tipler
| ekran tipi | QTI etkileşimi | correctResponse |
|---|---|---|
| `mcq` | `choiceInteraction` (maxChoices 1, multi ise 0) | doğru seçenek id'leri |
| `true_false` | `choiceInteraction` (true/false) | `true` \| `false` |
| `fill_blank` | boşluk başına `textEntryInteraction` | her boşluğun **ilk** kabul edilen cevabı |

Diğer tipler (oyun, adaptif, sürükle-bırak, hotspot, eşleştirme…) QTI standart etkileşimlerine birebir
oturmadığından **sessizce atlanır** (yalnız temiz eşlenenler dışa aktarılır — sahte dönüşüm yok).

## Çıktı yapısı (mcq örneği)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1"
                identifier="item-q1" title="…" adaptive="false" timeDependent="false">
  <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
    <correctResponse><value>a</value></correctResponse>
  </responseDeclaration>
  <outcomeDeclaration identifier="SCORE" cardinality="single" baseType="float"/>
  <itemBody>
    <choiceInteraction responseIdentifier="RESPONSE" maxChoices="1" shuffle="false">
      <prompt>2 + 2 = ?</prompt>
      <simpleChoice identifier="a">4</simpleChoice>
      <simpleChoice identifier="b">5</simpleChoice>
    </choiceInteraction>
  </itemBody>
  <responseProcessing template="http://www.imsglobal.org/question/qti_v2p1/rptemplates/match_correct"/>
</assessmentItem>
```
Prompt/seçenek metinleri düz metne indirgenir (QTI itemBody içerik modeli + güvenlik). responseProcessing
standart `match_correct` şablonunu kullanır (taşınabilir, motor-bağımsız puanlama).

## Kullanım
`export_qti(project_id)` → `{ project_id, count, items: [{ filename: "qti/<id>.xml", xml }] }`.
Yazar quiz ekranlarını QTI olarak alıp dış sistemlere yükler. (MCP araçlarından biri.)

## Sınırlar & yol haritası
- `fill_blank`: yalnız ilk kabul edilen cevap; eşanlamlı/çoklu cevap için QTI `mapResponse` ileride.
- `matching`/`sorting`/`hotspot` → QTI `associateInteraction`/`order`/`graphicGapMatch` ileride eklenebilir.
- QTI 3.0 (yeni ad alanı) ileride; şu an 2.1 (en yaygın LMS desteği).

## Durum & sıradaki (W8)
**W8a (done):** QTI 2.1 dışa aktarım (mcq/true_false/fill_blank) + `export_qti` aracı + testler + dok.
**Sıradaki W8b/W8c:** 5-LMS konformans matrisi (CI: tüm örnekler × SCORM 1.2/2004 → XSD + SCORM Cloud) +
WCAG 2.2 oyun a11y denetim aracı (W6 anti-slop + GAME-A11Y üzerine). Bkz. `docs/CONFORMANCE.md`,
`docs/LMS-INTEGRATION.md`, `docs/GAME-A11Y.md`.
